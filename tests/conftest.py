"""Shared pytest fixtures for FreshBooks tools tests."""

import json
from pathlib import Path

import pytest

from freshbooks_tools.config import Config, Tokens, RatesConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture
def mock_tokens():
    """Create mock OAuth tokens for testing."""
    return Tokens(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_type="Bearer",
    )


@pytest.fixture
def mock_config(mock_tokens):
    """Create mock application config."""
    return Config(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8374/callback",
        tokens=mock_tokens,
        rates=RatesConfig(),
    )


@pytest.fixture
def ar_aging_response():
    """Load AR aging API response fixture."""
    return load_fixture("ar_aging_response.json")


@pytest.fixture
def profit_loss_response():
    """Load P&L API response fixture."""
    return load_fixture("profit_loss_response.json")


@pytest.fixture
def user_me_response():
    """Load user identity API response fixture."""
    return load_fixture("user_me_response.json")
