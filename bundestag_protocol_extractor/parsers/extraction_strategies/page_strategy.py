"""
Page-based extraction strategy for protocol speech text.

This module provides a basic extraction strategy that uses page numbers
as the primary reference point for extracting speech content.
"""
import re
from typing import List, Dict, Any, Optional, Tuple

from bundestag_protocol_extractor.models.schema import Speech, PlenarProtocol
from bundestag_protocol_extractor.parsers.extraction_strategies.base_strategy import ExtractionStrategy
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class PageExtractionStrategy(ExtractionStrategy):
    """Page-based extraction strategy for speeches."""
    
    # Pattern to identify page numbers in the text
    PAGE_PATTERN = r'Deutscher Bundestag[\s–-]+\d+\.\s+Wahlperiode[\s–-]+(\d+)\.\s+Sitzung\.'
    
    def __init__(self):
        """Initialize the page extraction strategy."""
        super().__init__(name="page", confidence=0.4)
        
    def can_extract(self, protocol: PlenarProtocol) -> bool:
        """
        Check if page-based extraction is possible.
        
        Args:
            protocol: The protocol to check
            
        Returns:
            True if full text is available, False otherwise
        """
        return protocol.full_text is not None and len(protocol.full_text) > 0
    
    def extract(self, protocol: PlenarProtocol, speeches: List[Speech]) -> List[Speech]:
        """
        Extract speech text using page references.
        
        Args:
            protocol: The protocol containing the full text
            speeches: List of speeches with basic metadata
            
        Returns:
            Updated list of speeches with extracted text
        """
        logger.info(f"Extracting speeches using page strategy for protocol {protocol.dokumentnummer}")
        
        if not self.can_extract(protocol):
            logger.warning("Page extraction failed: no full text available")
            return speeches
            
        full_text = protocol.full_text
        
        # Create a page index mapping
        page_indices = self._create_page_index(full_text)
        
        # Process each speech
        for speech in speeches:
            # Skip if no page reference
            if not speech.page_start:
                metadata = self.get_extraction_metadata(False)
                speech.extraction_method = metadata["extraction_method"]
                speech.extraction_status = metadata["extraction_status"]
                speech.extraction_confidence = metadata["extraction_confidence"]
                
                speaker_name = f"{speech.speaker.titel} {speech.speaker.vorname} {speech.speaker.nachname}".strip()
                speech.text = f"[EXTRACTION_FAILED:NO_PAGE_REFERENCE] Speech by {speaker_name}"
                continue
                
            # Try to find the page
            page_str = str(speech.page_start)
            if page_str not in page_indices:
                metadata = self.get_extraction_metadata(False)
                speech.extraction_method = metadata["extraction_method"]
                speech.extraction_status = metadata["extraction_status"]
                speech.extraction_confidence = metadata["extraction_confidence"]
                
                speaker_name = f"{speech.speaker.titel} {speech.speaker.vorname} {speech.speaker.nachname}".strip()
                speech.text = f"[EXTRACTION_FAILED:PAGE_NOT_FOUND] Speech referenced at page {page_str}, speaker: {speaker_name}"
                continue
                
            # Get page start index
            page_start_idx = page_indices[page_str]
            
            # Determine extraction range (reasonable chunk from the page)
            # For page-based extraction, we use a standard chunk size
            # This is less accurate but ensures we get something
            start_idx = page_start_idx + 100  # Skip the page header
            
            # Determine end index based on next page or chunk size
            end_idx = len(full_text)
            
            # Find the next page
            next_page = None
            try:
                current_page_num = int(page_str)
                next_page_str = str(current_page_num + 1)
                if next_page_str in page_indices:
                    end_idx = page_indices[next_page_str]
            except ValueError:
                # Not a numeric page, use a fixed chunk
                end_idx = min(start_idx + 3000, len(full_text))
                
            # If next page isn't found, or is too far, limit to 3000 chars
            if end_idx - start_idx > 3000:
                end_idx = start_idx + 3000
                
            # Extract the text
            extracted_text = full_text[start_idx:end_idx].strip()
            
            # Clean up the text
            cleaned_text = self._clean_extracted_text(extracted_text)
            
            # Update the speech
            speech.text = cleaned_text
            
            # Calculate confidence based on text properties
            confidence_multiplier = 1.0
            
            # Shorter texts are more likely to be incomplete
            if len(cleaned_text) < 500:
                confidence_multiplier *= 0.7
                is_partial = True
            else:
                is_partial = False
                
            # Apply metadata
            metadata = self.get_extraction_metadata(True, is_partial)
            speech.extraction_method = metadata["extraction_method"]
            speech.extraction_status = metadata["extraction_status"]
            speech.extraction_confidence = metadata["extraction_confidence"] * confidence_multiplier
            
        return speeches
    
    def _create_page_index(self, text: str) -> Dict[str, int]:
        """
        Create an index of page numbers to their positions in the text.
        
        Args:
            text: Full protocol text
            
        Returns:
            Dictionary mapping page numbers to their position in the text
        """
        page_indices = {}
        
        # Find all page markers
        for match in re.finditer(self.PAGE_PATTERN, text):
            page_num = match.group(1)
            # Map both string and integer versions
            page_indices[page_num] = match.start()
            page_indices[int(page_num)] = match.start()
            
        return page_indices
    
    def _clean_extracted_text(self, text: str) -> str:
        """
        Clean up extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove page headers
        text = re.sub(self.PAGE_PATTERN, '', text)
        
        # Remove multiple consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Add note about extraction method
        result = (
            f"{text}\n\n"
            f"[Note: This text was extracted using page-based extraction and may be incomplete "
            f"or contain content from multiple speakers. For research purposes, please verify "
            f"with the original document.]"
        )
        
        return result