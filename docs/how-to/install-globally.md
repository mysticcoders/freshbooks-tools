# Install `fb` globally

Use `fb` from any directory, without `uv run`.

```bash
cd freshbooks-tools
uv tool install .
fb auth setup .env
```

With [just](https://just.systems/) installed, `just install` runs both steps. It runs `just doctor` first, which checks for uv, Python 3.11+, ngrok and a `.env`. If there is no `.env`, it skips `fb auth setup`.

`uv tool install` can't copy files, so `fb auth setup` does it: it checks the `.env` has a client id and secret, then copies it to the config directory, readable only by you. It asks before replacing an existing one.

Check it from somewhere else:

```bash
cd ~
fb auth status
```

## Update after pulling changes

```bash
uv tool install . --force
```

Your tokens, aliases and cache are in the config directory, so reinstalling keeps them.

## Where credentials are read from

The `.env` in the config directory first, then `.env` in the current directory. See [Configuration](../reference/configuration.md).
