# Authentication

`fb` uses the FreshBooks OAuth 2.0 authorization-code flow, with your own FreshBooks app as the OAuth client.

## Why ngrok

`fb auth login` opens the FreshBooks consent page in your browser and starts a small HTTP server on `127.0.0.1:8374` to receive the redirect. FreshBooks only redirects to HTTPS URLs it has on file for the app, and a laptop has no public HTTPS address. ngrok provides one and forwards it to the local port.

That's only needed during login. Afterwards, `fb` talks to the FreshBooks API directly.

## Tokens

Login returns an access token and a refresh token, saved in `tokens.json` in the config directory. Before each request `fb` checks the access token's expiry, with a five-minute margin, and refreshes it if needed. If a request still gets a 401, `fb` refreshes once and retries. You only log in again if the refresh token itself stops working.

## Account and business ids

The API addresses most data by account id (accounting) or business id (time tracking and projects). `fb` reads both from your profile on the first call and saves them in `account.json`. It uses your first business membership.

## Credentials file

The client id and secret identify your FreshBooks app, not you. They live in `.env` rather than `tokens.json`, so that one app can serve several logins. `fb auth setup` copies the `.env` to the config directory, so an installed `fb` doesn't depend on the repo checkout.
