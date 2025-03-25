"""
XML-based extraction strategy for protocol speech text.

This module provides an extraction strategy that uses XML parsing
to extract speech text with high fidelity.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.models.schema import Person, PlenarProtocol, Speech
from bundestag_protocol_extractor.parsers.extraction_strategies.base_strategy import (
    ExtractionStrategy,
)
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class XMLExtractionStrategy(ExtractionStrategy):
    """XML-based extraction strategy for speeches."""

    def __init__(self, api_client: BundestagAPIClient):
        """
        Initialize the XML extraction strategy.

        Args:
            api_client: API client for accessing protocol data
        """
        super().__init__(name="xml", confidence=1.0)
        self.api_client = api_client

    def can_extract(self, protocol: PlenarProtocol) -> bool:
        """
        Check if XML extraction is possible for this protocol.

        Args:
            protocol: The protocol to check

        Returns:
            True if XML data is available, False otherwise
        """
        # We'll always attempt XML extraction if we have protocol data
        return True

    def extract(self, protocol: PlenarProtocol, speeches: List[Speech]) -> List[Speech]:
        """
        Extract speech text using XML parsing.

        Args:
            protocol: The protocol containing the full text and metadata
            speeches: List of speeches with basic metadata

        Returns:
            Updated list of speeches with extracted text
        """
        logger.info(
            f"Extracting speeches using XML strategy for protocol {protocol.dokumentnummer}"
        )

        # Get protocol data in standard format for the API client
        protocol_data = {
            "id": protocol.id,
            "wahlperiode": protocol.wahlperiode,
            "dokumentnummer": protocol.dokumentnummer,
        }

        # If we have a PDF URL, add it to help with XML extraction
        if protocol.pdf_url:
            protocol_data["fundstelle"] = {"pdf_url": protocol.pdf_url}

        # Try to get the XML
        xml_root = self.api_client.get_plenarprotokoll_xml(protocol_data)

        if xml_root is None:
            logger.warning(
                f"XML extraction failed for protocol {protocol.dokumentnummer}"
            )
            # Mark all speeches as failed with XML extraction
            for speech in speeches:
                speech.extraction_method = self.name
                speech.extraction_status = "failed"
                speech.extraction_confidence = 0.0

                # Set standard placeholder for failed extraction
                speaker_name = f"{speech.speaker.titel} {speech.speaker.vorname} {speech.speaker.nachname}".strip()
                speech.text = f"[EXTRACTION_FAILED:NO_XML_AVAILABLE] Speech referenced at page {speech.page_start}, speaker: {speaker_name}"

            return speeches

        # Extract speeches from XML
        raw_speeches = self.api_client.parse_speeches_from_xml(xml_root)
        logger.info(f"Extracted {len(raw_speeches)} speeches from XML")

        # Map extracted speeches to our existing speech objects
        # There are multiple potential matching scenarios:
        # 1. Direct ID match if available
        # 2. Page number + speaker name match
        # 3. Speaker name + approximate position match

        # First, create a mapping by page number
        page_speeches = {}
        for raw_speech in raw_speeches:
            page = raw_speech.get("page", "")
            if page:
                if page not in page_speeches:
                    page_speeches[page] = []
                page_speeches[page].append(raw_speech)

        # Now process each speech and try to find a match
        for speech in speeches:
            # Try to match by page number first
            if speech.page_start and speech.page_start in page_speeches:
                # For speeches on the same page, try to match by speaker name
                for raw_speech in page_speeches[speech.page_start]:
                    # Check if the speaker names match approximately
                    speaker_last_name = speech.speaker.nachname.lower()
                    raw_last_name = raw_speech.get("speaker_last_name", "").lower()

                    if (
                        speaker_last_name
                        and raw_last_name
                        and speaker_last_name in raw_last_name
                        or raw_last_name in speaker_last_name
                    ):
                        # We found a match by page and speaker
                        self._apply_xml_speech_data(speech, raw_speech)
                        break
                else:
                    # No match by speaker, just use the first speech on this page
                    if page_speeches[speech.page_start]:
                        self._apply_xml_speech_data(
                            speech, page_speeches[speech.page_start][0]
                        )
                    else:
                        # Mark as failed extraction
                        metadata = self.get_extraction_metadata(False)
                        speech.extraction_method = metadata["extraction_method"]
                        speech.extraction_status = metadata["extraction_status"]
                        speech.extraction_confidence = metadata["extraction_confidence"]

                        # Set standard placeholder
                        speaker_name = f"{speech.speaker.titel} {speech.speaker.vorname} {speech.speaker.nachname}".strip()
                        speech.text = f"[EXTRACTION_FAILED:NO_MATCHING_XML_SPEECH] Speech referenced at page {speech.page_start}, speaker: {speaker_name}"
            else:
                # No page match, mark as failed extraction
                metadata = self.get_extraction_metadata(False)
                speech.extraction_method = metadata["extraction_method"]
                speech.extraction_status = metadata["extraction_status"]
                speech.extraction_confidence = metadata["extraction_confidence"]

                # Set standard placeholder
                speaker_name = f"{speech.speaker.titel} {speech.speaker.vorname} {speech.speaker.nachname}".strip()
                page_ref = speech.page_start or "unknown"
                speech.text = f"[EXTRACTION_FAILED:NO_MATCHING_PAGE_IN_XML] Speech referenced at page {page_ref}, speaker: {speaker_name}"

        return speeches

    def _apply_xml_speech_data(
        self, speech: Speech, raw_speech: Dict[str, Any]
    ) -> None:
        """
        Apply raw XML speech data to a Speech object.

        Args:
            speech: The Speech object to update
            raw_speech: Raw speech data from XML parsing
        """
        # Apply text content
        speech.text = raw_speech.get("text", "")

        # Add extraction metadata
        metadata = self.get_extraction_metadata(True)
        speech.extraction_method = metadata["extraction_method"]
        speech.extraction_status = metadata["extraction_status"]
        speech.extraction_confidence = metadata["extraction_confidence"]

        # Add extra metadata if available
        if "paragraphs" in raw_speech:
            speech.paragraphs = raw_speech["paragraphs"]

        if "comments" in raw_speech:
            speech.comments = raw_speech["comments"]

        # Update topics
        for comment in raw_speech.get("comments", []):
            # Some comments include information about topics
            if "betr.:" in comment.lower() or "betreffend:" in comment.lower():
                speech.topics.append(comment)

        # Add XML-specific metadata
        speech.is_interjection = raw_speech.get("is_interjection", False)
        speech.is_presidential_announcement = raw_speech.get(
            "is_presidential_announcement", False
        )
