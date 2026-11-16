# Upgrade from v1.2

This guide is for people who set up `fb` at the v1.2 release. It lists the changes that need action, in the order to do them.

## 1. Enable the new scopes on your FreshBooks app

`fb` now requests two scopes that v1.2 did not request:

| Scope | Used for |
|---|---|
| `user:reports:read` | AR aging, revenue, profit and loss |
| `user:bills:read` | Bills (`fb bills`, `list_bills`, `get_bill`) |

`fb auth login` requests every scope in [Configuration › OAuth scopes](../reference/configuration.md#oauth-scopes). Your app must have each of these scopes enabled. If one is missing from the app, login or the commands that need it fail.

1. Open https://my.freshbooks.com/#/developer and select your app.
2. Enable `user:reports:read` and `user:bills:read`.
3. Save the app.

## 2. Change the redirect URI (optional)

v1.2 needed an ngrok tunnel for the login redirect. `fb` now uses a hosted relay by default, so you don't need ngrok.

Your ngrok setup still works. `fb` uses `FRESHBOOKS_REDIRECT_URI` when it is set. To change to the relay:

1. On your FreshBooks app, add this redirect URI: `https://freshbooks-tools.wecodefire.com/callback`.
2. In your `.env`, delete the `FRESHBOOKS_REDIRECT_URI` line, or set it to the URI in step 1.

[Authentication](../explanation/authentication.md#the-redirect-relay) explains how the relay works.

## 3. Log in again

A token keeps the scopes it was issued with. Your v1.2 token does not have the new scopes, so get a new token:

```bash
fb auth logout && fb auth login
```

## 4. Check the config folder (macOS only)

On macOS, v1.2 kept its files in `~/Library/Application Support/freshbooks-tools`. `fb` now uses `~/.config/freshbooks-tools`.

You don't need to do anything. The first `fb` command moves the files and prints what it moved. If a file exists in both folders, `fb` keeps the new one and leaves the old one where it is.

On Linux and Windows, the folder did not change.

## 5. Copy your credentials to the config folder (optional)

v1.2 read `.env` from the current directory only. `fb` still does that, but it reads `.env` in the config folder first. Copy it there so `fb` works from any directory:

```bash
fb auth setup path/to/.env
```

## Check the upgrade

```bash
fb auth status
fb reports ar-aging
fb bills list --limit 1
```

If a command reports `insufficient_scope` or 403, see [Troubleshoot](troubleshoot.md#insufficient_scope-or-403-errors).
