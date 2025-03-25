"""Tests for the pandas_helper module."""
import pytest
from pathlib import Path

import pandas as pd
import numpy as np

from bundestag_protocol_extractor.utils.pandas_helper import BundestagDataFrames


def test_load_csv_data(temp_directory, mock_speeches_df, mock_protocols_df, mock_persons_df):
    """Test loading CSV data."""
    # Save test files
    mock_speeches_df.to_csv(temp_directory / "test_speeches.csv", index=False)
    mock_protocols_df.to_csv(temp_directory / "test_protocols.csv", index=False)
    mock_persons_df.to_csv(temp_directory / "test_persons.csv", index=False)
    
    # Create helper
    btdf = BundestagDataFrames(data_dir=temp_directory)
    
    # Test loading with base filename
    dataframes = btdf.load_csv_data(base_filename="test")
    
    assert len(dataframes) == 3
    assert "speeches" in dataframes
    assert "protocols" in dataframes
    assert "persons" in dataframes
    
    # Check dataframe contents
    assert len(dataframes["speeches"]) == 10
    assert len(dataframes["protocols"]) == 3
    assert len(dataframes["persons"]) == 5


def test_get_dataframe(mock_bundestag_dataframes):
    """Test getting a specific dataframe."""
    # Get speeches dataframe
    df_speeches = mock_bundestag_dataframes.get_dataframe("speeches")
    assert df_speeches is not None
    assert len(df_speeches) == 10
    
    # Try getting a non-existent dataframe
    df_nonexistent = mock_bundestag_dataframes.get_dataframe("nonexistent")
    assert df_nonexistent is None


def test_create_integrated_speeches_df(mock_bundestag_dataframes):
    """Test creating an integrated dataframe."""
    # Create integrated dataframe
    df_integrated = mock_bundestag_dataframes.create_integrated_speeches_df()
    
    # Check that it has the expected columns
    assert df_integrated is not None
    assert "person_first_name" in df_integrated.columns
    assert "protocol_date" in df_integrated.columns
    
    # Check that the data was merged correctly
    assert len(df_integrated) == 10


def test_filter_high_quality(mock_bundestag_dataframes):
    """Test filtering for high-quality speeches."""
    # Create integrated dataframe
    df_integrated = mock_bundestag_dataframes.create_integrated_speeches_df()
    
    # Filter for high-quality speeches
    high_quality = mock_bundestag_dataframes.filter_high_quality(df_integrated)
    
    # Check that only high-quality speeches are included
    assert len(high_quality) == 4
    assert all(high_quality["is_xml_extracted"])
    assert all(high_quality["is_complete"])


def test_filter_by_confidence(mock_bundestag_dataframes):
    """Test filtering by confidence score."""
    # Create integrated dataframe
    df_integrated = mock_bundestag_dataframes.create_integrated_speeches_df()
    
    # Filter by confidence score
    medium_confidence = mock_bundestag_dataframes.filter_by_confidence(df_integrated, min_confidence=0.5)
    
    # Check that only speeches with confidence >= 0.5 are included
    assert len(medium_confidence) == 7
    assert all(medium_confidence["extraction_confidence"] >= 0.5)


def test_get_quality_stats(mock_bundestag_dataframes):
    """Test getting quality statistics."""
    # Get quality statistics
    stats = mock_bundestag_dataframes.get_quality_stats(mock_bundestag_dataframes.get_dataframe("speeches"))
    
    # Check the statistics
    assert stats["total"] == 10
    assert stats["methods"]["xml"]["count"] == 4
    assert stats["status"]["complete"]["count"] == 7
    assert 0.67 < stats["confidence"]["avg"] < 0.69


def test_get_party_stats(mock_bundestag_dataframes):
    """Test getting party statistics."""
    # Create integrated dataframe
    df_integrated = mock_bundestag_dataframes.create_integrated_speeches_df()
    
    # Add speaker_party column if not present
    if "speaker_party" not in df_integrated.columns:
        df_integrated["speaker_party"] = ["A", "B", "C", "A", "B", "C", "D", "D", "A", "B"]
    
    # Get party statistics
    stats = mock_bundestag_dataframes.get_party_stats(df_integrated)
    
    # Check the statistics
    assert "party_counts" in stats
    assert "A" in stats["party_counts"]
    assert "B" in stats["party_counts"]


def test_get_speech_length_bins(mock_bundestag_dataframes, mock_speeches_df):
    """Test binning speech lengths."""
    # Add text length column if not present
    if "text_length" not in mock_speeches_df.columns:
        mock_speeches_df["text_length"] = mock_speeches_df["text"].str.len()
    
    # Get speech length bins
    bins = mock_bundestag_dataframes.get_speech_length_bins(mock_speeches_df, bin_size=100, max_length=500)
    
    # Check the binned data
    assert bins is not None
    assert len(bins) > 0
    assert "total" in bins.columns
    
    # Check that the bins contain appropriate data
    assert bins["total"].sum() > 0