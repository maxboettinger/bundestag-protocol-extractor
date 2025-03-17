"""
Command line interface for the Bundestag Protocol Extractor.

This module provides a command-line entry point for the package,
allowing it to be used as a console script.
"""
import sys
from bundestag_protocol_extractor.utils.logging import get_logger
from extractor import main as extractor_main

logger = get_logger(__name__)


def main():
    """
    Main entry point for the CLI.
    
    This function is registered as a console script in setup.py,
    allowing the package to be run with the 'bpe' command.
    """
    try:
        # Call the main function from extractor.py
        extractor_main()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())