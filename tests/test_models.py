"""Tests for the data models."""
import unittest
from datetime import date, datetime

from bundestag_protocol_extractor.models.schema import Person, Speech, PlenarProtocol


class TestModels(unittest.TestCase):
    """Test cases for data models."""

    def test_person_model(self):
        """Test the Person model."""
        # Create a basic person
        person = Person(
            id=123,
            nachname="Mustermann",
            vorname="Max",
            titel="Dr.",
            fraktion="Test Party",
            funktion="Test Function",
            ressort="Test Department",
            bundesland="Berlin"
        )
        
        # Verify attributes
        self.assertEqual(person.id, 123)
        self.assertEqual(person.nachname, "Mustermann")
        self.assertEqual(person.vorname, "Max")
        self.assertEqual(person.titel, "Dr.")
        self.assertEqual(person.fraktion, "Test Party")
        self.assertEqual(person.funktion, "Test Function")
        self.assertEqual(person.ressort, "Test Department")
        self.assertEqual(person.bundesland, "Berlin")
        
    def test_speech_model(self):
        """Test the Speech model."""
        # Create a person for the speech
        person = Person(
            id=123,
            nachname="Mustermann",
            vorname="Max"
        )
        
        # Create a speech
        speech = Speech(
            id=456,
            speaker=person,
            title="Test Speech",
            text="This is a test speech.",
            date=date(2023, 5, 15),
            protocol_id=789,
            protocol_number="20/123",
            page_start="45",
            page_end="46",
            topics=["Topic 1", "Topic 2"],
            related_proceedings=[{"id": "101", "titel": "Test Proceeding"}]
        )
        
        # Verify attributes
        self.assertEqual(speech.id, 456)
        self.assertEqual(speech.speaker, person)
        self.assertEqual(speech.title, "Test Speech")
        self.assertEqual(speech.text, "This is a test speech.")
        self.assertEqual(speech.date, date(2023, 5, 15))
        self.assertEqual(speech.protocol_id, 789)
        self.assertEqual(speech.protocol_number, "20/123")
        self.assertEqual(speech.page_start, "45")
        self.assertEqual(speech.page_end, "46")
        self.assertEqual(len(speech.topics), 2)
        self.assertEqual(speech.topics[0], "Topic 1")
        self.assertEqual(speech.topics[1], "Topic 2")
        self.assertEqual(len(speech.related_proceedings), 1)
        self.assertEqual(speech.related_proceedings[0]["id"], "101")
        
    def test_plenarprotocol_model(self):
        """Test the PlenarProtocol model."""
        # Create a protocol
        protocol = PlenarProtocol(
            id=123,
            dokumentnummer="20/123",
            wahlperiode=20,
            date=date(2023, 5, 15),
            title="Test Protocol",
            herausgeber="Deutscher Bundestag",
            full_text="This is the full text of the protocol.",
            pdf_url="http://example.com/test.pdf",
            updated_at=datetime(2023, 5, 16, 12, 0, 0)
        )
        
        # Add speeches to the protocol
        person = Person(
            id=456,
            nachname="Mustermann",
            vorname="Max"
        )
        
        speech = Speech(
            id=789,
            speaker=person,
            title="Test Speech",
            text="This is a test speech.",
            date=date(2023, 5, 15),
            protocol_id=123,
            protocol_number="20/123"
        )
        
        protocol.speeches.append(speech)
        
        # Add proceedings
        protocol.proceedings.append({"id": "101", "titel": "Test Proceeding"})
        
        # Add TOC entries
        protocol.toc.append({
            "title": "Test Block",
            "entries": [
                {"content": "Test Entry", "page": "1"}
            ]
        })
        
        # Add agenda items
        protocol.agenda_items.append({
            "id": "top1",
            "text": "Test Agenda Item"
        })
        
        # Verify attributes
        self.assertEqual(protocol.id, 123)
        self.assertEqual(protocol.dokumentnummer, "20/123")
        self.assertEqual(protocol.wahlperiode, 20)
        self.assertEqual(protocol.date, date(2023, 5, 15))
        self.assertEqual(protocol.title, "Test Protocol")
        self.assertEqual(protocol.herausgeber, "Deutscher Bundestag")
        self.assertEqual(protocol.full_text, "This is the full text of the protocol.")
        self.assertEqual(protocol.pdf_url, "http://example.com/test.pdf")
        self.assertEqual(protocol.updated_at, datetime(2023, 5, 16, 12, 0, 0))
        
        # Verify nested objects
        self.assertEqual(len(protocol.speeches), 1)
        self.assertEqual(protocol.speeches[0].id, 789)
        self.assertEqual(protocol.speeches[0].speaker.id, 456)
        
        self.assertEqual(len(protocol.proceedings), 1)
        self.assertEqual(protocol.proceedings[0]["id"], "101")
        
        self.assertEqual(len(protocol.toc), 1)
        self.assertEqual(protocol.toc[0]["title"], "Test Block")
        self.assertEqual(len(protocol.toc[0]["entries"]), 1)
        self.assertEqual(protocol.toc[0]["entries"][0]["content"], "Test Entry")
        
        self.assertEqual(len(protocol.agenda_items), 1)
        self.assertEqual(protocol.agenda_items[0]["id"], "top1")
        self.assertEqual(protocol.agenda_items[0]["text"], "Test Agenda Item")


if __name__ == '__main__':
    unittest.main()