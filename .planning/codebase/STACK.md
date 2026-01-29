# Technology Stack

**Analysis Date:** 2026-01-29

## Languages

**Primary:**
- Python 3.11+ - Core application language for CLI and all logic

## Runtime

**Environment:**
- Python 3.11+ (from `pyproject.toml` requires-python setting)

**Package Manager:**
- uv - UV package manager for dependency and environment management
- Lockfile: `uv.lock` (present)

## Frameworks

**Core:**
- Click 8.1+ - CLI framework for command-line interface (`src/freshbooks_tools/cli.py`)
- Textual 0.89+ - Terminal user interface framework for interactive invoice browser (`src/freshbooks_tools/ui/invoice_browser.py`)

**API/HTTP:**
- httpx 0.27+ - Async HTTP client for FreshBooks API requests (`src/freshbooks_tools/api/client.py`)

**Data Handling:**
- Pydantic 2.9+ - Data validation and modeling for API responses (`src/freshbooks_tools/models/schemas.py`)
- PyYAML 6.0+ - YAML parsing for rates configuration file (`src/freshbooks_tools/config.py`)
- python-dotenv 1.0+ - Environment variable loading from `.env` files (`src/freshbooks_tools/config.py`)

**UI/Display:**
- Rich 13.7+ - Rich terminal output for formatted tables and status messages (`src/freshbooks_tools/api/client.py`, `src/freshbooks_tools/cli.py`)

**Utilities:**
- platformdirs 4.3+ - Cross-platform config directory management (`src/freshbooks_tools/config.py`)

**Testing:**
- pytest 8.0+ - Test framework
- pytest-asyncio 0.24+ - Async test support

## Key Dependencies

**Critical:**
- httpx 0.27+ - Handles OAuth token exchange and all FreshBooks API communication with automatic token refresh
- Pydantic 2.9+ - Validates and structures FreshBooks API responses (TimeEntry, Invoice, Payment, Client models)
- Click 8.1+ - Entry point for CLI commands defined in `src/freshbooks_tools/cli.py`

**Infrastructure:**
- platformdirs 4.3+ - Secures token storage in `~/.config/freshbooks-tools/` with 0o700 directory permissions
- python-dotenv 1.0+ - Loads FreshBooks credentials from `.env` file
- PyYAML 6.0+ - Reads rates configuration from `~/.config/freshbooks-tools/rates.yaml`

## Configuration

**Environment:**
- Uses `.env` file at project root or `~/.config/freshbooks-tools/.env`
- Key environment variables:
  - `FRESHBOOKS_CLIENT_ID` - OAuth client ID from FreshBooks Developer Portal
  - `FRESHBOOKS_CLIENT_SECRET` - OAuth client secret
  - `FRESHBOOKS_REDIRECT_URI` - OAuth callback URL (requires HTTPS, uses ngrok for local dev)
  - `FRESHBOOKS_LOCAL_PORT` - Local port for OAuth callback server (default: 8374)

**Build:**
- Build config: `pyproject.toml` with Hatchling backend
- Package structure: `src/freshbooks_tools` layout
- CLI entry point: `fb` command via `freshbooks_tools.cli:cli`

## Platform Requirements

**Development:**
- Python 3.11 or later
- uv package manager
- ngrok for local OAuth testing (HTTPS requirement)
- Internet connection for FreshBooks API access

**Production:**
- Python 3.11+
- FreshBooks account with OAuth app credentials
- HTTPS redirect URI for OAuth callback (ngrok or hosted endpoint)

---

*Stack analysis: 2026-01-29*
