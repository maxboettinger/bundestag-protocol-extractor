"""
Main module for the Bundestag Protocol Extractor.
"""
import argparse
import os
import logging
from typing import Dict, List, Optional, Union, Any

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.utils.exporter import Exporter
from bundestag_protocol_extractor.models.schema import PlenarProtocol

logger = logging.getLogger(__name__)


class BundestagExtractor:
    """
    Main class for extracting and processing Bundestag plenarprotocols.
    """
    
    # Public API key
    DEFAULT_API_KEY = "I9FKdCn.hbfefNWCY336dL6x62vfwNKpoN2RZ1gp21"
    
    def __init__(self, api_key: Optional[str] = None, output_dir: str = "output", 
                 max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the extractor.
        
        Args:
            api_key: API key for the Bundestag API (defaults to public key)
            output_dir: Directory for output files
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
        """
        # Use provided API key or default to the public key
        api_key = api_key or self.DEFAULT_API_KEY
        self.api_client = BundestagAPIClient(api_key)
        self.parser = ProtocolParser(self.api_client, max_retries=max_retries, retry_delay=retry_delay)
        self.exporter = Exporter(output_dir)
    
    def get_protocols(self, period: int = 20, limit: Optional[int] = None) -> List[PlenarProtocol]:
        """
        Get plenarprotocols for a specific legislative period.
        
        Args:
            period: Legislative period (Wahlperiode), default is 20
            limit: Optional limit for the number of protocols to retrieve
            
        Returns:
            List of PlenarProtocol objects
        """
        # Get list of all protocols
        protocol_list = self.api_client.get_plenarprotokoll_list(wahlperiode=period)
        
        # Apply limit if specified
        if limit:
            protocol_list = protocol_list[:limit]
        
        protocols = []
        for protocol_metadata in protocol_list:
            protocol_id = int(protocol_metadata["id"])
            
            try:
                # Parse full protocol
                protocol = self.parser.parse_protocol(protocol_id)
                protocols.append(protocol)
                logger.info(f"Successfully parsed protocol {protocol_id}")
            except Exception as e:
                logger.error(f"Error processing protocol {protocol_id}: {e}")
                # Continue with other protocols rather than failing completely
                continue
        
        return protocols
    
    def export_to_csv(self, protocols: List[PlenarProtocol], output_dir: Optional[str] = None) -> None:
        """
        Export protocols to CSV files.
        
        Args:
            protocols: List of PlenarProtocol objects
            output_dir: Optional output directory
        """
        if output_dir:
            self.exporter.output_dir = output_dir
        
        self.exporter.export_to_csv(protocols)
    
    def export_to_json(self, protocols: List[PlenarProtocol], output_dir: Optional[str] = None) -> None:
        """
        Export protocols to a JSON file.
        
        Args:
            protocols: List of PlenarProtocol objects
            output_dir: Optional output directory
        """
        if output_dir:
            self.exporter.output_dir = output_dir
        
        self.exporter.export_to_json(protocols)


def main():
    """Command line interface for the extractor."""
    parser = argparse.ArgumentParser(description="Extract and structure data from the German Bundestag's API")
    # API key is hardcoded (public key)
    parser.add_argument("--api-key", help="API key for the Bundestag API (optional, defaults to public key)")
    parser.add_argument("--period", type=int, default=20, help="Legislative period (default: 20)")
    parser.add_argument("--limit", type=int, help="Limit the number of protocols to extract")
    parser.add_argument("--offset", type=int, default=0, 
                        help="Skip the first N protocols (useful for resuming after rate limiting)")
    parser.add_argument("--delay", type=float, default=0.5, 
                        help="Delay in seconds between API requests to avoid rate limiting (default: 0.5)")
    parser.add_argument("--retry", type=int, default=3,
                        help="Number of times to retry a request when rate limited (default: 3)")
    parser.add_argument("--index", type=int, 
                        help="Start processing from a specific protocol index (alternative to offset)")
    parser.add_argument("--resume-from", type=str,
                        help="Resume processing from a specific protocol number (e.g. '20/12')")
    parser.add_argument("--output-dir", default="output", help="Output directory for extracted data")
    parser.add_argument("--format", choices=["csv", "json", "both"], default="csv", 
                        help="Output format (default: csv)")
    parser.add_argument("--use-xml", action="store_true", default=True,
                        help="Use XML parsing for speeches (more accurate, default: True)")
    parser.add_argument("--no-xml", dest="use_xml", action="store_false",
                        help="Disable XML parsing for speeches")
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
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Use the provided API key or the default public key
    api_key = args.api_key if args.api_key else "I9FKdCn.hbfefNWCY336dL6x62vfwNKpoN2RZ1gp21"
    
    # Initialize extractor with retry parameters
    extractor = BundestagExtractor(
        api_key, 
        args.output_dir,
        max_retries=args.retry,
        retry_delay=args.delay
    )
    
    # Get protocols
    print(f"Retrieving protocols for Wahlperiode {args.period}...")
    print(f"Using {'provided' if args.api_key else 'default public'} API key")
    
    # Add use_xml parameter
    protocols = []
    try:
        import time
        
        # Get the full list of protocols first
        print("Retrieving protocol list (this may take a moment)...")
        protocol_list = extractor.api_client.get_plenarprotokoll_list(
            wahlperiode=args.period,
            max_retries=args.retry,
            retry_delay=args.delay
        )
        total_protocols = len(protocol_list)
        print(f"Found {total_protocols} protocols in total")
        
        # Determine where to start processing based on the provided parameters
        start_index = 0
        
        if args.index is not None:
            # Start from a specific index
            start_index = args.index
            print(f"Starting from index {start_index} based on --index parameter")
        elif args.offset > 0:
            # Skip the first N protocols
            start_index = args.offset
            print(f"Skipping first {start_index} protocols based on --offset parameter")
        elif args.resume_from:
            # Find the protocol with the specified document number
            target_doc_num = args.resume_from
            for idx, p in enumerate(protocol_list):
                if p.get("dokumentnummer") == target_doc_num:
                    start_index = idx
                    print(f"Found protocol {target_doc_num} at index {start_index}, resuming from here")
                    break
            else:
                print(f"Warning: Could not find protocol {target_doc_num}, starting from the beginning")
        
        # Apply index offset
        if start_index > 0:
            if start_index >= len(protocol_list):
                print(f"Error: Start index {start_index} is out of range (max: {len(protocol_list)-1})")
                return
            protocol_list = protocol_list[start_index:]
            print(f"Starting at protocol {start_index+1} of {total_protocols}")
        
        # Apply limit if specified
        if args.limit:
            protocol_list = protocol_list[:args.limit]
            print(f"Limited to {len(protocol_list)} protocols due to --limit parameter")
        
        print(f"Will process {len(protocol_list)} protocols...")
        
    except Exception as e:
        print(f"Error retrieving protocol list: {e}")
        print("Check if the API key is correct and the API is accessible")
        return
    
    # Track rate limiting
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    # Process each protocol
    for i, protocol_metadata in enumerate(protocol_list):
        protocol_id = int(protocol_metadata["id"])
        protocol_number = protocol_metadata.get('dokumentnummer', str(protocol_id))
        
        # Calculate the actual index in the full list
        full_index = i + start_index
        print(f"Processing protocol {full_index+1}/{total_protocols}: {protocol_number}")
        
        # Add delay to avoid rate limiting
        if i > 0 and args.delay > 0:
            time.sleep(args.delay)
        
        # Try multiple times in case of rate limiting
        retry_count = 0
        success = False
        
        while retry_count <= args.retry and not success:
            if retry_count > 0:
                # Exponential backoff for retries
                wait_time = args.delay * (2 ** retry_count)
                print(f"  Retry {retry_count}/{args.retry} after {wait_time:.1f}s wait...")
                time.sleep(wait_time)
            
            try:
                # Parse protocol with XML option
                protocol = extractor.parser.parse_protocol(protocol_id, use_xml=args.use_xml)
                protocols.append(protocol)
                print(f"  Found {len(protocol.speeches)} speeches")
                success = True
                consecutive_failures = 0  # Reset failure counter on success
                
            except Exception as e:
                retry_count += 1
                error_str = str(e)
                
                # Check if this is likely a rate limit error
                is_rate_limit = False
                if "429" in error_str or "Too Many Requests" in error_str:
                    is_rate_limit = True
                elif "challenge" in error_str:  # DIP API's rate limit mechanism
                    is_rate_limit = True
                elif "400 Bad Request" in error_str and "challenge" in error_str:
                    is_rate_limit = True
                
                if is_rate_limit and retry_count <= args.retry:
                    print(f"  Rate limit detected, will retry ({retry_count}/{args.retry})")
                else:
                    print(f"  Error processing protocol {protocol_id}: {e}")
                    if retry_count >= args.retry:
                        print(f"  Maximum retries reached, skipping this protocol")
                    else:
                        print(f"  This may be due to API changes or other issues. Continuing with next protocol...")
                    consecutive_failures += 1
                    break  # Exit retry loop
        
        # Check if we should pause due to too many consecutive failures
        if consecutive_failures >= max_consecutive_failures:
            print(f"Warning: {consecutive_failures} consecutive failures detected.")
            print(f"To resume from this point later, use: --resume-from {protocol_number}")
            print(f"Or use: --index {full_index + 1}")
            
            # Ask user if they want to continue
            if input("Too many failures in a row. Continue anyway? (y/n): ").lower() != 'y':
                print(f"Stopping processing. To resume later, use: --resume-from {protocol_number}")
                break
            else:
                consecutive_failures = 0  # Reset counter and continue
    
    print(f"Successfully processed {len(protocols)} protocols")
    
    # Export protocols
    if args.format in ["csv", "both"]:
        print("Exporting to CSV...")
        extractor.exporter.export_to_csv(
            protocols, 
            include_speech_text=args.include_speech_text,
            include_full_protocols=args.include_full_protocols,
            include_paragraphs=args.include_paragraphs,
            include_comments=args.include_comments
        )
        print(f"CSV files saved to {args.output_dir}")
    
    if args.format in ["json", "both"]:
        print("Exporting to JSON...")
        extractor.exporter.export_to_json(protocols)
        print(f"JSON file saved to {args.output_dir}")
    
    print("Done!")


if __name__ == "__main__":
    main()
