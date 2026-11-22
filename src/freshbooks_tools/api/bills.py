"""Bills API module."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..models import Bill, BillLine
from .client import FreshBooksClient


class BillsAPI:
    """API for querying bills."""

    def __init__(self, client: FreshBooksClient):
        self.client = client

    def _parse_amount(self, data, default_code: str = "USD") -> tuple[Decimal, str]:
        """Parse an amount field that may be a dict or scalar."""
        if isinstance(data, dict):
            return Decimal(str(data.get("amount", "0"))), data.get("code", default_code)
        if data is not None:
            return Decimal(str(data)), default_code
        return Decimal("0"), default_code

    def _parse_bill(self, data: dict) -> Bill:
        """Parse bill data from API response."""
        amount, currency_code = self._parse_amount(data.get("amount", {}))
        outstanding, _ = self._parse_amount(data.get("outstanding", {}))
        paid, _ = self._parse_amount(data.get("paid", {}))

        vendor_data = data.get("vendor", {})
        vendorid = vendor_data.get("vendorid") if vendor_data else None
        vendor_name = vendor_data.get("vendor_name") if vendor_data else None

        lines = []
        for line_data in data.get("lines", []):
            line_amount, _ = self._parse_amount(line_data.get("amount", {}))
            unit_cost = None
            uc_data = line_data.get("unit_cost", {})
            if isinstance(uc_data, dict) and uc_data.get("amount"):
                unit_cost = Decimal(str(uc_data["amount"]))
            elif uc_data and not isinstance(uc_data, dict):
                unit_cost = Decimal(str(uc_data))

            tax_amount1 = None
            t1 = line_data.get("tax_amount1")
            if isinstance(t1, dict) and t1.get("amount"):
                tax_amount1 = Decimal(str(t1["amount"]))
            elif t1 and not isinstance(t1, dict):
                tax_amount1 = Decimal(str(t1))

            tax_amount2 = None
            t2 = line_data.get("tax_amount2")
            if isinstance(t2, dict) and t2.get("amount"):
                tax_amount2 = Decimal(str(t2["amount"]))
            elif t2 and not isinstance(t2, dict):
                tax_amount2 = Decimal(str(t2))

            category_data = line_data.get("category")
            category_name = None
            if isinstance(category_data, dict):
                category_name = category_data.get("category")
            elif isinstance(category_data, str):
                category_name = category_data

            lines.append(BillLine(
                id=line_data.get("id"),
                amount=line_amount,
                description=line_data.get("description"),
                quantity=Decimal(str(line_data.get("quantity", "1"))),
                unit_cost=unit_cost,
                category=category_name,
                list_index=line_data.get("list_index"),
                tax_name1=line_data.get("tax_name1"),
                tax_amount1=tax_amount1,
                tax_name2=line_data.get("tax_name2"),
                tax_amount2=tax_amount2,
            ))

        return Bill(
            id=data["id"],
            vendorid=vendorid,
            vendor_name=vendor_name,
            bill_number=data.get("bill_number"),
            amount=amount,
            currency_code=currency_code,
            outstanding=outstanding,
            paid=paid,
            overall_category=data.get("overall_category"),
            overall_description=data.get("overall_description"),
            issue_date=data.get("issue_date"),
            due_date=data.get("due_date"),
            status=data.get("status"),
            vis_state=data.get("vis_state", 0),
            lines=lines,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def list(
        self,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        vendor_name: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[Bill], int]:
        """
        List bills with optional filters.

        Args:
            date_min: Minimum issue date (YYYY-MM-DD)
            date_max: Maximum issue date (YYYY-MM-DD)
            vendor_name: Filter by vendor name
            status: Filter by status
            page: Page number
            per_page: Results per page

        Returns:
            Tuple of (bills list, total count)
        """
        params: dict = {
            "page": page,
            "per_page": per_page,
            "include[]": "vendor",
        }

        if date_min is not None:
            params["search[date_min]"] = date_min

        if date_max is not None:
            params["search[date_max]"] = date_max

        if vendor_name is not None:
            params["search[vendor_name]"] = vendor_name

        if status is not None:
            params["search[status]"] = status

        url = self.client.accounting_url("bills/bills")
        response = self.client.get(url, params=params)

        result = response.get("response", {}).get("result", {})
        bills_data = result.get("bills", [])
        total = result.get("total", len(bills_data))

        bills = []
        for bill_data in bills_data:
            try:
                bill = self._parse_bill(bill_data)
                bills.append(bill)
            except (KeyError, ValueError):
                continue

        return bills, total

    def list_all(
        self,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        vendor_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Bill]:
        """List all bills (paginated automatically)."""
        all_bills = []
        page = 1
        per_page = 100

        while True:
            bills, total = self.list(
                date_min=date_min,
                date_max=date_max,
                vendor_name=vendor_name,
                status=status,
                page=page,
                per_page=per_page,
            )

            all_bills.extend(bills)

            if len(all_bills) >= total or not bills:
                break

            page += 1

        return all_bills

    def get(self, bill_id: int) -> Optional[Bill]:
        """Get a single bill by ID.

        Returns None when FreshBooks answers with an empty result.

        Raises:
            NotFoundError: FreshBooks answered 404.
            FreshBooksError: any other API or network failure, unchanged, so
                a missing scope or a timeout never reads as "not found".
        """
        url = self.client.accounting_url(f"bills/bills/{bill_id}")
        response = self.client.get(url, params={"include[]": "vendor"})
        bill_data = response.get("response", {}).get("result", {}).get("bill", {})

        if not bill_data:
            return None

        return self._parse_bill(bill_data)
