# Connect an LLM

If your client can't use MCP, or you'd rather the agent run visible commands, see [Use the CLI from an agent](use-the-cli-from-an-agent.md) instead.

`fb mcp` runs an [MCP](https://modelcontextprotocol.io/) server over stdio. Register it with an MCP client once, and you can ask things like "log two hours to acme today" or "what's overdue?". The [MCP tools reference](../reference/mcp-tools.md) lists what the LLM can do.

## Before you start

- Log in once in a terminal: `fb auth login`. The MCP server can't run the browser login itself.
- Install `fb` on your PATH ([Install `fb` globally](install-globally.md)), or use the `uv run --project` form below.
- Check it starts: `fb mcp` should sit waiting for input. Press Ctrl-C to stop it.

## Claude Code

```bash
claude mcp add --scope user freshbooks -- fb mcp
```

Without a global install:

```bash
claude mcp add --scope user freshbooks -- uv run --project /path/to/freshbooks-tools fb mcp
```

Run `/mcp` inside Claude Code to confirm it's connected.

## Claude Desktop

Edit `claude_desktop_config.json` (Settings › Developer › Edit Config). Desktop apps don't inherit your shell's PATH, so use the full path from `which fb`:

```json
{
  "mcpServers": {
    "freshbooks": {
      "command": "/Users/you/.local/bin/fb",
      "args": ["mcp"]
    }
  }
}
```

Restart Claude Desktop.

## Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.freshbooks]
command = "fb"
args = ["mcp"]
```

## Ollama and other local models

Ollama serves models but doesn't launch MCP servers itself. Use an MCP-capable client that drives Ollama models, and configure it to run the command `fb` with the argument `mcp` over stdio. Tool use works best with models trained for it.

## Try it

- "Log two hours to acme today."
- "Add another hour to acme." (adds to today's entry instead of creating a second one)
- "What did I work on this week?"
- "Make acme development my default."
- "Show me overdue invoices."
- "What can we invoice this month?" (owners and admins; see [Answer business questions](answer-business-questions.md))

When you ask to log time, the LLM calls `time_habits` first. That tells it which service you usually use on each project, so "two hours to acme" becomes two hours of Development if that's what you normally log there. It then calls `add_time_entry`, which your client will normally ask you to approve.

## If it doesn't work

- **"Not logged in"**: run `fb auth login` in a terminal.
- **"Missing FRESHBOOKS_CLIENT_ID"**: the server can't find your `.env`. Run `fb auth setup path/to/.env`; see [Install `fb` globally](install-globally.md).
- **A tool says "insufficient_scope"**: your FreshBooks app or login lacks a scope. See [Configuration › OAuth scopes](../reference/configuration.md#oauth-scopes).
