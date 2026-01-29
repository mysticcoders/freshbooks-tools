# External Integrations

**Analysis Date:** 2026-01-29

## APIs & External Services

**FreshBooks API:**
- Time Tracking API - Query and manage time entries across team members
  - SDK/Client: httpx via custom `FreshBooksClient` wrapper
  - Endpoint: `https://api.freshbooks.com/timetracking/business/{business_id}/time_entries`
  - Auth: Bearer token (OAuth 2.0)
  - Scopes: `user:time_entries:read`, `user:time_entries:write`
  - Implementation: `src/freshbooks_tools/api/time_entries.py`

- Accounting API - Query invoices, clients, and payments
  - Endpoint: `https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices`
  - Auth: Bearer token (OAuth 2.0)
  - Scopes: `user:invoices:read`, `user:payments:read`, `user:clients:read`
  - Implementation: `src/freshbooks_tools/api/invoices.py`

- Projects API - Query project information
  - Endpoint: `https://api.freshbooks.com/accounting/account/{account_id}/projects/projects`
  - Auth: Bearer token (OAuth 2.0)
  - Scopes: `user:projects:read`
  - Implementation: `src/freshbooks_tools/api/projects.py`

- Teams API - Query team members and billable rates
  - Endpoint: `https://api.freshbooks.com/accounting/account/{account_id}/users/team_members`
  - Auth: Bearer token (OAuth 2.0)
  - Scopes: `user:teams:read`, `user:billable_items:read`
  - Implementation: `src/freshbooks_tools/api/team.py`

- Auth API - Current user profile and business memberships
  - Endpoint: `https://api.freshbooks.com/auth/api/v1/users/me`
  - Auth: Bearer token (OAuth 2.0)
  - Scopes: `user:profile:read`
  - Implementation: `src/freshbooks_tools/api/client.py`

## Data Storage

**Databases:**
- Not used - this is a read-only/query-focused CLI tool

**File Storage:**
- Local filesystem only
  - Tokens: `~/.config/freshbooks-tools/tokens.json` (0o600 permissions)
  - Rates: `~/.config/freshbooks-tools/rates.yaml` (YAML format)
  - Account Info: `~/.config/freshbooks-tools/account.json` (0o600 permissions)
  - Client: Custom `FreshBooksClient` wrapper over httpx

**Caching:**
- In-memory client cache in `InvoicesAPI._clients_cache` for listing clients
- No persistent cache layer

## Authentication & Identity

**Auth Provider:**
- FreshBooks OAuth 2.0
  - Authorization URL: `https://auth.freshbooks.com/oauth/authorize`
  - Token URL: `https://api.freshbooks.com/auth/oauth/token`
  - Implementation: `src/freshbooks_tools/auth.py`
  - Flow: Authorization code with PKCE-ready structure
  - Token refresh: Automatic refresh on 401 responses via `refresh_access_token()`
  - Scopes:
    - `user:profile:read`
    - `user:time_entries:read`
    - `user:time_entries:write`
    - `user:projects:read`
    - `user:clients:read`
    - `user:billable_items:read`
    - `user:invoices:read`
    - `user:payments:read`
    - `user:teams:read`

**Local OAuth Callback Server:**
- Custom HTTP callback handler: `OAuthCallbackHandler` in `src/freshbooks_tools/auth.py`
- Listens on `127.0.0.1:8374` (configurable via `FRESHBOOKS_LOCAL_PORT`)
- Handles authorization code exchange and error responses
- Supports ngrok tunneling for HTTPS redirect URI requirement

## Monitoring & Observability

**Error Tracking:**
- None detected - errors logged to console via Rich

**Logs:**
- Console-based logging using Rich library (`src/freshbooks_tools/api/client.py`, `src/freshbooks_tools/auth.py`)
- Status messages for token refresh, API calls, and authentication flows
- No persistent log file storage

## CI/CD & Deployment

**Hosting:**
- Not specified - this is a CLI tool for local/terminal use

**CI Pipeline:**
- Not detected - no GitHub Actions, GitLab CI, or similar found

## Environment Configuration

**Required env vars:**
- `FRESHBOOKS_CLIENT_ID` - OAuth client ID (required)
- `FRESHBOOKS_CLIENT_SECRET` - OAuth client secret (required)
- `FRESHBOOKS_REDIRECT_URI` - OAuth callback URL with HTTPS scheme (required for OAuth flow)

**Optional env vars:**
- `FRESHBOOKS_LOCAL_PORT` - Local port for OAuth callback (default: 8374)

**Secrets location:**
- `.env` file at project root or `~/.config/freshbooks-tools/.env`
- Tokens stored securely in `~/.config/freshbooks-tools/tokens.json` with restricted permissions (0o600)
- Account credentials also stored in `~/.config/freshbooks-tools/account.json` (0o600)

## Webhooks & Callbacks

**Incoming:**
- OAuth callback endpoint: `http://127.0.0.1:{FRESHBOOKS_LOCAL_PORT}/callback`
  - Receives authorization code from FreshBooks after user login
  - Exchanges code for access/refresh tokens via `exchange_code_for_tokens()`
  - Returns HTML success/failure page to browser

**Outgoing:**
- None - tool is read-only for most operations (time entry creation is supported but no webhooks are sent)

## API Version & Headers

**FreshBooks API Configuration:**
- Base Auth URL: `https://api.freshbooks.com/auth/api/v1`
- Base Accounting URL: `https://api.freshbooks.com/accounting/account/{account_id}`
- Base TimeTracking URL: `https://api.freshbooks.com/timetracking/business/{business_id}`
- Base Comments URL: `https://api.freshbooks.com/comments/business/{business_id}`
- API Version header: `alpha` (via `Api-Version` header)
- Content-Type: `application/json`

**Token Refresh Logic:**
- Automatic: Any 401 response triggers `refresh_access_token()` in `FreshBooksClient._handle_response()`
- Token expiration tracked via `expires_at` field in `Tokens` dataclass
- Tokens saved to disk after refresh via `save_tokens()`

---

*Integration audit: 2026-01-29*
