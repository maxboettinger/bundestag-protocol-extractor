"""
Exporter module for saving extracted data to various formats.
"""
import csv
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import pandas as pd

from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


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
    
    def export_to_csv(self, protocols: List[PlenarProtocol], base_filename: Optional[str] = None,
                       include_speech_text: bool = True, include_full_protocols: bool = False,
                       include_paragraphs: bool = True, include_comments: bool = True) -> None:
        """
        Export the data to CSV files (multiple files for different entities).
        
        Args:
            protocols: List of PlenarProtocol objects
            base_filename: Optional base filename (default: will use wahlperiode)
            include_speech_text: Whether to include full speech text in CSV (can make files large)
            include_full_protocols: Whether to include full protocol text in CSV (can make files very large)
            include_paragraphs: Whether to export individual paragraphs for detailed analysis
            include_comments: Whether to export comments as separate entities
        """
        # Determine base filename
        if not base_filename:
            if protocols:
                wahlperiode = protocols[0].wahlperiode
                base_filename = f"bundestag_wp{wahlperiode}"
            else:
                base_filename = "bundestag_protocols"
        
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
                    for i, para in enumerate(getattr(speech, "paragraphs", [])):
                        paragraphs_data.append({
                            "speech_id": speech.id,
                            "protocol_id": protocol.id,
                            "paragraph_number": i + 1,
                            "text": para.get("text", ""),
                            "type": para.get("type", "")
                        })
                
                # Add comments data
                if include_comments:
                    for i, comment in enumerate(getattr(speech, "comments", [])):
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
        
        # Convert to dataframes
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
        
        # Save to CSV files
        df_protocols.to_csv(self.output_dir / f"{base_filename}_protocols.csv", index=False)
        df_speeches.to_csv(self.output_dir / f"{base_filename}_speeches.csv", index=False)
        df_persons.to_csv(self.output_dir / f"{base_filename}_persons.csv", index=False)
        df_proceedings.to_csv(self.output_dir / f"{base_filename}_proceedings.csv", index=False)
        df_speech_topics.to_csv(self.output_dir / f"{base_filename}_speech_topics.csv", index=False)
        
        # Save XML-specific data to CSV files
        if include_paragraphs and not df_paragraphs.empty:
            df_paragraphs.to_csv(self.output_dir / f"{base_filename}_paragraphs.csv", index=False)
        
        if include_comments and not df_comments.empty:
            df_comments.to_csv(self.output_dir / f"{base_filename}_comments.csv", index=False)
        
        if not df_agenda_items.empty:
            df_agenda_items.to_csv(self.output_dir / f"{base_filename}_agenda_items.csv", index=False)
        
        if not df_toc.empty:
            df_toc.to_csv(self.output_dir / f"{base_filename}_toc.csv", index=False)
        
        # Also export a README file explaining the data structure
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
        
        with open(self.output_dir / f"{base_filename}_README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    def export_to_json(self, protocols: List[PlenarProtocol], filename: Optional[str] = None) -> None:
        """
        Export the data to a single JSON file.
        
        Args:
            protocols: List of PlenarProtocol objects
            filename: Optional filename (default: will use wahlperiode)
        """
        # Determine filename
        if not filename:
            if protocols:
                wahlperiode = protocols[0].wahlperiode
                filename = f"bundestag_wp{wahlperiode}.json"
            else:
                filename = "bundestag_protocols.json"
        
        # Prepare data structure
        data = {
            "protocols": [],
            "speeches": [],
            "persons": {}
        }
        
        # Extract data from protocols
        for protocol in protocols:
            # Add protocol data (without speeches)
            protocol_dict = self._convert_protocol_to_dict(protocol)
            data["protocols"].append(protocol_dict)
            
            # Add speech data
            for speech in protocol.speeches:
                speech_dict = self._convert_speech_to_dict(speech)
                data["speeches"].append(speech_dict)
                
                # Add person data (avoid duplicates)
                person = speech.speaker
                if str(person.id) not in data["persons"]:
                    data["persons"][str(person.id)] = self._convert_person_to_dict(person)
        
        # Save to JSON file
        with open(self.output_dir / filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=DataEncoder, ensure_ascii=False, indent=2)
    
    def export_full_texts(self, protocols: List[PlenarProtocol], directory: Optional[str] = None) -> None:
        """
        Export the full text of each protocol to a separate text file.
        
        Args:
            protocols: List of PlenarProtocol objects
            directory: Optional subdirectory for text files (default: 'texts')
        """
        # Determine directory
        if not directory:
            directory = "texts"
        
        # Create directory if it doesn't exist
        text_dir = self.output_dir / directory
        os.makedirs(text_dir, exist_ok=True)
        
        # Export each protocol's full text
        for protocol in protocols:
            if protocol.full_text:
                filename = f"protocol_{protocol.dokumentnummer.replace('/', '_')}.txt"
                with open(text_dir / filename, 'w', encoding='utf-8') as f:
                    f.write(protocol.full_text)