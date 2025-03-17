"""
Exporter module for saving extracted data to various formats.

This module provides functionality for exporting extracted Bundestag protocol data
to various formats including CSV, JSON, and text files.
"""
import csv
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import pandas as pd

from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class DataEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling date and datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class Exporter:
    """
    Exporter for saving extracted data to various formats.
    Supports CSV, JSON, and other formats.
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize the exporter.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _convert_speech_to_dict(self, speech: Speech) -> Dict[str, Any]:
        """
        Convert a Speech object to a dictionary.
        
        Args:
            speech: Speech object
            
        Returns:
            Dictionary representation
        """
        # Convert the speech object to a dictionary
        speech_dict = {
            "id": speech.id,
            "title": speech.title,
            "text": speech.text,
            "date": speech.date,
            "protocol_id": speech.protocol_id,
            "protocol_number": speech.protocol_number,
            "page_start": speech.page_start,
            "page_end": speech.page_end,
            "topics": ",".join(speech.topics),
            "speaker_id": speech.speaker.id,
            "speaker_first_name": speech.speaker.vorname,
            "speaker_last_name": speech.speaker.nachname,
            "speaker_title": speech.speaker.titel,
            "speaker_party": speech.speaker.fraktion,
            "speaker_role": speech.speaker.rolle,
            "speaker_function": speech.speaker.funktion,
            "speaker_ministry": speech.speaker.ressort,
            "speaker_state": speech.speaker.bundesland
        }
        
        return speech_dict
    
    def _convert_protocol_to_dict(self, protocol: PlenarProtocol) -> Dict[str, Any]:
        """
        Convert a PlenarProtocol object to a dictionary.
        
        Args:
            protocol: PlenarProtocol object
            
        Returns:
            Dictionary representation
        """
        # Convert the protocol object to a dictionary
        protocol_dict = {
            "id": protocol.id,
            "dokumentnummer": protocol.dokumentnummer,
            "wahlperiode": protocol.wahlperiode,
            "date": protocol.date,
            "title": protocol.title,
            "herausgeber": protocol.herausgeber,
            "pdf_url": protocol.pdf_url,
            "updated_at": protocol.updated_at,
            "speech_count": len(protocol.speeches),
            "proceeding_count": len(protocol.proceedings),
            "full_text": protocol.full_text
        }
        
        return protocol_dict
    
    def _convert_person_to_dict(self, person: Person) -> Dict[str, Any]:
        """
        Convert a Person object to a dictionary.
        
        Args:
            person: Person object
            
        Returns:
            Dictionary representation
        """
        # Convert the person object to a dictionary
        person_dict = {
            "id": person.id,
            "first_name": person.vorname,
            "last_name": person.nachname,
            "name_suffix": person.namenszusatz,
            "title": person.titel,
            "party": person.fraktion,
            "role": person.rolle,
            "function": person.funktion,
            "ministry": person.ressort,
            "state": person.bundesland
        }
        
        return person_dict
    
    def export_to_csv(
        self, 
        protocols: List[PlenarProtocol], 
        base_filename: Optional[str] = None,
        include_speech_text: bool = True, 
        include_full_protocols: bool = False,
        include_paragraphs: bool = True, 
        include_comments: bool = True
    ) -> Dict[str, Path]:
        """
        Export the data to CSV files (multiple files for different entities).
        
        Args:
            protocols: List of PlenarProtocol objects
            base_filename: Optional base filename (default: will use wahlperiode)
            include_speech_text: Whether to include full speech text in CSV (can make files large)
            include_full_protocols: Whether to include full protocol text in CSV (can make files very large)
            include_paragraphs: Whether to export individual paragraphs for detailed analysis
            include_comments: Whether to export comments as separate entities
            
        Returns:
            Dictionary mapping file types to saved file paths
        """
        if not protocols:
            logger.warning("No protocols to export")
            return {}
            
        # Determine base filename
        if not base_filename:
            if protocols:
                wahlperiode = protocols[0].wahlperiode
                base_filename = f"bundestag_wp{wahlperiode}"
            else:
                base_filename = "bundestag_protocols"
        
        logger.info(f"Exporting {len(protocols)} protocols to CSV with base filename '{base_filename}'")
        logger.info(f"Export options: include_speech_text={include_speech_text}, "
                   f"include_full_protocols={include_full_protocols}, "
                   f"include_paragraphs={include_paragraphs}, "
                   f"include_comments={include_comments}")
        
        # Create dataframes for each entity type
        protocols_data = []
        speeches_data = []
        persons_data = {}  # Use dict to avoid duplicates
        proceedings_data = []  # New table for proceedings
        speech_topics_data = []  # New table for speech topics (many-to-many)
        
        # New tables for XML-specific data
        paragraphs_data = []  # Table for individual paragraphs within speeches
        comments_data = []  # Table for comments
        agenda_items_data = []  # Table for agenda items
        toc_data = []  # Table for table of contents entries
        
        # Extract data from protocols
        logger.debug("Preparing data for export")
        speech_count = 0
        paragraph_count = 0
        comment_count = 0
        
        for protocol in protocols:
            # Add protocol data
            protocol_dict = self._convert_protocol_to_dict(protocol)
            
            # Optionally exclude full text to reduce file size
            if not include_full_protocols:
                protocol_dict.pop("full_text", None)
                
            protocols_data.append(protocol_dict)
            
            # Add table of contents data
            for toc_block in getattr(protocol, 'toc', []):
                block_title = toc_block.get('title', '')
                
                for entry in toc_block.get('entries', []):
                    toc_data.append({
                        'protocol_id': protocol.id,
                        'block_title': block_title,
                        'content': entry.get('content', ''),
                        'page': entry.get('page', '')
                    })
            
            # Add agenda items data
            for item in getattr(protocol, 'agenda_items', []):
                agenda_items_data.append({
                    'protocol_id': protocol.id,
                    'item_id': item.get('id', ''),
                    'text': item.get('text', '')
                })
            
            # Add proceedings data (with foreign key to protocol)
            for proceeding in protocol.proceedings:
                if proceeding and "id" in proceeding and "titel" in proceeding:
                    proceedings_data.append({
                        "id": proceeding["id"],
                        "titel": proceeding["titel"],
                        "vorgangstyp": proceeding.get("vorgangstyp", ""),
                        "protocol_id": protocol.id
                    })
            
            # Add speech data
            for speech in protocol.speeches:
                speech_count += 1
                # Create speech dictionary
                speech_dict = self._convert_speech_to_dict(speech)
                
                # Add additional metadata
                speech_dict["is_president"] = getattr(speech, "is_president", False)
                speech_dict["page_section"] = getattr(speech, "page_section", "")
                
                # Optionally exclude full text to reduce file size
                if not include_speech_text:
                    speech_dict["text"] = f"Speech text excluded (length: {len(speech.text)} chars)"
                
                speeches_data.append(speech_dict)
                
                # Add paragraph data for detailed analysis
                if include_paragraphs:
                    speech_paragraphs = getattr(speech, "paragraphs", [])
                    paragraph_count += len(speech_paragraphs)
                    
                    for i, para in enumerate(speech_paragraphs):
                        paragraphs_data.append({
                            "speech_id": speech.id,
                            "protocol_id": protocol.id,
                            "paragraph_number": i + 1,
                            "text": para.get("text", ""),
                            "type": para.get("type", "")
                        })
                
                # Add comments data
                if include_comments:
                    speech_comments = getattr(speech, "comments", [])
                    comment_count += len(speech_comments)
                    
                    for i, comment in enumerate(speech_comments):
                        comments_data.append({
                            "speech_id": speech.id,
                            "protocol_id": protocol.id,
                            "comment_number": i + 1,
                            "text": comment
                        })
                
                # Add topic data (many-to-many relationship)
                for topic in speech.topics:
                    speech_topics_data.append({
                        "speech_id": speech.id,
                        "topic": topic,
                        "protocol_id": protocol.id
                    })
                
                # Add person data (avoid duplicates)
                person = speech.speaker
                if person.id not in persons_data:
                    persons_data[person.id] = self._convert_person_to_dict(person)
        
        # Log summary of collected data
        logger.info(f"Collected data: {len(protocols_data)} protocols, {speech_count} speeches, "
                   f"{len(persons_data)} persons, {paragraph_count} paragraphs, {comment_count} comments")
        
        # Convert to dataframes
        logger.debug("Converting to dataframes")
        df_protocols = pd.DataFrame(protocols_data)
        df_speeches = pd.DataFrame(speeches_data)
        df_persons = pd.DataFrame(list(persons_data.values()))
        df_proceedings = pd.DataFrame(proceedings_data)
        df_speech_topics = pd.DataFrame(speech_topics_data)
        
        # XML-specific dataframes
        df_paragraphs = pd.DataFrame(paragraphs_data)
        df_comments = pd.DataFrame(comments_data)
        df_agenda_items = pd.DataFrame(agenda_items_data)
        df_toc = pd.DataFrame(toc_data)
        
        # Dictionary to store file paths
        saved_files = {}
        
        # Save to CSV files
        logger.info("Saving dataframes to CSV files")
        
        # Core files
        protocols_path = self.output_dir / f"{base_filename}_protocols.csv"
        df_protocols.to_csv(protocols_path, index=False)
        saved_files['protocols'] = protocols_path
        logger.debug(f"Saved {len(df_protocols)} protocols to {protocols_path}")
        
        speeches_path = self.output_dir / f"{base_filename}_speeches.csv"
        df_speeches.to_csv(speeches_path, index=False)
        saved_files['speeches'] = speeches_path
        logger.debug(f"Saved {len(df_speeches)} speeches to {speeches_path}")
        
        persons_path = self.output_dir / f"{base_filename}_persons.csv"
        df_persons.to_csv(persons_path, index=False)
        saved_files['persons'] = persons_path
        logger.debug(f"Saved {len(df_persons)} persons to {persons_path}")
        
        proceedings_path = self.output_dir / f"{base_filename}_proceedings.csv"
        df_proceedings.to_csv(proceedings_path, index=False)
        saved_files['proceedings'] = proceedings_path
        logger.debug(f"Saved {len(df_proceedings)} proceedings to {proceedings_path}")
        
        topics_path = self.output_dir / f"{base_filename}_speech_topics.csv"
        df_speech_topics.to_csv(topics_path, index=False)
        saved_files['speech_topics'] = topics_path
        logger.debug(f"Saved {len(df_speech_topics)} speech topics to {topics_path}")
        
        # Save XML-specific data to CSV files
        if include_paragraphs and not df_paragraphs.empty:
            paragraphs_path = self.output_dir / f"{base_filename}_paragraphs.csv"
            df_paragraphs.to_csv(paragraphs_path, index=False)
            saved_files['paragraphs'] = paragraphs_path
            logger.debug(f"Saved {len(df_paragraphs)} paragraphs to {paragraphs_path}")
        
        if include_comments and not df_comments.empty:
            comments_path = self.output_dir / f"{base_filename}_comments.csv"
            df_comments.to_csv(comments_path, index=False)
            saved_files['comments'] = comments_path
            logger.debug(f"Saved {len(df_comments)} comments to {comments_path}")
        
        if not df_agenda_items.empty:
            agenda_items_path = self.output_dir / f"{base_filename}_agenda_items.csv"
            df_agenda_items.to_csv(agenda_items_path, index=False)
            saved_files['agenda_items'] = agenda_items_path
            logger.debug(f"Saved {len(df_agenda_items)} agenda items to {agenda_items_path}")
        
        if not df_toc.empty:
            toc_path = self.output_dir / f"{base_filename}_toc.csv"
            df_toc.to_csv(toc_path, index=False)
            saved_files['toc'] = toc_path
            logger.debug(f"Saved {len(df_toc)} TOC entries to {toc_path}")
            
        # Generate README
        readme_path = self._create_readme(base_filename, include_speech_text, include_full_protocols,
                                        include_paragraphs, include_comments)
        saved_files['readme'] = readme_path
            
        logger.info(f"CSV export complete: {len(saved_files)} files saved to {self.output_dir}")
        return saved_files
    
    def _create_readme(
        self,
        base_filename: str,
        include_speech_text: bool = True,
        include_full_protocols: bool = False,
        include_paragraphs: bool = True,
        include_comments: bool = True
    ) -> Path:
        """
        Create a README file explaining the data structure.
        
        Args:
            base_filename: Base filename for the export
            include_speech_text: Whether speech texts are included
            include_full_protocols: Whether full protocol texts are included
            include_paragraphs: Whether paragraphs are included
            include_comments: Whether comments are included
            
        Returns:
            Path to the created README file
        """
        logger.debug("Creating README file")
        
        # Readme content
        readme_content = f"""# Bundestag Protocol Data Export

## Data Structure
This export contains the following CSV files:

### Core Files
1. **{base_filename}_protocols.csv**: Basic information about each plenarprotocol
2. **{base_filename}_speeches.csv**: Individual speeches from the protocols
3. **{base_filename}_persons.csv**: Information about speakers (MPs, ministers, etc.)
4. **{base_filename}_proceedings.csv**: Proceedings referenced in the protocols
5. **{base_filename}_speech_topics.csv**: Topics associated with each speech

### Detailed Analysis Files (XML-based)
6. **{base_filename}_paragraphs.csv**: Individual paragraphs within speeches (for detailed text analysis)
7. **{base_filename}_comments.csv**: Comments and interjections in the protocols 
8. **{base_filename}_agenda_items.csv**: Agenda items for each session
9. **{base_filename}_toc.csv**: Table of contents with detailed document structure

## Relationships
- Each speech belongs to one protocol (protocol_id in speeches.csv)
- Each speech has one speaker (speaker_id in speeches.csv)
- Each speech consists of multiple paragraphs (speech_id in paragraphs.csv)
- Each proceeding is referenced in one or more protocols (protocol_id in proceedings.csv)
- Each speech can have multiple topics (speech_id in speech_topics.csv)
- Each speech can have multiple comments (speech_id in comments.csv)
- Each protocol has a table of contents (protocol_id in toc.csv)
- Each protocol has agenda items (protocol_id in agenda_items.csv)

## Research Applications
This dataset can be used for:
- Quantitative text analysis (word frequency, sentiment, etc.)
- Speaker analysis (how different MPs or parties speak)
- Topic tracking across protocols
- Interaction analysis (comments and interjections)
- Historical analysis across different legislative periods
- Parliamentary behavior and rhetoric studies

## Notes
- {'Full speech texts are included' if include_speech_text else 'Full speech texts are excluded to reduce file size'}
- {'Full protocol texts are included' if include_full_protocols else 'Full protocol texts are excluded to reduce file size'}
- {'Individual paragraphs are included for detailed analysis' if include_paragraphs else 'Individual paragraphs are excluded'}
- {'Comments and interjections are included' if include_comments else 'Comments and interjections are excluded'}
- Speech full text can be accessed from the original source if needed
- XML parsing was used to provide rich structure and detailed metadata

Generated on {datetime.now().strftime('%Y-%m-%d')} with Bundestag Protocol Extractor
"""
        
        # Write README file
        readme_path = self.output_dir / f"{base_filename}_README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
            
        logger.debug(f"Created README file at {readme_path}")
        return readme_path
    
    def export_to_json(
        self, 
        protocols: List[PlenarProtocol], 
        filename: Optional[str] = None
    ) -> Path:
        """
        Export the data to a single JSON file.
        
        Args:
            protocols: List of PlenarProtocol objects
            filename: Optional filename (default: will use wahlperiode)
            
        Returns:
            Path to the saved JSON file
        """
        if not protocols:
            logger.warning("No protocols to export to JSON")
            return Path(self.output_dir) / "empty_export.json"
            
        # Determine filename
        if not filename:
            if protocols:
                wahlperiode = protocols[0].wahlperiode
                filename = f"bundestag_wp{wahlperiode}.json"
            else:
                filename = "bundestag_protocols.json"
        
        logger.info(f"Exporting {len(protocols)} protocols to JSON file '{filename}'")
        
        # Prepare data structure
        data = {
            "protocols": [],
            "speeches": [],
            "persons": {}
        }
        
        # Extract data from protocols
        logger.debug("Preparing data for JSON export")
        speech_count = 0
        
        for protocol in protocols:
            # Add protocol data (without speeches)
            protocol_dict = self._convert_protocol_to_dict(protocol)
            data["protocols"].append(protocol_dict)
            
            # Add speech data
            for speech in protocol.speeches:
                speech_count += 1
                speech_dict = self._convert_speech_to_dict(speech)
                data["speeches"].append(speech_dict)
                
                # Add person data (avoid duplicates)
                person = speech.speaker
                if str(person.id) not in data["persons"]:
                    data["persons"][str(person.id)] = self._convert_person_to_dict(person)
        
        # Log summary
        logger.info(f"Prepared JSON data with {len(data['protocols'])} protocols, "
                   f"{speech_count} speeches, and {len(data['persons'])} persons")
        
        # Save to JSON file
        output_path = self.output_dir / filename
        logger.debug(f"Writing JSON to {output_path}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=DataEncoder, ensure_ascii=False, indent=2)
            
        logger.info(f"Successfully exported data to JSON file: {output_path}")
        return output_path
    
    def export_full_texts(
        self, 
        protocols: List[PlenarProtocol], 
        directory: Optional[str] = None
    ) -> List[Path]:
        """
        Export the full text of each protocol to a separate text file.
        
        Args:
            protocols: List of PlenarProtocol objects
            directory: Optional subdirectory for text files (default: 'texts')
            
        Returns:
            List of paths to the saved text files
        """
        if not protocols:
            logger.warning("No protocols to export as text files")
            return []
            
        # Determine directory
        if not directory:
            directory = "texts"
        
        # Create directory if it doesn't exist
        text_dir = self.output_dir / directory
        os.makedirs(text_dir, exist_ok=True)
        
        logger.info(f"Exporting full texts of {len(protocols)} protocols to directory '{text_dir}'")
        
        # Track saved files
        saved_files = []
        protocols_with_text = 0
        
        # Export each protocol's full text
        for protocol in protocols:
            if protocol.full_text:
                protocols_with_text += 1
                filename = f"protocol_{protocol.dokumentnummer.replace('/', '_')}.txt"
                file_path = text_dir / filename
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(protocol.full_text)
                    
                saved_files.append(file_path)
                logger.debug(f"Saved full text for protocol {protocol.dokumentnummer} to {file_path}")
            else:
                logger.debug(f"Protocol {protocol.dokumentnummer} has no full text, skipping")
        
        logger.info(f"Exported {protocols_with_text} text files to {text_dir}")
        return saved_files