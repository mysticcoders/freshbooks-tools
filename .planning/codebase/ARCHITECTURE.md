# Architecture

**Analysis Date:** 2026-01-29

## Pattern Overview

**Overall:** Layered architecture with distinct separation between CLI presentation, API integration, configuration management, and authentication.

**Key Characteristics:**
- Command-driven CLI using Click framework with nested command groups
- API abstraction layer with dedicated modules per FreshBooks endpoint
- Configuration-first design with secure token and rates management
- Interactive TUI mode for invoice browsing
- Automatic OAuth token refresh on expiration

## Layers

**CLI Presentation Layer:**
- Purpose: User-facing command interface with Rich formatting and table output
- Location: `src/freshbooks_tools/cli.py`, `src/freshbooks_tools/ui/`
- Contains: Click command definitions, output formatting, user prompts
- Depends on: API modules, configuration, models
- Used by: End users via terminal

**API Abstraction Layer:**
- Purpose: Encapsulate FreshBooks API interactions and normalize responses
- Location: `src/freshbooks_tools/api/`
- Contains: Specialized API modules (TimeEntriesAPI, InvoicesAPI, TeamAPI, etc.)
- Depends on: FreshBooksClient, authentication, models
- Used by: CLI commands, rate resolution

**HTTP Client Layer:**
- Purpose: Handle authenticated HTTP requests with automatic token refresh
- Location: `src/freshbooks_tools/api/client.py`
- Contains: FreshBooksClient with 401 retry logic, URL builders for different API namespaces
- Depends on: Authentication, configuration
- Used by: All API modules

**Authentication Layer:**
- Purpose: OAuth flow management and token lifecycle
- Location: `src/freshbooks_tools/auth.py`
- Contains: OAuth callback handler, token exchange, refresh logic, authorization URL generation
- Depends on: Configuration
- Used by: Client for token validation, CLI for login workflow

**Configuration & State Layer:**
- Purpose: Manage secrets, tokens, rates configuration, and account info
- Location: `src/freshbooks_tools/config.py`
- Contains: Config dataclasses, secure file handling, YAML rates parsing
- Depends on: External libraries (python-dotenv, pyyaml, platformdirs)
- Used by: All layers for runtime configuration

**Models Layer:**
- Purpose: Pydantic validation and normalization of API responses
- Location: `src/freshbooks_tools/models/schemas.py`
- Contains: TimeEntry, Invoice, Client, Project, TeamMember, and other domain models
- Depends on: Pydantic
- Used by: API modules for response parsing

## Data Flow

**Authentication Flow:**
1. User runs `fb auth login`
2. CLI loads config from .env (client_id, client_secret, redirect_uri)
3. OAuth flow starts: local server on port 8374 listens for callback
4. Browser opens FreshBooks authorization page
5. Authorization code received via callback
6. Client exchange code for tokens with FreshBooks API
7. Tokens saved to `~/.config/freshbooks-tools/tokens.json` with 0600 permissions
8. Account info (account_id, business_id) fetched and cached

**Time Entry Query Flow:**
1. User runs `fb time list --month 2024-12`
2. CLI loads config (including cached tokens)
3. FreshBooksClient created with auto-refresh capability
4. TimeEntriesAPI.list_by_month() called with year/month
5. Filters applied and time_entries endpoint queried
6. Responses parsed into TimeEntry models
7. RatesAPI resolves billable and cost rates for each entry
8. TeamAPI fetches teammate names
9. InvoicesAPI resolves client names
10. TimeEntryTable formats for display
11. Rich console renders table with calculated totals

**State Management:**
- Tokens: Stored in `~/.config/freshbooks-tools/tokens.json`, loaded on each command
- Rates: Stored in YAML at `~/.config/freshbooks-tools/rates.yaml`, loaded on startup
- Account Info: Stored in `~/.config/freshbooks-tools/account.json`, cached per session
- API Responses: Cached per session in FreshBooksClient and API modules (services, rates, team members)

## Key Abstractions

**FreshBooksClient:**
- Purpose: Unified HTTP interface with automatic token refresh on 401
- Location: `src/freshbooks_tools/api/client.py`
- Pattern: Context manager with lazy client initialization and URL builders for different API namespaces (accounting, timetracking, comments, auth)
- Exposes: `get()`, `post()`, URL builder methods (`timetracking_url()`, `accounting_url()`, etc.)

**RatesAPI:**
- Purpose: Multi-source rate resolution (API defaults + local config overrides)
- Location: `src/freshbooks_tools/api/rates.py`
- Pattern: Wraps TeamAPI and RatesConfig to provide unified rate lookup by identity_id
- Lookup order for billable rates: YAML override → API default → None
- Lookup order for cost rates: YAML only (API doesn't expose this)

**TimeEntryRow:**
- Purpose: Processed time entry with calculated amounts for display
- Location: `src/freshbooks_tools/ui/tables.py`
- Pattern: Dataclass that holds pre-calculated billable_amount and cost_amount properties

**Config/Tokens/RatesConfig:**
- Purpose: Strongly-typed configuration objects with safe serialization
- Location: `src/freshbooks_tools/config.py`
- Pattern: Dataclasses with `to_dict()` / `from_dict()` for JSON persistence and property decorators for derived values (is_expired, display_status)

## Entry Points

**CLI Entry Point:**
- Location: `src/freshbooks_tools/cli.py` line 46-50
- Triggers: User runs `fb` command (defined in pyproject.toml: `[project.scripts] fb = "freshbooks_tools.cli:cli"`)
- Responsibilities: Root Click group, routes to auth/time/invoices subcommands

**Auth Subcommand Group:**
- Location: `src/freshbooks_tools/cli.py` line 53-127
- Commands: `login`, `status`, `logout`
- Responsibilities: OAuth flow, token management

**Time Subcommand Group:**
- Location: `src/freshbooks_tools/cli.py` line 129-756
- Commands: `list`, `summary`, `export`, `add`, `unbilled`
- Responsibilities: Time entry queries, filtering, aggregation, export

**Invoices Subcommand Group:**
- Location: `src/freshbooks_tools/cli.py` line 758-943
- Commands: `browse` (interactive TUI), `list`, `show`
- Responsibilities: Invoice queries, interactive browsing with Textual

## Error Handling

**Strategy:** Try-except blocks at command level with user-friendly Rich console output

**Patterns:**
- OAuth errors: Caught in `start_oauth_flow()`, presented to user with setup instructions
- Token expiration: Automatic refresh in FreshBooksClient.get/post before returning 401
- API errors: `response.raise_for_status()` in client, caught at command level
- Validation errors: Click parameter validation, month format validation with custom exceptions
- Missing data: Graceful fallbacks (e.g., "-" for missing client names, "No Client" for unbilled entries)

## Cross-Cutting Concerns

**Logging:**
- Rich console output for status messages, warnings, errors
- No structured logging; all output through Rich with styled markup

**Validation:**
- Click type validators for command parameters (month format, dates, ranges)
- Pydantic models for API response validation with KeyError handling fallbacks

**Authentication:**
- Token passed in Authorization header for all requests
- Automatic refresh on 401 response before retry
- Expired tokens detected via `is_expired` property checking expiry timestamp

**Rate Resolution:**
- Multi-layer: RatesAPI checks YAML config first, then API rates, then None
- Identity_id is primary lookup key (supports both direct int and string representations in YAML)
- Billable rates sourced from API or YAML override; cost rates from YAML only

**Configuration Loading:**
- Environment variables via .env with fallback to system .env
- YAML for rates with flexible structure (by email or identity_id)
- Account info auto-fetched from API and cached locally
- Secure file permissions: 0600 for tokens, 0700 for config directory
