# Authentication

`fb` uses the FreshBooks OAuth 2.0 authorization-code flow, with your own FreshBooks app as the OAuth client.

## The redirect relay

`fb auth login` opens the FreshBooks consent page in your browser and starts a small HTTP server on `127.0.0.1:8374` to receive the redirect. FreshBooks only redirects to HTTPS URLs it has on file for the app, and it rejects localhost, so it can't send the browser straight to that server.

`https://freshbooks-tools.wecodefire.com/callback` fills the gap. It's a Cloudflare Worker that answers every request to `/callback` with a redirect to `http://127.0.0.1:8374/callback`, keeping the query string. Your browser follows it, and `fb` receives the authorization code locally.

- It's the default `FRESHBOOKS_REDIRECT_URI`, so the only setup is registering it on your FreshBooks app.
- It never sees your client secret. The authorization code passes through it in the URL, but a code is useless without the secret, expires quickly and can only be used once.
- It stores nothing, and logging is turned off.
- The source is in [`relay/`](../../relay/). Deploy your own copy with `cf deploy` from that directory, after changing the domain in `relay/cloudflare.config.ts`.

To use your own tunnel instead, such as ngrok, set `FRESHBOOKS_REDIRECT_URI` to the tunnel URL plus `/callback` and register that on the app. Set `FRESHBOOKS_LOCAL_PORT` if the tunnel forwards to a port other than 8374.

The relay is only involved during login. Afterwards, `fb` talks to the FreshBooks API directly.

## Tokens

Login returns an access token and a refresh token, saved in `tokens.json` in the config directory. Before each request `fb` checks the access token's expiry, with a five-minute margin, and refreshes it if needed. If a request still gets a 401, `fb` refreshes once and retries. You only log in again if the refresh token itself stops working.

FreshBooks issues a new refresh token on every refresh and invalidates the old one. So that `fb mcp` and a CLI command running at the same time don't both spend the same refresh token, `fb` refreshes while holding a lock on `tokens.lock`, and first re-reads `tokens.json` in case another process already refreshed.

Each login also sends a random `state` value, and the callback is rejected unless FreshBooks returns the same value, so a forged callback can't log `fb` in to someone else's account.

## Account and business ids

The API addresses most data by account id (accounting) or business id (time tracking and projects). `fb` reads both from your profile on the first call and saves them in `account.json`. It uses your first business membership.

## Credentials file

The client id and secret identify your FreshBooks app, not you. They live in `.env` rather than `tokens.json`, so that one app can serve several logins. `fb auth setup` copies the `.env` to the config directory, so an installed `fb` doesn't depend on the repo checkout.
