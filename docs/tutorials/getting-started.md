# Getting started

In this tutorial you'll connect `fb` to your FreshBooks account, look at your projects, and log your first time entry. It takes about fifteen minutes, most of it in the FreshBooks developer portal.

You'll need Python 3.11+, [uv](https://docs.astral.sh/uv/), [ngrok](https://ngrok.com/download), and a FreshBooks account.

## 1. Install

```bash
git clone https://github.com/mysticcoders/freshbooks-tools.git
cd freshbooks-tools
uv sync
uv run fb --help
```

You should see the list of command groups: `auth`, `time`, `projects`, `alias`, and so on.

## 2. Create a FreshBooks app

`fb` talks to FreshBooks through OAuth, so it needs an app of its own.

1. Open https://my.freshbooks.com/#/developer and click **Create App**.
2. Give it any name, website and description.
3. Enable the scopes listed in [Configuration › OAuth scopes](../reference/configuration.md#oauth-scopes).
4. Keep the page open: you'll need the **Client ID**, the **Client Secret**, and the redirect URI field.

## 3. Open an HTTPS tunnel

FreshBooks only redirects to HTTPS URLs, and the login flow listens on your machine. ngrok bridges the two. In a separate terminal:

```bash
ngrok http 8374
```

Copy the `https://…ngrok-free.app` URL it prints. Add `<that URL>/callback` as the redirect URI in your FreshBooks app.

## 4. Add your credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
FRESHBOOKS_CLIENT_ID=<client id>
FRESHBOOKS_CLIENT_SECRET=<client secret>
FRESHBOOKS_REDIRECT_URI=https://abc123.ngrok-free.app/callback
```

## 5. Log in

```bash
uv run fb auth login
```

A browser window opens. Approve the app, and the terminal reports success. Check it:

```bash
uv run fb auth status
```

You can stop ngrok now. It's only needed to log in; after that `fb` refreshes its token on its own.

## 6. Look at your projects

```bash
uv run fb projects list
```

Each project shows its id, client, and services:

```text
  Acme Consulting (id 1001001)
    Client: Acme Corp
    - Meetings (id 2002001)
    - Development (id 2002002)
    - Discovery (id 2002003)
```

## 7. Log time

Name the project and service by any part of their names:

```bash
uv run fb time add --hours 2 --project acme --service dev --note "First entry from fb"
```

Then see it:

```bash
uv run fb time list -m 11
```

`-m 11` means November of this year.

## 8. Make it shorter

Save the project and service you use most as a default alias:

```bash
uv run fb alias set acme-dev -p acme -s dev --default
uv run fb time add --hours 2
```

That's the whole loop. From here:

- [Log time with aliases](../how-to/log-time-with-aliases.md) covers aliases in more depth.
- [Connect an LLM](../how-to/connect-an-llm.md) lets you say "log two hours to acme today" to Claude instead.
- [Install `fb` globally](../how-to/install-globally.md) drops the `uv run` prefix.
