"""Tests for the main BundestagExtractor class."""
import pytest
from unittest.mock import patch, MagicMock
import os
from datetime import date
from pathlib import Path

from bundestag_protocol_extractor import BundestagExtractor
from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


@pytest.fixture
def extractor_test_setup(temp_directory):
    """Set up test fixtures for BundestagExtractor tests."""
    # Mock dependencies
    with patch('bundestag_protocol_extractor.extractor.BundestagAPIClient') as mock_api_client, \
         patch('bundestag_protocol_extractor.extractor.ProtocolParser') as mock_parser, \
         patch('bundestag_protocol_extractor.extractor.Exporter') as mock_exporter, \
         patch('bundestag_protocol_extractor.extractor.ProgressTracker') as mock_progress_tracker:
        
        # Create test extractor
        extractor = BundestagExtractor(
            api_key="test_api_key",
            output_dir=str(temp_directory)
        )
        
        # Get mock instances
        api_client_instance = mock_api_client.return_value
        parser_instance = mock_parser.return_value
        exporter_instance = mock_exporter.return_value
        progress_instance = mock_progress_tracker.return_value
        
        # Create test protocols
        protocol1 = PlenarProtocol(
            id=123, 
            dokumentnummer="20/123", 
            wahlperiode=20, 
            date=date(2023, 5, 15),
            title="Protocol 1",
            herausgeber="Deutscher Bundestag"
        )
        
        protocol2 = PlenarProtocol(
            id=456, 
            dokumentnummer="20/456", 
            wahlperiode=20, 
            date=date(2023, 5, 16),
            title="Protocol 2",
            herausgeber="Deutscher Bundestag"
        )
        
        # Set up mock return values
        api_client_instance.get_plenarprotokoll_list.return_value = [
            {"id": "123", "dokumentnummer": "20/123"},
            {"id": "456", "dokumentnummer": "20/456"}
        ]
        parser_instance.parse_protocol.side_effect = [protocol1, protocol2]
        exporter_instance.export_to_csv.return_value = {
            "protocols": temp_directory / "protocols.csv",
            "speeches": temp_directory / "speeches.csv",
        }
        exporter_instance.export_to_json.return_value = temp_directory / "protocols.json"
        
        yield {
            "extractor": extractor,
            "api_client": mock_api_client,
            "api_instance": api_client_instance,
            "parser_instance": parser_instance,
            "exporter_instance": exporter_instance,
            "progress_instance": progress_instance,
            "protocols": [protocol1, protocol2],
            "temp_directory": temp_directory
        }


def test_initialization(temp_directory):
    """Test initialization of the extractor."""
    with patch('bundestag_protocol_extractor.extractor.BundestagAPIClient') as mock_api_client:
        # Test creation with API key and output_dir
        extractor = BundestagExtractor(
            api_key="test_key",
            output_dir=str(temp_directory),
            enable_xml_cache=False
        )
        
        # Check that the mock was called correctly
        mock_api_client.assert_called_once()
        
        # Verify expected attributes
        assert str(extractor.output_dir) == str(temp_directory)
        assert extractor.enable_xml_cache == False


def test_get_protocols(extractor_test_setup):
    """Test the get_protocols method."""
    # Get test objects
    extractor = extractor_test_setup["extractor"]
    api_instance = extractor_test_setup["api_instance"]
    parser_instance = extractor_test_setup["parser_instance"]
    progress_instance = extractor_test_setup["progress_instance"]
    
    # Call the method
    protocols = extractor.get_protocols(period=20, limit=2)
    
    # Verify API client was called correctly
    api_instance.get_plenarprotokoll_list.assert_called_with(
        wahlperiode=20,
        max_retries=3,
        retry_delay=1.0,
        progress_tracker=progress_instance
    )
    
    # Verify parser was called for each protocol
    assert parser_instance.parse_protocol.call_count == 2
    
    # Verify progress tracker was used correctly
    progress_instance.init_total.assert_called_with(2)
    assert progress_instance.complete_protocol.call_count == 2
    progress_instance.complete.assert_called_once()
    
    # Verify the returned protocols
    assert len(protocols) == 2
    assert protocols[0].id == 123
    assert protocols[1].id == 456


def test_export_to_csv(extractor_test_setup):
    """Test the export_to_csv method."""
    # Get test objects
    extractor = extractor_test_setup["extractor"]
    exporter_instance = extractor_test_setup["exporter_instance"]
    protocols = extractor_test_setup["protocols"]
    temp_directory = extractor_test_setup["temp_directory"]
    
    # Call the method with just the first protocol
    result = extractor.export_to_csv([protocols[0]])
    
    # Verify exporter was called correctly
    exporter_instance.export_to_csv.assert_called_with(
        [protocols[0]],
        include_speech_text=True,
        include_full_protocols=False,
        include_paragraphs=True,
        include_comments=True
    )
    
    # Verify the result
    assert len(result) == 2
    assert result["protocols"] == temp_directory / "protocols.csv"
    assert result["speeches"] == temp_directory / "speeches.csv"


def test_export_to_json(extractor_test_setup):
    """Test the export_to_json method."""
    # Get test objects
    extractor = extractor_test_setup["extractor"]
    exporter_instance = extractor_test_setup["exporter_instance"]
    protocols = extractor_test_setup["protocols"]
    temp_directory = extractor_test_setup["temp_directory"]
    
    # Call the method with just the first protocol
    result = extractor.export_to_json([protocols[0]])
    
    # Verify exporter was called correctly
    exporter_instance.export_to_json.assert_called_with([protocols[0]], filename=None)
    
    # Verify the result
    assert result == temp_directory / "protocols.json"