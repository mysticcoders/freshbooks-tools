"""Tests for the default OAuth redirect through the hosted relay."""

import pytest

from freshbooks_tools import auth, config
from freshbooks_tools.config import DEFAULT_REDIRECT_URI, Config


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Point config at an empty directory and clear FreshBooks variables."""
    d = tmp_path / "config"
    monkeypatch.setattr(config, "CONFIG_DIR", d)
    monkeypatch.setattr(config, "ENV_FILE", d / ".env")
    for k in ("FRESHBOOKS_CLIENT_ID", "FRESHBOOKS_CLIENT_SECRET", "FRESHBOOKS_REDIRECT_URI", "FRESHBOOKS_LOCAL_PORT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    return d


def test_redirect_defaults_to_hosted_relay(isolated_env, monkeypatch):
    monkeypatch.setenv("FRESHBOOKS_CLIENT_ID", "cid")
    monkeypatch.setenv("FRESHBOOKS_CLIENT_SECRET", "csec")

    assert config.load_env_config()[2] == "https://freshbooks-tools.wecodefire.com/callback"


def test_empty_redirect_variable_falls_back_to_relay(isolated_env, monkeypatch):
    monkeypatch.setenv("FRESHBOOKS_CLIENT_ID", "cid")
    monkeypatch.setenv("FRESHBOOKS_CLIENT_SECRET", "csec")
    monkeypatch.setenv("FRESHBOOKS_REDIRECT_URI", "")

    assert config.load_env_config()[2] == DEFAULT_REDIRECT_URI


def test_custom_redirect_overrides_relay(isolated_env, monkeypatch):
    monkeypatch.setenv("FRESHBOOKS_CLIENT_ID", "cid")
    monkeypatch.setenv("FRESHBOOKS_CLIENT_SECRET", "csec")
    monkeypatch.setenv("FRESHBOOKS_REDIRECT_URI", "https://abc123.ngrok-free.app/callback")

    assert config.load_env_config()[2] == "https://abc123.ngrok-free.app/callback"


def test_authorization_url_uses_relay():
    url = auth.get_authorization_url(Config(client_id="cid", client_secret="csec"), "state")

    assert "redirect_uri=https%3A%2F%2Ffreshbooks-tools.wecodefire.com%2Fcallback" in url


def test_relay_rejects_custom_local_port(isolated_env, monkeypatch):
    monkeypatch.setenv("FRESHBOOKS_LOCAL_PORT", "9000")

    with pytest.raises(ValueError, match="only forwards to port 8374"):
        auth.start_oauth_flow(Config(client_id="cid", client_secret="csec"))
