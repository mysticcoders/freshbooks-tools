# Setup and development tasks for freshbooks-tools. Run `just` to list them.

ngrok_doc := "docs/tutorials/getting-started.md (section 3, Open an HTTPS tunnel)"

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
    if command -v ngrok >/dev/null; then
        echo "ok    ngrok: $(ngrok version)"
    else
        echo "WARN  ngrok is missing. It is needed only for 'fb auth login'."
        echo "      Install it: https://ngrok.com/download"
        echo "      Set it up: {{ngrok_doc}}"
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

# Log in to FreshBooks. Start ngrok first; this recipe does not start it.
login:
    @echo "fb auth login needs an HTTPS tunnel to port 8374:"
    @echo "  1. In another terminal, run: ngrok http 8374"
    @echo "  2. Set FRESHBOOKS_REDIRECT_URI in .env to the ngrok URL plus /callback."
    @echo "  Details: {{ngrok_doc}}"
    uv run fb auth login
