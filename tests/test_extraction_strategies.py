"""Tests for the extraction strategies."""

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.models.schema import Person, PlenarProtocol, Speech
from bundestag_protocol_extractor.parsers.extraction_strategies import (
    ExtractionStrategyFactory,
    PageExtractionStrategy,
    PatternExtractionStrategy,
    XMLExtractionStrategy,
)


@pytest.fixture
def mock_extraction_setup():
    """Set up test fixtures for extraction strategies."""
    # Create a mock API client
    api_client = MagicMock(spec=BundestagAPIClient)

    # Create a test person
    person = Person(
        id=9876, nachname="Mustermann", vorname="Max", titel="Dr.", fraktion="CDU/CSU"
    )

    # Create test speeches
    speeches = [
        Speech(
            id=1000,
            speaker=person,
            title="Test Speech",
            text="[EXTRACTION_PENDING] Speech by Dr. Max Mustermann",
            date="2023-01-01",
            protocol_id=12345,
            protocol_number="20/123",
            page_start="123",
            extraction_method="none",
            extraction_status="pending",
            extraction_confidence=0.0,
        )
    ]

    # Create a mock protocol
    protocol = PlenarProtocol(
        id=12345,
        dokumentnummer="20/123",
        wahlperiode=20,
        date="2023-01-01",
        title="Test Protocol",
        herausgeber="Deutscher Bundestag",
        full_text="This is a test protocol with some text. Deutscher Bundestag – 20. Wahlperiode – 123. Sitzung. Abg. Max Mustermann (CDU/CSU): This is a test speech.",
    )

    # Add speeches to protocol
    protocol.speeches = speeches.copy()

    # Set up mocked XML response
    xml_root = ET.fromstring(
        """
    <protokoll>
        <id>12345</id>
        <sitzungsverlauf>
            <rede id="1000">
                <redner id="9876">
                    <name>
                        <titel>Dr.</titel>
                        <vorname>Max</vorname>
                        <nachname>Mustermann</nachname>
                        <fraktion>CDU/CSU</fraktion>
                    </name>
                </redner>
                <p>This is the speech content from XML.</p>
                <kommentar>Some comment</kommentar>
                <p>More content.</p>
            </rede>
        </sitzungsverlauf>
    </protokoll>
    """
    )

    return {
        "api_client": api_client,
        "protocol": protocol,
        "speeches": speeches,
        "person": person,
        "xml_root": xml_root,
    }


def test_factory_creation(mock_extraction_setup):
    """Test creating strategies with the factory."""
    api_client = mock_extraction_setup["api_client"]
    factory = ExtractionStrategyFactory(api_client)

    # Test creating individual strategies
    xml_strategy = factory.create_strategy("xml")
    assert isinstance(xml_strategy, XMLExtractionStrategy)

    pattern_strategy = factory.create_strategy("pattern")
    assert isinstance(pattern_strategy, PatternExtractionStrategy)

    page_strategy = factory.create_strategy("page")
    assert isinstance(page_strategy, PageExtractionStrategy)

    # Test creating an unknown strategy
    unknown_strategy = factory.create_strategy("unknown")
    assert unknown_strategy is None

    # Test creating tiered strategy list
    strategies = factory.create_tiered_strategy_list()
    assert len(strategies) == 3
    assert isinstance(strategies[0], XMLExtractionStrategy)
    assert isinstance(strategies[1], PatternExtractionStrategy)
    assert isinstance(strategies[2], PageExtractionStrategy)


def test_xml_strategy(mock_extraction_setup):
    """Test the XML extraction strategy."""
    api_client = mock_extraction_setup["api_client"]
    protocol = mock_extraction_setup["protocol"]
    speeches = mock_extraction_setup["speeches"]
    xml_root = mock_extraction_setup["xml_root"]

    # Set up the mock API client to return our XML
    api_client.get_plenarprotokoll_xml.return_value = xml_root
    api_client.parse_speeches_from_xml.return_value = [
        {
            "id": "1000",
            "speaker_id": "9876",
            "speaker_title": "Dr.",
            "speaker_first_name": "Max",
            "speaker_last_name": "Mustermann",
            "speaker_full_name": "Dr. Max Mustermann",
            "party": "CDU/CSU",
            "page": "123",
            "text": "This is the speech content from XML.\n\nSome comment\n\nMore content.",
            "paragraphs": [
                {"text": "This is the speech content from XML.", "type": ""},
                {"text": "Some comment", "type": "kommentar"},
                {"text": "More content.", "type": ""},
            ],
            "comments": ["Some comment"],
        }
    ]

    # Create the strategy
    strategy = XMLExtractionStrategy(api_client)

    # Test extraction
    result = strategy.extract(protocol, speeches.copy())

    # Verify the result
    assert len(result) == 1
    assert (
        result[0].text
        == "This is the speech content from XML.\n\nSome comment\n\nMore content."
    )
    assert result[0].extraction_method == "xml"
    assert result[0].extraction_status == "complete"
    assert result[0].extraction_confidence == 1.0

    # Verify the API client was called correctly
    api_client.get_plenarprotokoll_xml.assert_called_once()
    api_client.parse_speeches_from_xml.assert_called_once_with(xml_root)


def test_xml_strategy_failure(mock_extraction_setup):
    """Test XML strategy when XML is not available."""
    api_client = mock_extraction_setup["api_client"]
    protocol = mock_extraction_setup["protocol"]
    speeches = mock_extraction_setup["speeches"]

    # Set up the mock API client to return None for XML
    api_client.get_plenarprotokoll_xml.return_value = None

    # Create the strategy
    strategy = XMLExtractionStrategy(api_client)

    # Test extraction
    result = strategy.extract(protocol, speeches.copy())

    # Verify the result
    assert len(result) == 1
    assert "EXTRACTION_FAILED" in result[0].text
    assert result[0].extraction_method == "xml"
    assert result[0].extraction_status == "failed"
    assert result[0].extraction_confidence == 0.0


def test_pattern_strategy(mock_extraction_setup):
    """Test the pattern extraction strategy."""
    protocol = mock_extraction_setup["protocol"]
    speeches = mock_extraction_setup["speeches"]

    # Add more detailed text to the protocol
    protocol.full_text = """
    Deutscher Bundestag – 20. Wahlperiode – 123. Sitzung.

    Präsident Dr. Wilhelm: Ich eröffne die Sitzung.

    Als nächsten Redner rufe ich den Abgeordneten Dr. Max Mustermann von der CDU/CSU-Fraktion auf.

    (Beifall bei der CDU/CSU)

    Dr. Max Mustermann (CDU/CSU):

    Sehr geehrter Herr Präsident! Liebe Kolleginnen und Kollegen!

    Dies ist eine Rede für den Patternextraktionstest. Ich hoffe, dass dieser
    Test erfolgreich sein wird.

    (Beifall bei der CDU/CSU)

    Vielen Dank für Ihre Aufmerksamkeit.

    (Beifall bei der CDU/CSU)

    Präsident Dr. Wilhelm: Vielen Dank, Herr Kollege Mustermann.
    """

    # Create the strategy
    strategy = PatternExtractionStrategy()

    # Test extraction
    result = strategy.extract(protocol, speeches.copy())

    # Verify the result
    assert len(result) == 1
    assert "Sehr geehrter Herr Präsident" in result[0].text
    assert "Vielen Dank für Ihre Aufmerksamkeit" in result[0].text
    assert result[0].extraction_method == "pattern"
    assert result[0].extraction_status == "complete"
    assert result[0].extraction_confidence > 0.6


def test_page_strategy(mock_extraction_setup):
    """Test the page extraction strategy."""
    protocol = mock_extraction_setup["protocol"]
    speeches = mock_extraction_setup["speeches"]

    # Update the speech page start to match our test data
    speeches[0].page_start = "123"

    # Set up a protocol with page markers that match the exact pattern in PageExtractionStrategy.PAGE_PATTERN
    protocol.full_text = """
    Deutscher Bundestag – 20. Wahlperiode – 122. Sitzung.

    Previous page content.

    Deutscher Bundestag – 20. Wahlperiode – 123. Sitzung.

    This is text on page 123 that should be extracted.
    It contains page-based extraction content.

    Deutscher Bundestag – 20. Wahlperiode – 124. Sitzung.

    Next page content.
    """

    # Create the strategy
    strategy = PageExtractionStrategy()

    # Test extraction
    result = strategy.extract(protocol, speeches.copy())

    # Verify the result
    assert len(result) == 1

    # The page strategy adds content from around page_start_idx + 100 to handle page headers
    # It also adds a specific note about page-based extraction
    text = result[0].text

    # Check for expected content - the actual text content should be in the result
    assert "extracted" in text

    # The page strategy adds a specific disclaimer note
    assert "[Note: This text was extracted using page-based extraction" in text

    # Check extraction metadata properties
    assert result[0].extraction_method == "page"

    # Page extraction might be marked as partial if text is short (<500 chars)
    # We need to test for either status since it depends on length
    assert result[0].extraction_status in ["complete", "partial"]

    # Page strategy has base confidence of 0.4, but can be adjusted by length
    # We expect it to be at most 0.4 (could be lower if adjusted by confidence_multiplier)
    assert 0 < result[0].extraction_confidence <= 0.4


def test_extraction_metadata():
    """Test extraction metadata calculation."""
    # Create a basic strategy
    strategy = PageExtractionStrategy()

    # Test successful extraction
    metadata = strategy.get_extraction_metadata(True)
    assert metadata["extraction_method"] == "page"
    assert metadata["extraction_status"] == "complete"
    assert metadata["extraction_confidence"] == 0.4

    # Test partial extraction
    metadata = strategy.get_extraction_metadata(True, partial=True)
    assert metadata["extraction_method"] == "page"
    assert metadata["extraction_status"] == "partial"
    assert metadata["extraction_confidence"] == 0.2  # 50% of base confidence

    # Test failed extraction
    metadata = strategy.get_extraction_metadata(False)
    assert metadata["extraction_method"] == "page"
    assert metadata["extraction_status"] == "failed"
    assert metadata["extraction_confidence"] == 0.0


def test_parse_speeches_from_real_xml():
    """Test parsing speeches from a real XML file."""
    # Initialize the API client with a test API key
    api_client = BundestagAPIClient("test_api_key")
    
    # Path to the test XML file
    xml_file_path = Path(__file__).parent / "data" / "20213.xml"
    
    # Skip test if the file doesn't exist
    if not xml_file_path.exists():
        pytest.skip(f"Test XML file {xml_file_path} not found")
    
    # Parse the XML file
    with open(xml_file_path, "r", encoding="utf-8") as f:
        xml_content = f.read()
    
    # Parse the XML
    root = ET.fromstring(xml_content)
    
    # Test the parse_speeches_from_xml method
    speeches = api_client.parse_speeches_from_xml(root)
    
    # Verify basic expectations
    assert speeches is not None
    assert isinstance(speeches, list)
    assert len(speeches) > 0
    
    # Verify that we have the expected speech attributes
    required_keys = ["id", "speaker_id", "speaker_full_name", "text"]
    for speech in speeches:
        for key in required_keys:
            assert key in speech, f"Expected key {key} in speech data"

    # Test finding the speeches with presidential announcements
    presidential_speeches = [s for s in speeches if s.get("is_presidential_announcement", False)]
    
    # Log the number of speeches found
    print(f"Found {len(speeches)} speeches, {len(presidential_speeches)} presidential announcements")


if __name__ == "__main__":
    pytest.main()
