# Setup and development tasks for freshbooks-tools. Run `just` to list them.

redirect_doc := "docs/tutorials/getting-started.md (section 3, Set the redirect URI)"

# List the recipes.
default:
    @just --list

# Check the tools and credentials that setup needs. Fails only on a missing required tool.
doctor:
    #!/usr/bin/env bash
    fail=0
    if command -v uv >/dev/null; then
        echo "ok    uv: $(uv --version)"
    else
        echo "FAIL  uv is missing. Install it: https://docs.astral.sh/uv/getting-started/installation/"
        fail=1
    fi
    if ! command -v uv >/dev/null; then
        echo "SKIP  Python 3.11+ is checked through uv."
    elif py=$(uv python find '>=3.11' 2>/dev/null); then
        echo "ok    Python 3.11+: ${py}"
    else
        echo "FAIL  Python 3.11+ is missing. Install it: uv python install 3.11"
        fail=1
    fi
    if [[ ! -f .env ]]; then
        echo "WARN  .env is missing. Copy .env.example to .env and add your FreshBooks app credentials."
        echo "      See docs/tutorials/getting-started.md (section 4)."
    elif grep -Eq '^FRESHBOOKS_CLIENT_ID=.+' .env && grep -Eq '^FRESHBOOKS_CLIENT_SECRET=.+' .env \
        && ! grep -Eq '^FRESHBOOKS_CLIENT_(ID|SECRET)=your_' .env; then
        echo "ok    .env has a client id and secret"
    else
        echo "WARN  .env has no real FRESHBOOKS_CLIENT_ID or FRESHBOOKS_CLIENT_SECRET."
    fi
    exit ${fail}

# Install the project and its dev dependencies into .venv.
sync:
    uv sync

# Install fb on your PATH and copy .env to the config directory.
install: doctor
    uv tool install . --force
    @if [ -f .env ]; then fb auth setup .env; else echo "WARN  No .env, so 'fb auth setup' was skipped. Run it after you create .env."; fi

# Run the test suite.
test *args:
    uv run pytest {{args}}

# Log in to FreshBooks through the hosted redirect relay.
login:
    @echo "Your FreshBooks app's redirect URI must be https://freshbooks-tools.wecodefire.com/callback"
    @echo "  (or match FRESHBOOKS_REDIRECT_URI if you run your own tunnel)."
    @echo "  Details: {{redirect_doc}}"
    uv run fb auth login
