# Use the CLI from an agent

When MCP isn't an option (the client doesn't support it, or you'd rather the agent run commands it can show you), an agent with shell access can drive `fb` directly. Point the agent at this page, for example from your `CLAUDE.md` or `AGENTS.md`:

```markdown
For FreshBooks tasks, use the `fb` CLI as described in docs/how-to/use-the-cli-from-an-agent.md.
```

The rest of this page is written for the agent.

---

## Rules

- Add `--json` to every read command and parse stdout as JSON when the exit code is 0.
- A non-zero exit code means failure, and the output is a plain-text error message, not JSON. Report it; don't retry blindly.
- Never run `fb auth login`: it opens a browser and needs the user. If a command says "Not authenticated", ask the user to run it.
- `-h` on `fb time add` means `--hours`, not help. Use `--help` for help.
- Pass ids rather than name fragments to `fb time add` and `fb alias set`. If a fragment matches several projects or services, `fb` prompts, and with no terminal the command fails with "Cancelled".
- Dates are `YYYY-MM-DD`. `-m 10` means October of the current year; `-m 2025-10` for another year.
- Ask the user before running commands that write: `fb time add`, `fb alias set/default/rm`.

## Logging time ("log 2 hours to acme today")

1. Find the user's habits:

   ```bash
   fb time habits --json
   ```

   It returns `today`, `aliases`, `default_alias`, and `projects`, each with `project_id`, `services` (most-used first, with `service_id` and hours) and `usual_service`.

2. Pick the project matching the user's words: alias names, `project`, `client`. If two fit, ask.
3. Use the project's `usual_service` unless the user named a service. For a project with no history:

   ```bash
   fb projects list --json
   ```

   and ask which service.

4. File it, after confirming with the user:

   ```bash
   fb time add --hours 2 --project 1001001 --service 2002002 --note "..."
   ```

   Add `--date YYYY-MM-DD` for a day other than today. The output confirms project, service, date and entry id.

5. If the user wants this to be the default:

   ```bash
   fb alias set acme-dev --project 1001001 --service 2002002 --default
   ```

   After that, `fb time add --hours 2` files to it.

## Questions

| Question | Command |
|---|---|
| What did I log this month? | `fb time list -m 11 --json` |
| What do I usually work on? | `fb time habits --json` |
| Projects and services | `fb projects list --json` |
| Aliases | `fb alias list --json` |
| Unbilled time | `fb time unbilled --by-client --json` |
| Team time this month | `fb time summary -m 11 --by-teammate --json` |
| Invoices for a client | `fb invoices list --client Acme --json` |
| One invoice | `fb invoices show 0000072 --json` |
| Overdue invoices | `fb invoices list --status overdue --json` |
| Receivables by age | `fb reports ar-aging --json` |
| What a client owes | `fb reports client-ar --client-name Acme --json` |
| Revenue | `fb reports revenue --start-date 2026-01-01 --end-date 2026-03-31 --json` |
| Expenses | `fb expenses list --start-date 2026-10-01 --json` |
| Team members | `fb team --json` |

Every command and option is in the [CLI reference](../reference/cli.md).

## Errors

| Message | Meaning | What to do |
|---|---|---|
| Not authenticated | No login | Ask the user to run `fb auth login` |
| Missing FRESHBOOKS_CLIENT_ID | No credentials found | Ask the user to run `fb auth setup path/to/.env` |
| insufficient_scope / 403 | Token or role doesn't allow it | Tell the user; they may need `fb auth logout` and `fb auth login`, or a different FreshBooks role |
| No projects found matching | Bad name | Run `fb projects list --json` and pick by id |
| Cancelled | Ambiguous name prompted with no terminal | Retry with ids |
