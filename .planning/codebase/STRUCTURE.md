# Codebase Structure

**Analysis Date:** 2026-01-29

## Directory Layout

```
freshbooks-tools/
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules
├── .planning/                  # GSD planning artifacts
├── .ropeproject/               # Rope IDE config
├── LICENSE                     # Project license
├── README.md                   # Project documentation
├── pyproject.toml              # uv/hatchling configuration
├── uv.lock                     # Locked dependencies
└── src/
    └── freshbooks_tools/       # Main package
        ├── __init__.py         # Package initialization with __version__
        ├── cli.py              # Click CLI entry point with all commands
        ├── auth.py             # OAuth authentication flow
        ├── config.py           # Configuration, tokens, rates management
        ├── api/                # FreshBooks API modules
        │   ├── __init__.py
        │   ├── client.py       # HTTP client with auto token refresh
        │   ├── time_entries.py # Time entry queries and creation
        │   ├── invoices.py     # Invoice queries and client lookups
        │   ├── projects.py     # Project queries and matching
        │   ├── team.py         # Team member lookups and identity resolution
        │   └── rates.py        # Rate resolution (billable/cost)
        ├── models/             # Data models and schemas
        │   ├── __init__.py
        │   └── schemas.py      # Pydantic models for all domain objects
        └── ui/                 # User interface components
            ├── __init__.py
            ├── tables.py       # Rich table formatters for time entries and invoices
            └── invoice_browser.py  # Interactive Textual TUI for invoice browsing
```

## Directory Purposes

**src/freshbooks_tools/:**
- Purpose: Main package containing all application code
- Contains: CLI, API integration, models, configuration, authentication, UI
- Key files: `cli.py` (1090 lines), `config.py` (281 lines), `auth.py` (220 lines)

**src/freshbooks_tools/api/:**
- Purpose: Encapsulate all FreshBooks API interactions
- Contains: Specialized API classes for different FreshBooks endpoints
- Key files: `client.py` (HTTP base), `time_entries.py` (267 lines), `invoices.py`, `team.py`, `projects.py`, `rates.py`
- Pattern: Each module exports a single API class that takes FreshBooksClient in constructor

**src/freshbooks_tools/models/:**
- Purpose: Pydantic-validated domain models for API responses
- Contains: TimeEntry, Invoice, Project, Client, TeamMember, Service, and related models
- Key files: `schemas.py` (250 lines) with nested models and computed properties

**src/freshbooks_tools/ui/:**
- Purpose: User-facing output formatting and interactive interfaces
- Contains: Rich table formatters and Textual-based interactive browser
- Key files: `tables.py` (Rich table builders), `invoice_browser.py` (interactive TUI)

**tests/:**
- Purpose: Test suite
- Current state: Empty __init__.py file, no tests present

**.planning/:**
- Purpose: GSD mapping and planning artifacts
- Contains: Architecture and structure analysis documents

## Key File Locations

**Entry Points:**
- `src/freshbooks_tools/cli.py`: Main CLI entry point with @click.group() root at line 46
- Script entry: Defined in `pyproject.toml` line 17-18: `fb = "freshbooks_tools.cli:cli"`
- Package init: `src/freshbooks_tools/__init__.py` with version string

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, build config, uv dev-dependencies
- `.env.example`: Template for required environment variables (FRESHBOOKS_CLIENT_ID, FRESHBOOKS_CLIENT_SECRET, FRESHBOOKS_REDIRECT_URI)
- `src/freshbooks_tools/config.py`: Config loading, token/rates/account persistence

**Core Logic:**
- `src/freshbooks_tools/api/client.py`: HTTP client with token refresh (lines 14-179)
- `src/freshbooks_tools/auth.py`: OAuth flow and token management
- `src/freshbooks_tools/api/time_entries.py`: Time entry API queries
- `src/freshbooks_tools/api/rates.py`: Rate resolution logic

**Testing:**
- `tests/__init__.py`: Empty test module
- No test files currently present (no *.test.py or *.spec.py files)

## Naming Conventions

**Files:**
- `snake_case` for all module files (cli.py, config.py, auth.py)
- API modules: Plural noun form (time_entries.py, invoices.py, projects.py)
- Model file: Singular (schemas.py)

**Directories:**
- `snake_case` for all directories (api/, ui/, models/)
- Functional grouping: api/ for all FreshBooks integration, ui/ for presentation, models/ for schemas

**Classes:**
- `PascalCase` for all classes (FreshBooksClient, TimeEntriesAPI, TimeEntry, Config, RatesConfig)
- API classes: Suffix with "API" (TimeEntriesAPI, InvoicesAPI, ProjectsAPI, TeamAPI, RatesAPI)
- Model classes: Domain names without suffix (TimeEntry, Invoice, Project, Client)

**Functions:**
- `snake_case` for all functions (load_config, ensure_valid_token, get_authorization_url)
- Private functions: Leading underscore (_handle_response, _print_time_summary_json)
- CLI commands: `snake_case` with no prefix (auth_login, time_list, invoices_browse)

**Variables:**
- `snake_case` for all variables, constants use `UPPER_CASE`
- Path constants: `UPPER_CASE` (CONFIG_DIR, TOKENS_FILE, RATES_FILE)
- Command-local: Short names acceptable in tight scopes (e.g., `fm` for formatter)

**Types:**
- Type hints used throughout with `Optional[T]`, `list[T]`, `dict[K, V]` syntax
- Dataclass annotations for Config, Tokens, RatesConfig
- Pydantic BaseModel for all API response models

## Where to Add New Code

**New API Endpoint:**
- Implementation: Create new file in `src/freshbooks_tools/api/{resource}.py`
- Pattern: Class `{Resource}API(object)` with FreshBooksClient in __init__
- Models: Add to `src/freshbooks_tools/models/schemas.py` if needed
- CLI command: Add to appropriate group in `src/freshbooks_tools/cli.py` (create new @cli.group() if category doesn't exist)
- Example: To add projects API, follow pattern of `TimeEntriesAPI` in time_entries.py

**New CLI Command:**
- Primary code: Add function with @command decorator to existing group in `src/freshbooks_tools/cli.py`
- Output formatting: If table needed, add to `src/freshbooks_tools/ui/tables.py`
- Configuration: If new config option needed, update `src/freshbooks_tools/config.py` and RatesConfig
- Pattern: Follow existing commands (auth_login, time_list) for Click decorator usage and error handling

**New UI Component:**
- Implementation: Add to `src/freshbooks_tools/ui/tables.py` or new file in ui/
- Pattern: Class that takes `Console` as optional parameter, render method returns Rich object
- Usage: Import and call from CLI command, passing `console` from module-level singleton

**Utilities:**
- Shared helpers: Keep in module where primarily used, or create utils.py if used across multiple modules
- Validation: Use Click parameter types and custom validators in CLI functions
- Date/time helpers: Currently in API modules (e.g., get_month_range in time_entries.py)

## Special Directories

**.planning/codebase/:**
- Purpose: GSD-generated documentation (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by mapping commands)
- Committed: Yes
- Contents: This analysis and related planning documents

**.ropeproject/:**
- Purpose: Rope IDE configuration for refactoring support
- Generated: Yes (IDE-generated)
- Committed: Yes
- Contents: IDE metadata, not application code

**.venv/:**
- Purpose: Python virtual environment (created by uv)
- Generated: Yes
- Committed: No (.gitignored)
- Contents: Installed dependencies, Python runtime

**tests/:**
- Purpose: Test suite (currently empty)
- Generated: No (manually created)
- Committed: Yes
- Contents: Currently just __init__.py, ready for test files

## Module Organization

**API Modules Pattern:**
All API modules follow consistent structure:
1. Docstring describing the module purpose
2. Imports (models, client, config as needed)
3. Single API class with __init__ taking FreshBooksClient and related APIs
4. Methods for list, get, create, update, delete operations
5. Caching when appropriate (services in RatesAPI, team members in TeamAPI)
6. URL building via client helper methods

**CLI Structure:**
- Root `@click.group()` for main `cli` command at line 46
- Sub-groups for command families: `auth`, `time`, `invoices` using `@cli.group()`
- Commands in groups using `@group.command("name")` decorator
- Click options for parameters with help text and defaults
- Try-except wrapping actual logic for error handling
- Rich console output with markup for colors and formatting

**Config Strategy:**
- Environment variables (from .env) for secrets
- JSON files in ~/.config/freshbooks-tools/ for persistent state:
  - tokens.json: OAuth tokens (0600 permissions)
  - account.json: Cached account_id/business_id
  - rates.yaml: User-provided cost/billable rate overrides
- Dataclass representation for type safety and serialization

## Import Organization

**Standard pattern in all modules:**
1. `"""Docstring"""` - Module purpose
2. Standard library imports (datetime, json, pathlib, etc.)
3. Third-party imports (click, pydantic, httpx, rich, etc.)
4. Relative imports from local package (`from ..config import`, `from .client import`)
5. Blank line separating groups

**Example from cli.py (lines 1-29):**
```python
"""CLI entry point for FreshBooks tools."""

import csv
import json
import sys
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Optional

import click
from rich.console import Console

from .api.client import FreshBooksClient
from .api.invoices import InvoicesAPI
from .api.projects import ProjectsAPI
...
```

## Path Aliases

No path aliases configured in tsconfig or similar. All imports use relative paths or absolute package paths:
- Relative: `from ..config import load_config`
- Absolute: `from freshbooks_tools.api.client import FreshBooksClient`
- Module-level imports for commonly used utils (Console from rich always imported locally)
