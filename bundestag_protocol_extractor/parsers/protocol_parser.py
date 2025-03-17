"""
Parser for extracting structured data from Bundestag plenarprotokolle.
"""
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


class ProtocolParser:
    """Parser for Bundestag plenarprotokolle."""
    
    def __init__(self, api_client: BundestagAPIClient, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the parser.
        
        Args:
            api_client: API client instance
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
        """
        self.api_client = api_client
        self.persons_cache: Dict[int, Person] = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def _parse_date(self, date_str: str) -> datetime.date:
        """
        Parse a date string into a datetime.date object.
        
        Args:
            date_str: Date string in format YYYY-MM-DD
            
        Returns:
            datetime.date object
        """
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    
    def _get_person(self, person_id: int) -> Person:
        """
        Get person data from cache or API.
        
        Args:
            person_id: Person ID
            
        Returns:
            Person object
        """
        if person_id in self.persons_cache:
            return self.persons_cache[person_id]
        
        try:
            person_data = self.api_client.get_person(
                person_id, 
                max_retries=self.max_retries,
                retry_delay=self.retry_delay
            )
            
            # Extract basic person data
            person = Person(
                id=int(person_data["id"]),
                nachname=person_data["nachname"],
                vorname=person_data["vorname"],
                namenszusatz=person_data.get("namenszusatz"),
                titel=person_data.get("titel", "")
            )
            
            # Add role information if available
            if "person_roles" in person_data and person_data["person_roles"]:
                role = person_data["person_roles"][0]  # Use first role
                person.fraktion = role.get("fraktion")
                person.funktion = role.get("funktion")
                person.ressort = role.get("ressort_titel")
                person.bundesland = role.get("bundesland")
            
            # Cache for future use
            self.persons_cache[person_id] = person
            return person
            
        except Exception as e:
            # If we can't get the person data, create a placeholder
            print(f"Could not retrieve person with ID {person_id}: {e}")
            placeholder = Person(
                id=person_id,
                nachname="Unknown",
                vorname="Unknown",
                titel=f"Person {person_id}"
            )
            # Cache the placeholder to avoid repeated API calls
            self.persons_cache[person_id] = placeholder
            return placeholder
    
    def _extract_speeches_from_activity(self, 
                                        protocol_id: int, 
                                        protocol_number: str,
                                        protocol_date: datetime.date) -> List[Speech]:
        """
        Extract speeches from activities in a plenarprotokoll.
        
        Args:
            protocol_id: Plenarprotokoll ID
            protocol_number: Plenarprotokoll document number
            protocol_date: Plenarprotokoll date
            
        Returns:
            List of Speech objects
        """
        speeches = []
        
        # Get speech activities for this protocol
        activities = self.api_client.get_aktivitaet_list(
            plenarprotokoll_id=protocol_id,
            aktivitaetsart="Rede",
            max_retries=self.max_retries,
            retry_delay=self.retry_delay
        )
        
        for activity in activities:
            # Skip if no fundstelle
            if "fundstelle" not in activity:
                continue
                
            # Basic speech data
            speech_id = int(activity["id"])
            title = activity["titel"]
            
            # Try to find speaker in the activity title
            speaker_id = None
            # Look in the vorgangsbezug for associated persons
            for relation in activity.get("vorgangsbezug", []):
                # In the future, we might need to refine this selection logic
                if relation and "id" in relation:
                    # For now, just take the first one as speaker
                    speaker_id = int(relation["id"])
                    break
            
            # If we couldn't find a speaker, we'll create a placeholder
            if not speaker_id:
                # Create a placeholder person from the title
                # Since we don't have an ID, we'll use a negative number
                placeholder_person = Person(
                    id=-speech_id,  # Negative ID to avoid collision
                    nachname="Unknown",
                    vorname="Unknown",
                    titel=title  # Use full title as a placeholder
                )
                speaker = placeholder_person
            else:
                # Get the actual person data
                speaker = self._get_person(speaker_id)
            
            # Extract location information
            fundstelle = activity["fundstelle"]
            page_start = fundstelle.get("seite")
            page_end = None
            
            # Get related proceedings
            related_proceedings = activity.get("vorgangsbezug", [])
            
            # Get topics from deskriptors
            topics = [d["name"] for d in activity.get("deskriptor", [])]
            
            # For the actual speech text, we would need to parse the full protocol text
            # Here we'll just set a placeholder
            speech_text = f"Speech text would be extracted from the full protocol text based on page {page_start}"
            
            speech = Speech(
                id=speech_id,
                speaker=speaker,
                title=title,
                text=speech_text,
                date=protocol_date,
                protocol_id=protocol_id,
                protocol_number=protocol_number,
                page_start=page_start,
                page_end=page_end,
                topics=topics,
                related_proceedings=related_proceedings
            )
            
            speeches.append(speech)
        
        return speeches
    
    def parse_protocol(self, protocol_id: int, include_full_text: bool = True, use_xml: bool = True) -> PlenarProtocol:
        """
        Parse a plenarprotokoll.
        
        Args:
            protocol_id: Plenarprotokoll ID
            include_full_text: Whether to include the full text
            use_xml: Whether to try parsing speeches from XML format (more accurate)
            
        Returns:
            PlenarProtocol object
        """
        # Get protocol data
        protocol_data = self.api_client.get_plenarprotokoll(
            protocol_id,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay
        )
        
        # Extract basic protocol data
        protocol = PlenarProtocol(
            id=int(protocol_data["id"]),
            dokumentnummer=protocol_data["dokumentnummer"],
            wahlperiode=protocol_data["wahlperiode"],
            date=self._parse_date(protocol_data["datum"]),
            title=protocol_data["titel"],
            herausgeber=protocol_data["herausgeber"]
        )
        
        # Get XML data if requested (preferred method)
        speeches_from_xml = []
        xml_root = None
        
        if use_xml:
            print(f"Attempting to get XML data for protocol {protocol_id}")
            try:
                # Try to get structured XML data
                xml_root = self.api_client.get_plenarprotokoll_xml(protocol_data)
                
                if xml_root is not None:
                    print(f"Successfully retrieved XML for protocol {protocol_id}")
                    # Extract full text from XML if available
                    text_element = xml_root.find("text")
                    if text_element is not None and text_element.text:
                        protocol.full_text = text_element.text
                        print("Extracted full text from XML")
                    
                    # Extract metadata from XML
                    try:
                        metadata = self.api_client.extract_metadata_from_xml(xml_root)
                        
                        # Add metadata to protocol
                        protocol.toc = metadata.get("table_of_contents", [])
                        protocol.agenda_items = metadata.get("agenda_items", [])
                        print(f"Extracted metadata: {len(protocol.toc)} TOC items, {len(protocol.agenda_items)} agenda items")
                    except Exception as e:
                        print(f"Error extracting metadata from XML: {e}")
                    
                    # Extract speeches from XML
                    try:
                        speeches_from_xml = self.api_client.parse_speeches_from_xml(xml_root)
                        print(f"Extracted {len(speeches_from_xml)} speeches from XML")
                    except Exception as e:
                        print(f"Error parsing speeches from XML: {e}")
                        speeches_from_xml = []
                    
                    # Convert raw speech data to Speech objects
                    for speech_data in speeches_from_xml:
                        try:
                            # Create a person object from the speech data
                            party = speech_data.get("party", "")
                            
                            # Try to use speaker_id as numeric ID or generate a unique negative ID
                            try:
                                speaker_id_str = speech_data.get("speaker_id", "")
                                if speaker_id_str:
                                    speaker_id = int(speaker_id_str.replace("r", ""))
                                else:
                                    speaker_id = -len(self.persons_cache) - 1  # Generate a unique negative ID
                            except (ValueError, TypeError):
                                speaker_id = -len(self.persons_cache) - 1  # Generate a unique negative ID
                            
                            person = Person(
                                id=speaker_id,
                                nachname=speech_data.get("speaker_last_name", ""),
                                vorname=speech_data.get("speaker_first_name", ""),
                                titel=speech_data.get("speaker_title", ""),
                                fraktion=party
                            )
                            
                            # Generate a unique ID for the speech
                            try:
                                speech_id_str = speech_data.get("id", "")
                                if speech_id_str:
                                    speech_id = int(speech_id_str.replace("ID", ""))
                                else:
                                    speech_id = -len(protocol.speeches) - 1  # Generate a unique negative ID
                            except (ValueError, TypeError):
                                speech_id = -len(protocol.speeches) - 1  # Generate a unique negative ID
                            
                            # Extract comments and paragraphs
                            comments = speech_data.get("comments", [])
                            paragraphs = speech_data.get("paragraphs", [])
                            
                            # Add to topics if there are comments (often contain topic information)
                            topics = []
                            for comment in comments:
                                # Some comments include information about topics
                                if "betr.:" in comment.lower() or "betreffend:" in comment.lower():
                                    topics.append(comment)
                            
                            # Create speech object with rich metadata
                            speech = Speech(
                                id=speech_id,
                                speaker=person,
                                title=speech_data.get("speaker_full_name", ""),
                                text=speech_data.get("text", ""),
                                date=protocol.date,
                                protocol_id=protocol.id,
                                protocol_number=protocol.dokumentnummer,
                                page_start=speech_data.get("page", ""),
                                page_end=None,  # We don't have an end page in the XML
                                topics=topics
                            )
                            
                            # Add extra metadata not in the standard model
                            speech.paragraphs = paragraphs
                            speech.comments = comments
                            speech.is_president = speech_data.get("is_president", False)
                            speech.page_section = speech_data.get("page_section", "")
                            
                            protocol.speeches.append(speech)
                        except Exception as e:
                            print(f"Error processing speech data: {e}")
                else:
                    print(f"Could not retrieve XML for protocol {protocol_id}")
            except Exception as e:
                print(f"Error parsing XML for protocol {protocol_id}: {e}")
                # Fallback to regular method
                pass
        
        # If we couldn't get speeches from XML or it was not requested,
        # fall back to the regular method
        if not protocol.speeches or not use_xml:
            # Get JSON text data if needed
            if include_full_text and not protocol.full_text:
                try:
                    text_data = self.api_client.get_plenarprotokoll_text(
                        protocol_id,
                        max_retries=self.max_retries,
                        retry_delay=self.retry_delay
                    )
                    if "text" in text_data:
                        protocol.full_text = text_data["text"]
                except Exception as e:
                    print(f"Could not get plenarprotokoll text: {e}")
            
            # Extract speeches from activity metadata
            try:
                protocol.speeches = self._extract_speeches_from_activity(
                    protocol_id=protocol.id,
                    protocol_number=protocol.dokumentnummer,
                    protocol_date=protocol.date
                )
            except Exception as e:
                print(f"Could not extract speeches from activity: {e}")
                # Return empty list if this fails
                protocol.speeches = []
        
        # Get PDF URL if available
        if "fundstelle" in protocol_data and "pdf_url" in protocol_data["fundstelle"]:
            protocol.pdf_url = protocol_data["fundstelle"]["pdf_url"]
        
        # Parse updated_at timestamp
        if "aktualisiert" in protocol_data:
            protocol.updated_at = datetime.fromisoformat(protocol_data["aktualisiert"].replace("Z", "+00:00"))
        
        # Extract proceedings
        protocol.proceedings = protocol_data.get("vorgangsbezug", [])
        
        # If we have both full text and speeches without text, try to extract text
        if protocol.full_text and any(not speech.text or speech.text.startswith("Speech text would be extracted") 
                                     for speech in protocol.speeches):
            protocol.speeches = self.parse_protocol_speeches(protocol)
        
        return protocol
    
    def parse_protocol_speeches(self, protocol: PlenarProtocol) -> List[Speech]:
        """
        Extract speech texts from the full protocol text.
        This is a more advanced parser that would extract the actual speech texts
        based on page numbers and other markers in the full text.
        
        Args:
            protocol: PlenarProtocol with full_text
            
        Returns:
            Updated list of speeches with extracted text
        """
        if not protocol.full_text:
            raise ValueError("Protocol full text is required to extract speeches")
        
        full_text = protocol.full_text
        speeches = []
        
        # For each speech in the protocol
        for speech in protocol.speeches:
            # This would require a more sophisticated algorithm to extract the exact text
            # based on page numbers, speaker names, etc.
            # For now, we'll just use a placeholder extraction
            
            # If we have page markers, try to extract text between them
            if speech.page_start:
                # Extract a section around the page marker
                page_marker = speech.page_start
                
                # Simple approach: find text near the page marker
                # In a real implementation, this would be much more sophisticated
                try:
                    # Find the page in the text
                    page_index = full_text.find(f"S. {page_marker}")
                    if page_index == -1:
                        page_index = full_text.find(page_marker)
                    
                    if page_index != -1:
                        # Take some text after the page index
                        start_index = page_index + len(page_marker) + 10
                        end_index = min(start_index + 1000, len(full_text))
                        
                        # Extract text
                        extracted_text = full_text[start_index:end_index]
                        
                        # Update speech with extracted text
                        speech.text = extracted_text
                except Exception as e:
                    # If extraction fails, keep the placeholder
                    print(f"Failed to extract speech text: {e}")
            
            speeches.append(speech)
        
        return speeches
    
    def get_all_protocols(self, wahlperiode: int = 20) -> List[PlenarProtocol]:
        """
        Get all plenarprotokolle for a legislative period.
        
        Args:
            wahlperiode: Legislative period (default: 20)
            
        Returns:
            List of PlenarProtocol objects
        """
        protocols = []
        
        # Get list of all protocols
        protocol_list = self.api_client.get_plenarprotokoll_list(wahlperiode=wahlperiode)
        
        for protocol_metadata in protocol_list:
            protocol_id = int(protocol_metadata["id"])
            
            # Parse full protocol
            protocol = self.parse_protocol(protocol_id)
            protocols.append(protocol)
        
        return protocols