# Answer business questions

For business owners and admins: receivables, invoices, unbilled time, revenue and expenses, from the command line or by asking an LLM. What you can see depends on your FreshBooks role; see [Roles and permissions](../explanation/roles-and-permissions.md).

## Set up

Each person uses their own FreshBooks login, so each person sets up `fb` themselves:

1. Follow [Getting started](../tutorials/getting-started.md) through step 5 (log in). Creating your own FreshBooks app is simplest. To share one app instead, its owner shares the client id and secret privately and registers your redirect URI on the app.
2. Optionally [install `fb` globally](install-globally.md) and [connect your LLM](connect-an-llm.md).

If you logged in before `user:reports:read` was added, log in again so your token carries it:

```bash
fb auth logout && fb auth login
```

## Who owes us money?

| Ask the LLM | Or run |
|---|---|
| "What's our AR aging?" | `fb reports ar-aging` |
| "How much does Acme owe?" | `fb reports client-ar --client-name Acme` |
| "Show Acme's invoices" | `fb invoices list --client Acme` |
| "What's overdue?" | `fb invoices list --status overdue` |
| "Show invoice 0000072" | `fb invoices show 0000072` |

## What can we invoice?

| Ask the LLM | Or run |
|---|---|
| "What unbilled time do we have?" | `fb time unbilled --by-client` |
| "Unbilled time by project since October" | `fb time unbilled --by-project --after 2026-10-01` |
| "What did the team log this month?" | `fb time summary -m 11 --by-teammate` |

Amounts come from billable rates. If an amount is zero, no rate is set for that person or service; the LLM tool reports those hours as `hours_without_rate`. See [Rates](../explanation/rates.md).

## How's the business doing?

| Ask the LLM | Or run |
|---|---|
| "Revenue for Q3" | `fb reports revenue --start-date 2026-07-01 --end-date 2026-09-30` |
| "Profit and loss this year by month" | (LLM only: `profit_and_loss`) |
| "What did we spend on software in October?" | `fb reports expense-summary --start-date 2026-10-01 --end-date 2026-10-31` |
| "List expenses from AWS" | `fb expenses list --vendor AWS` |

## Export for an accountant

```bash
fb reports ar-aging --export csv
fb reports expense-summary --start-date 2026-01-01 --end-date 2026-12-31 --export csv
fb time export -m 10 --output october-time.csv
```

All CLI options are in the [CLI reference](../reference/cli.md); the LLM's tools are in the [MCP tools reference](../reference/mcp-tools.md).
