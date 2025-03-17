# Bundestag Protocol Extractor

A Python package that extracts and structures information from the German Bundestag's open data API. This package allows researchers and analysts to access parliamentary protocols in a structured format suitable for analysis.

## Features

- Extract plenar protocols from the Bundestag API
- Convert protocols into structured, machine-readable formats
- Extract speeches with speaker metadata (name, party, role)
- Access topic information and related proceedings
- Export data to CSV and JSON for easy analysis
- Rich metadata extraction (speakers, parties, topics, etc.)
- Flexible and modular architecture
- Robust handling of API rate limiting with exponential backoff
- Comprehensive logging system with configurable verbosity
- Automatic progress tracking for long-running extractions
- Job resumption capabilities for interrupted extractions

## Installation

### Using pip

```bash
pip install bundestag-protocol-extractor
```

### Using conda

```bash
conda env create -f environment.yml
conda activate bundestag-protocol-extractor
pip install -e .
```

## Usage

### As a Python Package

```python
from extractor import BundestagExtractor
from bundestag_protocol_extractor.utils.logging import setup_logging
import logging

# Set up logging
setup_logging(log_level=logging.INFO)

# Initialize the extractor with your API key
extractor = BundestagExtractor(api_key="YOUR_API_KEY")

# Fetch protocols for a specific legislative period (20th Bundestag)
protocols = extractor.get_protocols(period=20, limit=5)  # Limit is optional

# Export to CSV (creates separate files for protocols, speeches, and persons)
exported_files = extractor.export_to_csv(
    protocols, 
    output_dir="./data",
    include_speech_text=True
)

# Export to JSON (creates a single JSON file with all data)
json_path = extractor.export_to_json(protocols, output_dir="./data")
```

### Advanced Usage with Progress Tracking

For long-running extractions, you can use the progress tracking system:

```python
from extractor import BundestagExtractor
from bundestag_protocol_extractor.utils.logging import setup_logging
from bundestag_protocol_extractor.utils.progress import ProgressTracker
import logging

# Set up detailed logging
setup_logging(log_level=logging.DEBUG, console_level=logging.INFO)

# Initialize the extractor
extractor = BundestagExtractor(
    api_key="YOUR_API_KEY",
    retry_delay=1.0,
    max_retries=5
)

# List available progress files to potentially resume
progress = ProgressTracker(wahlperiode=20, output_dir="./output")
available_progress = progress.list_available_progress_files()
for p in available_progress:
    print(f"Progress file: {p['file_path']}, Completed: {p['completed_count']}/{p['total_protocols']}")

# Extract with various options
protocols = extractor.get_protocols(
    period=20,
    limit=10,
    offset=0,
    use_xml=True,
    # To resume from a specific progress file:
    # resume_from="/path/to/progress_file.json"
)

# Export with full options
exported_files = extractor.export_to_csv(
    protocols,
    include_speech_text=True,
    include_full_protocols=False,
    include_paragraphs=True,
    include_comments=True
)
```

### Command Line Interface

The package includes a command-line interface that can be used in two ways:

Using the installed package:
```bash
bpe --api-key YOUR_API_KEY --period 20 --limit 5 --output-dir ./data --format both
```

Or directly from the source:
```bash
python extractor.py --api-key YOUR_API_KEY --period 20 --limit 5 --output-dir ./data --format both
```

#### Logging Options

The CLI provides several logging options:

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

#### Progress Tracking and Resumption

The extractor supports automatic progress tracking and job resumption:

```bash
# List available progress files
bpe --list-progress

# Resume from a specific progress file
bpe --resume /path/to/progress_file.json

# Resume from a specific protocol
bpe --resume-from "20/123"

# Resume from a specific index
bpe --index 50

# Skip first N protocols
bpe --offset 25
```

## Data Structure

The extracted data is structured in a relational format with multiple CSV files:

### Core Files
1. **protocols.csv**: Basic information about each plenarprotocol (date, title, metadata)
2. **speeches.csv**: Individual speeches with speaker references and content
3. **persons.csv**: Information about speakers (MPs, ministers, etc.) including party and role
4. **proceedings.csv**: Proceedings referenced in the protocols
5. **speech_topics.csv**: Topics associated with each speech (many-to-many relationship)

### Detailed Analysis Files (XML-based)
6. **paragraphs.csv**: Individual paragraphs within speeches for detailed text analysis
7. **comments.csv**: Comments and interjections in the protocols 
8. **agenda_items.csv**: Agenda items for each session
9. **toc.csv**: Table of contents entries with detailed document structure

### Relationships
- Each speech belongs to one protocol (protocol_id in speeches.csv)
- Each speech has one speaker (speaker_id in speeches.csv)
- Each speech consists of multiple paragraphs (speech_id in paragraphs.csv)
- Each speech can have multiple topics (speech_id in speech_topics.csv)
- Each speech can have multiple comments (speech_id in comments.csv)

## API Key

You need to register for an API key from the Bundestag DIP API. Visit [the official documentation](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) for information on how to obtain a key.

## Documentation

For full documentation, see [the docs](https://bundestag-protocol-extractor.readthedocs.io/).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
