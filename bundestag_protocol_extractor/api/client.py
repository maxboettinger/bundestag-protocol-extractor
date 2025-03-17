"""
API client for the Bundestag DIP API.

This module provides a client for interacting with the German Bundestag's DIP API,
handling authentication, rate limiting, XML retrieval, and data extraction.
"""
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urljoin

import requests

from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class BundestagAPIClient:
    """Client for the Bundestag DIP API."""

    # Base URL must include "/v1/" as specified in the API documentation
    BASE_URL = "https://search.dip.bundestag.de/api/v1/"
    BUNDESTAG_XML_URL = "https://www.bundestag.de/resource/blob"

    def __init__(self, api_key: str):
        """
        Initialize the API client.

        Args:
            api_key: API key for the Bundestag DIP API
        """
        self.api_key = api_key
        # Format according to API documentation: "ApiKey YOUR_API_KEY"
        # If the key already includes "ApiKey" prefix, don't add it again
        if api_key.startswith("ApiKey "):
            api_header = api_key
        else:
            api_header = f"ApiKey {api_key}"
            
        self.headers = {"Authorization": api_header}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, 
        format_xml: bool = False,
        retry_count: int = 0,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> Union[Dict[str, Any], str]:
        """
        Make a request to the API with rate limiting handling.

        Args:
            endpoint: API endpoint
            params: Query parameters
            format_xml: If True, request XML format and return as string
            retry_count: Current retry attempt (for internal use)
            max_retries: Maximum number of retries in case of rate limiting
            retry_delay: Base delay in seconds between retries (will use exponential backoff)
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            Response JSON data or XML string
        """
        url = urljoin(self.BASE_URL, endpoint)
        
        # Initialize params if None
        params = params or {}
        
        # Add API key as query parameter (apikey) as an alternative to header auth
        # This ensures the API key is used even if the header approach fails
        if 'apikey' not in params:
            params['apikey'] = self.api_key
        
        # Set format parameter based on request type
        if format_xml:
            params["format"] = "xml"
        else:
            # Explicitly request JSON format to be safe
            params["format"] = "json"
        
        # Record API call in progress tracker if provided
        if progress_tracker:
            progress_tracker.update_api_stats(api_call=True)
        
        logger.debug(f"API request: {endpoint} (params: {params})")
        
        try:
            response = self.session.get(url, params=params)
            
            # Check for rate limiting response (DIP API uses .enodia/challenge in the redirect URL)
            if response.status_code in [429, 400, 403] or '.enodia/challenge' in response.url:
                if progress_tracker:
                    progress_tracker.update_api_stats(rate_limit=True)
                
                if retry_count < max_retries:
                    # Calculate delay with exponential backoff
                    wait_time = retry_delay * (2 ** retry_count)
                    logger.warning(f"Rate limit detected, retrying in {wait_time:.1f}s "
                                  f"(attempt {retry_count+1}/{max_retries})")
                    time.sleep(wait_time)
                    
                    # Record retry in progress tracker if provided
                    if progress_tracker:
                        progress_tracker.update_api_stats(retry=True)
                    
                    # Recursive retry with increased counter
                    return self._make_request(
                        endpoint=endpoint,
                        params=params,
                        format_xml=format_xml,
                        retry_count=retry_count + 1,
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        progress_tracker=progress_tracker
                    )
                else:
                    # If we've exhausted retries, raise the error
                    logger.error(f"Rate limit persists after {max_retries} retries")
                    response.raise_for_status()
            
            # For other errors, just raise immediately
            response.raise_for_status()
            
            # Log success at debug level
            logger.debug(f"API request successful: {endpoint}")
            
            if format_xml:
                return response.text
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            # Log the full URL that failed for easier debugging
            full_url = response.request.url
            logger.error(f"API request failed: {full_url}")
            logger.error(f"Response status: {response.status_code}, content: {response.text[:200]}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception for {endpoint}: {str(e)}")
            raise

    def get_all_results(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3, retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all results for a paginated endpoint using cursor-based pagination.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            List of all documents
        """
        params = params or {}
        all_documents = []
        
        logger.info(f"Fetching all results for {endpoint} with pagination")
        
        # Initial request with retry support
        response = self._make_request(
            endpoint, params,
            max_retries=max_retries,
            retry_delay=retry_delay,
            progress_tracker=progress_tracker
        )
        
        documents = response.get("documents", [])
        all_documents.extend(documents)
        logger.info(f"Retrieved {len(documents)} items in first page")
        
        # Continue fetching until cursor doesn't change
        current_cursor = response.get("cursor")
        page_count = 1
        
        # Use TQDM for progress if we have an estimated total
        total_estimate = response.get("numFound", 0)
        
        while current_cursor:
            # Add a small delay between pagination requests to avoid rate limiting
            time.sleep(retry_delay)
            
            params["cursor"] = current_cursor
            response = self._make_request(
                endpoint, params,
                max_retries=max_retries,
                retry_delay=retry_delay,
                progress_tracker=progress_tracker
            )
            
            documents = response.get("documents", [])
            
            # If no new documents or cursor hasn't changed, we're done
            if not documents or response.get("cursor") == current_cursor:
                break
                
            all_documents.extend(documents)
            current_cursor = response.get("cursor")
            page_count += 1
            
            # Log progress for large datasets
            if page_count % 5 == 0:
                logger.info(f"Retrieved {len(all_documents)}/{total_estimate} items in {page_count} pages")
        
        logger.info(f"Completed pagination: {len(all_documents)} total items in {page_count} pages")
            
        return all_documents

    def get_plenarprotokoll_list(
        self, 
        wahlperiode: int = 20, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of plenarprotokolle for the specified legislative period.
        Based on the API endpoint: GET /plenarprotokoll

        Args:
            wahlperiode: Legislative period (default: 20)
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            List of plenarprotokolle metadata
        """
        params = {"f.wahlperiode": wahlperiode}
        logger.info(f"Retrieving list of plenarprotokolle for Wahlperiode {wahlperiode}")
        
        return self.get_all_results(
            "plenarprotokoll", 
            params, 
            max_retries=max_retries, 
            retry_delay=retry_delay,
            progress_tracker=progress_tracker
        )

    def get_plenarprotokoll(
        self, 
        id: int, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for a specific plenarprotokoll.
        Based on the API endpoint: GET /plenarprotokoll/{id}

        Args:
            id: ID of the plenarprotokoll
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            Plenarprotokoll metadata
        """
        logger.debug(f"Retrieving metadata for plenarprotokoll ID {id}")
        return self._make_request(
            f"plenarprotokoll/{id}", 
            max_retries=max_retries, 
            retry_delay=retry_delay,
            progress_tracker=progress_tracker
        )

    def get_plenarprotokoll_text(
        self, 
        id: int, 
        format_xml: bool = False, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> Union[Dict[str, Any], str]:
        """
        Get full text and metadata for a specific plenarprotokoll.
        Based on the API endpoint: GET /plenarprotokoll-text/{id}

        Args:
            id: ID of the plenarprotokoll
            format_xml: If True, request XML format and return as string
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            Plenarprotokoll full text and metadata as JSON or XML string
        """
        logger.debug(f"Retrieving {'XML' if format_xml else 'text'} for plenarprotokoll ID {id}")
        return self._make_request(
            f"plenarprotokoll-text/{id}", 
            format_xml=format_xml,
            max_retries=max_retries, 
            retry_delay=retry_delay,
            progress_tracker=progress_tracker
        )
    
    def get_plenarprotokoll_xml(
        self, 
        plenarprotokoll_data: Dict[str, Any],
        progress_tracker: Optional[Any] = None
    ) -> Optional[ET.Element]:
        """
        Get the XML version of a plenarprotokoll from the Bundestag website.
        Uses direct URL approach based on the example: 
        "https://www.bundestag.de/resource/blob/1033454/dc5b0f6a13e444d2f09c333a3702b1cc/20204.xml"
        
        Args:
            plenarprotokoll_data: Plenarprotokoll metadata from the API
            progress_tracker: Optional progress tracker to update API stats
            
        Returns:
            XML root element or None if not found
        """
        try:
            # Extract the document information
            protocol_id = int(plenarprotokoll_data["id"])
            wahlperiode = str(plenarprotokoll_data["wahlperiode"])
            dokument_nummer = plenarprotokoll_data["dokumentnummer"].split("/")[-1]
            doc_identifier = f"{wahlperiode}/{dokument_nummer}"
            
            logger.info(f"Retrieving XML for protocol {doc_identifier} (ID: {protocol_id})")
            
            # First try a direct approach with the PDF URL
            document_id = None
            if "fundstelle" in plenarprotokoll_data and "pdf_url" in plenarprotokoll_data["fundstelle"]:
                pdf_url = plenarprotokoll_data["fundstelle"]["pdf_url"]
                logger.debug(f"Found PDF URL: {pdf_url}")
                
                # Extract document ID from PDF URL if possible
                match = re.search(r'blob/(\d+)/', pdf_url)
                if match:
                    document_id = match.group(1)
                    logger.debug(f"Extracted document ID: {document_id}")
            
            # URLs to try
            urls_to_try = []
            
            # If we found a document ID, try the exact format from the example
            if document_id:
                # Format as in example: "https://www.bundestag.de/resource/blob/1033454/dc5b0f6a13e444d2f09c333a3702b1cc/20204.xml"
                # Construct document number in the format used in the XML URL (wahlperiode + session number)
                doc_number = f"{wahlperiode}{dokument_nummer}"
                urls_to_try.append(f"{self.BUNDESTAG_XML_URL}/{document_id}/{doc_number}.xml")
            
            # Try a few other patterns based on the PDF URL
            if "fundstelle" in plenarprotokoll_data and "pdf_url" in plenarprotokoll_data["fundstelle"]:
                pdf_url = plenarprotokoll_data["fundstelle"]["pdf_url"]
                # Extract the base path from PDF URL and replace .pdf with .xml
                pdf_url_base = pdf_url.replace('.pdf', '')
                urls_to_try.append(f"{pdf_url_base}.xml")
            
            logger.info(f"Attempting {len(urls_to_try)} possible XML URLs for protocol {doc_identifier}")
            
            # Try each URL
            for url in urls_to_try:
                logger.debug(f"Trying XML URL: {url}")
                
                # Update API stats in progress tracker
                if progress_tracker:
                    progress_tracker.update_api_stats(api_call=True)
                    
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        logger.info(f"Successfully retrieved XML from {url}")
                        try:
                            root = ET.fromstring(response.text)
                            return root
                        except ET.ParseError as e:
                            logger.warning(f"XML parsing error: {e}")
                    else:
                        logger.debug(f"HTTP error {response.status_code} for URL: {url}")
                except requests.RequestException as e:
                    logger.debug(f"Request error for {url}: {e}")
            
            # If all URLs failed, try the API with XML format
            logger.info("All direct URL attempts failed, trying API with XML format...")
            try:
                xml_text = self.get_plenarprotokoll_text(
                    protocol_id, 
                    format_xml=True,
                    progress_tracker=progress_tracker
                )
                root = ET.fromstring(xml_text)
                logger.info("Successfully retrieved XML from API")
                return root
            except Exception as e:
                logger.error(f"Could not get XML from API: {e}")
            
            logger.warning(f"Could not find XML for protocol {doc_identifier}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving XML: {e}", exc_info=True)
            return None
    
# Method removed as we now extract document ID directly from PDF URL in get_plenarprotokoll_xml
    
    def parse_speeches_from_xml(self, xml_root: ET.Element) -> List[Dict[str, Any]]:
        """
        Parse speeches from the structured plenarprotokoll XML.
        
        Args:
            xml_root: XML root element
            
        Returns:
            List of speech data with rich metadata
        """
        speeches = []
        
        # Look for the sitzungsverlauf element which contains all speeches
        sitzungsverlauf = xml_root.find(".//sitzungsverlauf")
        if sitzungsverlauf is None:
            return speeches
        
        # Find all rede elements (speeches)
        rede_elements = sitzungsverlauf.findall(".//rede")
        
        for rede in rede_elements:
            # Get the speech ID
            speech_id = rede.get("id", "")
            
            # Get speaker information from the redner element
            redner_elem = rede.find(".//redner")
            if redner_elem is None:
                continue
                
            # Extract speaker details
            speaker_id = redner_elem.get("id", "")
            name_elem = redner_elem.find("name")
            
            if name_elem is None:
                continue
            
            # Extract name components
            titel = name_elem.findtext("titel", "").strip()
            vorname = name_elem.findtext("vorname", "").strip()
            nachname = name_elem.findtext("nachname", "").strip()
            fraktion = name_elem.findtext("fraktion", "").strip()
            
            # Compile full speaker name
            full_name = f"{titel} {vorname} {nachname}".strip()
            
            # Get page reference information
            xref = rede.find(".//xref")
            page_start = ""
            page_section = ""
            if xref is not None:
                a_elem = xref.find(".//a")
                if a_elem is not None:
                    page_elem = a_elem.find("seite")
                    section_elem = a_elem.find("seitenbereich")
                    if page_elem is not None:
                        page_start = page_elem.text
                    if section_elem is not None:
                        page_section = section_elem.text
            
            # Extract paragraphs of speech text
            paragraphs = []
            p_elems = rede.findall(".//p")
            for p in p_elems:
                # Skip non-text elements or elements with no text
                if p.text is None:
                    continue
                
                # Get paragraph text
                paragraph_text = p.text.strip()
                
                # Get paragraph class/type if available
                paragraph_class = p.get("klasse", "")
                
                paragraphs.append({
                    "text": paragraph_text,
                    "type": paragraph_class
                })
            
            # Extract comments
            comments = []
            comment_elems = rede.findall(".//kommentar")
            for comment in comment_elems:
                if comment.text:
                    comments.append(comment.text.strip())
            
            # Combine all paragraphs into a single text
            full_text = "\n\n".join([p["text"] for p in paragraphs])
            
            # Create speech data
            speech = {
                "id": speech_id,
                "speaker_id": speaker_id,
                "speaker_title": titel,
                "speaker_first_name": vorname,
                "speaker_last_name": nachname,
                "speaker_full_name": full_name,
                "party": fraktion,
                "page": page_start,
                "page_section": page_section,
                "paragraphs": paragraphs,
                "comments": comments,
                "text": full_text
            }
            
            speeches.append(speech)
        
        # Also extract comments from the sitzungsbeginn if available
        # These are usually the president's opening remarks
        sitzungsbeginn = sitzungsverlauf.find(".//sitzungsbeginn")
        if sitzungsbeginn:
            # Get the president's name
            president_name = sitzungsbeginn.findtext(".//name", "").strip()
            
            # Get all paragraphs from the opening
            paragraphs = []
            p_elems = sitzungsbeginn.findall(".//p")
            for p in p_elems:
                if p.text:
                    paragraphs.append({
                        "text": p.text.strip(),
                        "type": p.get("klasse", "")
                    })
            
            # Combine all paragraphs into a single text
            full_text = "\n\n".join([p["text"] for p in paragraphs])
            
            # Create opening speech data
            if president_name and paragraphs:
                # Try to determine president's last name
                name_parts = president_name.split()
                last_name = name_parts[-1] if name_parts else ""
                
                opening_speech = {
                    "id": "sitzungsbeginn",
                    "speaker_id": "",
                    "speaker_title": "Präsident/in",
                    "speaker_first_name": "",
                    "speaker_last_name": last_name,
                    "speaker_full_name": president_name,
                    "party": "",
                    "page": "",
                    "page_section": "",
                    "paragraphs": paragraphs,
                    "comments": [],
                    "text": full_text,
                    "is_president": True
                }
                
                speeches.append(opening_speech)
        
        return speeches
    
    def extract_metadata_from_xml(self, xml_root: ET.Element) -> Dict[str, Any]:
        """
        Extract metadata from the plenarprotokoll XML.
        
        Args:
            xml_root: XML root element
            
        Returns:
            Dictionary with metadata
        """
        metadata = {}
        
        # Extract basic document metadata
        metadata["id"] = xml_root.findtext("id", "")
        metadata["dokumentart"] = xml_root.findtext("dokumentart", "")
        metadata["dokumentnummer"] = xml_root.findtext("dokumentnummer", "")
        metadata["wahlperiode"] = xml_root.findtext("wahlperiode", "")
        metadata["herausgeber"] = xml_root.findtext("herausgeber", "")
        metadata["datum"] = xml_root.findtext("datum", "")
        metadata["titel"] = xml_root.findtext("titel", "")
        
        # Extract table of contents (inhaltsverzeichnis)
        toc = []
        vorspann = xml_root.find(".//vorspann")
        if vorspann is not None:
            inhaltsverzeichnis = vorspann.find("inhaltsverzeichnis")
            if inhaltsverzeichnis is not None:
                # Extract blocks from table of contents
                for ivz_block in inhaltsverzeichnis.findall(".//ivz-block"):
                    block_title = ivz_block.findtext("ivz-block-titel", "").strip()
                    entries = []
                    
                    for ivz_eintrag in ivz_block.findall(".//ivz-eintrag"):
                        entry_content = ivz_eintrag.findtext(".//ivz-eintrag-inhalt", "").strip()
                        page = ""
                        
                        # Get page reference if available
                        a_elem = ivz_eintrag.find(".//a")
                        if a_elem is not None:
                            page = a_elem.get("href", "")
                        
                        entries.append({
                            "content": entry_content,
                            "page": page
                        })
                    
                    toc.append({
                        "title": block_title,
                        "entries": entries
                    })
        
        metadata["table_of_contents"] = toc
        
        # Extract agenda items (tagesordnungspunkte)
        agenda_items = []
        for top_elem in xml_root.findall(".//tagesordnungspunkt"):
            top_id = top_elem.get("top-id", "")
            
            # Extract all paragraphs for this agenda item
            item_text = []
            for p in top_elem.findall(".//p"):
                if p.text:
                    item_text.append(p.text.strip())
            
            agenda_items.append({
                "id": top_id,
                "text": "\n".join(item_text)
            })
        
        metadata["agenda_items"] = agenda_items
        
        return metadata
    
    def get_person_list(self, wahlperiode: int = 20, 
                     max_retries: int = 3, retry_delay: float = 1.0) -> List[Dict[str, Any]]:
        """
        Get a list of persons for the specified legislative period.
        Based on the API endpoint: GET /person

        Args:
            wahlperiode: Legislative period (default: 20)
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries

        Returns:
            List of person metadata
        """
        params = {"f.wahlperiode": wahlperiode}
        return self.get_all_results("person", params, 
                                   max_retries=max_retries, 
                                   retry_delay=retry_delay)
    
    def get_person(self, id: int, max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """
        Get metadata for a specific person.
        Based on the API endpoint: GET /person/{id}

        Args:
            id: ID of the person
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries

        Returns:
            Person metadata
        """
        return self._make_request(f"person/{id}", 
                                max_retries=max_retries, 
                                retry_delay=retry_delay)
    
    def get_aktivitaet_list(
        self, 
        plenarprotokoll_id: Optional[int] = None,
        wahlperiode: Optional[int] = None,
        aktivitaetsart: Optional[str] = None,
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        progress_tracker: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of activities.
        Based on the API endpoint: GET /aktivitaet

        Args:
            plenarprotokoll_id: Filter by plenarprotokoll ID
            wahlperiode: Filter by legislative period
            aktivitaetsart: Filter by activity type (e.g. "Rede")
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries
            progress_tracker: Optional progress tracker to update API stats

        Returns:
            List of activity metadata
        """
        params = {}
        if plenarprotokoll_id:
            params["f.plenarprotokoll"] = plenarprotokoll_id
        if wahlperiode:
            params["f.wahlperiode"] = wahlperiode
        
        activities = self.get_all_results("aktivitaet", params, 
                                        max_retries=max_retries, 
                                        retry_delay=retry_delay,
                                        progress_tracker=progress_tracker)
        
        # Filter by aktivitaetsart if provided
        if aktivitaetsart:
            activities = [
                activity for activity in activities 
                if activity.get("aktivitaetsart") == aktivitaetsart
            ]
            
        return activities
    
    def get_aktivitaet(self, id: int, max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """
        Get metadata for a specific activity.
        Based on the API endpoint: GET /aktivitaet/{id}

        Args:
            id: ID of the activity
            max_retries: Maximum number of retries for rate limiting
            retry_delay: Base delay in seconds between retries

        Returns:
            Activity metadata
        """
        return self._make_request(f"aktivitaet/{id}", 
                                max_retries=max_retries, 
                                retry_delay=retry_delay)
        
    def get_raw_plenarprotokoll_xml(self, id: int) -> str:
        """
        Get the raw XML content for a plenarprotokoll.
        This is useful for debugging XML parsing issues.
        Based on the API endpoint: GET /plenarprotokoll-text/{id}?format=xml
        
        Args:
            id: ID of the plenarprotokoll
            
        Returns:
            Raw XML string
        """
        return self._make_request(f"plenarprotokoll-text/{id}", format_xml=True)