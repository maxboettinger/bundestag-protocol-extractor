"""
Test module to ensure all package modules can be imported properly.
This helps detect packaging issues where some modules might be missing.
"""

import importlib
import os
import pkgutil
import sys
from pathlib import Path


def test_all_modules_importable():
    """Test that all modules in the package are importable."""
    # Get the root directory of the package
    package_name = "bundestag_protocol_extractor"
    package_dir = Path(__file__).parent.parent / package_name

    # List to store any import errors
    import_errors = []

    # Walk through all Python modules in the package
    for root, dirs, files in os.walk(package_dir):
        root_path = Path(root)
        relative_path = root_path.relative_to(package_dir.parent)

        # Convert path to module notation
        module_prefix = str(relative_path).replace(os.path.sep, ".")

        # Try to import each Python file
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                module_name = f"{module_prefix}.{file[:-3]}"
                try:
                    importlib.import_module(module_name)
                except ImportError as e:
                    import_errors.append((module_name, str(e)))

    # Check if there were any import errors
    assert (
        not import_errors
    ), f"The following modules had import errors: {import_errors}"


def test_package_structure():
    """Test that the package has the expected structure with required modules."""
    # Define the minimum required modules/packages that should be part of the package
    required_modules = [
        "bundestag_protocol_extractor.api.client",
        "bundestag_protocol_extractor.extractor",
        "bundestag_protocol_extractor.models.schema",
        "bundestag_protocol_extractor.parsers.protocol_parser",
        "bundestag_protocol_extractor.utils.exporter",
        "bundestag_protocol_extractor.utils.logging",  # Critical module that was missing
        "bundestag_protocol_extractor.utils.progress",
        "bundestag_protocol_extractor.cli",
    ]

    # Try to import each required module
    missing_modules = []
    for module in required_modules:
        try:
            importlib.import_module(module)
        except ImportError as e:
            missing_modules.append((module, str(e)))

    # Check if any required modules are missing
    assert (
        not missing_modules
    ), f"The following required modules are missing: {missing_modules}"
