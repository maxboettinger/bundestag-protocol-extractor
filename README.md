# Bundestag Protocol Extractor

[![PyPI version](https://img.shields.io/pypi/v/bundestag-protocol-extractor.svg)](https://pypi.org/project/bundestag-protocol-extractor/)
[![Python Versions](https://img.shields.io/pypi/pyversions/bundestag-protocol-extractor.svg)](https://pypi.org/project/bundestag-protocol-extractor/)
[![License](https://img.shields.io/pypi/l/bundestag-protocol-extractor.svg)](https://github.com/maxboettinger/bundestag-protocol-extractor/blob/main/LICENSE)
[![Tests](https://github.com/maxboettinger/bundestag-protocol-extractor/actions/workflows/test.yml/badge.svg)](https://github.com/maxboettinger/bundestag-protocol-extractor/actions/workflows/test.yml)

Extract and structure data from the German Bundestag's parliamentary protocols using the official DIP API.

## 🚀 Quick Start

### Installation

```bash
pip install bundestag-protocol-extractor
```

### Command Line Usage

```bash
# Extract protocols from the 20th legislative period, limit to 5
bpe --period 20 --limit 5 --output-dir ./data

# Export to both CSV and JSON format
bpe --period 20 --limit 5 --format both

# Use a specific API key (optional, package includes a public key)
bpe --api-key YOUR_API_KEY --period 20 --limit 5
```

## 🔍 Overview

This package allows researchers, journalists, and political analysts to access German parliamentary protocols (plenarprotokolle) in a structured format suitable for analysis. It extracts speeches, speaker metadata, topics, and related information from the Bundestag's official API.

## ✨ Features

- **Extract Protocols**: Access plenarprotokolle from all legislative periods
- **Structure Content**: Extract individual speeches with rich metadata
- **Speaker Metadata**: Get information about speakers (name, party, role)
- **Topic Analysis**: Access topic information and related proceedings
- **Multiple Export Formats**: Export to CSV and JSON for easy analysis
- **Automatic Rate Limiting**: Robust handling of API limits with exponential backoff
- **Progress Tracking**: Resume long-running extractions if interrupted
- **Flexible Configuration**: Fine-tune extraction parameters based on your needs

## 📋 Detailed Usage

### Command Line Interface

```bash
# Basic usage
bpe --period 20 --limit 5 --output-dir ./data

# List help and all available options
bpe --help

# Extract all protocols from the current legislative period
bpe --period 20 --output-dir ./data

# Use XML parsing for more detailed extraction (default)
bpe --period 20 --use-xml

# Disable XML parsing (faster but less detailed)
bpe --period 20 --no-xml
```

#### Control Output Format

```bash
# Export to CSV (default)
bpe --period 20 --format csv

# Export to JSON
bpe --period 20 --format json

# Export to both formats
bpe --period 20 --format both

# Exclude full speech text to reduce file size
bpe --period 20 --exclude-speech-text

# Include full protocol text (large files)
bpe --period 20 --include-full-protocols
```

#### Logging Options

```bash
# Enable verbose output (INFO to console, DEBUG to log file)
bpe --period 20 --verbose

# Enable full debug logging (DEBUG to both console and log file)
bpe --period 20 --debug

# Quiet mode (WARNING to console, INFO to log file)
bpe --period 20 --quiet

# Specify custom log file
bpe --period 20 --log-file /path/to/custom/log/file.log
```

#### Progress Tracking & Resumption

```bash
# List available progress files
bpe --list-progress

# Resume from a specific progress file
bpe --resume /path/to/progress_file.json

# Resume from a specific protocol
bpe --resume-from "20/123"

# Skip first N protocols
bpe --offset 25
```

### Python API

You can also use the package directly in your Python code:

```python
from bundestag_protocol_extractor import BundestagExtractor
import logging

# Initialize the extractor (uses default public API key)
extractor = BundestagExtractor()

# Or with your own API key
# extractor = BundestagExtractor(api_key="YOUR_API_KEY")

# Fetch protocols for a specific legislative period (20th Bundestag)
protocols = extractor.get_protocols(period=20, limit=5)

# Export to CSV (creates separate files for protocols, speeches, etc.)
exported_files = extractor.export_to_csv(
    protocols,
    output_dir="./data",
    include_speech_text=True
)

# Export to JSON (creates a single JSON file with all data)
json_path = extractor.export_to_json(protocols, output_dir="./data")
```

## 📊 Data Structure

The extracted data is organized in a relational format with multiple CSV files:

### Core Files

1. **protocols.csv**: Basic protocol metadata (date, title, etc.)
2. **speeches.csv**: Individual speeches with speaker references
3. **persons.csv**: Speaker information (name, party, role)
4. **proceedings.csv**: Related parliamentary proceedings
5. **speech_topics.csv**: Topics associated with each speech

### Detailed Files (XML-based)

6. **paragraphs.csv**: Individual paragraphs for detailed text analysis
7. **comments.csv**: Comments and interjections
8. **agenda_items.csv**: Agenda items for each session
9. **toc.csv**: Table of contents with document structure

## 🔑 API Key

The package includes a public API key with limited rate allowance. For extensive usage, register for your own API key from the Bundestag DIP API:

Visit: [Dokumentations- und Informationssystems für Parlamentsmaterialien (DIP) API Documentation](https://dip.bundestag.de/über-dip/hilfe/api)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
