"""
Extraction strategy module for text extraction from protocols.

This module provides various strategies for extracting speech text from
Bundestag protocols, using the Strategy pattern to encapsulate different
extraction algorithms.
"""

from bundestag_protocol_extractor.parsers.extraction_strategies.base_strategy import ExtractionStrategy
from bundestag_protocol_extractor.parsers.extraction_strategies.xml_strategy import XMLExtractionStrategy
from bundestag_protocol_extractor.parsers.extraction_strategies.pattern_strategy import PatternExtractionStrategy
from bundestag_protocol_extractor.parsers.extraction_strategies.page_strategy import PageExtractionStrategy
from bundestag_protocol_extractor.parsers.extraction_strategies.factory import ExtractionStrategyFactory

__all__ = [
    'ExtractionStrategy',
    'XMLExtractionStrategy',
    'PatternExtractionStrategy',
    'PageExtractionStrategy',
    'ExtractionStrategyFactory',
]