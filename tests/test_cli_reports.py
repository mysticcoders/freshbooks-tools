"""CLI integration tests for reports commands using CliRunner."""

import json
import re

import pytest
from click.testing import CliRunner

from freshbooks_tools.cli import cli
from freshbooks_tools.config import Config, RatesConfig, Tokens


@pytest.fixture
def runner():
    """Create CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_tokens_no_auth():
    """Create mock config with no tokens (unauthenticated)."""
    return None


class TestArAgingCommand:
    """Tests for the ar-aging reports command."""

    def test_ar_aging_json_output(
        self, runner, httpx_mock, mock_config, ar_aging_response, monkeypatch
    ):
        """Verify ar-aging command returns valid JSON with currency_code."""
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config,
        )

        httpx_mock.add_response(
            url=re.compile(r".*/accounting/account/.*/reports/accounting/accounts_aging.*"),
            json=ar_aging_response,
        )

        monkeypatch.setattr(
            "freshbooks_tools.config.load_account_info",
            lambda: ("ABC123", 98765),
        )

        result = runner.invoke(cli, ["reports", "ar-aging", "--json"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "currency_code" in output
        assert output["currency_code"] == "USD"

    def test_ar_aging_requires_auth(self, runner, monkeypatch):
        """Verify ar-aging command fails when not authenticated."""
        mock_config_no_auth = Config(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8374/callback",
            tokens=None,
            rates=RatesConfig(),
        )
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config_no_auth,
        )

        result = runner.invoke(cli, ["reports", "ar-aging"])

        assert result.exit_code != 0
        assert "not authenticated" in result.output.lower() or "auth login" in result.output.lower()


class TestClientArCommand:
    """Tests for the client-ar reports command."""

    def test_client_ar_requires_client_option(self, runner, mock_config, monkeypatch):
        """Verify client-ar command fails without --client-id or --client-name."""
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config,
        )

        result = runner.invoke(cli, ["reports", "client-ar"])

        assert result.exit_code != 0
        assert "client-id" in result.output.lower() or "client-name" in result.output.lower()


class TestRevenueCommand:
    """Tests for the revenue reports command."""

    def test_revenue_requires_dates(self, runner, mock_config, monkeypatch):
        """Verify revenue command fails without --start-date and --end-date."""
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config,
        )

        result = runner.invoke(cli, ["reports", "revenue"])

        assert result.exit_code != 0
        assert "start-date" in result.output.lower() or "required" in result.output.lower()

    def test_revenue_json_output(
        self, runner, httpx_mock, mock_config, ar_aging_response, profit_loss_response, monkeypatch
    ):
        """Verify revenue command returns JSON with periods and ar_balance."""
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config,
        )

        monkeypatch.setattr(
            "freshbooks_tools.config.load_account_info",
            lambda: ("ABC123", 98765),
        )

        httpx_mock.add_response(
            url=re.compile(r".*/accounting/businesses/.*/reports/profit_and_loss.*"),
            json=profit_loss_response,
        )
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/account/.*/reports/accounting/accounts_aging.*"),
            json=ar_aging_response,
        )

        result = runner.invoke(
            cli,
            [
                "reports", "revenue",
                "--start-date", "2026-01-01",
                "--end-date", "2026-01-31",
                "--json",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "periods" in output
        assert "ar_balance" in output
        assert output["ar_balance"] == 1850.0

    def test_revenue_requires_end_date(self, runner, mock_config, monkeypatch):
        """Verify revenue command fails with only --start-date."""
        monkeypatch.setattr(
            "freshbooks_tools.cli.load_config",
            lambda: mock_config,
        )

        result = runner.invoke(
            cli, ["reports", "revenue", "--start-date", "2026-01-01"]
        )

        assert result.exit_code != 0
