# FreshBooks Tools

A Python CLI for querying FreshBooks time entries, invoices, and team data with support for cost/billable rate tracking and an interactive invoice browser.

## Features

- **Time Tracking**: List, filter, and export time entries by teammate and month
- **Rate Management**: Track billable rates (from API) and cost rates (local config) for profit analysis
- **Invoice Browser**: Interactive TUI for browsing invoices with color-coded statuses
- **Team Management**: View team members and contractors with their rates
- **OAuth Authentication**: Secure FreshBooks API authentication with token refresh

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/yourusername/freshbooks-tools.git
cd freshbooks-tools

# Install dependencies
uv sync
```

## Configuration

### FreshBooks API Credentials

1. Create a FreshBooks app at https://my.freshbooks.com/#/developer
2. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
FRESHBOOKS_CLIENT_ID=your_client_id
FRESHBOOKS_CLIENT_SECRET=your_client_secret
FRESHBOOKS_REDIRECT_URI=https://your-ngrok-url.ngrok-free.app
```

### OAuth Setup (requires HTTPS)

FreshBooks requires HTTPS for OAuth callbacks. Use [ngrok](https://ngrok.com/) for local development:

```bash
# Start ngrok
ngrok http 8374

# Copy the HTTPS URL to your .env file
# Example: https://abc123.ngrok-free.app
```

Then authenticate:

```bash
uv run fb auth login
```

### Rate Configuration

Cost rates are not exposed by the FreshBooks API. Generate a rates template:

```bash
uv run fb rates-init
```

Edit the generated file at `~/.config/freshbooks-tools/rates.yaml` to add cost rates for profit tracking.

## Usage

### Time Entries

```bash
# List time entries for current month
uv run fb time list

# List entries for a specific month
uv run fb time list --month 2024-12

# Filter by teammate
uv run fb time list --teammate "John Doe"

# Show monthly summary
uv run fb time summary --month 2024-12

# Export to CSV
uv run fb time export --month 2024-12 --output timesheet.csv
```

### Invoices

```bash
# Launch interactive invoice browser (TUI)
uv run fb invoices browse

# List invoices
uv run fb invoices list

# Filter by status
uv run fb invoices list --status paid
uv run fb invoices list --status overdue

# Show specific invoice
uv run fb invoices show 12345
```

### Team

```bash
# List all team members and contractors with rates
uv run fb team
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

## Invoice Browser

The interactive invoice browser (`fb invoices browse`) provides a three-panel interface:

- **Left**: Client list sorted by invoice count
- **Center**: Invoice table with status, amount, and outstanding balance
- **Right**: Detailed view with payments and line items

**Keyboard shortcuts:**
- Arrow keys: Navigate
- `Enter`: Select
- `r`: Refresh data
- `q` or `Esc`: Quit

**Status colors:**
- Green: Paid
- Yellow: Partial
- Cyan: Viewed
- Blue: Sent
- Red: Overdue

## Data Storage

- **Tokens**: `~/.config/freshbooks-tools/tokens.json`
- **Rates**: `~/.config/freshbooks-tools/rates.yaml`

## Development

```bash
# Run tests
uv run pytest

# Run with verbose output
uv run fb --help
```

## License

MIT License - see [LICENSE](LICENSE) file.
