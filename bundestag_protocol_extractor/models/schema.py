"""
Data models for the Bundestag protocol extractor.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Union, Any


@dataclass
class Person:
    """Represents a person (member of the Bundestag or other speaker)."""
    
    id: int
    nachname: str
    vorname: str
    namenszusatz: Optional[str] = None
    titel: str = ""
    fraktion: Optional[str] = None
    rolle: Optional[str] = None
    funktion: Optional[str] = None
    ressort: Optional[str] = None
    bundesland: Optional[str] = None


@dataclass
class Speech:
    """Represents a speech in a plenarprotokoll."""
    
    id: int
    speaker: Person
    title: str
    text: str
    date: date
    protocol_id: int
    protocol_number: str
    page_start: Optional[str] = None
    page_end: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    related_proceedings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlenarProtocol:
    """Represents a plenarprotokoll."""
    
    id: int
    dokumentnummer: str
    wahlperiode: int
    date: date
    title: str
    herausgeber: str
    full_text: Optional[str] = None
    speeches: List[Speech] = field(default_factory=list)
    proceedings: List[Dict[str, Any]] = field(default_factory=list)
    pdf_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    # Additional XML metadata
    toc: List[Dict[str, Any]] = field(default_factory=list)
    agenda_items: List[Dict[str, Any]] = field(default_factory=list)