# FreshBooks Tools

A CLI and MCP server for FreshBooks: log time, check receivables, invoices, unbilled time, revenue and expenses from your terminal, or by asking Claude, Codex or another LLM.

```bash
fb time add --hours 2                 # to your default project and service
fb time habits                        # what you usually log, and where
fb invoices list --status overdue
fb reports ar-aging
```

Or, with `fb mcp` registered in your LLM client:

> Log two hours to acme today.
>
> What can we invoice this month?

## Quick start

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and a FreshBooks app with OAuth credentials.

```bash
git clone https://github.com/mysticcoders/freshbooks-tools.git
cd freshbooks-tools
uv sync
cp .env.example .env          # add your FreshBooks client id, secret and redirect URI
uv run fb auth login          # needs an HTTPS tunnel such as ngrok during login
uv run fb projects list
```

[Getting started](docs/tutorials/getting-started.md) walks through every step, including creating the FreshBooks app.

To use `fb` from anywhere:

```bash
uv tool install .
fb auth setup .env            # copy credentials where the installed fb can find them
```

To connect Claude Code:

```bash
claude mcp add --scope user freshbooks -- fb mcp
```

Other clients, and agents without MCP, are covered in [Connect an LLM](docs/how-to/connect-an-llm.md) and [Use the CLI from an agent](docs/how-to/use-the-cli-from-an-agent.md).

## Documentation

- **Tutorial:** [Getting started](docs/tutorials/getting-started.md)
- **How-to:** [Log time with aliases](docs/how-to/log-time-with-aliases.md) · [Connect an LLM](docs/how-to/connect-an-llm.md) · [Use the CLI from an agent](docs/how-to/use-the-cli-from-an-agent.md) · [Answer business questions](docs/how-to/answer-business-questions.md) · [Install globally](docs/how-to/install-globally.md) · [Run reports and exports](docs/how-to/run-reports.md) · [Configure cost rates](docs/how-to/configure-cost-rates.md) · [Troubleshoot](docs/how-to/troubleshoot.md)
- **Reference:** [CLI commands](docs/reference/cli.md) · [MCP tools](docs/reference/mcp-tools.md) · [Configuration and files](docs/reference/configuration.md)
- **Explanation:** [Authentication](docs/explanation/authentication.md) · [Roles and permissions](docs/explanation/roles-and-permissions.md) · [Lookups and caching](docs/explanation/lookups-and-caching.md) · [Rates](docs/explanation/rates.md) · [LLM integration](docs/explanation/llm-integration.md)

## Development

```bash
uv sync
uv run pytest
uv run pytest --cov=freshbooks_tools --cov-report=term-missing
uv run python scripts/gen_reference.py   # after changing commands or MCP tools
```

## License

MIT License. See [LICENSE](LICENSE).
