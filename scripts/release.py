#!/usr/bin/env python
"""
Release script for bundestag-protocol-extractor.

This script automates the process of creating a new release:
1. Updates version numbers
2. Creates git tag
3. Builds distribution packages
4. Uploads to PyPI (with confirmation)

Usage:
    python scripts/release.py [major|minor|patch]
"""
import os
import re
import sys
import subprocess
from pathlib import Path
import argparse
from typing import Tuple, List

# Ensure we're in the project root
project_root = Path(__file__).parent.parent.absolute()
os.chdir(project_root)

# Define paths
INIT_PATH = "bundestag_protocol_extractor/__init__.py"
PYPROJECT_PATH = "pyproject.toml"


def get_current_version() -> Tuple[int, int, int]:
    """Get current version from __init__.py."""
    with open(INIT_PATH, "r") as f:
        content = f.read()
        version_match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', content)
        if not version_match:
            raise ValueError(f"Could not find version in {INIT_PATH}")
        return tuple(map(int, version_match.groups()))


def bump_version(current_version: Tuple[int, int, int], bump_type: str) -> Tuple[int, int, int]:
    """Bump version based on bump_type (major, minor, patch)."""
    major, minor, patch = current_version
    
    if bump_type == "major":
        return (major + 1, 0, 0)
    elif bump_type == "minor":
        return (major, minor + 1, 0)
    elif bump_type == "patch":
        return (major, minor, patch + 1)
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def update_version_in_files(new_version: Tuple[int, int, int]) -> None:
    """Update version in __init__.py and pyproject.toml."""
    version_str = f"{new_version[0]}.{new_version[1]}.{new_version[2]}"
    
    # Update __init__.py
    with open(INIT_PATH, "r") as f:
        content = f.read()
    
    new_content = re.sub(
        r'__version__ = "\d+\.\d+\.\d+"',
        f'__version__ = "{version_str}"',
        content
    )
    
    with open(INIT_PATH, "w") as f:
        f.write(new_content)
    
    # Update pyproject.toml
    with open(PYPROJECT_PATH, "r") as f:
        content = f.read()
    
    new_content = re.sub(
        r'version = "\d+\.\d+\.\d+"',
        f'version = "{version_str}"',
        content
    )
    
    with open(PYPROJECT_PATH, "w") as f:
        f.write(new_content)
    
    print(f"Updated version to {version_str} in files")


def run_command(command: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(command)}")
    return subprocess.run(command, check=check)


def create_git_tag(version: Tuple[int, int, int]) -> None:
    """Create a git tag for the new version."""
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    tag = f"v{version_str}"
    
    # Check if tag exists
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True,
        text=True,
        check=True
    )
    
    if tag in result.stdout.strip().split("\n"):
        print(f"Tag {tag} already exists")
        return
    
    # Create tag
    run_command(["git", "tag", "-a", tag, "-m", f"Release {version_str}"])
    print(f"Created git tag: {tag}")


def commit_version_changes(version: Tuple[int, int, int]) -> None:
    """Commit version changes to git."""
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    
    # Add files
    run_command(["git", "add", INIT_PATH, PYPROJECT_PATH])
    
    # Commit
    run_command([
        "git", "commit", "-m", f"Bump version to {version_str}"
    ])
    
    print(f"Committed version changes for {version_str}")


def build_package() -> None:
    """Build the package."""
    # Clean dist directory
    if os.path.exists("dist"):
        for file in os.listdir("dist"):
            os.unlink(os.path.join("dist", file))
    
    # Build package
    run_command(["python", "-m", "build"])
    print("Built distribution packages")


def upload_to_pypi(test: bool = False) -> None:
    """Upload the package to PyPI."""
    if test:
        run_command(["twine", "upload", "--repository", "testpypi", "dist/*"])
        print("Uploaded to TestPyPI")
    else:
        run_command(["twine", "upload", "dist/*"])
        print("Uploaded to PyPI")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Release script for bundestag-protocol-extractor")
    parser.add_argument(
        "bump",
        choices=["major", "minor", "patch"],
        help="Version part to bump"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually make changes, just print what would happen"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Upload to TestPyPI instead of PyPI"
    )
    args = parser.parse_args()
    
    # Get current version
    current_version = get_current_version()
    print(f"Current version: {current_version[0]}.{current_version[1]}.{current_version[2]}")
    
    # Bump version
    new_version = bump_version(current_version, args.bump)
    version_str = f"{new_version[0]}.{new_version[1]}.{new_version[2]}"
    print(f"New version: {version_str}")
    
    if args.dry_run:
        print("Dry run, not making changes")
        return
    
    # Ensure we have necessary tools
    try:
        run_command(["pip", "install", "build", "twine"])
    except subprocess.CalledProcessError:
        print("Failed to install build and twine. Please install them manually.")
        return
    
    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True
    )
    
    if result.stdout.strip() and not ("bundestag_protocol_extractor/__init__.py" in result.stdout and "pyproject.toml" in result.stdout):
        print("There are uncommitted changes. Please commit or stash them before releasing.")
        return
    
    # Update version in files
    update_version_in_files(new_version)
    
    # Commit changes
    commit_version_changes(new_version)
    
    # Create git tag
    create_git_tag(new_version)
    
    # Build package
    build_package()
    
    # Ask for confirmation before uploading
    if args.test:
        destination = "TestPyPI"
    else:
        destination = "PyPI"
    
    response = input(f"Ready to upload to {destination}. Continue? [y/N] ")
    if response.lower() != "y":
        print("Aborted upload")
        return
    
    # Upload to PyPI
    upload_to_pypi(test=args.test)
    
    # Push changes and tag to remote
    push_response = input("Push changes and tag to remote? [y/N] ")
    if push_response.lower() == "y":
        run_command(["git", "push"])
        run_command(["git", "push", "--tags"])
        print("Pushed changes and tag to remote")
    
    print(f"✨ Released version {version_str}")
    
    # Suggest creating GitHub release
    print("\nNext steps:")
    print(f"1. Create a GitHub release at: https://github.com/maxboettinger/bundestag-protocol-extractor/releases/new?tag=v{version_str}")
    print("2. Add release notes and publish")
    print(f"3. Verify the package is available: pip install bundestag-protocol-extractor=={version_str}")


if __name__ == "__main__":
    main()