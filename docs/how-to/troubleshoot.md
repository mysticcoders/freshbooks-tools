# Troubleshoot

## "Not authenticated"

```bash
fb auth status
fb auth login
```

## "Missing FRESHBOOKS_CLIENT_ID or FRESHBOOKS_CLIENT_SECRET"

`fb` can't find a `.env`. Either run from the repo directory, or copy it to the config directory:

```bash
fb auth setup path/to/.env
```

## OAuth callback fails

1. Your FreshBooks app's redirect URI must be exactly `https://freshbooks-tools.wecodefire.com/callback`, or match `FRESHBOOKS_REDIRECT_URI` if you set it.
2. Leave `fb auth login` running until the browser comes back. If the browser shows "connection refused" on `127.0.0.1:8374`, `fb` had stopped listening (it waits two minutes); run it again.
3. Port 8374 must be free. The hosted relay only forwards to 8374. To use another port, run your own tunnel (for example `ngrok http <port>`), set `FRESHBOOKS_LOCAL_PORT`, and set `FRESHBOOKS_REDIRECT_URI` to the tunnel URL plus `/callback`.

## Token refresh keeps failing

```bash
fb auth logout
fb auth login
```

## "insufficient_scope" or 403 errors

Your FreshBooks app or token is missing a scope. Compare your app with [Configuration › OAuth scopes](../reference/configuration.md#oauth-scopes), then log out and in again so the new token carries the scope.

## Names show as "Project 123" or "Service 456"

The lookup cache may be stale or the id may be new. `fb` refetches once on a miss, but you can force it:

```bash
fb cache clear
```

## Amounts show as zero

FreshBooks hides rates from project members. Run `fb rates show` to see what applies, and `fb rates set <rate>` to set yours. See [Configure cost rates](configure-cost-rates.md#billable-amounts-show-as-zero).

## Rate limit exceeded

Wait for the retry time in the message. The lookup cache keeps repeated commands from re-fetching names and rates, which helps.

## "Skipped N malformed entries"

FreshBooks returned records `fb` couldn't parse. The rest of the output is still valid; check those records in FreshBooks.
