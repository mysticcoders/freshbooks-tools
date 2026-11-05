# Log time with aliases

An alias names a project, and optionally a service, so you can log time without typing either.

## Find the ids

```bash
fb projects list          # or --json
```

## Create aliases

`-p` and `-s` take an id or any part of a name. The alias stores ids, so renaming the project in FreshBooks doesn't break it.

```bash
fb alias set acme-dev  -p 1001001 -s 2002002 --default
fb alias set acme-meet -p acme -s meet
```

`--default` makes it the alias `fb time add` uses when you don't pass `-p`.

## Log time

```bash
fb time add -h 2                         # default alias
fb time add -h 1 -p acme-meet -n "standup"
fb time add -h 3 -p acme-dev -s disc    # alias's project, different service
fb time add -h 2 -d 2026-11-03           # a past date
```

`-p` accepts an alias, a project id, or part of a project name, in that order. If a name matches several projects, `fb` asks which one.

## Manage aliases

```bash
fb alias list             # --json for scripts
fb alias default acme-meet
fb alias rm acme-meet    # clears the default too, if it was the default
```

Aliases live in `aliases.json` in the config directory; see [Configuration](../reference/configuration.md#files).
