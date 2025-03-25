"""
Pandas helper utilities for data science workflows.

This module provides tools for working with Bundestag protocol data
in pandas DataFrames, making it easier to filter, analyze, and
visualize the extracted data.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import numpy as np
from pandas import DataFrame

from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class BundestagDataFrames:
    """Helper class for working with Bundestag data in pandas."""
    
    def __init__(self, data_dir: Union[str, Path] = "output"):
        """
        Initialize the pandas helper.
        
        Args:
            data_dir: Directory containing the CSV data files
        """
        self.data_dir = Path(data_dir)
        self.dataframes = {}
        
    def load_csv_data(self, base_filename: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Load all related CSV files into pandas DataFrames.
        
        Args:
            base_filename: Base filename for the CSV files (without _entity.csv)
            
        Returns:
            Dictionary of DataFrames by entity type
        """
        # Find CSV files that match the pattern
        if base_filename:
            csv_files = list(self.data_dir.glob(f"{base_filename}_*.csv"))
        else:
            # Try to find the most recent set of files
            all_csv_files = list(self.data_dir.glob("*.csv"))
            
            # Group by base filename
            file_groups = {}
            for file_path in all_csv_files:
                name_parts = file_path.stem.split('_')
                if len(name_parts) >= 2:
                    base = '_'.join(name_parts[:-1])  # All parts except the last
                    if base not in file_groups:
                        file_groups[base] = []
                    file_groups[base].append(file_path)
            
            # Select the group with the most files
            if file_groups:
                best_base = max(file_groups.items(), key=lambda x: len(x[1]))[0]
                csv_files = file_groups[best_base]
                logger.info(f"Automatically selected base filename: {best_base}")
            else:
                csv_files = []
        
        if not csv_files:
            logger.warning(f"No CSV files found in {self.data_dir} with base filename {base_filename}")
            return {}
        
        # Load each CSV file
        for file_path in csv_files:
            entity_type = file_path.stem.split('_')[-1]  # Last part after the last underscore
            
            try:
                df = pd.read_csv(file_path)
                self.dataframes[entity_type] = df
                logger.debug(f"Loaded {len(df)} rows from {file_path}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        logger.info(f"Loaded {len(self.dataframes)} dataframes: {', '.join(self.dataframes.keys())}")
        return self.dataframes
    
    def get_dataframe(self, entity_type: str) -> Optional[pd.DataFrame]:
        """
        Get a specific DataFrame by entity type.
        
        Args:
            entity_type: Entity type (e.g., "speeches", "protocols")
            
        Returns:
            DataFrame or None if not found
        """
        return self.dataframes.get(entity_type)
    
    def create_integrated_speeches_df(self) -> Optional[pd.DataFrame]:
        """
        Create an integrated DataFrame with speeches and related entities.
        
        Returns:
            Integrated DataFrame or None if required dataframes not loaded
        """
        # Check if we have the required dataframes
        required = ["speeches", "protocols", "persons"]
        if not all(r in self.dataframes for r in required):
            missing = [r for r in required if r not in self.dataframes]
            logger.warning(f"Missing required dataframes: {', '.join(missing)}")
            return None
        
        # Start with the speeches dataframe
        df_speeches = self.dataframes["speeches"].copy()
        df_protocols = self.dataframes["protocols"].copy()
        df_persons = self.dataframes["persons"].copy()
        
        # Rename person columns to avoid conflicts
        person_columns = {
            "id": "person_id",
            "first_name": "person_first_name",
            "last_name": "person_last_name",
            "title": "person_title",
            "party": "person_party",
            "role": "person_role",
            "function": "person_function",
            "ministry": "person_ministry",
            "state": "person_state"
        }
        df_persons = df_persons.rename(columns=person_columns)
        
        # Rename protocol columns to avoid conflicts
        protocol_columns = {
            "id": "protocol_id_full",
            "dokumentnummer": "protocol_dokumentnummer",
            "wahlperiode": "protocol_wahlperiode",
            "date": "protocol_date",
            "title": "protocol_title"
        }
        df_protocols = df_protocols[["id", "dokumentnummer", "wahlperiode", "date", "title"]].rename(columns=protocol_columns)
        
        # Merge speeches with persons
        df_integrated = pd.merge(
            df_speeches,
            df_persons,
            left_on="speaker_id",
            right_on="person_id",
            how="left"
        )
        
        # Merge with protocols
        df_integrated = pd.merge(
            df_integrated,
            df_protocols,
            left_on="protocol_id",
            right_on="protocol_id_full",
            how="left"
        )
        
        # Add topic data if available
        if "speech_topics" in self.dataframes:
            # We'll use a different approach for topics since it's a many-to-many relationship
            # First, create a dictionary mapping speech_id to list of topics
            speech_topics = {}
            df_topics = self.dataframes["speech_topics"]
            
            for _, row in df_topics.iterrows():
                speech_id = row["speech_id"]
                topic = row["topic"]
                
                if speech_id not in speech_topics:
                    speech_topics[speech_id] = []
                    
                speech_topics[speech_id].append(topic)
            
            # Then, create a new column with the list of topics
            df_integrated["topics_list"] = df_integrated["id"].map(
                lambda x: speech_topics.get(x, [])
            )
            
            # Add a column with the number of topics
            df_integrated["topic_count"] = df_integrated["topics_list"].apply(len)
        
        # Add paragraphs if available
        if "paragraphs" in self.dataframes:
            # Create a dictionary mapping speech_id to paragraph count
            speech_paragraphs = {}
            df_paragraphs = self.dataframes["paragraphs"]
            
            # Group by speech_id and count paragraphs
            paragraph_counts = df_paragraphs.groupby("speech_id").size()
            
            # Add paragraph count column
            df_integrated["paragraph_count"] = df_integrated["id"].map(
                lambda x: paragraph_counts.get(x, 0)
            )
        
        # Add comments if available
        if "comments" in self.dataframes:
            # Create a dictionary mapping speech_id to comment count
            speech_comments = {}
            df_comments = self.dataframes["comments"]
            
            # Group by speech_id and count comments
            comment_counts = df_comments.groupby("speech_id").size()
            
            # Add comment count column
            df_integrated["comment_count"] = df_integrated["id"].map(
                lambda x: comment_counts.get(x, 0)
            )
        
        # Add text analysis columns
        if "text" in df_integrated.columns:
            # Text length
            df_integrated["text_length"] = df_integrated["text"].str.len()
            
            # Word count (naive implementation, could be improved)
            df_integrated["word_count"] = df_integrated["text"].str.split().str.len()
            
            # Flag for failed extraction indicators
            df_integrated["has_extraction_error"] = df_integrated["text"].str.contains(
                "EXTRACTION_FAILED", case=True, na=False
            )
        
        logger.info(f"Created integrated DataFrame with {len(df_integrated)} rows")
        return df_integrated
    
    def filter_high_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter for high-quality speech data (XML extracted, complete).
        
        Args:
            df: DataFrame to filter
            
        Returns:
            Filtered DataFrame
        """
        return df[df["is_xml_extracted"] & df["is_complete"]]
    
    def filter_by_confidence(self, df: pd.DataFrame, min_confidence: float = 0.5) -> pd.DataFrame:
        """
        Filter by minimum confidence score.
        
        Args:
            df: DataFrame to filter
            min_confidence: Minimum confidence score
            
        Returns:
            Filtered DataFrame
        """
        return df[df["extraction_confidence"] >= min_confidence]
    
    def create_multi_index_df(self) -> Optional[pd.DataFrame]:
        """
        Create a multi-index DataFrame for hierarchical analysis.
        
        Returns:
            Multi-index DataFrame or None if required dataframes not loaded
        """
        # Check if we have the integrated dataframe
        integrated_df = self.create_integrated_speeches_df()
        if integrated_df is None:
            return None
        
        # Create a multi-index DataFrame
        # First level: protocol_id
        # Second level: speech_id
        df_multi = integrated_df.copy()
        
        # Set the multi-index
        df_multi = df_multi.set_index(["protocol_id", "id"])
        
        # Sort by protocol date and speech order
        if "protocol_date" in df_multi.columns:
            df_multi = df_multi.sort_index(level=0)
        
        return df_multi
    
    def get_quality_stats(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Get quality statistics for speeches.
        
        Args:
            df: DataFrame to analyze (uses speeches dataframe if None)
            
        Returns:
            Dictionary with quality statistics
        """
        if df is None:
            df = self.dataframes.get("speeches")
            
        if df is None:
            logger.warning("No speeches dataframe available")
            return {}
        
        total = len(df)
        
        if total == 0:
            return {"total": 0, "error": "No speech data"}
        
        # Calculate quality metrics
        xml_count = df[df["extraction_method"] == "xml"].shape[0]
        pattern_count = df[df["extraction_method"] == "pattern"].shape[0]
        page_count = df[df["extraction_method"] == "page"].shape[0]
        none_count = df[df["extraction_method"] == "none"].shape[0]
        
        complete_count = df[df["extraction_status"] == "complete"].shape[0]
        partial_count = df[df["extraction_status"] == "partial"].shape[0]
        failed_count = df[df["extraction_status"] == "failed"].shape[0]
        
        high_confidence = df[df["extraction_confidence"] >= 0.8].shape[0]
        medium_confidence = df[(df["extraction_confidence"] >= 0.5) & (df["extraction_confidence"] < 0.8)].shape[0]
        low_confidence = df[(df["extraction_confidence"] >= 0.2) & (df["extraction_confidence"] < 0.5)].shape[0]
        very_low_confidence = df[df["extraction_confidence"] < 0.2].shape[0]
        
        stats = {
            "total": total,
            "methods": {
                "xml": {"count": xml_count, "percentage": (xml_count / total) * 100},
                "pattern": {"count": pattern_count, "percentage": (pattern_count / total) * 100},
                "page": {"count": page_count, "percentage": (page_count / total) * 100},
                "none": {"count": none_count, "percentage": (none_count / total) * 100}
            },
            "status": {
                "complete": {"count": complete_count, "percentage": (complete_count / total) * 100},
                "partial": {"count": partial_count, "percentage": (partial_count / total) * 100},
                "failed": {"count": failed_count, "percentage": (failed_count / total) * 100}
            },
            "confidence": {
                "high": {"count": high_confidence, "percentage": (high_confidence / total) * 100},
                "medium": {"count": medium_confidence, "percentage": (medium_confidence / total) * 100},
                "low": {"count": low_confidence, "percentage": (low_confidence / total) * 100},
                "very_low": {"count": very_low_confidence, "percentage": (very_low_confidence / total) * 100},
                "avg": df["extraction_confidence"].mean(),
                "median": df["extraction_confidence"].median()
            }
        }
        
        return stats
    
    def get_party_stats(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Get party statistics for speeches.
        
        Args:
            df: DataFrame to analyze (uses integrated dataframe if None)
            
        Returns:
            Dictionary with party statistics
        """
        if df is None:
            df = self.create_integrated_speeches_df()
            
        if df is None or df.empty:
            logger.warning("No suitable dataframe available")
            return {}
        
        if "person_party" not in df.columns and "speaker_party" not in df.columns:
            logger.warning("No party column found in dataframe")
            return {}
        
        # Use appropriate party column
        party_col = "person_party" if "person_party" in df.columns else "speaker_party"
        
        # Count speeches by party
        party_counts = df[party_col].value_counts().to_dict()
        
        # Calculate percentages
        total = sum(party_counts.values())
        party_percentages = {party: (count / total) * 100 for party, count in party_counts.items()}
        
        # Calculate average text length by party if text_length is available
        party_text_lengths = {}
        if "text_length" in df.columns:
            for party in party_counts.keys():
                party_df = df[df[party_col] == party]
                party_text_lengths[party] = {
                    "avg_length": float(party_df["text_length"].mean()),
                    "median_length": float(party_df["text_length"].median()),
                    "total_length": int(party_df["text_length"].sum())
                }
        
        # Calculate extraction method distribution by party
        party_methods = {}
        for party in party_counts.keys():
            party_df = df[df[party_col] == party]
            methods = party_df["extraction_method"].value_counts().to_dict()
            
            # Calculate percentages
            party_total = sum(methods.values())
            method_percentages = {method: (count / party_total) * 100 for method, count in methods.items()}
            
            party_methods[party] = {
                "counts": methods,
                "percentages": method_percentages
            }
        
        stats = {
            "total_speeches": total,
            "party_counts": party_counts,
            "party_percentages": party_percentages,
            "party_text_lengths": party_text_lengths,
            "party_methods": party_methods
        }
        
        return stats
    
    def get_speech_length_bins(
        self,
        df: Optional[pd.DataFrame] = None,
        bin_size: int = 500,
        max_length: int = 10000
    ) -> pd.DataFrame:
        """
        Create bins of speech lengths for analysis.
        
        Args:
            df: DataFrame to analyze (uses integrated dataframe if None)
            bin_size: Size of each bin in characters
            max_length: Maximum length to consider
            
        Returns:
            DataFrame with binned speech lengths
        """
        if df is None:
            df = self.create_integrated_speeches_df()
            
        if df is None or df.empty:
            logger.warning("No suitable dataframe available")
            return pd.DataFrame()
        
        if "text_length" not in df.columns and "text" in df.columns:
            df = df.copy()
            df["text_length"] = df["text"].str.len()
            
        if "text_length" not in df.columns:
            logger.warning("No text_length column found in dataframe")
            return pd.DataFrame()
        
        # Create bins
        bins = list(range(0, max_length + bin_size, bin_size))
        labels = [f"{i}-{i+bin_size-1}" for i in range(0, max_length, bin_size)]
        
        # Add a bin for speeches longer than max_length
        bins.append(float('inf'))
        labels.append(f"{max_length}+")
        
        # Create a new column with binned lengths
        df_copy = df.copy()
        df_copy["length_bin"] = pd.cut(df_copy["text_length"], bins=bins, labels=labels, right=False)
        
        # Count speeches in each bin by extraction method
        # Include observed=True to address FutureWarning
        bin_counts = df_copy.groupby(["length_bin", "extraction_method"], observed=True).size().unstack(fill_value=0)
        
        # Add total column
        bin_counts["total"] = bin_counts.sum(axis=1)
        
        # Calculate percentages
        bin_percentages = bin_counts.div(bin_counts["total"], axis=0) * 100
        bin_percentages = bin_percentages.drop(columns=["total"])
        
        # Rename columns for clarity
        bin_percentages = bin_percentages.rename(columns={col: f"{col}_pct" for col in bin_percentages.columns})
        
        # Combine counts and percentages
        result = pd.concat([bin_counts, bin_percentages], axis=1)
        
        return result