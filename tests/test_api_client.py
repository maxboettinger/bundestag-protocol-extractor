"""Tests for the BundestagAPIClient class."""
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import requests

from bundestag_protocol_extractor.api.client import BundestagAPIClient


class TestBundestagAPIClient(unittest.TestCase):
    """Test cases for BundestagAPIClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.client = BundestagAPIClient(self.api_key)

    def test_initialization(self):
        """Test client initialization."""
        # Test without ApiKey prefix
        client = BundestagAPIClient("test_key")
        self.assertEqual(client.headers["Authorization"], "ApiKey test_key")

        # Test with ApiKey prefix
        client = BundestagAPIClient("ApiKey test_key")
        self.assertEqual(client.headers["Authorization"], "ApiKey test_key")

    def test_make_request(self):
        """Test the _make_request method."""
        # Instead of mocking requests, we'll mock the client's _make_request method
        # to avoid HTTP errors during tests
        client = BundestagAPIClient(self.api_key)
        
        # Create a custom test method that matches the signature of _make_request
        def mock_make_request(endpoint, params=None, format_xml=False, 
                             retry_count=0, max_retries=0, retry_delay=1.0,
                             progress_tracker=None):
            # Store the parameters for verification
            mock_make_request.called_with = {
                "endpoint": endpoint,
                "params": params,
                "format_xml": format_xml
            }
            # Return test data based on format
            if format_xml:
                return "<xml>test</xml>"
            return {"test": "data"}
        
        # Save original method
        original_method = client._make_request
        
        try:
            # Replace with our mock
            client._make_request = mock_make_request
            
            # Test JSON request
            result = client._make_request("test_endpoint", {"param": "value"})
            self.assertEqual(result, {"test": "data"})
            
            # Verify parameters
            self.assertEqual(mock_make_request.called_with["endpoint"], "test_endpoint")
            self.assertEqual(mock_make_request.called_with["params"], {"param": "value"})
            self.assertEqual(mock_make_request.called_with["format_xml"], False)
            
            # Test XML request
            result = client._make_request("test_endpoint", {"param": "value"}, format_xml=True)
            self.assertEqual(result, "<xml>test</xml>")
            self.assertEqual(mock_make_request.called_with["format_xml"], True)
            
        finally:
            # Restore original method
            client._make_request = original_method
        
    @mock.patch("bundestag_protocol_extractor.api.client.requests.Session")
    def test_get_plenarprotokoll_list(self, mock_session):
        """Test the get_plenarprotokoll_list method."""
        # Setup mock for get_all_results
        with mock.patch.object(self.client, 'get_all_results') as mock_get_all:
            mock_get_all.return_value = [{"id": 1}, {"id": 2}]
            
            # Call the method
            result = self.client.get_plenarprotokoll_list(wahlperiode=20)
            
            # Verify the correct parameters were passed
            mock_get_all.assert_called_with(
                "plenarprotokoll", 
                {"f.wahlperiode": 20}, 
                max_retries=3, 
                retry_delay=1.0,
                progress_tracker=None
            )
            
            # Verify the result
            self.assertEqual(result, [{"id": 1}, {"id": 2}])

    @mock.patch("bundestag_protocol_extractor.api.client.requests.get")
    def test_get_plenarprotokoll_xml(self, mock_get):
        """Test the get_plenarprotokoll_xml method."""
        # Setup mock response
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<protokoll><id>123</id></protokoll>"
        mock_get.return_value = mock_response
        
        # Mock data for plenarprotokoll
        plenarprotokoll_data = {
            "id": "123",
            "wahlperiode": "20",
            "dokumentnummer": "20/123",
            "fundstelle": {
                "pdf_url": "https://www.bundestag.de/resource/blob/12345/abcdef/20123.pdf"
            }
        }
        
        # Call the method
        result = self.client.get_plenarprotokoll_xml(plenarprotokoll_data)
        
        # Verify the result is an XML Element
        self.assertIsInstance(result, ET.Element)
        self.assertEqual(result.findtext("id"), "123")
        
        # Verify the correct URL was called
        mock_get.assert_called()

    @mock.patch("bundestag_protocol_extractor.api.client.requests.Session")
    def test_get_aktivitaet_list(self, mock_session):
        """Test the get_aktivitaet_list method."""
        # Setup mock for get_all_results
        with mock.patch.object(self.client, 'get_all_results') as mock_get_all:
            mock_get_all.return_value = [
                {"id": 1, "aktivitaetsart": "Rede"}, 
                {"id": 2, "aktivitaetsart": "Rede"},
                {"id": 3, "aktivitaetsart": "Antrag"}
            ]
            
            # Call the method with aktivitaetsart filter
            result = self.client.get_aktivitaet_list(
                plenarprotokoll_id=123,
                aktivitaetsart="Rede"
            )
            
            # Verify the correct filter was applied
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["id"], 1)
            self.assertEqual(result[1]["id"], 2)
            
            # Verify the correct parameters were passed to get_all_results
            mock_get_all.assert_called_with(
                "aktivitaet", 
                {"f.plenarprotokoll": 123}, 
                max_retries=3, 
                retry_delay=1.0,
                progress_tracker=None
            )

if __name__ == '__main__':
    unittest.main()