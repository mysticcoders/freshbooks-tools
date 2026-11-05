# Configuration and files

## Config directory

| Platform | Location |
|---|---|
| macOS | `~/Library/Application Support/freshbooks-tools/` |
| Linux | `~/.config/freshbooks-tools/` |
| Windows | `%APPDATA%\freshbooks-tools\` |

The directory is created with owner-only permissions (0700); files `fb` writes there are 0600.

## Environment variables

Read from `.env` in the config directory if it exists, otherwise from `.env` in the current directory, then from the process environment.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `FRESHBOOKS_CLIENT_ID` | yes | | OAuth app client id |
| `FRESHBOOKS_CLIENT_SECRET` | yes | | OAuth app client secret |
| `FRESHBOOKS_REDIRECT_URI` | for login | `http://localhost:8374/callback` | Must be HTTPS and registered in the app |
| `FRESHBOOKS_LOCAL_PORT` | no | `8374` | Port the login callback listens on |

## Files

| File | Written by | Contents |
|---|---|---|
| `.env` | `fb auth setup` | Credentials (above) |
| `tokens.json` | `fb auth login`, token refresh | OAuth access and refresh tokens |
| `account.json` | first API call | Account id and business id |
| `aliases.json` | `fb alias`, MCP `set_alias` | Aliases and the default alias |
| `lookup_cache.json` | most commands | Cached names, team, clients, services and rates |
| `rates.yaml` | `fb rates-init`, you | Cost and billable rate overrides |

`fb auth logout` deletes `tokens.json` and `lookup_cache.json`. `fb cache clear` deletes `lookup_cache.json`.

### aliases.json

```json
{
  "default": "acme-dev",
  "aliases": {
    "acme-dev": {
      "project_id": 1001001,
      "project": "Acme Consulting",
      "service_id": 2002002,
      "service": "Development"
    }
  }
}
```

`service_id` and `service` are `null` for a project-only alias. Ids are what `fb` uses; the names are for reading.

### lookup_cache.json

Keyed by request URL. Each entry holds the time it was fetched and the API response. Entries older than 24 hours are refetched. See [Lookups and caching](../explanation/lookups-and-caching.md).

### rates.yaml

```yaml
default_cost_rate: 50.00
default_billable_rate: 150.00

# by email
cost_rates:
  "john@example.com": 50.00
billable_rates:
  "john@example.com": 150.00

# by FreshBooks identity id (see fb team --json)
members:
  9535329:
    name: "Joseph Ottinger"     # for your reference only
    cost_rate: 75.00
    billable_rate: 200.00

# billable rate by project id (see fb projects list)
projects:
  1001001:
    billable_rate: 125.00
```

A `members` billable rate takes precedence over a `projects` one. The full order is in [Rates](../explanation/rates.md).

## OAuth scopes

Enable these on your FreshBooks app. `fb auth login` requests them all.

| Scope | Used for |
|---|---|
| `user:profile:read` | Your identity, account and business ids |
| `user:time_entries:read` | Time lists, summaries, `time_habits` |
| `user:time_entries:write` | `fb time add`, `add_time_entry` |
| `user:projects:read` | Projects and their services |
| `user:clients:read` | Client names |
| `user:billable_items:read` | Services and service rates |
| `user:invoices:read` | Invoices |
| `user:payments:read` | Invoice payments |
| `user:teams:read` | Team members |
| `user:expenses:read` | Expenses |
| `user:reports:read` | AR aging, revenue, profit and loss |

Adding a scope to the app doesn't change an existing token: run `fb auth logout` and `fb auth login` afterwards.

Scopes say what `fb` may ask for; your FreshBooks role decides what you get. A contractor's token can carry `user:reports:read` and still be refused reports. See [Roles and permissions](../explanation/roles-and-permissions.md).
