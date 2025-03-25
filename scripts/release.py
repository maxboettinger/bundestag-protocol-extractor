#!/usr/bin/env python
"""
Release script for bundestag-protocol-extractor.

This script automates the process of creating a new release:
1. Validates the project and runs tests
2. Updates version numbers
3. Builds and verifies distribution packages
4. Creates git tag and commits changes
5. Uploads to PyPI (with confirmation)

Usage:
    python scripts/release.py [major|minor|patch]
"""
import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Ensure we're in the project root
project_root = Path(__file__).parent.parent.absolute()
os.chdir(project_root)

# Define paths
INIT_PATH = "bundestag_protocol_extractor/__init__.py"
PYPROJECT_PATH = "pyproject.toml"


class ReleaseStep(Enum):
    """Enumeration of steps in the release process."""
    PREPARE = "prepare"
    LINT = "lint"
    TEST = "test"
    VERSION = "version"
    BUILD = "build"
    VERIFY = "verify"
    TAG = "tag"
    UPLOAD = "upload"
    PUBLISH = "publish"


class ReleaseError(Exception):
    """Exception raised when a release step fails."""
    def __init__(self, step: ReleaseStep, message: str):
        self.step = step
        self.message = message
        super().__init__(f"Error in {step.value} step: {message}")


class ReleaseManager:
    """Manages the release process for bundestag-protocol-extractor."""

    def __init__(self, bump_type: str, dry_run: bool = False, test_pypi: bool = False):
        """Initialize the release manager.
        
        Args:
            bump_type: Type of version bump ('major', 'minor', or 'patch')
            dry_run: If True, don't make any changes
            test_pypi: If True, upload to TestPyPI instead of PyPI
        """
        self.bump_type = bump_type
        self.dry_run = dry_run
        self.test_pypi = test_pypi
        self.current_version: Optional[Tuple[int, int, int]] = None
        self.new_version: Optional[Tuple[int, int, int]] = None
        self.version_str: Optional[str] = None
        self.tag_created = False
        self.changes_committed = False
        self.temp_dir: Optional[Path] = None
    
    def run_command(self, command: List[str], check: bool = True, 
                   capture_output: bool = False) -> subprocess.CompletedProcess:
        """Run a command and return the result.
        
        Args:
            command: Command to run
            check: If True, raise an exception if the command fails
            capture_output: If True, capture the command output
            
        Returns:
            The completed process
        """
        print(f"Running: {' '.join(command)}")
        return subprocess.run(
            command, 
            check=check, 
            capture_output=capture_output,
            text=capture_output
        )

    def get_current_version(self) -> Tuple[int, int, int]:
        """Get current version from __init__.py.
        
        Returns:
            The current version as a tuple (major, minor, patch)
        """
        with open(INIT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            version_match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', content)
            if not version_match:
                raise ReleaseError(ReleaseStep.PREPARE, f"Could not find version in {INIT_PATH}")
            return tuple(map(int, version_match.groups()))

    def bump_version(self, current_version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Bump version based on bump_type.
        
        Args:
            current_version: Current version as a tuple (major, minor, patch)
            
        Returns:
            The new version as a tuple (major, minor, patch)
        """
        major, minor, patch = current_version

        if self.bump_type == "major":
            return (major + 1, 0, 0)
        elif self.bump_type == "minor":
            return (major, minor + 1, 0)
        elif self.bump_type == "patch":
            return (major, minor, patch + 1)
        else:
            raise ReleaseError(ReleaseStep.VERSION, f"Invalid bump type: {self.bump_type}")

    def update_version_in_files(self, new_version: Tuple[int, int, int]) -> None:
        """Update version in __init__.py and pyproject.toml.
        
        Args:
            new_version: New version as a tuple (major, minor, patch)
        """
        if self.dry_run:
            print("Dry run: would update version in files")
            return
            
        version_str = f"{new_version[0]}.{new_version[1]}.{new_version[2]}"

        # Update __init__.py
        with open(INIT_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = re.sub(
            r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{version_str}"', content
        )

        with open(INIT_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Update pyproject.toml
        with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = re.sub(
            r'version = "\d+\.\d+\.\d+"', f'version = "{version_str}"', content
        )

        with open(PYPROJECT_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Updated version to {version_str} in files")

    def run_linting(self) -> bool:
        """Run linting checks on the codebase.
        
        Returns:
            True if linting passes, False otherwise
        """
        print("Running linting checks...")
        try:
            # Run Black
            self.run_command(["black", "--check", "."])
            
            # Run isort
            self.run_command(["isort", "--check", "."])
            
            # Run flake8
            self.run_command(["flake8", "."])
            
            # Run mypy
            self.run_command(["mypy", "."])
            
            print("✅ Linting checks passed")
            return True
        except subprocess.CalledProcessError:
            print("❌ Linting checks failed! Fix the issues before releasing.")
            return False

    def run_tests(self) -> bool:
        """Run tests to ensure package quality before release.
        
        Returns:
            True if tests pass, False otherwise
        """
        print("Running tests before release...")
        
        # Run all tests with pytest
        try:
            print("Running pytest suite...")
            self.run_command(["pytest", "-xvs"])
        except subprocess.CalledProcessError:
            print("❌ Tests failed! Fix the issues before releasing.")
            return False
        
        # Verify critical module imports
        try:
            print("Verifying critical module imports...")
            
            # Test package can be imported
            test_import_cmd = [
                "python", "-c", 
                "import importlib.util; "
                "spec = importlib.util.find_spec('bundestag_protocol_extractor.utils.logging'); "
                "print('✓ Critical module check: logging module can be imported' if spec else '❌ Critical module check: logging module MISSING!')"
            ]
            
            # Run the import test
            result = self.run_command(test_import_cmd, capture_output=True)
            print(result.stdout.strip())
            
            if "MISSING" in result.stdout:
                print("❌ Critical module check failed. Package may be missing required modules.")
                return False
            
        except subprocess.CalledProcessError:
            print("❌ Package verification failed!")
            return False
        
        print("✅ All tests passed!")
        return True

    def build_package(self) -> bool:
        """Build the package.
        
        Returns:
            True if package built successfully, False otherwise
        """
        if self.dry_run:
            print("Dry run: would build package")
            return True
            
        # Clean dist directory
        if os.path.exists("dist"):
            for file in os.listdir("dist"):
                os.unlink(os.path.join("dist", file))

        # Build package
        try:
            self.run_command(["python", "-m", "build"])
            print("✅ Built distribution packages")
            
            # Verify the built distribution with twine
            print("Verifying built packages with twine...")
            self.run_command(["twine", "check", "dist/*"])
            print("✅ Package verification passed")
            
            return True
        except subprocess.CalledProcessError:
            print("❌ Package build or verification failed!")
            return False

    def verify_installation(self) -> bool:
        """Verify the built package can be installed and imported.
        
        Returns:
            True if installation verification passes, False otherwise
        """
        if self.dry_run:
            print("Dry run: would verify installation")
            return True
            
        print("Testing installation in virtual environment...")
        
        # Create a temporary directory for the virtual environment
        self.temp_dir = Path(tempfile.mkdtemp())
        venv_dir = self.temp_dir / "venv"
        
        try:
            # Create virtual environment
            self.run_command([sys.executable, "-m", "venv", str(venv_dir)])
            
            # Determine paths based on platform
            if sys.platform == 'win32':
                python_cmd = str(venv_dir / "Scripts" / "python")
                pip_cmd = str(venv_dir / "Scripts" / "pip")
            else:
                python_cmd = str(venv_dir / "bin" / "python")
                pip_cmd = str(venv_dir / "bin" / "pip")
            
            # Install the package
            print("Installing package in test environment...")
            wheel_file = next(Path("dist").glob("*.whl"))
            self.run_command([pip_cmd, "install", str(wheel_file)])
            
            # Test importing critical modules
            print("Verifying critical module imports...")
            test_modules = [
                "bundestag_protocol_extractor",
                "bundestag_protocol_extractor.utils.logging",
                "bundestag_protocol_extractor.api.client",
                "bundestag_protocol_extractor.parsers.protocol_parser",
            ]
            
            for module in test_modules:
                test_cmd = [
                    python_cmd, "-c", 
                    f"import {module}; print(f'✅ Successfully imported {module}')"
                ]
                self.run_command(test_cmd)
            
            print("✅ Installation verification passed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation verification failed: {e}")
            return False
        finally:
            # Clean up temporary directory
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None

    def commit_version_changes(self) -> None:
        """Commit version changes to git."""
        if self.dry_run:
            print("Dry run: would commit version changes")
            return
            
        if not self.new_version:
            raise ReleaseError(ReleaseStep.VERSION, "New version not set")
            
        version_str = f"{self.new_version[0]}.{self.new_version[1]}.{self.new_version[2]}"

        # Add files
        self.run_command(["git", "add", INIT_PATH, PYPROJECT_PATH])

        # Commit
        self.run_command(["git", "commit", "-m", f"Bump version to {version_str}"])
        self.changes_committed = True

        print(f"Committed version changes for {version_str}")

    def create_git_tag(self) -> None:
        """Create a git tag for the new version."""
        if self.dry_run:
            print("Dry run: would create git tag")
            return
            
        if not self.new_version:
            raise ReleaseError(ReleaseStep.TAG, "New version not set")
            
        version_str = f"{self.new_version[0]}.{self.new_version[1]}.{self.new_version[2]}"
        tag = f"v{version_str}"

        # Check if tag exists
        result = self.run_command(
            ["git", "tag", "-l", tag], capture_output=True
        )

        if tag in result.stdout.strip().split("\n"):
            print(f"Tag {tag} already exists")
            return

        # Create tag
        self.run_command(["git", "tag", "-a", tag, "-m", f"Release {version_str}"])
        self.tag_created = True
        print(f"Created git tag: {tag}")

    def upload_to_pypi(self) -> None:
        """Upload the package to PyPI."""
        if self.dry_run:
            print("Dry run: would upload to PyPI")
            return
            
        if self.test_pypi:
            self.run_command(["twine", "upload", "--repository", "testpypi", "dist/*"])
            print("Uploaded to TestPyPI")
        else:
            self.run_command(["twine", "upload", "dist/*"])
            print("Uploaded to PyPI")

    def push_changes(self) -> None:
        """Push changes and tags to remote."""
        if self.dry_run:
            print("Dry run: would push changes and tags")
            return
            
        self.run_command(["git", "push"])
        self.run_command(["git", "push", "--tags"])
        print("Pushed changes and tag to remote")

    def check_dependencies(self) -> bool:
        """Check if required dependencies are installed.
        
        Returns:
            True if all dependencies are installed, False otherwise
        """
        try:
            # Ensure build and twine are installed
            self.run_command(["pip", "install", "--quiet", "build", "twine"])
            
            # Check for git
            self.run_command(["git", "--version"])
            
            # Check for pytest
            self.run_command(["pytest", "--version"])
            
            # Check for black, isort, flake8, mypy
            self.run_command(["black", "--version"])
            self.run_command(["isort", "--version"])
            self.run_command(["flake8", "--version"])
            self.run_command(["mypy", "--version"])
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Missing dependency: {e}")
            return False

    def check_git_status(self) -> bool:
        """Check if the git repository is clean.
        
        Returns:
            True if the repository is clean, False otherwise
        """
        # Check for uncommitted changes
        result = self.run_command(
            ["git", "status", "--porcelain"], capture_output=True
        )

        if result.stdout.strip() and not (
            "bundestag_protocol_extractor/__init__.py" in result.stdout
            and "pyproject.toml" in result.stdout
        ):
            print(
                "There are uncommitted changes. Please commit or stash them before releasing."
            )
            return False
            
        return True

    def cleanup(self) -> None:
        """Clean up temporary resources and revert changes if needed."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def release(self) -> bool:
        """Run the release process.
        
        Returns:
            True if the release was successful, False otherwise
        """
        try:
            print("Starting release process...")
            
            # Check dependencies
            print("\n=== Checking dependencies ===")
            if not self.check_dependencies():
                print("❌ Required dependencies are missing. Please install them and try again.")
                return False
                
            # Check git status
            print("\n=== Checking git status ===")
            if not self.check_git_status():
                return False
                
            # Get current version
            self.current_version = self.get_current_version()
            print(
                f"Current version: {self.current_version[0]}.{self.current_version[1]}.{self.current_version[2]}"
            )
            
            # Bump version
            self.new_version = self.bump_version(self.current_version)
            self.version_str = f"{self.new_version[0]}.{self.new_version[1]}.{self.new_version[2]}"
            print(f"New version: {self.version_str}")
            
            if self.dry_run:
                print("Dry run mode: no changes will be made")
                
            # Run linting
            print("\n=== Running linting checks ===")
            if not self.run_linting():
                return False
                
            # Run tests
            print("\n=== Running tests ===")
            if not self.run_tests():
                return False
                
            # Update version in files
            print("\n=== Updating version ===")
            self.update_version_in_files(self.new_version)
            
            # Commit version changes
            print("\n=== Committing version changes ===")
            self.commit_version_changes()
            
            # Build package
            print("\n=== Building package ===")
            if not self.build_package():
                return False
                
            # Verify installation
            print("\n=== Verifying installation ===")
            if not self.verify_installation():
                return False
                
            # Only create the git tag after all tests and verification have passed
            print("\n=== Creating git tag ===")
            self.create_git_tag()
            
            # Ask for confirmation before uploading
            print("\n=== Upload to PyPI ===")
            if self.test_pypi:
                destination = "TestPyPI"
            else:
                destination = "PyPI"

            if not self.dry_run:
                response = input(f"Ready to upload to {destination}. Continue? [y/N] ")
                if response.lower() != "y":
                    print("Aborted upload")
                    return True  # Return True because this is a user decision, not an error
                
                # Upload to PyPI
                self.upload_to_pypi()
                
                # Ask to push changes and tag
                push_response = input("Push changes and tag to remote? [y/N] ")
                if push_response.lower() == "y":
                    self.push_changes()
            
            print(f"✨ Released version {self.version_str}")
            
            # Suggest next steps
            print("\nNext steps:")
            print(
                f"1. Create a GitHub release at: https://github.com/maxboettinger/bundestag-protocol-extractor/releases/new?tag=v{self.version_str}"
            )
            print("2. Add release notes and publish")
            print(
                f"3. Verify the package is available: pip install bundestag-protocol-extractor=={self.version_str}"
            )
            
            return True
            
        except ReleaseError as e:
            print(f"Release failed: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
        finally:
            self.cleanup()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Release script for bundestag-protocol-extractor"
    )
    parser.add_argument(
        "bump", choices=["major", "minor", "patch"], help="Version part to bump"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually make changes, just print what would happen",
    )
    parser.add_argument(
        "--test", action="store_true", help="Upload to TestPyPI instead of PyPI"
    )
    parser.add_argument(
        "--skip-lint", action="store_true", help="Skip linting checks"
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip running tests"
    )
    args = parser.parse_args()

    # Create and run the release manager
    manager = ReleaseManager(args.bump, args.dry_run, args.test)
    success = manager.release()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
