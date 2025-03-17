"""
Main module for directly executing the package.

This allows running the package with:
python -m bundestag_protocol_extractor

It simply forwards to the CLI main function.
"""
import sys
from bundestag_protocol_extractor.cli import main

if __name__ == "__main__":
    sys.exit(main())