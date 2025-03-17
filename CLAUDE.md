# Bundestag Protocol Extractor: Dev Reference

## Commands
- **Setup**: `conda env create -f environment.yml && conda activate bundestag-protocol-extractor`
- **Install Dev**: `pip install -e ".[dev]"`
- **Lint**: `black . && isort . && flake8 .`
- **Type Check**: `mypy .`
- **Test**: `pytest`
- **Single Test**: `pytest tests/test_file.py::test_function -v`
- **Coverage**: `pytest --cov=bundestag_protocol_extractor`
- **Docs**: `pip install -e ".[docs]" && cd docs && make html`

## Code Style
- **Formatting**: Black (88 char line length)
- **Imports**: isort with Black profile (stdlib → third-party → local)
- **Types**: Strict typing with MyPy (all functions must be typed)
- **Docstrings**: Google style format
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Error handling**: Use typed exceptions, explicit error messages
- **Dependencies**: Only add essential dependencies

## Project Structure
- Modular architecture with clear separation of concerns
- API clients in `api/`, data models in `models/`, parsers in `parsers/`
- Write unit tests for all new functionality