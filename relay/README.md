# OAuth redirect relay

FreshBooks only redirects to HTTPS URLs and rejects localhost. `fb auth login` listens on `http://127.0.0.1:8374/callback`. This Cloudflare Worker, served at `https://freshbooks-tools.wecodefire.com`, joins the two:

- `GET /callback` redirects (302) to `http://127.0.0.1:8374/callback` with the same query string (`code`, `state`, `error`).
- Everything else is the static site in `public/`, a one-page explainer covering setup with the hosted callback, how the callback works, and how to host your own or use ngrok. Unknown paths return 404.

Only `/callback` runs the Worker (`assets.runWorkerFirst` in `cloudflare.config.ts`); the site is served as static assets with the security headers in `public/_headers`.

The relay never sees the client secret, stores nothing, and has logging turned off. Responses are `Cache-Control: no-store` and `Referrer-Policy: no-referrer`, so the code isn't cached or leaked in a `Referer` header.

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
