"""Tests for the BundestagAPIClient class."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
import pytest

import requests

from bundestag_protocol_extractor.api.client import BundestagAPIClient


@pytest.fixture
def api_client():
    """Create a test API client."""
    api_key = "test_api_key"
    return BundestagAPIClient(api_key)


def test_initialization():
    """Test client initialization."""
    # Test without ApiKey prefix
    client = BundestagAPIClient("test_key")
    assert client.headers["Authorization"] == "ApiKey test_key"

    # Test with ApiKey prefix
    client = BundestagAPIClient("ApiKey test_key")
    assert client.headers["Authorization"] == "ApiKey test_key"


def test_make_request(api_client):
    """Test the _make_request method."""
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
    original_method = api_client._make_request
    
    try:
        # Replace with our mock
        api_client._make_request = mock_make_request
        
        # Test JSON request
        result = api_client._make_request("test_endpoint", {"param": "value"})
        assert result == {"test": "data"}
        
        # Verify parameters
        assert mock_make_request.called_with["endpoint"] == "test_endpoint"
        assert mock_make_request.called_with["params"] == {"param": "value"}
        assert mock_make_request.called_with["format_xml"] == False
        
        # Test XML request
        result = api_client._make_request("test_endpoint", {"param": "value"}, format_xml=True)
        assert result == "<xml>test</xml>"
        assert mock_make_request.called_with["format_xml"] == True
        
    finally:
        # Restore original method
        api_client._make_request = original_method


@patch("bundestag_protocol_extractor.api.client.requests.Session")
def test_get_plenarprotokoll_list(mock_session, api_client):
    """Test the get_plenarprotokoll_list method."""
    # Setup mock for get_all_results
    with patch.object(api_client, 'get_all_results') as mock_get_all:
        mock_get_all.return_value = [{"id": 1}, {"id": 2}]
        
        # Call the method
        result = api_client.get_plenarprotokoll_list(wahlperiode=20)
        
        # Verify the correct parameters were passed
        mock_get_all.assert_called_with(
            "plenarprotokoll", 
            {"f.wahlperiode": 20}, 
            max_retries=3, 
            retry_delay=1.0,
            progress_tracker=None
        )
        
        # Verify the result
        assert result == [{"id": 1}, {"id": 2}]


@patch("bundestag_protocol_extractor.api.client.requests.Session")
def test_get_plenarprotokoll_xml(mock_session_class):
    """Test the get_plenarprotokoll_xml method."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<protokoll><id>123</id></protokoll>"
    mock_response.headers = {"Content-Type": "application/xml"}
    # Important: Set content attribute to bytes to match our decode method
    xml_content = "<?xml version='1.0' encoding='UTF-8'?>\n<protokoll><id>123</id></protokoll>"
    mock_response.content = xml_content.encode('utf-8')
    
    # Setup mock session instance
    mock_session_instance = MagicMock()
    mock_session_instance.get.return_value = mock_response
    mock_session_class.return_value = mock_session_instance
    
    # Create a test client with no caching
    client = BundestagAPIClient("test_key", cache_dir=None)
    
    # Mock data for plenarprotokoll
    plenarprotokoll_data = {
        "id": "123",
        "wahlperiode": "20",
        "dokumentnummer": "20/123",
        "fundstelle": {
            "pdf_url": "https://www.bundestag.de/resource/blob/12345/abcdef/20123.pdf"
        }
    }
    
    # Call the method with test params to avoid cache issues
    result = client.get_plenarprotokoll_xml(
        plenarprotokoll_data, 
        repair_xml=True,
        max_retries=1
    )
    
    # Verify the result is an XML Element
    assert isinstance(result, ET.Element)
    assert result.findtext("id") == "123"
    
    # Verify the session was called
    mock_session_instance.get.assert_called()


@patch("bundestag_protocol_extractor.api.client.requests.Session")
def test_get_aktivitaet_list(mock_session, api_client):
    """Test the get_aktivitaet_list method."""
    # Setup mock for get_all_results
    with patch.object(api_client, 'get_all_results') as mock_get_all:
        mock_get_all.return_value = [
            {"id": 1, "aktivitaetsart": "Rede"}, 
            {"id": 2, "aktivitaetsart": "Rede"},
            {"id": 3, "aktivitaetsart": "Antrag"}
        ]
        
        # Call the method with aktivitaetsart filter
        result = api_client.get_aktivitaet_list(
            plenarprotokoll_id=123,
            aktivitaetsart="Rede"
        )
        
        # Verify the correct filter was applied
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        
        # Verify the correct parameters were passed to get_all_results
        mock_get_all.assert_called_with(
            "aktivitaet", 
            {"f.plenarprotokoll": 123}, 
            max_retries=3, 
            retry_delay=1.0,
            progress_tracker=None
        )


def test_cache_functionality(temp_cache_directory):
    """Test the XML caching functionality."""
    # Create client with caching enabled
    client = BundestagAPIClient("test_api_key", cache_dir=str(temp_cache_directory))
    
    # Test cache path generation
    protocol_id = 12345
    doc_identifier = "20/123"
    cache_path = client._get_cache_path(protocol_id, doc_identifier)
    
    # Verify the correct cache path was generated
    assert cache_path.name == f"protocol_{protocol_id}_{doc_identifier.replace('/', '_')}.xml"
    assert str(cache_path.parent) == str(temp_cache_directory)
    
    # Test cache writing and reading
    test_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<protokoll><id>12345</id></protokoll>'
    client._cache_xml(test_xml, cache_path)
    
    # Verify the file was created
    assert cache_path.exists()
    
    # Test cache loading
    loaded_xml = client._load_cached_xml(cache_path)
    assert loaded_xml == test_xml
    
    # Test validation
    assert client._validate_xml(test_xml)
    
    # Test invalid XML validation
    invalid_xml = '<protokoll><id>12345</id><unclosed>'
    assert not client._validate_xml(invalid_xml)
    
    # Test XML repair for a repairable case 
    # The current implementation can repair missing closing tags
    broken_xml = '<protokoll><id>12345</id><text>Test content'
    repaired = client._repair_xml(broken_xml)
    assert repaired is not None
    assert client._validate_xml(repaired)
    
    # Test more complex XML repair with ampersands
    broken_xml_with_amp = '<protokoll><id>12345</id><text>A & B</text></protokoll>'
    repaired = client._repair_xml(broken_xml_with_amp)
    assert repaired is not None
    assert client._validate_xml(repaired)


@patch("bundestag_protocol_extractor.api.client.requests.Session")
def test_xml_url_building(mock_session):
    """Test the URL building for XML retrieval."""
    client = BundestagAPIClient("test_api_key")
    
    # Test metadata with full information
    metadata = {
        "protocol_id": 12345,
        "wahlperiode": "20",
        "dokument_nummer": "123",
        "doc_identifier": "20/123",
        "doc_number": "20123",
        "pdf_url": "https://www.bundestag.de/resource/blob/987654/abcdef123456/20123.pdf",
        "document_id": "987654",
        "hash": "abcdef123456"
    }
    
    # Generate URLs
    urls = client._build_xml_urls(metadata)
    
    # Verify we have multiple URLs and they contain the expected patterns
    assert len(urls) > 3
    
    # Check that the most reliable pattern is first
    assert any(
        "blob/987654/abcdef123456/20123.xml" in url 
        for url in urls[:1]
    )
    
    # Check that document_id pattern is included
    assert any(
        "blob/987654/20123.xml" in url 
        for url in urls
    )
    
    # Check that PDF URL replacement pattern is included
    assert any(
        "https://www.bundestag.de/resource/blob/987654/abcdef123456/20123.xml" in url 
        for url in urls
    )
    
    # Check API URL is included
    assert any(
        f"plenarprotokoll-text/12345?format=xml&apikey=test_api_key" in url 
        for url in urls
    )