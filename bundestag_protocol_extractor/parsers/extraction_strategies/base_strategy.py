"""
Base extraction strategy for protocol speech text extraction.

This module provides the abstract base class for extraction strategies
following the Strategy pattern.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from bundestag_protocol_extractor.models.schema import PlenarProtocol, Speech
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionStrategy(ABC):
    """Abstract base class for extraction strategies."""

    def __init__(self, name: str, confidence: float):
        """
        Initialize the extraction strategy.

        Args:
            name: Name of the strategy for identification
            confidence: Base confidence score for this extraction method
        """
        self.name = name
        self.base_confidence = confidence

    @abstractmethod
    def extract(self, protocol: PlenarProtocol, speeches: List[Speech]) -> List[Speech]:
        """
        Extract speech text from the protocol.

        Args:
            protocol: The protocol containing the full text and metadata
            speeches: List of speeches with basic metadata but without text

        Returns:
            Updated list of speeches with extracted text and extraction metadata
        """
        pass

    def can_extract(self, protocol: PlenarProtocol) -> bool:
        """
        Check if this strategy can be applied to the given protocol.

        Args:
            protocol: The protocol to check

        Returns:
            True if this strategy can be applied, False otherwise
        """
        return True

    def get_extraction_metadata(
        self, success: bool, partial: bool = False
    ) -> Dict[str, Any]:
        """
        Get standard extraction metadata.

        Args:
            success: Whether extraction was successful
            partial: Whether only partial extraction was possible

        Returns:
            Dictionary with extraction metadata
        """
        if not success:
            return {
                "extraction_method": self.name,
                "extraction_status": "failed",
                "extraction_confidence": 0.0,
            }

        if partial:
            return {
                "extraction_method": self.name,
                "extraction_status": "partial",
                "extraction_confidence": self.base_confidence * 0.5,
            }

        return {
            "extraction_method": self.name,
            "extraction_status": "complete",
            "extraction_confidence": self.base_confidence,
        }
