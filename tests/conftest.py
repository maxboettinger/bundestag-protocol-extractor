"""
Pytest configuration for the bundestag-protocol-extractor package.

This module provides fixtures and configuration for pytest tests.
"""
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd
from matplotlib.figure import Figure
import requests
import xml.etree.ElementTree as ET

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.models.schema import PlenarProtocol, Speech, Person
from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.parsers.extraction_strategies import (
    XMLExtractionStrategy, PatternExtractionStrategy, PageExtractionStrategy, 
    ExtractionStrategyFactory
)
from bundestag_protocol_extractor.utils.data_quality import DataQualityReporter
from bundestag_protocol_extractor.utils.pandas_helper import BundestagDataFrames
from bundestag_protocol_extractor import BundestagExtractor


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        yield temp_path


@pytest.fixture
def mock_api_client(monkeypatch):
    """Create a mock API client."""
    # Create a minimal API client with monkey-patched methods
    api_client = BundestagAPIClient("test_api_key")
    
    # Mock the API methods to avoid real API calls
    monkeypatch.setattr(api_client, "_make_request", lambda *args, **kwargs: {"test": "data"})
    monkeypatch.setattr(api_client, "get_plenarprotokoll", lambda *args, **kwargs: {
        "id": "123",
        "wahlperiode": "20",
        "dokumentnummer": "20/123",
        "datum": "2023-01-01",
        "titel": "Test Protocol",
        "herausgeber": "Deutscher Bundestag",
        "fundstelle": {"pdf_url": "https://example.com/test.pdf"}
    })
    
    return api_client


@pytest.fixture
def mock_protocol_parser(mock_api_client):
    """Create a mock protocol parser."""
    return ProtocolParser(mock_api_client)


@pytest.fixture
def sample_protocols():
    """Create a sample list of protocols for testing."""
    # Create a person
    person = Person(
        id=100,
        nachname="Test",
        vorname="User",
        titel="Dr.",
        fraktion="TEST"
    )
    
    # Create speeches
    speeches = [
        Speech(
            id=1,
            speaker=person,
            title="Test Speech",
            text="This is a test speech.",
            date="2023-01-01",
            protocol_id=123,
            protocol_number="20/123",
            page_start="1",
            extraction_method="xml",
            extraction_status="complete",
            extraction_confidence=1.0
        ),
        Speech(
            id=2,
            speaker=person,
            title="Another Speech",
            text="This is another test speech.",
            date="2023-01-01",
            protocol_id=123,
            protocol_number="20/123",
            page_start="2",
            extraction_method="pattern",
            extraction_status="complete",
            extraction_confidence=0.7
        )
    ]
    
    # Create a protocol
    protocol = PlenarProtocol(
        id=123,
        dokumentnummer="20/123",
        wahlperiode=20,
        date="2023-01-01",
        title="Test Protocol",
        herausgeber="Deutscher Bundestag",
        full_text="This is the full protocol text.",
        speeches=speeches,
        pdf_url="https://example.com/test.pdf"
    )
    
    return [protocol]


@pytest.fixture
def mock_speeches_df():
    """Create a mock speeches DataFrame."""
    return pd.DataFrame({
        "id": range(10),
        "speaker_id": [100, 101, 102, 100, 101, 102, 103, 103, 104, 104],
        "protocol_id": [1, 1, 1, 2, 2, 2, 3, 3, 3, 3],
        "protocol_number": ["20/1", "20/1", "20/1", "20/2", "20/2", "20/2", "20/3", "20/3", "20/3", "20/3"],
        "extraction_method": ["xml", "xml", "pattern", "pattern", "page", "xml", "none", "xml", "pattern", "page"],
        "extraction_status": ["complete", "complete", "complete", "partial", "complete", "complete", "failed", "complete", "partial", "complete"],
        "extraction_confidence": [1.0, 1.0, 0.7, 0.6, 0.4, 1.0, 0.0, 1.0, 0.7, 0.4],
        "text": ["Test " * 100, "Test " * 200, "Test " * 50, "Test " * 40, "Test " * 30, 
                 "Test " * 150, "", "Test " * 120, "Test " * 60, "Test " * 35],
        "speaker_party": ["A", "B", "C", "A", "B", "C", "D", "D", "A", "B"],
        "is_xml_extracted": [True, True, False, False, False, True, False, True, False, False],
        "is_complete": [True, True, True, False, True, True, False, True, False, True],
        "is_high_confidence": [True, True, False, False, False, True, False, True, False, False]
    })


@pytest.fixture
def mock_protocols_df():
    """Create a mock protocols DataFrame."""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "dokumentnummer": ["20/1", "20/2", "20/3"],
        "wahlperiode": [20, 20, 20],
        "date": ["2022-01-01", "2022-01-15", "2022-02-01"],
        "title": ["Session 1", "Session 2", "Session 3"]
    })


@pytest.fixture
def mock_persons_df():
    """Create a mock persons DataFrame."""
    return pd.DataFrame({
        "id": [100, 101, 102, 103, 104],
        "first_name": ["Alice", "Bob", "Charlie", "David", "Eva"],
        "last_name": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "title": ["Dr.", "", "Prof.", "", "Dr."],
        "party": ["A", "B", "C", "D", "A"]
    })


@pytest.fixture
def mock_bundestag_dataframes(temp_directory, mock_speeches_df, mock_protocols_df, mock_persons_df):
    """Create a mock BundestagDataFrames with pre-loaded data."""
    # Save test files in the temp directory
    mock_speeches_df.to_csv(temp_directory / "test_speeches.csv", index=False)
    mock_protocols_df.to_csv(temp_directory / "test_protocols.csv", index=False)
    mock_persons_df.to_csv(temp_directory / "test_persons.csv", index=False)
    
    # Create the helper and load the data
    btdf = BundestagDataFrames(data_dir=temp_directory)
    btdf.dataframes = {
        "speeches": mock_speeches_df,
        "protocols": mock_protocols_df,
        "persons": mock_persons_df
    }
    
    return btdf


@pytest.fixture
def mock_quality_report() -> Dict[str, Any]:
    """Create a mock quality report for testing."""
    return {
        "generated_at": "2023-01-01T12:00:00",
        "total_speeches": 10,
        "extraction_methods": {
            "counts": {"xml": 4, "pattern": 3, "page": 2, "none": 1},
            "percentages": {"xml": 40.0, "pattern": 30.0, "page": 20.0, "none": 10.0}
        },
        "extraction_status": {
            "counts": {"complete": 7, "partial": 2, "failed": 1},
            "percentages": {"complete": 70.0, "partial": 20.0, "failed": 10.0}
        },
        "confidence_metrics": {
            "average": 0.68,
            "median": 0.7,
            "min": 0.0,
            "max": 1.0,
            "distribution": {
                "high_confidence": 4,
                "high_confidence_percentage": 40.0,
                "medium_confidence": 3,
                "medium_confidence_percentage": 30.0,
                "low_confidence": 2,
                "low_confidence_percentage": 20.0,
                "very_low_confidence": 1,
                "very_low_confidence_percentage": 10.0
            }
        },
        "text_metrics": {
            "average_length": 500,
            "median_length": 400,
            "min_length": 0,
            "max_length": 1000,
            "truncated_count": 1,
            "truncated_percentage": 10.0,
            "length_by_method": {
                "xml": {"average": 600, "median": 550, "min": 300, "max": 800},
                "pattern": {"average": 400, "median": 350, "min": 200, "max": 600},
                "page": {"average": 300, "median": 250, "min": 150, "max": 400}
            }
        }
    }


@pytest.fixture
def mock_visualizations(temp_directory) -> Dict[str, Path]:
    """Create mock visualization paths for testing."""
    # Create directories for visualizations
    figures_dir = temp_directory / "figures"
    figures_dir.mkdir(exist_ok=True)
    
    # Create empty files for each visualization
    method_path = figures_dir / "test_extraction_methods.png"
    status_path = figures_dir / "test_extraction_status.png"
    confidence_path = figures_dir / "test_confidence_distribution.png"
    dashboard_path = figures_dir / "test_quality_dashboard.png"
    
    # Create empty files
    for path in [method_path, status_path, confidence_path, dashboard_path]:
        with open(path, "wb") as f:
            f.write(b"")
    
    # Return paths dictionary
    return {
        "method_distribution": method_path,
        "status_distribution": status_path,
        "confidence_distribution": confidence_path,
        "dashboard": dashboard_path
    }


@pytest.fixture
def mock_quality_reporter(temp_directory, monkeypatch):
    """Create a mock DataQualityReporter with mocked visualization methods."""
    reporter = DataQualityReporter(output_dir=temp_directory)
    
    # Create a mock Figure to return
    def mock_generate_visualizations(*args, **kwargs):
        if kwargs.get("save_plots", False):
            # Create a figures directory
            figures_dir = temp_directory / "figures"
            figures_dir.mkdir(exist_ok=True)
            
            # Create empty visualization files
            visualizations = {
                "method_distribution": figures_dir / f"{kwargs.get('base_filename', 'test')}_extraction_methods.png",
                "status_distribution": figures_dir / f"{kwargs.get('base_filename', 'test')}_extraction_status.png",
                "confidence_distribution": figures_dir / f"{kwargs.get('base_filename', 'test')}_confidence_distribution.png",
                "dashboard": figures_dir / f"{kwargs.get('base_filename', 'test')}_quality_dashboard.png"
            }
            
            # Create empty files
            for path in visualizations.values():
                with open(path, "wb") as f:
                    f.write(b"")
                    
            return visualizations
        else:
            # Create Figure objects
            import matplotlib.pyplot as plt
            fig1, _ = plt.subplots()
            fig2, _ = plt.subplots()
            fig3, _ = plt.subplots()
            fig4, _ = plt.subplots()
            
            return {
                "method_distribution": fig1,
                "status_distribution": fig2,
                "confidence_distribution": fig3,
                "dashboard": fig4
            }
    
    # Patch the visualization method
    monkeypatch.setattr(reporter, "generate_quality_visualizations", mock_generate_visualizations)
    
    return reporter


@pytest.fixture
def mock_session():
    """Create a mock requests.Session for API testing."""
    mock_session = MagicMock(spec=requests.Session)
    return mock_session


@pytest.fixture
def mock_extractor(temp_directory, monkeypatch):
    """Create a mock BundestagExtractor for testing."""
    # Create a test extractor with mocked dependencies
    with patch('bundestag_protocol_extractor.extractor.BundestagAPIClient'), \
         patch('bundestag_protocol_extractor.extractor.ProtocolParser'), \
         patch('bundestag_protocol_extractor.extractor.Exporter'), \
         patch('bundestag_protocol_extractor.extractor.ProgressTracker'):
        
        extractor = BundestagExtractor(
            api_key="test_api_key",
            output_dir=str(temp_directory),
            enable_xml_cache=True,
            cache_dir=str(temp_directory / "cache"),
            repair_xml=True
        )
        
        return extractor


@pytest.fixture
def temp_cache_directory(temp_directory):
    """Create a temporary cache directory for API client testing."""
    cache_dir = temp_directory / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir