"""
Main module for the Bundestag Protocol Extractor.

This module provides the high-level functionality for extracting 
and processing German Bundestag plenarprotocols.
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.utils.exporter import Exporter
from bundestag_protocol_extractor.models.schema import PlenarProtocol
from bundestag_protocol_extractor.utils.logging import get_logger
from bundestag_protocol_extractor.utils.progress import ProgressTracker

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