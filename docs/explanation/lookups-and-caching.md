# Lookups and caching

Time entries and invoices refer to people, clients, projects and services by id. To show names, `fb` looks those ids up, and without a cache a single `fb time list` makes a dozen or more API calls before printing anything.

## What's cached

Lookup responses: projects, each project's services, team members, staff, project members, clients, the business service list, team member rates and service rates. They're saved in `lookup_cache.json` in the config directory, keyed by request URL.

Time entries, invoices, expenses and reports are not cached. They're the data you're asking about, so they're always fetched fresh.

## When the cache is refreshed

- **On a miss.** If an id or name isn't in the cached data, say a new project, a new client or a service someone just added, `fb` refetches that dataset and saves the result. It does this at most once per dataset per command, so an id that really doesn't exist doesn't cause repeated calls.
- **After 24 hours.** A miss only catches new things. A renamed project or a changed billable rate would otherwise be wrong indefinitely, so every entry expires after a day.
- **On request.** `fb projects list` always refetches projects and services. `fb cache clear` drops everything. `fb auth logout` deletes the cache too, since it holds names, emails and rates.

Rates don't refresh on a miss, because a person without a rate is normal. A changed rate appears within a day, or immediately after `fb cache clear`.

## Matching names

Wherever you can name a project or service (`fb time add`, `fb alias set`, the MCP tools), `fb` tries, in order:

1. An alias name (projects only).
2. An exact id.
3. A case-insensitive substring of the name: `acme` matches "Acme Consulting".

If several match, the CLI asks which one, and the MCP tools return the candidates so the LLM can ask you.

## Why project services are looked up per project

A project's services can be missing from the business-wide service list. They may belong to the client's business rather than yours. So `fb` reads service names from the project first and falls back to the business list.
