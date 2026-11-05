# FreshBooks Tools documentation

The docs follow [Diataxis](https://diataxis.fr/): pick the section by what you're trying to do.

| | |
|---|---|
| **[Tutorials](tutorials/)**: learn by doing | [Getting started](tutorials/getting-started.md): from a FreshBooks app to your first time entry |
| **[How-to guides](how-to/)**: get a task done | [Log time with aliases](how-to/log-time-with-aliases.md) · [Connect an LLM (MCP)](how-to/connect-an-llm.md) · [Use the CLI from an agent](how-to/use-the-cli-from-an-agent.md) · [Answer business questions](how-to/answer-business-questions.md) · [Install `fb` globally](how-to/install-globally.md) · [Run reports and exports](how-to/run-reports.md) · [Configure cost rates](how-to/configure-cost-rates.md) · [Troubleshoot](how-to/troubleshoot.md) |
| **[Reference](reference/)**: look something up | [CLI commands](reference/cli.md) · [MCP tools](reference/mcp-tools.md) · [Configuration and files](reference/configuration.md) |
| **[Explanation](explanation/)**: understand how it works | [Authentication](explanation/authentication.md) · [Roles and permissions](explanation/roles-and-permissions.md) · [Lookups and caching](explanation/lookups-and-caching.md) · [Rates](explanation/rates.md) · [LLM integration](explanation/llm-integration.md) |

`reference/cli.md` and `reference/mcp-tools.md` are generated from the code by `scripts/gen_reference.py`; the test suite fails if they go stale.
