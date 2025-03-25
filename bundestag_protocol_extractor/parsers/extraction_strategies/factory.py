"""
Factory for creating extraction strategies.

This module provides a factory for creating and composing different
extraction strategies following the Factory pattern.
"""

from typing import Any, Dict, List, Optional

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.parsers.extraction_strategies.base_strategy import (
    ExtractionStrategy,
)
from bundestag_protocol_extractor.parsers.extraction_strategies.page_strategy import (
    PageExtractionStrategy,
)
from bundestag_protocol_extractor.parsers.extraction_strategies.pattern_strategy import (
    PatternExtractionStrategy,
)
from bundestag_protocol_extractor.parsers.extraction_strategies.xml_strategy import (
    XMLExtractionStrategy,
)
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionStrategyFactory:
    """Factory for creating extraction strategies."""

    def __init__(self, api_client: BundestagAPIClient):
        """
        Initialize the factory.

        Args:
            api_client: API client for extraction strategies that need it
        """
        self.api_client = api_client

    def create_strategy(self, strategy_name: str) -> Optional[ExtractionStrategy]:
        """
        Create a specific extraction strategy.

        Args:
            strategy_name: Name of the strategy to create

        Returns:
            Extraction strategy instance or None if not found
        """
        if strategy_name == "xml":
            return XMLExtractionStrategy(self.api_client)
        elif strategy_name == "pattern":
            return PatternExtractionStrategy()
        elif strategy_name == "page":
            return PageExtractionStrategy()
        else:
            logger.warning(f"Unknown extraction strategy: {strategy_name}")
            return None

    def create_tiered_strategy_list(self) -> List[ExtractionStrategy]:
        """
        Create a list of strategies in order of preference.

        Returns:
            List of extraction strategies
        """
        return [
            self.create_strategy("xml"),
            self.create_strategy("pattern"),
            self.create_strategy("page"),
        ]
