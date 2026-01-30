"""Unit tests for ReportsAPI module."""

from decimal import Decimal
import re

import pytest

from freshbooks_tools.api.client import FreshBooksClient
from freshbooks_tools.api.reports import ReportsAPI, calculate_dso, get_days_in_period
from freshbooks_tools.models import AccountAgingReport, ProfitLossReport


class TestGetArAging:
    """Tests for ReportsAPI.get_ar_aging()."""

    def test_get_ar_aging_returns_report(
        self, httpx_mock, mock_config, ar_aging_response
    ):
        """Verify get_ar_aging returns AccountAgingReport with correct data."""
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/account/ABC123/reports/accounting/accounts_aging.*"),
            json=ar_aging_response,
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765
            api = ReportsAPI(client)
            report = api.get_ar_aging()

        assert isinstance(report, AccountAgingReport)
        assert report.currency_code == "USD"
        assert report.company_name == "Test Company"
        assert report.totals.total.amount == Decimal("1850.00")
        assert report.totals.current.amount == Decimal("1000.00")
        assert len(report.accounts) == 1

    def test_get_ar_aging_with_params(
        self, httpx_mock, mock_config, ar_aging_response
    ):
        """Verify start_date, end_date, currency_code params are passed correctly."""
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/account/ABC123/reports/accounting/accounts_aging.*"),
            json=ar_aging_response,
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765
            api = ReportsAPI(client)
            api.get_ar_aging(
                start_date="2026-01-01",
                end_date="2026-01-31",
                currency_code="CAD",
            )

        request = httpx_mock.get_request()
        assert "start_date=2026-01-01" in str(request.url)
        assert "end_date=2026-01-31" in str(request.url)
        assert "currency_code=CAD" in str(request.url)


class TestGetProfitAndLoss:
    """Tests for ReportsAPI.get_profit_and_loss()."""

    def test_get_profit_and_loss_returns_report(
        self, httpx_mock, mock_config, profit_loss_response
    ):
        """Verify get_profit_and_loss returns ProfitLossReport with income periods."""
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/businesses/98765/reports/profit_and_loss.*"),
            json=profit_loss_response,
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765
            api = ReportsAPI(client)
            report = api.get_profit_and_loss(
                start_date="2026-01-01",
                end_date="2026-01-31",
            )

        assert isinstance(report, ProfitLossReport)
        assert report.currency_code == "USD"
        assert report.resolution == "m"
        assert len(report.income) == 1
        assert report.income[0].total.amount == Decimal("10000.00")

    def test_get_profit_and_loss_with_params(
        self, httpx_mock, mock_config, profit_loss_response
    ):
        """Verify all params (start_date, end_date, resolution, currency_code) passed correctly."""
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/businesses/98765/reports/profit_and_loss.*"),
            json=profit_loss_response,
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765
            api = ReportsAPI(client)
            api.get_profit_and_loss(
                start_date="2026-01-01",
                end_date="2026-12-31",
                resolution="q",
                currency_code="EUR",
            )

        request = httpx_mock.get_request()
        assert "start_date=2026-01-01" in str(request.url)
        assert "end_date=2026-12-31" in str(request.url)
        assert "resolution=q" in str(request.url)
        assert "currency_code=EUR" in str(request.url)


class TestCalculateDso:
    """Tests for calculate_dso() helper function."""

    def test_calculate_dso_normal_case(self):
        """Test DSO calculation: (1000 AR / 10000 revenue) * 30 days = 3.0."""
        result = calculate_dso(
            ar_balance=Decimal("1000"),
            revenue=Decimal("10000"),
            days_in_period=30,
        )
        assert result == Decimal("3.0")

    def test_calculate_dso_zero_revenue(self):
        """Test DSO returns None for zero revenue."""
        result = calculate_dso(
            ar_balance=Decimal("1000"),
            revenue=Decimal("0"),
            days_in_period=30,
        )
        assert result is None

    def test_calculate_dso_negative_revenue(self):
        """Test DSO returns None for negative revenue."""
        result = calculate_dso(
            ar_balance=Decimal("1000"),
            revenue=Decimal("-500"),
            days_in_period=30,
        )
        assert result is None


class TestGetDaysInPeriod:
    """Tests for get_days_in_period() helper function."""

    def test_get_days_in_period_monthly(self):
        """Test monthly resolution: January 2026 = 31 days."""
        result = get_days_in_period(year=2026, month=1, resolution="m")
        assert result == 31

    def test_get_days_in_period_monthly_february(self):
        """Test monthly resolution: February 2026 = 28 days (non-leap)."""
        result = get_days_in_period(year=2026, month=2, resolution="m")
        assert result == 28

    def test_get_days_in_period_quarterly(self):
        """Test quarterly resolution: Q1 2026 = 90 days."""
        result = get_days_in_period(year=2026, month=1, resolution="q")
        assert result == 90

    def test_get_days_in_period_yearly(self):
        """Test yearly resolution: 2026 = 365 days (non-leap)."""
        result = get_days_in_period(year=2026, month=1, resolution="y")
        assert result == 365

    def test_get_days_in_period_yearly_leap(self):
        """Test yearly resolution: 2024 = 366 days (leap year)."""
        result = get_days_in_period(year=2024, month=1, resolution="y")
        assert result == 366
