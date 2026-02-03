"""Expenses API module."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..models import Expense, ExpenseCategory
from .client import FreshBooksClient


class ExpensesAPI:
    """API for querying expenses."""

    def __init__(self, client: FreshBooksClient):
        self.client = client
        self._categories_cache: Optional[dict[int, ExpenseCategory]] = None

    def _parse_expense(self, data: dict) -> Expense:
        """Parse expense data from API response."""
        amount_data = data.get("amount", {})
        if isinstance(amount_data, dict):
            amount = Decimal(str(amount_data.get("amount", "0")))
            currency_code = amount_data.get("code", "USD")
        else:
            amount = Decimal(str(amount_data)) if amount_data else Decimal("0")
            currency_code = "USD"

        tax_amount1 = None
        tax1_data = data.get("taxAmount1", {})
        if isinstance(tax1_data, dict) and tax1_data.get("amount"):
            tax_amount1 = Decimal(str(tax1_data["amount"]))
        elif tax1_data and not isinstance(tax1_data, dict):
            tax_amount1 = Decimal(str(tax1_data))

        tax_amount2 = None
        tax2_data = data.get("taxAmount2", {})
        if isinstance(tax2_data, dict) and tax2_data.get("amount"):
            tax_amount2 = Decimal(str(tax2_data["amount"]))
        elif tax2_data and not isinstance(tax2_data, dict):
            tax_amount2 = Decimal(str(tax2_data))

        return Expense(
            expenseid=data["expenseid"],
            amount=amount,
            currency_code=currency_code,
            date=data.get("date", ""),
            vendor=data.get("vendor"),
            categoryid=data.get("categoryid"),
            staffid=data.get("staffid"),
            clientid=data.get("clientid"),
            projectid=data.get("projectid"),
            notes=data.get("notes"),
            status=data.get("status", 0),
            taxAmount1=tax_amount1,
            taxAmount2=tax_amount2,
            taxName1=data.get("taxName1"),
            taxName2=data.get("taxName2"),
            invoiceid=data.get("invoiceid"),
            vis_state=data.get("vis_state", 0),
        )

    def list(
        self,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        categoryid: Optional[int] = None,
        vendor: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[Expense], int]:
        """
        List expenses with optional filters.

        Args:
            date_min: Minimum expense date (YYYY-MM-DD)
            date_max: Maximum expense date (YYYY-MM-DD)
            categoryid: Filter by category ID
            vendor: Filter by vendor name
            status: Filter by status (0=internal, 1=outstanding, 2=invoiced, 4=recouped)
            page: Page number
            per_page: Results per page

        Returns:
            Tuple of (expenses list, total count)
        """
        params = {
            "page": page,
            "per_page": per_page,
        }

        if date_min is not None:
            params["search[date_min]"] = date_min

        if date_max is not None:
            params["search[date_max]"] = date_max

        if categoryid is not None:
            params["search[categoryid]"] = categoryid

        if vendor is not None:
            params["search[vendor]"] = vendor

        if status is not None:
            params["search[status]"] = status

        url = self.client.accounting_url("expenses/expenses")
        response = self.client.get(url, params=params)

        result = response.get("response", {}).get("result", {})
        expenses_data = result.get("expenses", [])
        total = result.get("total", len(expenses_data))

        expenses = []
        for exp_data in expenses_data:
            try:
                expense = self._parse_expense(exp_data)
                expenses.append(expense)
            except (KeyError, ValueError):
                continue

        return expenses, total

    def list_all(
        self,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        categoryid: Optional[int] = None,
        vendor: Optional[str] = None,
        status: Optional[int] = None,
    ) -> list[Expense]:
        """List all expenses (paginated automatically)."""
        all_expenses = []
        page = 1
        per_page = 100

        while True:
            expenses, total = self.list(
                date_min=date_min,
                date_max=date_max,
                categoryid=categoryid,
                vendor=vendor,
                status=status,
                page=page,
                per_page=per_page,
            )

            all_expenses.extend(expenses)

            if len(all_expenses) >= total or not expenses:
                break

            page += 1

        return all_expenses

    def get(self, expense_id: int) -> Optional[Expense]:
        """Get a single expense by ID."""
        url = self.client.accounting_url(f"expenses/expenses/{expense_id}")
        try:
            response = self.client.get(url)
            exp_data = response.get("response", {}).get("result", {}).get("expense", {})

            if not exp_data:
                return None

            return self._parse_expense(exp_data)
        except Exception:
            return None

    def list_categories(self) -> list[ExpenseCategory]:
        """List all expense categories (cached)."""
        if self._categories_cache is not None:
            return list(self._categories_cache.values())

        all_categories = []
        page = 1
        per_page = 100

        while True:
            params = {
                "page": page,
                "per_page": per_page,
            }

            url = self.client.accounting_url("expenses/categories")
            response = self.client.get(url, params=params)

            result = response.get("response", {}).get("result", {})
            categories_data = result.get("categories", [])
            total = result.get("total", len(categories_data))

            for cat_data in categories_data:
                try:
                    category = ExpenseCategory(
                        categoryid=cat_data["categoryid"],
                        category=cat_data.get("category", ""),
                        is_cogs=cat_data.get("is_cogs", False),
                        vis_state=cat_data.get("vis_state", 0),
                    )
                    all_categories.append(category)
                except (KeyError, ValueError):
                    continue

            if len(all_categories) >= total or not categories_data:
                break

            page += 1

        self._categories_cache = {cat.id: cat for cat in all_categories}
        return all_categories

    def get_category_name(self, category_id: int) -> str:
        """Get category name by ID (uses cache)."""
        self.list_categories()
        if self._categories_cache and category_id in self._categories_cache:
            return self._categories_cache[category_id].name
        return f"Category {category_id}"

    def clear_cache(self) -> None:
        """Clear cached category data."""
        self._categories_cache = None
