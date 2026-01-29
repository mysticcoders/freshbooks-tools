# Coding Conventions

**Analysis Date:** 2026-01-29

## Naming Patterns

**Files:**
- Module files use snake_case: `time_entries.py`, `freshbooks_tools/cli.py`
- Package directories use snake_case: `freshbooks_tools/`, `freshbooks_tools/api/`
- Test files located in `tests/` directory (currently empty/minimal)

**Functions:**
- Function names use snake_case: `parse_month()`, `list_time_entries()`, `get_team_member_name()`
- Private helper functions prefixed with underscore: `_print_time_summary_json()`, `_handle_response()`
- Click command functions use descriptive names: `auth_login()`, `time_list()`, `invoices_browse()`

**Variables:**
- Local variables use snake_case: `entry_date`, `total_hours`, `billable_rate`
- Constants use UPPER_SNAKE_CASE: `BASE_AUTH_URL`, `APP_NAME`, `SCOPES`, `AUTH_URL`
- Boolean variables start with descriptive verbs: `is_expired`, `include_team`, `billable`
- Collection variables use plural form: `entries`, `all_invoices`, `members_by_id`

**Types:**
- Classes use PascalCase: `FreshBooksClient`, `TimeEntry`, `InvoicesAPI`, `Config`, `RatesConfig`
- Type hints use modern Python syntax: `list[TimeEntry]`, `dict[str, Decimal]`, `Optional[int]`
- All Pydantic models inherit from `BaseModel`

## Code Style

**Formatting:**
- No explicit formatter configured (no ruff, black, or other tool in pyproject.toml)
- Code follows PEP 8 conventions
- Consistent with Python 3.11+ type hints
- Line length appears to be ~100-120 characters based on existing code

**Linting:**
- No linting configuration found in pyproject.toml
- Code includes type hints throughout, supporting static analysis
- Uses `from __future__ import annotations` for forward references where needed

## Import Organization

**Order:**
1. Standard library imports (`http.server`, `json`, `sys`, `datetime`, `pathlib`, etc.)
2. Third-party imports (`httpx`, `click`, `pydantic`, `rich`, `dotenv`, `yaml`, `platformdirs`)
3. Local relative imports (`.api`, `..auth`, `..models`)

**Path Aliases:**
- No path aliases configured
- Uses relative imports consistently: `from .api.client import FreshBooksClient`
- From standard library or third-party: absolute imports

**Example pattern from `cli.py`:**
```python
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal

import click
from rich.console import Console

from .api.client import FreshBooksClient
from .auth import start_oauth_flow
from .config import load_config, load_tokens
```

## Error Handling

**Patterns:**
- Exceptions are caught broadly and converted to user-friendly error messages via `console.print()`
- System exits use `sys.exit(1)` for error cases
- Specific exception types caught where detail matters: `(json.JSONDecodeError, KeyError)`, `(KeyError, ValueError)`
- API responses validate presence of expected keys with fallback to defaults or skip with `continue`
- Token operations check for expiration and auto-refresh transparently in client

**Example from `api/client.py`:**
```python
def _handle_response(self, response: httpx.Response, retry_on_401: bool = True) -> dict[str, Any]:
    if response.status_code == 401 and retry_on_401:
        console.print("[dim]Token expired, refreshing...[/dim]")
        tokens = refresh_access_token(self.config)
        save_tokens(tokens)
        self.config.tokens = tokens
        return None
    response.raise_for_status()
    return response.json()
```

## Logging

**Framework:** Rich Console for all user-facing output

**Patterns:**
- Import: `from rich.console import Console` then `console = Console()`
- Informational messages: `console.print("[dim]message[/dim]")`
- Success messages: `console.print("[green]message[/green]")`
- Warnings: `console.print("[yellow]message[/yellow]")`
- Errors: `console.print(f"[red]Error:[/red] {e}")`
- Emphasis/section headers: `console.print(f"[bold]Title[/bold]")`
- Complex output includes formatting tags: `[cyan]`, `[magenta]`, `[link=url]`

All console output includes Rich formatting for better CLI UX.

## Comments

**When to Comment:**
- Every function includes a docstring describing purpose, parameters, and returns
- Classes include docstrings describing their role
- Complex business logic gets block-level docstrings explaining the "why"
- No inline comments on individual lines per user instructions

**JSDoc/TSDoc:**
- Uses Python docstrings in Google/NumPy style
- Parameters documented in Args section
- Return values documented in Returns section
- Example from `time_entries.py`:
```python
def list(
    self,
    identity_id: Optional[int] = None,
    started_from: Optional[datetime] = None,
    ...
) -> tuple[list[TimeEntry], int]:
    """
    List time entries with optional filters.

    Args:
        identity_id: Filter by specific teammate
        started_from: Start of date range (UTC)
        ...

    Returns:
        Tuple of (time entries list, total count)
    """
```

## Function Design

**Size:** Functions are moderately sized (20-100 lines typical)
- Utility functions like `parse_month()` are short (10 lines)
- API methods like `list()` are ~60 lines with detailed parameter handling
- CLI command handlers like `time_list()` are longer (100+ lines) due to business logic and output formatting

**Parameters:**
- Type hints required on all parameters
- Optional parameters default to `None`
- Keyword-only arguments used when multiple optional params: `def create(..., billable: bool = True) -> TimeEntry:`

**Return Values:**
- Type hints required on all return values
- Tuples return multiple values: `tuple[list[TimeEntry], int]`
- Use `Optional[Type]` for nullable returns
- Dataclass/Pydantic models used for structured returns

## Module Design

**Exports:**
- No explicit `__all__` definitions found
- Classes and functions are implicitly exported when defined at module level
- API classes instantiated with a shared client: `TimeEntriesAPI(client)`, `InvoicesAPI(client)`

**Barrel Files:**
- `src/freshbooks_tools/models/__init__.py` exports model classes
- `src/freshbooks_tools/api/__init__.py` exports API classes

**Module Organization:**
- `cli.py`: All click commands and command group definitions
- `api/client.py`: HTTP client with OAuth token management
- `api/*.py`: Specialized API endpoints (time_entries, invoices, rates, team, etc.)
- `models/schemas.py`: All Pydantic model definitions
- `config.py`: Configuration, token, and rates management
- `auth.py`: OAuth flow and token refresh logic
- `ui/*.py`: Rich console table formatting and Textual UI

---

*Convention analysis: 2026-01-29*
