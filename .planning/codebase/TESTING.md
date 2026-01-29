# Testing Patterns

**Analysis Date:** 2026-01-29

## Test Framework

**Runner:**
- pytest 8.0+
- pytest-asyncio 0.24+
- Config: `pyproject.toml` specifies dependencies but no pytest configuration section

**Assertion Library:**
- pytest built-in assertions (pytest.raises, assert, etc.)

**Run Commands:**
```bash
pytest                 # Run all tests
pytest -v              # Run with verbose output
pytest tests/          # Run tests in tests/ directory
pytest --asyncio-mode=auto  # Run async tests
```

## Test File Organization

**Location:**
- Tests located in `tests/` directory (separate from source)
- Source code in `src/freshbooks_tools/`

**Naming:**
- Test directory: `tests/__init__.py` exists but is minimal
- No test files currently in repository (only empty `__init__.py`)
- Pattern expected: `test_*.py` or `*_test.py` following pytest convention

**Structure:**
```
freshbooks-tools/
├── src/
│   └── freshbooks_tools/
│       ├── api/
│       ├── models/
│       ├── ui/
│       ├── auth.py
│       ├── cli.py
│       ├── config.py
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── test_auth.py          (expected)
    ├── test_config.py        (expected)
    ├── test_api/
    │   ├── test_client.py    (expected)
    │   └── test_time_entries.py (expected)
    └── conftest.py           (expected for fixtures)
```

## Test Structure

**Suite Organization:**
Structure would follow standard pytest class-based or function-based approach:

**Patterns (to establish when writing tests):**
- Use pytest fixtures for setup/teardown
- Use `pytest.mark.asyncio` for async tests
- Fixtures for config, mock client, and sample data
- Parametrize tests with multiple inputs using `@pytest.mark.parametrize`

**Setup/Teardown:**
- Fixtures with `scope="function"` for per-test setup
- Config fixtures that load test .env files
- Mock httpx.Client for API testing

**Assertion Pattern (expected):**
```python
def test_parse_month_valid():
    year, month = parse_month("2024-01")
    assert year == 2024
    assert month == 1

def test_parse_month_invalid():
    with pytest.raises(click.BadParameter):
        parse_month("2024-13")
```

## Mocking

**Framework:** unittest.mock (Python standard library) or pytest-mock

**Patterns (establish with first tests):**
```python
from unittest.mock import Mock, patch, MagicMock

def test_with_mock_client(monkeypatch):
    mock_response = {"time_entries": []}
    monkeypatch.setattr(httpx.Client, 'get', Mock(return_value=mock_response))
```

**What to Mock:**
- External HTTP calls via httpx (all FreshBooks API calls)
- File I/O operations (config loading, token persistence)
- OAuth browser launch (webbrowser.open)
- Rich console output for assertion verification

**What NOT to Mock:**
- Pydantic model creation and validation
- Dataclass instances (Config, Tokens, RatesConfig)
- Local business logic (filtering, calculations, parsing)
- Internal method calls within same class

## Fixtures and Factories

**Test Data:**
When establishing test patterns, use factory fixtures:

```python
# conftest.py
import pytest
from freshbooks_tools.models import TimeEntry, Invoice, Config, Tokens
from datetime import datetime

@pytest.fixture
def mock_config():
    return Config(
        client_id="test-client",
        client_secret="test-secret",
        redirect_uri="http://localhost:8374/callback",
    )

@pytest.fixture
def mock_tokens():
    return Tokens(
        access_token="test-access",
        refresh_token="test-refresh",
    )

@pytest.fixture
def sample_time_entry():
    return TimeEntry(
        id=1,
        identity_id=100,
        duration=3600,
        started_at=datetime(2024, 1, 15, 9, 0),
        billable=True,
    )
```

**Location:**
- Main fixtures in `tests/conftest.py`
- Shared fixtures for all tests
- Feature-specific fixtures in related test files
- Factory functions for generating test data variations

## Coverage

**Requirements:** No coverage enforced in configuration

**View Coverage (when configured):**
```bash
pytest --cov=src/freshbooks_tools --cov-report=html
```

**Key areas to test when implementing:**
- `api/client.py`: Token refresh logic, retry on 401
- `config.py`: Load/save tokens and rates, token expiration checks
- `auth.py`: OAuth flow, token exchange
- `api/*.py`: List, filter, and create operations
- `cli.py`: Command parsing and execution
- `models/schemas.py`: Pydantic validation (especially optional fields and aliases)

## Test Types

**Unit Tests:**
- Scope: Individual functions and methods
- Approach: Isolate with mocks, test one behavior at a time
- Examples: `parse_month()`, token expiration checks, rate resolution priority
- No external calls or file I/O

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Mock HTTP layer, test API client + config + auth flow
- Examples: Time entry list with filtering, invoice retrieval with client lookup
- May use fixture databases or test API responses

**E2E Tests:**
- Framework: Textual/Click for CLI commands
- Not currently in use - would test full CLI workflows end-to-end

## Common Patterns

**Async Testing:**
Use `pytest-asyncio` for async methods:

```python
@pytest.mark.asyncio
async def test_fetch_account_info():
    mock_client = AsyncMock(spec=httpx.Client)
    mock_client.get.return_value = {"response": {...}}
    # test async code
```

**Error Testing:**
Test exception handling for user-facing errors:

```python
def test_invalid_month_format():
    with pytest.raises(click.BadParameter, match="Invalid month format"):
        parse_month("invalid")

def test_unauthorized_access(mock_client):
    mock_client.get.side_effect = httpx.HTTPStatusError(401)
    with pytest.raises(ValueError, match="Not authenticated"):
        api.list_time_entries()
```

**Parametrized Tests:**
Test multiple inputs with one test function:

```python
@pytest.mark.parametrize("month_str,expected_year,expected_month", [
    ("2024-01", 2024, 1),
    ("2024-12", 2024, 12),
    ("2025-06", 2025, 6),
])
def test_parse_month(month_str, expected_year, expected_month):
    year, month = parse_month(month_str)
    assert year == expected_year
    assert month == expected_month
```

---

*Testing analysis: 2026-01-29*
