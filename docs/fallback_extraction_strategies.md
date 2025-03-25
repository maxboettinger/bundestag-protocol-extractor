# Fallback Extraction Strategies

This document describes the multi-strategy approach implemented for speech extraction from Bundestag protocols, following the Strategy Pattern design.

## Overview

The extraction system uses a tiered approach to extract speech content from protocols, automatically falling back to less precise methods when necessary. This ensures maximum content coverage while maintaining transparency about extraction quality.

## Extraction Strategies

### 1. XML-based Extraction (Primary Strategy)

- **Method**: Extracts structured speech content from XML data
- **Confidence Score**: 1.0 (highest)
- **Status**: "complete"
- **When Used**: When XML data is available for the protocol
- **Advantages**:
  - Highest accuracy and structure
  - Clearly identified speaker and speech boundaries
  - Includes structured metadata like comments, interjections
- **Limitations**:
  - XML not always available for all protocols
  - Some older protocols may use different XML schemas
  - API retrieval can occasionally fail

### 2. Pattern-based Extraction (First Fallback)

- **Method**: Uses pattern matching to identify speeches in raw text
- **Confidence Score**: 0.7 (medium)
- **Status**: "complete" or "partial" depending on boundaries
- **When Used**: When XML is unavailable but full text is available
- **Advantages**:
  - Works with standard text formats
  - Can identify speech boundaries with reasonable accuracy
  - Detects speaker names and structural elements
- **Patterns Used**:
  - `SPEAKER_PATTERN`: Identifies speaker names and introductions
  - `PAGE_MARKER`: Identifies page boundaries
  - `INTERJECTION_START`/`INTERJECTION_FULL`: Identifies comments and interjections
  - `SPEECH_END_MARKER`: Identifies speech conclusions
- **Limitations**:
  - Less precise than XML extraction
  - May occasionally merge adjacent speeches
  - Requires pattern recognition that can vary by protocol format

### 3. Page-based Extraction (Last Resort)

- **Method**: Extracts text sections around specified page numbers
- **Confidence Score**: 0.4 (low)
- **Status**: "complete" or "partial" depending on content
- **When Used**: When only page reference metadata is available
- **Advantages**:
  - Works with minimal metadata (just page numbers)
  - Always produces some content for analysis
  - Clearly labeled with extraction confidence
- **Limitations**:
  - Low precision, extracts page chunks rather than specific speeches
  - May include content from adjacent speeches
  - Requires manual verification for critical research

## Strategy Selection Process

1. The system first attempts XML extraction as the primary strategy
2. For speeches that couldn't be extracted with XML, the system attempts pattern matching
3. For remaining unextracted speeches, the system falls back to page-based extraction
4. Any speech that couldn't be extracted by any strategy is clearly marked as failed extraction

## Extraction Metadata

Each extracted speech includes detailed metadata:

- **extraction_method**: The method used ("xml", "pattern", "page", or "none")
- **extraction_status**: Status of extraction ("complete", "partial", or "failed")
- **extraction_confidence**: Confidence score from 0.0 to 1.0

## Using Extraction Metadata in Research

When using the extracted data for research:

1. **Filter by extraction method**:
   - For highest precision: `extraction_method == "xml"`
   - For good coverage: `extraction_method in ["xml", "pattern"]`
   - For maximum coverage: include all methods

2. **Filter by confidence threshold**:
   - High confidence threshold: `extraction_confidence >= 0.8`
   - Medium confidence threshold: `extraction_confidence >= 0.5`
   - Low confidence threshold: Include all

3. **Examine extraction status**:
   - For complete speeches: `extraction_status == "complete"`
   - For partial content: Include "partial" status with caution
   - Avoid failed extractions: Exclude `extraction_status == "failed"`

4. **Data quality reporting**: The exporter includes helper columns for pandas filtering:
   - `is_xml_extracted`: True for XML-extracted speeches
   - `is_complete`: True for completely extracted speeches
   - `is_high_confidence`: True for high-confidence extractions (score >= 0.8)

## Adding New Strategies

The system is designed for extensibility through the Strategy Pattern. New extraction strategies can be implemented by:

1. Creating a class that inherits from `ExtractionStrategy`
2. Implementing the `extract()` and `can_extract()` methods
3. Providing appropriate confidence scores and status indicators
4. Adding the strategy to the `ExtractionStrategyFactory`

This modular design allows the system to evolve with new extraction techniques while maintaining backward compatibility and consistent quality metrics.