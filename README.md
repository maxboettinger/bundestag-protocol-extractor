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
from bundestag_protocol_extractor import BundestagExtractor

# Initialize the extractor with your API key
extractor = BundestagExtractor(api_key="YOUR_API_KEY")

# Fetch protocols for a specific legislative period (20th Bundestag)
protocols = extractor.get_protocols(period=20, limit=5)  # Limit is optional

# Export to CSV (creates separate files for protocols, speeches, and persons)
extractor.export_to_csv(protocols, output_dir="./data")

# Export to JSON (creates a single JSON file with all data)
extractor.export_to_json(protocols, output_dir="./data")
```

### Command Line Interface

The package includes a command-line interface:

```bash
python extractor.py --api-key YOUR_API_KEY --period 20 --limit 5 --output-dir ./data --format both
```

## Data Structure

The extracted data is structured in a relational format:

1. **Protocols**: Basic metadata about each protocol
2. **Speeches**: Individual speeches with speaker information, text content, and metadata
3. **Persons**: Information about speakers, including party and role

## API Key

You need to register for an API key from the Bundestag DIP API. Visit [the official documentation](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) for information on how to obtain a key.

## Documentation

For full documentation, see [the docs](https://bundestag-protocol-extractor.readthedocs.io/).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
