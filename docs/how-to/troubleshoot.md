# Troubleshoot

## "Not authenticated"

```bash
fb auth status
fb auth login        # needs ngrok running; see Getting started
```

## "Missing FRESHBOOKS_CLIENT_ID or FRESHBOOKS_CLIENT_SECRET"

`fb` can't find a `.env`. Either run from the repo directory, or copy it to the config directory:

```bash
fb auth setup path/to/.env
```

## OAuth callback fails

1. Make sure ngrok is running: `ngrok http 8374`.
2. `FRESHBOOKS_REDIRECT_URI` in `.env` must be the current ngrok URL plus `/callback`. Free ngrok URLs change on every restart.
3. The same URL must be registered in your FreshBooks app.
4. Port 8374 must be free. To use another, set `FRESHBOOKS_LOCAL_PORT` and run `ngrok http <port>`.

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

## Rate limit exceeded

Wait for the retry time in the message. The lookup cache keeps repeated commands from re-fetching names and rates, which helps.

## "Skipped N malformed entries"

FreshBooks returned records `fb` couldn't parse. The rest of the output is still valid; check those records in FreshBooks.
