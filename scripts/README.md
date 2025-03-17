# Release Process

This directory contains scripts to help with managing releases.

## Manual Release Process

Use the `release.py` script to create a new release:

```bash
# For a patch release (0.1.0 -> 0.1.1)
python scripts/release.py patch

# For a minor release (0.1.0 -> 0.2.0)
python scripts/release.py minor

# For a major release (0.1.0 -> 1.0.0)
python scripts/release.py major
```

This script will:

1. Update version numbers in `bundestag_protocol_extractor/__init__.py` and `pyproject.toml`
2. Commit these changes
3. Create a git tag
4. Build distribution packages
5. Upload to PyPI (with confirmation)
6. Push changes to GitHub (with confirmation)

### Options

- `--dry-run`: Don't make any changes, just show what would happen
- `--test`: Upload to TestPyPI instead of the real PyPI

Example:
```bash
# Test the release process without making changes
python scripts/release.py patch --dry-run

# Release to TestPyPI
python scripts/release.py patch --test
```

## Automated Release Process

This project uses GitHub Actions to automatically publish to PyPI when a new GitHub Release is created.

To trigger an automated release:

1. Update the version in code (you can use `release.py` with `--dry-run` to help)
2. Commit and push these changes
3. Create a new tag: `git tag v0.1.1 && git push origin v0.1.1`
4. Create a new release on GitHub, using the tag

The GitHub Actions workflow will:
1. Verify the tag matches the package version
2. Build the package
3. Publish to PyPI
4. Verify the package is available on PyPI

## PyPI Setup

Before you can publish to PyPI, you need to:

1. Create an account on [PyPI](https://pypi.org/)
2. Generate an API token on your [PyPI account settings](https://pypi.org/manage/account/)
3. Add the token to your GitHub repository secrets as `PYPI_API_TOKEN`

## Notes for Maintainers

- Always use semantic versioning (MAJOR.MINOR.PATCH)
- Update CHANGELOG.md for each release
- Test the package before releasing: `pip install -e .`