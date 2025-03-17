"""Bundestag Protocol Extractor package.

A package for extracting and structuring information from the 
German Bundestag's open data API.
"""

from bundestag_protocol_extractor.api.client import BundestagAPIClient
from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol
from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.utils.exporter import Exporter

__version__ = "0.1.0"
__all__ = ["BundestagAPIClient", "Person", "Speech", "PlenarProtocol", 
           "ProtocolParser", "Exporter"]
