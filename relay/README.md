# OAuth redirect relay

FreshBooks only redirects to HTTPS URLs and rejects localhost. `fb auth login` listens on `http://127.0.0.1:8374/callback`. This Cloudflare Worker, served at `https://freshbooks-tools.wecodefire.com`, joins the two:

- `GET /callback` redirects (302) to `http://127.0.0.1:8374/callback` with the same query string (`code`, `state`, `error`).
- `GET /` explains what the host is for.
- Anything else returns 404.

It never sees the client secret, stores nothing, and has logging turned off. Responses are `Cache-Control: no-store` and `Referrer-Policy: no-referrer`, so the code isn't cached or leaked in a `Referer` header.

## Develop and deploy

Requires Node.js 22.18+ and the [`cf` CLI](https://developers.cloudflare.com/cf/).

```bash
cd relay
npm install
npm run typecheck
cf dev       # local server; try /callback?code=test
cf deploy    # publishes to the domain in cloudflare.config.ts
```

To host your own copy, change `domains` in `cloudflare.config.ts` to a hostname on a zone in your Cloudflare account, deploy, and set `FRESHBOOKS_REDIRECT_URI` to `https://<your-host>/callback`.
