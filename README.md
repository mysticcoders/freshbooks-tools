# FreshBooks Tools

A Python CLI for querying FreshBooks financial data - AR aging, revenue reports, time entries, and invoices. Works both interactively and as a Claude Code skill.

## Quick Start

```bash
# Clone and install
git clone https://github.com/mysticcoders/freshbooks-tools.git
cd freshbooks-tools
uv sync

# Authenticate (requires OAuth setup - see below)
uv run fb auth login

# Run your first command
uv run fb reports ar-aging
```

## Why This Tool?

Get quick answers to financial questions directly from your terminal. Ask "What's our AR aging?" or "How much does Acme Corp owe?" and get instant answers. Designed to work seamlessly with Claude Code for AI-assisted financial querying.

## Installation

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/freshbooks-tools.git
cd freshbooks-tools

# Install dependencies
uv sync
```

### Global Installation (Optional)

To install the CLI globally and use `fb` from anywhere:

```bash
uv tool install .
```

## OAuth Setup

FreshBooks uses OAuth 2.0 for authentication. This requires creating an app in the FreshBooks Developer Portal.

### Creating a FreshBooks App

1. Go to https://my.freshbooks.com/#/developer
2. Click "Create App"
3. Fill in app details:
   - **App Name:** Your preferred name (e.g., "FreshBooks CLI")
   - **Website:** Can be any URL (e.g., your GitHub repo)
   - **Description:** Brief description of usage
4. Note your **Client ID** and **Client Secret**

### Required OAuth Scopes

When creating your FreshBooks app, enable these scopes:

| Scope | Purpose | Required |
|-------|---------|----------|
| `user:profile:read` | Basic identity info | Yes (auto-included) |
| `user:time_entries:read` | View time entries | Yes |
| `user:time_entries:write` | Add time entries | Yes |
| `user:projects:read` | View projects | Yes |
| `user:clients:read` | View client names | Yes |
| `user:invoices:read` | View invoices | Yes |
| `user:payments:read` | View payments | Yes |
| `user:teams:read` | View team members | Yes |
| `user:billable_items:read` | View services/rates | Yes |
| `user:expenses:read` | View expenses | Yes |

### Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
FRESHBOOKS_CLIENT_ID=your_client_id
FRESHBOOKS_CLIENT_SECRET=your_client_secret
FRESHBOOKS_REDIRECT_URI=https://your-ngrok-url.ngrok-free.app/callback
```

### OAuth Callback (requires HTTPS)

FreshBooks requires HTTPS for OAuth callbacks. Use [ngrok](https://ngrok.com/) for local development:

1. Install ngrok: https://ngrok.com/download

2. Start the tunnel:
   ```bash
   ngrok http 8374
   ```

3. Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

4. Update your `.env` file:
   ```env
   FRESHBOOKS_REDIRECT_URI=https://abc123.ngrok-free.app/callback
   ```

5. Add the same URL to your FreshBooks app in the Developer Portal

6. Authenticate:
   ```bash
   uv run fb auth login
   ```

## Usage

### Financial Reports

```bash
# AR aging report - see outstanding invoices by age bucket
uv run fb reports ar-aging
uv run fb reports ar-aging --json
uv run fb reports ar-aging --export csv

# Client-specific AR - check what a specific client owes
uv run fb reports client-ar --client-name "Acme Corp"
uv run fb reports client-ar --client-id 12345 --detail
uv run fb reports client-ar --client-name "Acme" --json

# Revenue summary - income by period with DSO metric
uv run fb reports revenue --start-date 2026-01-01 --end-date 2026-01-31
uv run fb reports revenue --resolution quarterly --start-date 2026-01-01 --end-date 2026-12-31
uv run fb reports revenue --start-date 2026-01-01 --end-date 2026-03-31 --json
```

### Time Tracking

```bash
# List time entries
uv run fb time list
uv run fb time list --month 2026-01
uv run fb time list --teammate "John Doe"
uv run fb time list --json

# Add a time entry
uv run fb time add --hours 2 --project "Project Name" --note "Task description"
uv run fb time add --hours 1.5 --project "Client Work" --service "Development" --date 2026-01-15

# Time summary
uv run fb time summary --month 2026-01
uv run fb time summary --month 2026-01 --by-teammate
uv run fb time summary --month 2026-01 --by-client --json

# Unbilled time
uv run fb time unbilled
uv run fb time unbilled --by-client
uv run fb time unbilled --by-project --json

# Export time entries
uv run fb time export --month 2026-01 --output timesheet.csv
```

### Invoices

```bash
# List invoices
uv run fb invoices list
uv run fb invoices list --client "Acme Corp"
uv run fb invoices list --status paid
uv run fb invoices list --status overdue --json

# Show invoice details
uv run fb invoices show INV-0001
uv run fb invoices show 12345 --json

# Interactive invoice browser (TUI)
uv run fb invoices browse
```

### Team

```bash
# List team members with rates
uv run fb team
uv run fb team --json
```

### Authentication

```bash
# Login (opens browser for OAuth)
uv run fb auth login

# Check authentication status
uv run fb auth status

# Logout (remove stored tokens)
uv run fb auth logout
```

### Rate Configuration

Cost rates are not exposed by the FreshBooks API. Generate a rates template to configure them:

```bash
uv run fb rates-init
```

Edit the generated file at the credential storage location (see below) to add cost rates for profit tracking.

## Using with Claude Code

This CLI is designed to work as a Claude Code skill. The `--json` flag outputs structured data that Claude can parse and summarize.

### Example Prompts

```
"What's my current AR aging?"
```
Claude runs: `fb reports ar-aging --json`

```
"How much does Acme Corp owe us?"
```
Claude runs: `fb reports client-ar --client-name "Acme Corp" --json`

```
"Show revenue for Q1 2026"
```
Claude runs: `fb reports revenue --start-date 2026-01-01 --end-date 2026-03-31 --json`

```
"What's my DSO for the last 3 months?"
```
Claude runs: `fb reports revenue --start-date 2026-01-01 --end-date 2026-03-31 --resolution monthly --json`

```
"Add 2 hours to Project X for today"
```
Claude runs: `fb time add --hours 2 --project "Project X"`

```
"How much unbilled time do I have?"
```
Claude runs: `fb time unbilled --json`

```
"Show me overdue invoices"
```
Claude runs: `fb invoices list --status overdue --json`

### JSON Output

All commands support `--json` for machine-readable output:

```bash
uv run fb reports ar-aging --json
```

```json
{
  "currency_code": "USD",
  "totals": {
    "total": {"amount": "15000.00", "code": "USD"},
    "bucket_0_30": {"amount": "5000.00", "code": "USD"},
    "bucket_31_60": {"amount": "3000.00", "code": "USD"},
    "bucket_61_90": {"amount": "2000.00", "code": "USD"},
    "bucket_91_plus": {"amount": "5000.00", "code": "USD"}
  }
}
```

## Credential Storage

Credentials and configuration are stored in platform-specific locations:

| Platform | Location |
|----------|----------|
| macOS | `~/Library/Application Support/freshbooks-tools/` |
| Linux | `~/.config/freshbooks-tools/` |
| Windows | `%APPDATA%\freshbooks-tools\` |

### Files

- `tokens.json` - OAuth access and refresh tokens
- `account.json` - Account and business IDs
- `rates.yaml` - Custom cost rate configuration

## Troubleshooting

### "Not authenticated" Error

Check your authentication status:

```bash
uv run fb auth status
```

If tokens are expired or missing, re-authenticate:

```bash
uv run fb auth login
```

### OAuth Callback Failed

FreshBooks requires HTTPS for OAuth callbacks. If you see callback errors:

1. Ensure ngrok is running:
   ```bash
   ngrok http 8374
   ```

2. Verify the HTTPS URL in `.env` matches your ngrok URL:
   ```env
   FRESHBOOKS_REDIRECT_URI=https://abc123.ngrok-free.app/callback
   ```

3. Confirm the same URL is registered in your FreshBooks app settings

4. Retry authentication:
   ```bash
   uv run fb auth login
   ```

### "Connection refused" on localhost:8374

The local OAuth server listens on `127.0.0.1:8374` during authentication.

- Check if port 8374 is available (not used by another process)
- Ensure your firewall allows connections to port 8374
- Try a different port by modifying the redirect URI

### Token Refresh Errors

If token refresh fails repeatedly:

1. Clear existing tokens:
   ```bash
   uv run fb auth logout
   ```

2. Re-authenticate:
   ```bash
   uv run fb auth login
   ```

### Rate Limit Errors

If you see "Rate limit exceeded" errors:

- Wait for the indicated retry time before making more requests
- Reduce request frequency
- Use the `--json` flag and cache results when possible

### API Response Errors

If you see warnings about skipped records:

- Some API responses may have malformed data
- The tool will warn you and continue with valid records
- Check FreshBooks for data consistency issues

## Development

```bash
# Install development dependencies
uv sync

# Run tests
uv run pytest

# Run with verbose output
uv run fb --help

# Check all available commands
uv run fb reports --help
uv run fb time --help
uv run fb invoices --help
```

## License

MIT License - see [LICENSE](LICENSE) file.
