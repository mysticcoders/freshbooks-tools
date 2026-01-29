"""Reports API module for FreshBooks financial reports."""

from typing import Optional

from ..models import AccountAgingReport
from .client import FreshBooksClient


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
