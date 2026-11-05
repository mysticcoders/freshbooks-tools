# LLM integration

The goal: say "log two hours to acme today" to an assistant and have the right time entry appear in FreshBooks, without naming the service or remembering ids.

## Why MCP instead of the CLI

An assistant with shell access can already run `fb ... --json`. MCP improves on that in three ways:

- **Discovery.** The client learns the tools, their parameters and descriptions when it connects, with no prompt engineering or README reading.
- **Instructions.** The server sends a short workflow, the steps for logging time, that the client gives the model.
- **Approval.** Each tool is marked read-only or not, and clients ask before running write tools.

`fb mcp` uses the same code as the CLI: the same login, cache, aliases and name matching. Anything set up in one works in the other.

## How "usually do development" works

The model doesn't know your habits, so the server tells it. `time_habits` reads your own time entries from the last 90 days and returns, for each project, the hours per service, most-used first, along with your aliases and today's date. The instructions tell the model to use the project's `usual_service` when you don't name one.

That's computed fresh each time rather than stored. If you switch from Development to Discovery for a month, the suggestion follows. An alias is the way to pin a choice: the model can create one with `set_alias` when you ask.

## What happens when it's ambiguous

If a name matches several projects or services, the tool returns an error listing the candidates with their ids, and the instructions tell the model to ask you. Nothing is filed on a guess.

## Errors the model can act on

Tool errors carry the reason: "No project matches 'foo'. Call list_projects…", "Not logged in… run `fb auth login`", or the FreshBooks API's own message, such as a missing OAuth scope. The model can recover or tell you what to do instead of reporting a bare failure.

## Beyond time

Owners and admins get read-only tools for invoices (filterable by client), unbilled time with amounts, receivables aging, profit and loss, expenses, and the team, so "what does Acme owe?" or "what can we invoice?" works the same way. What each person sees depends on their FreshBooks role; see [Roles and permissions](roles-and-permissions.md).

## Without MCP

Everything here is also in the CLI, with `--json` output, including `fb time habits` for the usual-service lookup. [Use the CLI from an agent](../how-to/use-the-cli-from-an-agent.md) gives an agent the same workflow as the MCP instructions.
