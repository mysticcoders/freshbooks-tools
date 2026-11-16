"""Tests for OAuth state checking, callback escaping and locked token refresh."""

import socketserver
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest

from freshbooks_tools import auth, config
from freshbooks_tools.config import Config, Tokens


@pytest.fixture
def callback_server():
    """Run OAuthCallbackHandler for one request on a free port; yields a GET helper."""
    auth.OAuthCallbackHandler.authorization_code = None
    auth.OAuthCallbackHandler.error = None
    auth.OAuthCallbackHandler.expected_state = "expected-state"
    server = socketserver.TCPServer(("127.0.0.1", 0), auth.OAuthCallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    def get(params: dict) -> httpx.Response:
        url = f"http://127.0.0.1:{server.server_address[1]}/callback?{urlencode(params)}"
        return httpx.get(url, timeout=5)

    yield get
    thread.join(timeout=5)
    server.server_close()
    auth.OAuthCallbackHandler.expected_state = None


def test_authorization_url_carries_state():
    url = auth.get_authorization_url(Config(client_id="cid", client_secret="csec"), "abc123")

    assert parse_qs(urlparse(url).query)["state"] == ["abc123"]


def test_callback_accepts_matching_state(callback_server):
    response = callback_server({"code": "the-code", "state": "expected-state"})

    assert response.status_code == 200
    assert auth.OAuthCallbackHandler.authorization_code == "the-code"
    assert auth.OAuthCallbackHandler.error is None


def test_callback_rejects_wrong_state(callback_server):
    response = callback_server({"code": "forged-code", "state": "other"})

    assert response.status_code == 400
    assert auth.OAuthCallbackHandler.authorization_code is None
    assert "State mismatch" in auth.OAuthCallbackHandler.error


def test_callback_rejects_missing_state(callback_server):
    response = callback_server({"code": "forged-code"})

    assert response.status_code == 400
    assert auth.OAuthCallbackHandler.authorization_code is None


def test_callback_escapes_error_description(callback_server):
    response = callback_server({
        "error": "access_denied",
        "error_description": "<script>alert(1)</script>",
        "state": "expected-state",
    })

    assert response.status_code == 400
    assert "<script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def _tokens(access: str, refresh: str, expires_in_minutes: int) -> Tokens:
    return Tokens(
        access_token=access,
        refresh_token=refresh,
        expires_at=datetime.now() + timedelta(minutes=expires_in_minutes),
    )


@pytest.fixture
def token_dir(tmp_path, monkeypatch):
    """Point token storage and its lock at a temporary directory."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "TOKENS_FILE", tmp_path / "tokens.json")
    monkeypatch.setattr(config, "TOKENS_LOCK_FILE", tmp_path / "tokens.lock")
    return tmp_path


def test_refresh_reuses_tokens_another_process_saved(token_dir, monkeypatch):
    stale = _tokens("old-access", "old-refresh", -1)
    config.save_tokens(_tokens("new-access", "new-refresh", 600))
    calls = []
    monkeypatch.setattr(auth, "refresh_access_token", lambda c: calls.append(c) or None)
    cfg = Config(client_id="cid", client_secret="csec", tokens=stale)

    result = auth.refresh_tokens_locked(cfg)

    assert calls == []
    assert result.access_token == "new-access"
    assert cfg.tokens.access_token == "new-access"


def test_refresh_uses_newest_refresh_token_on_disk(token_dir, monkeypatch):
    config.save_tokens(_tokens("disk-access", "disk-refresh", -1))
    used = []

    def fake_refresh(c):
        used.append(c.tokens.refresh_token)
        return _tokens("fresh-access", "fresh-refresh", 600)

    monkeypatch.setattr(auth, "refresh_access_token", fake_refresh)
    cfg = Config(client_id="cid", client_secret="csec", tokens=_tokens("held-access", "held-refresh", -1))

    result = auth.refresh_tokens_locked(cfg)

    assert used == ["disk-refresh"]
    assert result.access_token == "fresh-access"
    assert config.load_tokens().refresh_token == "fresh-refresh"


def test_concurrent_refreshes_call_freshbooks_once(token_dir, monkeypatch):
    stale = _tokens("old-access", "old-refresh", -1)
    config.save_tokens(stale)
    calls = []

    def slow_refresh(c):
        calls.append(c.tokens.refresh_token)
        time.sleep(0.2)
        return _tokens(f"access-{len(calls)}", f"refresh-{len(calls)}", 600)

    monkeypatch.setattr(auth, "refresh_access_token", slow_refresh)
    configs = [Config(client_id="cid", client_secret="csec", tokens=stale) for _ in range(2)]
    threads = [threading.Thread(target=auth.refresh_tokens_locked, args=(c,)) for c in configs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert calls == ["old-refresh"]
    assert {c.tokens.access_token for c in configs} == {"access-1"}
