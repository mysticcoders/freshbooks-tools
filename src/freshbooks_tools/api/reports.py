"""Reports API module for FreshBooks financial reports."""

import calendar
from decimal import Decimal
from typing import Optional

from ..models import AccountAgingReport, ProfitLossReport
from .client import FreshBooksClient


def calculate_dso(
    ar_balance: Decimal,
    revenue: Decimal,
    days_in_period: int
) -> Optional[Decimal]:
    """
    Calculate Days Sales Outstanding.

    Args:
        ar_balance: Current accounts receivable balance
        revenue: Revenue for the period
        days_in_period: Number of days in the period

    Returns:
        DSO value rounded to 1 decimal place, or None if revenue is zero/negative
    """
    if revenue <= 0:
        return None
    dso = (ar_balance / revenue) * Decimal(days_in_period)
    return dso.quantize(Decimal("0.1"))


def get_days_in_period(year: int, month: int, resolution: str) -> int:
    """
    Get number of days in a period based on resolution.

    Args:
        year: Calendar year
        month: Month number (1-12), used as period start for quarterly
        resolution: "m" (monthly), "q" (quarterly), or "y" (yearly)

    Returns:
        Number of days in the period
    """
    if resolution == "m":
        return calendar.monthrange(year, month)[1]
    elif resolution == "q":
        quarter_month = ((month - 1) // 3) * 3 + 1
        return sum(
            calendar.monthrange(year, quarter_month + i)[1]
            for i in range(3)
        )
    elif resolution == "y":
        return 366 if calendar.isleap(year) else 365
    else:
        raise ValueError(f"Unknown resolution: {resolution}")


class ReportsAPI:
    """API for FreshBooks financial reports."""

    def __init__(self, client: FreshBooksClient):
        """
        Initialize ReportsAPI.

        Args:
            client: Authenticated FreshBooksClient instance
        """
        self.client = client

    def get_ar_aging(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        currency_code: Optional[str] = None,
    ) -> AccountAgingReport:
        """
        Get accounts receivable aging report.

        Args:
            start_date: Filter invoices created after this date (YYYY-MM-DD)
            end_date: Report date (YYYY-MM-DD), defaults to today
            currency_code: Currency filter (e.g., 'USD', 'CAD')

        Returns:
            AccountAgingReport with totals and per-client breakdowns
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if currency_code:
            params["currency_code"] = currency_code

        url = self.client.reports_url("accounts_aging", use_business_id=False)
        response = self.client.get(url, params=params)

        data = response.get("response", {}).get("result", {}).get("accounts_aging", {})

        return AccountAgingReport(**data)

    def get_profit_and_loss(
        self,
        start_date: str,
        end_date: str,
        resolution: str = "m",
        currency_code: Optional[str] = None,
    ) -> ProfitLossReport:
        """
        Get profit and loss report with revenue by period.

        Args:
            start_date: Report start date (YYYY-MM-DD)
            end_date: Report end date (YYYY-MM-DD)
            resolution: Period resolution - "m" (monthly), "q" (quarterly), "y" (yearly)
            currency_code: Currency filter (e.g., 'USD', 'CAD')

        Returns:
            ProfitLossReport with income totals per period
        """
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "resolution": resolution,
            "use_ledger_entries": "true",
        }
        if currency_code:
            params["currency_code"] = currency_code

        url = self.client.reports_url("profit_and_loss", use_business_id=True)
        response = self.client.get(url, params=params)

        data = response.get("response", {}).get("result", {}).get("profit_and_loss", {})

        return ProfitLossReport(**data)
