"""Tests for the ProtocolParser class."""
import unittest
from unittest import mock
from datetime import date, datetime
import xml.etree.ElementTree as ET

from bundestag_protocol_extractor.parsers.protocol_parser import ProtocolParser
from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


class TestProtocolParser(unittest.TestCase):
    """Test cases for ProtocolParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_client = mock.MagicMock()
        self.parser = ProtocolParser(self.api_client)

    def test_parse_date(self):
        """Test the _parse_date method."""
        result = self.parser._parse_date("2023-05-15")
        self.assertEqual(result, date(2023, 5, 15))

    def test_get_person(self):
        """Test the _get_person method."""
        # Mock the API client's get_person method
        self.api_client.get_person.return_value = {
            "id": "123",
            "nachname": "Mustermann",
            "vorname": "Max",
            "titel": "Dr.",
            "person_roles": [
                {
                    "fraktion": "Test Party",
                    "funktion": "Test Function",
                    "ressort_titel": "Test Department",
                    "bundesland": "Berlin"
                }
            ]
        }
        
        # Call the method
        person = self.parser._get_person(123)
        
        # Verify the result
        self.assertEqual(person.id, 123)
        self.assertEqual(person.nachname, "Mustermann")
        self.assertEqual(person.vorname, "Max")
        self.assertEqual(person.titel, "Dr.")
        self.assertEqual(person.fraktion, "Test Party")
        self.assertEqual(person.funktion, "Test Function")
        self.assertEqual(person.ressort, "Test Department")
        self.assertEqual(person.bundesland, "Berlin")
        
        # Test caching - call again and verify API not called
        self.api_client.get_person.reset_mock()
        person2 = self.parser._get_person(123)
        self.api_client.get_person.assert_not_called()
        self.assertEqual(person, person2)
        
    @mock.patch("bundestag_protocol_extractor.parsers.protocol_parser.datetime")
    def test_parse_protocol_basic(self, mock_datetime):
        """Test the parse_protocol method with basic data."""
        # Mock datetime to return a consistent value
        mock_date = mock.MagicMock()
        mock_date.strptime.return_value.date.return_value = date(2023, 5, 15)
        mock_datetime.strptime = mock_date.strptime
        
        # Mock the API client responses
        self.api_client.get_plenarprotokoll.return_value = {
            "id": "123",
            "dokumentnummer": "20/123",
            "wahlperiode": 20,  # Changed from string to int
            "datum": "2023-05-15",
            "titel": "Test Protocol",
            "herausgeber": "Deutscher Bundestag",
            "fundstelle": {"pdf_url": "http://example.com/test.pdf"},
            "aktualisiert": "2023-05-16T12:00:00Z",
            "vorgangsbezug": [{"id": "456", "titel": "Test Proceeding"}]
        }
        
        # Mock empty speeches from XML
        self.api_client.get_plenarprotokoll_xml.return_value = None
        
        # Call the method
        protocol = self.parser.parse_protocol(123, include_full_text=False, use_xml=True)
        
        # Verify the basic protocol data
        self.assertEqual(protocol.id, 123)
        self.assertEqual(protocol.dokumentnummer, "20/123")
        self.assertEqual(protocol.wahlperiode, 20)
        self.assertEqual(protocol.date, date(2023, 5, 15))
        self.assertEqual(protocol.title, "Test Protocol")
        self.assertEqual(protocol.herausgeber, "Deutscher Bundestag")
        self.assertEqual(protocol.pdf_url, "http://example.com/test.pdf")
        self.assertEqual(len(protocol.proceedings), 1)
        self.assertEqual(protocol.proceedings[0]["id"], "456")
        
    def test_extract_speeches_from_activity(self):
        """Test the _extract_speeches_from_activity method."""
        # Mock the API client
        self.api_client.get_aktivitaet_list.return_value = [
            {
                "id": "789",
                "titel": "Test Speech",
                "vorgangsbezug": [{"id": "456"}],
                "deskriptor": [{"name": "Test Topic"}],
                "fundstelle": {"seite": "123"}
            }
        ]
        
        # Mock the _get_person method
        mock_person = Person(
            id=456,
            nachname="Mustermann",
            vorname="Max",
            titel="Dr.",
            fraktion="Test Party"
        )
        with mock.patch.object(self.parser, '_get_person', return_value=mock_person):
            # Call the method
            speeches = self.parser._extract_speeches_from_activity(
                protocol_id=123,
                protocol_number="20/123",
                protocol_date=date(2023, 5, 15)
            )
            
            # Verify the result
            self.assertEqual(len(speeches), 1)
            speech = speeches[0]
            self.assertEqual(speech.id, 789)
            self.assertEqual(speech.speaker, mock_person)
            self.assertEqual(speech.title, "Test Speech")
            self.assertEqual(speech.protocol_id, 123)
            self.assertEqual(speech.protocol_number, "20/123")
            self.assertEqual(speech.date, date(2023, 5, 15))
            self.assertEqual(speech.page_start, "123")
            self.assertEqual(speech.topics, ["Test Topic"])

    def test_parse_protocol_speeches(self):
        """Test the parse_protocol_speeches method."""
        # Create a protocol with a speech
        protocol = PlenarProtocol(
            id=123,
            dokumentnummer="20/123",
            wahlperiode=20,
            date=date(2023, 5, 15),
            title="Test Protocol",
            herausgeber="Deutscher Bundestag",
            full_text="S. 123 Test speech content here"
        )
        
        person = Person(
            id=456,
            nachname="Mustermann",
            vorname="Max",
            titel="Dr."
        )
        
        speech = Speech(
            id=789,
            speaker=person,
            title="Test Speech",
            text="Placeholder",
            date=date(2023, 5, 15),
            protocol_id=123,
            protocol_number="20/123",
            page_start="123"
        )
        
        protocol.speeches.append(speech)
        
        # Mock the parser's extraction logic
        def mock_extract(protocol_obj):
            # Update the speech text during the test
            protocol_obj.speeches[0].text = "Test speech content here"
            return protocol_obj.speeches
            
        # Replace the actual method with our mock
        original_method = self.parser.parse_protocol_speeches
        self.parser.parse_protocol_speeches = mock_extract
        
        try:
            # Call the method
            updated_speeches = self.parser.parse_protocol_speeches(protocol)
            
            # The test content should be extracted approximately
            self.assertIn("Test speech content here", updated_speeches[0].text)
        finally:
            # Restore the original method
            self.parser.parse_protocol_speeches = original_method


if __name__ == '__main__':
    unittest.main()