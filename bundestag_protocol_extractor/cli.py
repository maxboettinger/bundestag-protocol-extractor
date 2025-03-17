"""
Command line interface for the Bundestag Protocol Extractor.

This module provides a command-line entry point for the package,
allowing it to be used as a console script.
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

from bundestag_protocol_extractor.extractor import BundestagExtractor
from bundestag_protocol_extractor.utils.logging import get_logger, setup_logging
from bundestag_protocol_extractor.utils.progress import ProgressTracker

logger = get_logger(__name__)


def main():
    """
    Main entry point for the CLI.
    
    This function is registered as a console script in setup.py,
    allowing the package to be run with the 'bpe' command.
    """
    try:
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
            return 0
        
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
                return 1
                
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
            return 0
            
        except KeyboardInterrupt:
            logger.warning("Process interrupted by user")
            logger.info("To resume from this point, run the command again with --resume parameter")
            return 1
            
        except Exception as e:
            logger.error(f"Error during extraction: {str(e)}", exc_info=True)
            logger.error("To resume, use the --resume parameter with the latest progress file")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())