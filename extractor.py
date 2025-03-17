"""
Main module for the Bundestag Protocol Extractor.

This module provides the command-line interface and high-level functionality
for extracting and processing German Bundestag plenarprotocols.
"""
import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.utils.exporter import Exporter
from bundestag_protocol_extractor.models.schema import PlenarProtocol
from bundestag_protocol_extractor.utils.logging import get_logger, setup_logging
from bundestag_protocol_extractor.utils.progress import ProgressTracker
import logging

logger = get_logger(__name__)


class BundestagExtractor:
    """
    Main class for extracting and processing Bundestag plenarprotocols.
    """
    
    # Public API key
    DEFAULT_API_KEY = "I9FKdCn.hbfefNWCY336dL6x62vfwNKpoN2RZ1gp21"
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        output_dir: str = "output", 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        resume_from: Optional[str] = None
    ):
        """
        Initialize the extractor.
        
        Args:
            api_key: API key for the Bundestag API (defaults to public key)
            output_dir: Directory for output files
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            resume_from: Optional path to a progress file to resume from
        """
        self.output_dir = Path(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Use provided API key or default to the public key
        api_key = api_key or self.DEFAULT_API_KEY
        self.api_client = BundestagAPIClient(api_key)
        self.parser = ProtocolParser(self.api_client, max_retries=max_retries, retry_delay=retry_delay)
        self.exporter = Exporter(output_dir)
        
        # Store parameters for potential resume
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.resume_from = resume_from
        
        logger.info(f"Initialized BundestagExtractor (output_dir={output_dir}, max_retries={max_retries})")
    
    def get_protocols(
        self, 
        period: int = 20, 
        limit: Optional[int] = None,
        offset: int = 0,
        index: Optional[int] = None,
        resume_from_doc: Optional[str] = None,
        use_xml: bool = True
    ) -> List[PlenarProtocol]:
        """
        Get plenarprotocols for a specific legislative period.
        
        Args:
            period: Legislative period (Wahlperiode), default is 20
            limit: Optional limit for the number of protocols to retrieve
            offset: Skip the first N protocols
            index: Start processing from a specific protocol index
            resume_from_doc: Resume processing from a specific protocol number
            use_xml: Whether to use XML parsing for speeches
            
        Returns:
            List of PlenarProtocol objects
        """
        # Initialize progress tracker
        job_params = {
            'wahlperiode': period,
            'limit': limit,
            'offset': offset,
            'index': index,
            'resume_from_doc': resume_from_doc,
            'use_xml': use_xml,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay
        }
        
        progress = ProgressTracker(
            wahlperiode=period,
            output_dir=self.output_dir,
            job_params=job_params,
            resume_from=self.resume_from
        )
        
        # Get list of all protocols
        logger.info(f"Retrieving protocols for Wahlperiode {period}")
        protocol_list = self.api_client.get_plenarprotokoll_list(
            wahlperiode=period,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            progress_tracker=progress
        )
        
        total_protocols = len(protocol_list)
        logger.info(f"Found {total_protocols} protocols in total")
        
        # Determine where to start processing based on the provided parameters
        start_index = 0
        
        if index is not None:
            # Start from a specific index
            start_index = index
            logger.info(f"Starting from index {start_index} based on 'index' parameter")
        elif offset > 0:
            # Skip the first N protocols
            start_index = offset
            logger.info(f"Skipping first {start_index} protocols based on 'offset' parameter")
        elif resume_from_doc:
            # Find the protocol with the specified document number
            for idx, p in enumerate(protocol_list):
                if p.get("dokumentnummer") == resume_from_doc:
                    start_index = idx
                    logger.info(f"Found protocol {resume_from_doc} at index {start_index}, resuming from here")
                    break
            else:
                logger.warning(f"Could not find protocol {resume_from_doc}, starting from the beginning")
        
        # Apply index offset
        if start_index > 0:
            if start_index >= len(protocol_list):
                logger.error(f"Start index {start_index} is out of range (max: {len(protocol_list)-1})")
                return []
            protocol_list = protocol_list[start_index:]
            logger.info(f"Starting at protocol {start_index+1} of {total_protocols}")
        
        # Apply limit if specified
        if limit:
            protocol_list = protocol_list[:limit]
            logger.info(f"Limited to {len(protocol_list)} protocols due to 'limit' parameter")
        
        # Initialize progress tracker with the total number of protocols
        progress.init_total(len(protocol_list))
        
        # Process each protocol
        protocols = []
        
        for i, protocol_metadata in enumerate(protocol_list):
            protocol_id = int(protocol_metadata["id"])
            protocol_number = protocol_metadata.get('dokumentnummer', str(protocol_id))
            
            # Calculate the actual index in the full list
            full_index = i + start_index
            
            # Skip if already processed successfully (for resumed jobs)
            if protocol_id in progress.progress.completed_protocol_ids:
                logger.info(f"Protocol {protocol_number} (ID: {protocol_id}) already processed, skipping")
                continue
            
            # Delay to avoid rate limiting
            if i > 0 and self.retry_delay > 0:
                time.sleep(self.retry_delay)
            
            try:
                # Parse full protocol
                protocol = self.parser.parse_protocol(
                    protocol_id,
                    use_xml=use_xml,
                    progress_tracker=progress
                )
                protocols.append(protocol)
                
                # Mark as complete in progress tracker
                # (this is also done in parse_protocol, but doing here as well for safety)
                progress.complete_protocol(protocol_id)
                
            except Exception as e:
                error_msg = f"Error processing protocol {protocol_id}: {str(e)}"
                logger.error(error_msg)
                
                # Record failure in progress tracker
                progress.fail_protocol(protocol_id, str(e))
                
                # Continue with other protocols rather than failing completely
                continue
        
        # Complete progress tracking
        stats = progress.complete()
        logger.info(f"Extraction completed. Successfully processed {len(protocols)} protocols")
        
        return protocols
    
    def export_to_csv(
        self, 
        protocols: List[PlenarProtocol], 
        output_dir: Optional[str] = None,
        include_speech_text: bool = True,
        include_full_protocols: bool = False,
        include_paragraphs: bool = True,
        include_comments: bool = True
    ) -> Dict[str, Path]:
        """
        Export protocols to CSV files.
        
        Args:
            protocols: List of PlenarProtocol objects
            output_dir: Optional output directory
            include_speech_text: Whether to include full speech text
            include_full_protocols: Whether to include full protocol text
            include_paragraphs: Whether to include paragraphs
            include_comments: Whether to include comments
            
        Returns:
            Dictionary of exported files by type
        """
        if not protocols:
            logger.warning("No protocols to export to CSV")
            return {}
            
        logger.info(f"Exporting {len(protocols)} protocols to CSV")
        
        if output_dir:
            previous_dir = self.exporter.output_dir
            self.exporter.output_dir = Path(output_dir)
            os.makedirs(self.exporter.output_dir, exist_ok=True)
        
        try:
            exported_files = self.exporter.export_to_csv(
                protocols,
                include_speech_text=include_speech_text,
                include_full_protocols=include_full_protocols,
                include_paragraphs=include_paragraphs,
                include_comments=include_comments
            )
            
            logger.info(f"CSV export complete: {len(exported_files)} files created")
            return exported_files
            
        except Exception as e:
            logger.error(f"Error during CSV export: {str(e)}")
            raise
        finally:
            # Restore original output directory if changed
            if output_dir:
                self.exporter.output_dir = previous_dir
    
    def export_to_json(
        self, 
        protocols: List[PlenarProtocol], 
        output_dir: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Path:
        """
        Export protocols to a JSON file.
        
        Args:
            protocols: List of PlenarProtocol objects
            output_dir: Optional output directory
            filename: Optional filename for the JSON file
            
        Returns:
            Path to the exported JSON file
        """
        if not protocols:
            logger.warning("No protocols to export to JSON")
            return Path(self.exporter.output_dir) / "empty_export.json"
            
        logger.info(f"Exporting {len(protocols)} protocols to JSON")
        
        if output_dir:
            previous_dir = self.exporter.output_dir
            self.exporter.output_dir = Path(output_dir)
            os.makedirs(self.exporter.output_dir, exist_ok=True)
        
        try:
            output_path = self.exporter.export_to_json(protocols, filename=filename)
            logger.info(f"JSON export complete: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error during JSON export: {str(e)}")
            raise
        finally:
            # Restore original output directory if changed
            if output_dir:
                self.exporter.output_dir = previous_dir


def main():
    """Command line interface for the extractor."""
    parser = argparse.ArgumentParser(description="Extract and structure data from the German Bundestag's API")
    
    # Basic options
    parser.add_argument("--api-key", help="API key for the Bundestag API (optional, defaults to public key)")
    parser.add_argument("--period", type=int, default=20, help="Legislative period (default: 20)")
    parser.add_argument("--output-dir", default="output", help="Output directory for extracted data")
    
    # Extraction control
    parser.add_argument("--limit", type=int, help="Limit the number of protocols to extract")
    parser.add_argument("--offset", type=int, default=0, 
                        help="Skip the first N protocols (useful for resuming)")
    parser.add_argument("--index", type=int, 
                        help="Start processing from a specific protocol index (alternative to offset)")
    parser.add_argument("--resume-from", type=str,
                        help="Resume processing from a specific protocol number (e.g. '20/12')")
                        
    # Rate limiting
    parser.add_argument("--delay", type=float, default=0.5, 
                        help="Delay in seconds between API requests to avoid rate limiting (default: 0.5)")
    parser.add_argument("--retry", type=int, default=3,
                        help="Number of times to retry a request when rate limited (default: 3)")
                        
    # XML options
    parser.add_argument("--use-xml", action="store_true", default=True,
                        help="Use XML parsing for speeches (more accurate, default: True)")
    parser.add_argument("--no-xml", dest="use_xml", action="store_false",
                        help="Disable XML parsing for speeches")
                        
    # Export options
    parser.add_argument("--format", choices=["csv", "json", "both"], default="csv", 
                        help="Output format (default: csv)")
    parser.add_argument("--include-speech-text", action="store_true", default=True,
                        help="Include full speech text in CSV exports (default: True)")
    parser.add_argument("--exclude-speech-text", dest="include_speech_text", action="store_false",
                        help="Exclude full speech text from CSV exports to reduce file size")
    parser.add_argument("--include-full-protocols", action="store_true", default=False,
                        help="Include full protocol text in CSV exports (default: False)")
    parser.add_argument("--include-paragraphs", action="store_true", default=True,
                        help="Include individual paragraphs for detailed analysis (default: True)")
    parser.add_argument("--exclude-paragraphs", dest="include_paragraphs", action="store_false",
                        help="Exclude individual paragraphs to reduce file size")
    parser.add_argument("--include-comments", action="store_true", default=True,
                        help="Include comments and interjections (default: True)")
    parser.add_argument("--exclude-comments", dest="include_comments", action="store_false",
                        help="Exclude comments and interjections to reduce file size")
                        
    # Progress and resumption
    parser.add_argument("--resume", help="Resume from a saved progress file")
    parser.add_argument("--list-progress", action="store_true", help="List available progress files")
    
    # Logging options
    log_group = parser.add_argument_group("Logging Options")
    log_level = log_group.add_mutually_exclusive_group()
    log_level.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    log_level.add_argument("--debug", action="store_true", help="Enable debug logging")
    log_level.add_argument("--quiet", "-q", action="store_true", help="Minimal console output")
    log_group.add_argument("--log-file", help="Custom log file path")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Set up logging based on verbosity level
    if args.debug:
        # Full debug logging
        log_level = logging.DEBUG
        console_level = logging.DEBUG
    elif args.verbose:
        # Verbose logging - debug to file, info to console
        log_level = logging.DEBUG
        console_level = logging.INFO
    elif args.quiet:
        # Quiet mode - info to file, warning to console
        log_level = logging.INFO
        console_level = logging.WARNING
    else:
        # Default - info level for both
        log_level = logging.INFO
        console_level = logging.INFO
    
    # Configure logging
    log_file = args.log_file
    if not log_file:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = output_dir / "logs" / f"bundestag_extractor_{timestamp}.log"
    
    setup_logging(
        log_file=log_file,
        log_level=log_level,
        console_level=console_level,
        module_levels={
            "urllib3": logging.WARNING,
            "requests": logging.WARNING,
        }
    )
    
    logger.info("Bundestag Protocol Extractor")
    logger.info(f"Output directory: {output_dir}")
    
    # Check if we should list progress files and exit
    if args.list_progress:
        from bundestag_protocol_extractor.utils.progress import ProgressTracker
        progress = ProgressTracker(wahlperiode=args.period, output_dir=output_dir)
        available_progress = progress.list_available_progress_files()
        
        if not available_progress:
            logger.info("No progress files found")
        else:
            logger.info(f"Found {len(available_progress)} progress files:")
            for i, p in enumerate(available_progress):
                logger.info(f"{i+1}. Job ID: {p['job_id']}, WP{p['wahlperiode']}, "
                           f"Status: {p['status']}, "
                           f"Progress: {p['completed_count']}/{p['total_protocols']} "
                           f"({p['completed_count']/p['total_protocols']*100:.1f}%), "
                           f"Last updated: {p['last_update']}")
                logger.info(f"   Resume with: --resume \"{p['file_path']}\"")
        return
    
    # Use the provided API key or the default public key
    api_key = args.api_key
    
    # Initialize extractor with retry parameters
    extractor = BundestagExtractor(
        api_key, 
        args.output_dir,
        max_retries=args.retry,
        retry_delay=args.delay,
        resume_from=args.resume
    )
    
    # Get protocols
    logger.info(f"Starting extraction for Wahlperiode {args.period}")
    logger.info(f"Using {'provided' if args.api_key else 'default public'} API key")
    
    try:
        # Get protocols with all the parameters
        protocols = extractor.get_protocols(
            period=args.period,
            limit=args.limit,
            offset=args.offset,
            index=args.index,
            resume_from_doc=args.resume_from,
            use_xml=args.use_xml
        )
        
        if not protocols:
            logger.warning("No protocols were extracted")
            return
            
        logger.info(f"Successfully extracted {len(protocols)} protocols")
        
        # Export protocols
        if args.format in ["csv", "both"]:
            logger.info("Exporting to CSV...")
            exported_files = extractor.export_to_csv(
                protocols, 
                include_speech_text=args.include_speech_text,
                include_full_protocols=args.include_full_protocols,
                include_paragraphs=args.include_paragraphs,
                include_comments=args.include_comments
            )
            logger.info(f"CSV files saved to {args.output_dir}")
        
        if args.format in ["json", "both"]:
            logger.info("Exporting to JSON...")
            json_path = extractor.export_to_json(protocols)
            logger.info(f"JSON file saved to {json_path}")
        
        logger.info("Extraction completed successfully")
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        logger.info("To resume from this point, run the command again with --resume parameter")
        return
        
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}", exc_info=True)
        logger.error("To resume, use the --resume parameter with the latest progress file")
        return


if __name__ == "__main__":
    main()
