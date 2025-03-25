"""
Pattern-based extraction strategy for protocol speech text.

This module provides an extraction strategy that uses text patterns
to extract speech content with medium fidelity.
"""

import re
from typing import Any, Dict, List, Match, Optional, Tuple

from bundestag_protocol_extractor.models.schema import PlenarProtocol, Speech
from bundestag_protocol_extractor.parsers.extraction_strategies.base_strategy import (
    ExtractionStrategy,
)
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class PatternExtractionStrategy(ExtractionStrategy):
    """Pattern-based extraction strategy for speeches."""

    # Common patterns found in Bundestag protocols
    SPEAKER_PATTERN = r"(?:(?:Abg\.|Abgeordnete[r]?|Bundesminister(?:in)?|Präsident(?:in)?|Vizepräsident(?:in)?|Staatsminister(?:in)?)\s+)?([A-Z][a-zäöüß]+(?:\s+[a-zäöüß]+)?\s+[A-ZÄÖÜ][a-zäöüß]+)(?:\s+\([A-Za-zÄÖÜäöüß/\s]+\))?:"
    PAGE_MARKER = (
        r"Deutscher Bundestag[\s–-]+\d+\.\s+Wahlperiode[\s–-]+(\d+)\.\s+Sitzung\."
    )
    INTERJECTION_START = r"\((?:Beifall|\s*Zuruf|Lachen|Heiterkeit|Widerspruch)"
    INTERJECTION_FULL = r"\([^)]{2,100}\)"
    SPEECH_END_MARKER = (
        r"(?:Vielen|Herzlichen)?\s*Dank(?:\s*für\s*[Ii]hre\s*Aufmerksamkeit)?\.?"
    )

    def __init__(self):
        """Initialize the pattern extraction strategy."""
        super().__init__(name="pattern", confidence=0.7)

    def can_extract(self, protocol: PlenarProtocol) -> bool:
        """
        Check if pattern extraction is possible for this protocol.

        Args:
            protocol: The protocol to check

        Returns:
            True if full text is available, False otherwise
        """
        return protocol.full_text is not None and len(protocol.full_text) > 0

    def extract(self, protocol: PlenarProtocol, speeches: List[Speech]) -> List[Speech]:
        """
        Extract speech text using pattern matching.

        Args:
            protocol: The protocol containing the full text
            speeches: List of speeches with basic metadata

        Returns:
            Updated list of speeches with extracted text
        """
        logger.info(
            f"Extracting speeches using pattern strategy for protocol {protocol.dokumentnummer}"
        )

        if not self.can_extract(protocol):
            logger.warning("Pattern extraction failed: no full text available")
            return speeches

        full_text = protocol.full_text

        # Create a page index mapping to help with navigation
        page_indices = self._create_page_index(full_text)

        # Find all potential speaker starts
        speaker_matches = list(re.finditer(self.SPEAKER_PATTERN, full_text))

        # Process each speech
        for speech in speeches:
            # Get the speaker information
            speaker_name = f"{speech.speaker.vorname} {speech.speaker.nachname}".strip()
            speaker_last_name = speech.speaker.nachname

            # Start with page information if available
            if speech.page_start and speech.page_start in page_indices:
                # Get the start index for this page
                start_idx = page_indices[speech.page_start]

                # Try to find the speaker name near this page
                speaker_idx = self._find_speaker_near_page(
                    full_text,
                    speaker_matches,
                    speaker_name,
                    speaker_last_name,
                    start_idx,
                )

                if speaker_idx != -1:
                    # Found speaker reference, now extract the speech content
                    speech_text, is_partial = self._extract_speech_content(
                        full_text, speaker_idx, speaker_matches, speaker_name
                    )

                    if speech_text:
                        speech.text = speech_text
                        metadata = self.get_extraction_metadata(True, is_partial)
                        speech.extraction_method = metadata["extraction_method"]
                        speech.extraction_status = metadata["extraction_status"]
                        speech.extraction_confidence = metadata["extraction_confidence"]

                        # Calculate additional confidence based on text quality
                        if not is_partial:
                            # Check speech length (normalize to 0.0-0.2 range)
                            length_factor = min(len(speech_text) / 5000, 1.0) * 0.2

                            # Check for interjections (good indicator of speech boundaries)
                            interjection_count = len(
                                re.findall(self.INTERJECTION_FULL, speech_text)
                            )
                            interjection_factor = min(interjection_count / 5, 1.0) * 0.1

                            # Apply the confidence adjustments
                            speech.extraction_confidence += (
                                length_factor + interjection_factor
                            )

                            # Cap at base confidence
                            speech.extraction_confidence = min(
                                speech.extraction_confidence, self.base_confidence
                            )

                        continue

            # If we didn't find the speech by page, try searching the entire document
            speaker_idx = self._find_speaker_in_document(
                full_text, speaker_matches, speaker_name, speaker_last_name
            )

            if speaker_idx != -1:
                # Found speaker reference, now extract the speech content
                speech_text, is_partial = self._extract_speech_content(
                    full_text, speaker_idx, speaker_matches, speaker_name
                )

                if speech_text:
                    speech.text = speech_text
                    metadata = self.get_extraction_metadata(True, is_partial)
                    speech.extraction_method = metadata["extraction_method"]
                    speech.extraction_status = metadata["extraction_status"]
                    speech.extraction_confidence = (
                        metadata["extraction_confidence"] * 0.9
                    )  # Slightly lower confidence when not using page
                    continue

            # If we get here, we couldn't extract the speech
            metadata = self.get_extraction_metadata(False)
            speech.extraction_method = metadata["extraction_method"]
            speech.extraction_status = metadata["extraction_status"]
            speech.extraction_confidence = metadata["extraction_confidence"]

            # Set standard placeholder
            page_ref = speech.page_start or "unknown"
            speech.text = f"[EXTRACTION_FAILED:NO_PATTERN_MATCH] Speech referenced at page {page_ref}, speaker: {speaker_name}"

        return speeches

    def _create_page_index(self, text: str) -> Dict[str, int]:
        """
        Create an index of page numbers to their positions in the text.

        Args:
            text: Full protocol text

        Returns:
            Dictionary mapping page numbers to their position in the text
        """
        page_indices = {}

        # Find all page markers
        for match in re.finditer(self.PAGE_MARKER, text):
            page_num = match.group(1)
            # Map both string and integer versions
            page_indices[page_num] = match.start()
            page_indices[int(page_num)] = match.start()

        return page_indices

    def _find_speaker_near_page(
        self,
        text: str,
        speaker_matches: List[Match],
        speaker_name: str,
        speaker_last_name: str,
        page_start_idx: int,
    ) -> int:
        """
        Find a speaker reference near a specific page.

        Args:
            text: Full protocol text
            speaker_matches: List of regex matches for all speakers
            speaker_name: Full name of the speaker to find
            speaker_last_name: Last name of the speaker
            page_start_idx: Start index of the page in the text

        Returns:
            Index of the speaker mention or -1 if not found
        """
        # Look in a window around the page start (± 30000 chars)
        window_start = max(0, page_start_idx - 10000)
        window_end = min(len(text), page_start_idx + 20000)

        # Find potential matches in this window
        candidates = []

        for match in speaker_matches:
            if window_start <= match.start() <= window_end:
                full_match = match.group(0)
                captured_name = match.group(1)

                # Check for name match
                if self._is_name_match(captured_name, speaker_name, speaker_last_name):
                    candidates.append((match.start(), captured_name))

        # Return the first match or -1 if none found
        return candidates[0][0] if candidates else -1

    def _find_speaker_in_document(
        self,
        text: str,
        speaker_matches: List[Match],
        speaker_name: str,
        speaker_last_name: str,
    ) -> int:
        """
        Find a speaker reference anywhere in the document.

        Args:
            text: Full protocol text
            speaker_matches: List of regex matches for all speakers
            speaker_name: Full name of the speaker to find
            speaker_last_name: Last name of the speaker

        Returns:
            Index of the speaker mention or -1 if not found
        """
        candidates = []

        for match in speaker_matches:
            captured_name = match.group(1)

            # Check for name match
            if self._is_name_match(captured_name, speaker_name, speaker_last_name):
                candidates.append((match.start(), captured_name))

        # Return the first match or -1 if none found
        return candidates[0][0] if candidates else -1

    def _is_name_match(
        self, captured_name: str, speaker_name: str, speaker_last_name: str
    ) -> bool:
        """
        Check if a captured name matches the speaker name.

        Args:
            captured_name: Name captured from regex
            speaker_name: Full speaker name
            speaker_last_name: Speaker's last name

        Returns:
            True if the names match, False otherwise
        """
        # Convert to lowercase for comparison
        captured_lower = captured_name.lower()
        speaker_lower = speaker_name.lower()
        last_name_lower = speaker_last_name.lower()

        # Check for exact match
        if captured_lower == speaker_lower:
            return True

        # Check if last name is present
        if last_name_lower and last_name_lower in captured_lower:
            return True

        # Check for partial match (at least 70% similarity)
        if speaker_lower and self._text_similarity(captured_lower, speaker_lower) > 0.7:
            return True

        return False

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using character overlap.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0

        # Simple character-based similarity
        shorter = text1 if len(text1) <= len(text2) else text2
        longer = text2 if len(text1) <= len(text2) else text1

        # Count matching characters
        matches = sum(1 for char in shorter if char in longer)

        return matches / len(longer)

    def _extract_speech_content(
        self,
        text: str,
        speaker_idx: int,
        speaker_matches: List[Match],
        speaker_name: str,
    ) -> Tuple[str, bool]:
        """
        Extract speech content starting from a speaker mention.

        Args:
            text: Full protocol text
            speaker_idx: Index of the speaker mention
            speaker_matches: List of all speaker mentions
            speaker_name: Name of the speaker

        Returns:
            Tuple of (extracted_text, is_partial)
        """
        # Start from the speaker introduction (skip the colon)
        colon_idx = text.find(":", speaker_idx)
        if colon_idx == -1:
            start_idx = speaker_idx
        else:
            start_idx = colon_idx + 1

        # Find the end of the speech
        # Option 1: Another speaker starts
        next_speaker_idx = len(text)

        for match in speaker_matches:
            if match.start() > start_idx:
                next_speaker_idx = match.start()
                break

        # Option 2: End of speech marker
        end_markers = ["Vielen Dank.", "Herzlichen Dank.", "Ich danke Ihnen."]
        end_marker_idx = next_speaker_idx

        for marker in end_markers:
            idx = text.find(marker, start_idx, next_speaker_idx)
            if idx != -1:
                # Found an end marker before the next speaker
                end_marker_idx = min(end_marker_idx, idx + len(marker))

        # Also look for the regex pattern
        end_match = re.search(self.SPEECH_END_MARKER, text[start_idx:next_speaker_idx])
        if end_match:
            end_match_idx = start_idx + end_match.end()
            end_marker_idx = min(end_marker_idx, end_match_idx)

        # Determine the end index and whether it's partial
        end_idx = min(next_speaker_idx, end_marker_idx)
        is_partial = end_idx == next_speaker_idx and end_marker_idx == next_speaker_idx

        # Extract the text
        speech_text = text[start_idx:end_idx].strip()

        # Check if the extracted text is reasonable
        if len(speech_text) < 50:
            # Too short to be a real speech
            return "", True

        # Clean up the speech text
        speech_text = self._clean_speech_text(speech_text)

        return speech_text, is_partial

    def _clean_speech_text(self, text: str) -> str:
        """
        Clean up extracted speech text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned speech text
        """
        # Remove leading/trailing whitespace
        text = text.strip()

        # Remove multiple consecutive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove page headers/footers
        text = re.sub(self.PAGE_MARKER, "", text)

        # Format interjections consistently
        def format_interjection(match):
            interjection = match.group(0)
            if not interjection.endswith(")"):
                interjection = interjection + ")"
            return "\n" + interjection + "\n"

        text = re.sub(self.INTERJECTION_FULL, format_interjection, text)

        return text
