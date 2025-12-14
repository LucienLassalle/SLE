# SLE Tests

Unit and integration tests for SLE.

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_config_loader.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

## Test Files

- `test_config_loader.py` - Configuration loading and validation
- `test_exporters.py` - Exporter functionality and mocking
- `test_integration.py` - End-to-end workflow tests

## Requirements

```bash
pip install pytest pytest-cov
```
