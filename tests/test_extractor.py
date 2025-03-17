"""Tests for the main BundestagExtractor class."""
import unittest
from unittest import mock
import os
from datetime import date
from pathlib import Path

from bundestag_protocol_extractor import BundestagExtractor
from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


class TestBundestagExtractor(unittest.TestCase):
    """Test cases for BundestagExtractor."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_api_client = mock.patch('bundestag_protocol_extractor.extractor.BundestagAPIClient').start()
        self.mock_parser = mock.patch('bundestag_protocol_extractor.extractor.ProtocolParser').start()
        self.mock_exporter = mock.patch('bundestag_protocol_extractor.extractor.Exporter').start()
        self.mock_progress_tracker = mock.patch('bundestag_protocol_extractor.extractor.ProgressTracker').start()
        
        # Setup test directory
        self.test_output_dir = "test_output"
        
        # Create test extractor
        self.extractor = BundestagExtractor(
            api_key="test_api_key",
            output_dir=self.test_output_dir
        )
        
        # Setup mock instances
        self.api_client_instance = self.mock_api_client.return_value
        self.parser_instance = self.mock_parser.return_value
        self.exporter_instance = self.mock_exporter.return_value
        self.progress_instance = self.mock_progress_tracker.return_value
        
    def tearDown(self):
        """Tear down test fixtures."""
        mock.patch.stopall()
        
        # Clean up test directory if it was created
        if os.path.exists(self.test_output_dir):
            try:
                os.rmdir(self.test_output_dir)
            except OSError:
                pass
    
    def test_initialization(self):
        """Test initialization of the extractor."""
        # Test with explicit API key
        extractor = BundestagExtractor(api_key="test_key", output_dir="test_dir")
        self.mock_api_client.assert_called_with("test_key")
        
        # Test with default API key
        extractor = BundestagExtractor(output_dir="test_dir")
        self.mock_api_client.assert_called_with(BundestagExtractor.DEFAULT_API_KEY)
    
    def test_get_protocols(self):
        """Test the get_protocols method."""
        # Mock API client and parser responses
        self.api_client_instance.get_plenarprotokoll_list.return_value = [
            {"id": "123", "dokumentnummer": "20/123"},
            {"id": "456", "dokumentnummer": "20/456"}
        ]
        
        # Create mock protocols
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
        
        # Mock the parser's parse_protocol method to return these protocols
        self.parser_instance.parse_protocol.side_effect = [protocol1, protocol2]
        
        # Call the method
        protocols = self.extractor.get_protocols(period=20, limit=2)
        
        # Verify API client was called correctly
        self.api_client_instance.get_plenarprotokoll_list.assert_called_with(
            wahlperiode=20,
            max_retries=3,
            retry_delay=1.0,
            progress_tracker=self.progress_instance
        )
        
        # Verify parser was called for each protocol
        self.assertEqual(self.parser_instance.parse_protocol.call_count, 2)
        
        # Verify progress tracker was used correctly
        self.progress_instance.init_total.assert_called_with(2)
        self.assertEqual(self.progress_instance.complete_protocol.call_count, 2)
        self.progress_instance.complete.assert_called_once()
        
        # Verify the returned protocols
        self.assertEqual(len(protocols), 2)
        self.assertEqual(protocols[0].id, 123)
        self.assertEqual(protocols[1].id, 456)
    
    def test_export_to_csv(self):
        """Test the export_to_csv method."""
        # Create test protocols
        protocol = PlenarProtocol(
            id=123, 
            dokumentnummer="20/123", 
            wahlperiode=20, 
            date=date(2023, 5, 15),
            title="Protocol 1",
            herausgeber="Deutscher Bundestag"
        )
        
        protocols = [protocol]
        
        # Mock exporter response
        self.exporter_instance.export_to_csv.return_value = {
            "protocols": Path("test_output/protocols.csv"),
            "speeches": Path("test_output/speeches.csv"),
        }
        
        # Call the method
        result = self.extractor.export_to_csv(protocols)
        
        # Verify exporter was called correctly
        self.exporter_instance.export_to_csv.assert_called_with(
            protocols,
            include_speech_text=True,
            include_full_protocols=False,
            include_paragraphs=True,
            include_comments=True
        )
        
        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result["protocols"], Path("test_output/protocols.csv"))
        self.assertEqual(result["speeches"], Path("test_output/speeches.csv"))
    
    def test_export_to_json(self):
        """Test the export_to_json method."""
        # Create test protocols
        protocol = PlenarProtocol(
            id=123, 
            dokumentnummer="20/123", 
            wahlperiode=20, 
            date=date(2023, 5, 15),
            title="Protocol 1",
            herausgeber="Deutscher Bundestag"
        )
        
        protocols = [protocol]
        
        # Mock exporter response
        self.exporter_instance.export_to_json.return_value = Path("test_output/protocols.json")
        
        # Call the method
        result = self.extractor.export_to_json(protocols)
        
        # Verify exporter was called correctly
        self.exporter_instance.export_to_json.assert_called_with(protocols, filename=None)
        
        # Verify the result
        self.assertEqual(result, Path("test_output/protocols.json"))


if __name__ == '__main__':
    unittest.main()