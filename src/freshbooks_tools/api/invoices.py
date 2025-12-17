"""Invoices and payments API module."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from ..models import Client, Invoice, InvoiceLine, Payment
from .client import FreshBooksClient


class InvoicesAPI:
    """API for querying invoices, payments, and clients."""

    def __init__(self, client: FreshBooksClient):
        self.client = client
        self._clients_cache: Optional[dict[int, Client]] = None

    def list_invoices(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        include_lines: bool = False,
        include_payments: bool = True,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[Invoice], int]:
        """
        List invoices with optional filters.

        Args:
            customer_id: Filter by client ID
            status: Filter by v3_status (draft, sent, viewed, paid, partial, overdue)
            date_min: Minimum create date (YYYY-MM-DD)
            date_max: Maximum create date (YYYY-MM-DD)
            include_lines: Include line items
            include_payments: Include payments
            page: Page number
            per_page: Results per page

        Returns:
            Tuple of (invoices list, total count)
        """
        params = {
            "page": page,
            "per_page": per_page,
        }

        includes = []
        if include_lines:
            includes.append("lines")
        if include_payments:
            includes.append("payments")
        if includes:
            params["include"] = ",".join(includes)

        if customer_id is not None:
            params["search[customerid]"] = customer_id

        if status is not None:
            params["search[v3_status]"] = status

        if date_min is not None:
            params["search[date_min]"] = date_min

        if date_max is not None:
            params["search[date_max]"] = date_max

        url = self.client.accounting_url("invoices/invoices")
        response = self.client.get(url, params=params)

        result = response.get("response", {}).get("result", {})
        invoices_data = result.get("invoices", [])
        total = result.get("total", len(invoices_data))

        invoices = []
        for inv_data in invoices_data:
            try:
                lines = []
                for line in inv_data.get("lines", []):
                    lines.append(InvoiceLine(
                        lineid=line.get("lineid"),
                        name=line.get("name"),
                        description=line.get("description"),
                        qty=Decimal(str(line.get("qty", 1))),
                        unit_cost=Decimal(str(line["unit_cost"]["amount"])) if line.get("unit_cost") else None,
                        amount=Decimal(str(line["amount"]["amount"])) if line.get("amount") else None,
                        type=line.get("type", 0),
                    ))

                payments = []
                for pay in inv_data.get("payments", []):
                    payments.append(Payment(
                        paymentid=pay["paymentid"],
                        invoiceid=pay["invoiceid"],
                        amount=Decimal(str(pay["amount"]["amount"])) if isinstance(pay.get("amount"), dict) else Decimal(str(pay.get("amount", 0))),
                        date=pay.get("date", ""),
                        type=pay.get("type"),
                        note=pay.get("note"),
                        gateway=pay.get("gateway"),
                    ))

                amount_val = None
                if inv_data.get("amount"):
                    if isinstance(inv_data["amount"], dict):
                        amount_val = Decimal(str(inv_data["amount"]["amount"]))
                    else:
                        amount_val = Decimal(str(inv_data["amount"]))

                paid_val = None
                if inv_data.get("paid"):
                    if isinstance(inv_data["paid"], dict):
                        paid_val = Decimal(str(inv_data["paid"]["amount"]))
                    else:
                        paid_val = Decimal(str(inv_data["paid"]))

                outstanding_val = None
                if inv_data.get("outstanding"):
                    if isinstance(inv_data["outstanding"], dict):
                        outstanding_val = Decimal(str(inv_data["outstanding"]["amount"]))
                    else:
                        outstanding_val = Decimal(str(inv_data["outstanding"]))

                invoice = Invoice(
                    invoiceid=inv_data["invoiceid"],
                    invoice_number=inv_data.get("invoice_number"),
                    customerid=inv_data["customerid"],
                    create_date=inv_data.get("create_date", ""),
                    due_date=inv_data.get("due_date"),
                    currency_code=inv_data.get("currency_code", "USD"),
                    status=inv_data.get("status", 1),
                    v3_status=inv_data.get("v3_status"),
                    amount=amount_val,
                    paid=paid_val,
                    outstanding=outstanding_val,
                    discount_value=Decimal(str(inv_data["discount_value"])) if inv_data.get("discount_value") else None,
                    fname=inv_data.get("fname"),
                    lname=inv_data.get("lname"),
                    organization=inv_data.get("organization"),
                    lines=lines,
                    payments=payments,
                )
                invoices.append(invoice)
            except (KeyError, ValueError) as e:
                continue

        return invoices, total

    def list_all_invoices(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
        include_lines: bool = False,
        include_payments: bool = True,
    ) -> list[Invoice]:
        """List all invoices (paginated automatically)."""
        all_invoices = []
        page = 1
        per_page = 100

        while True:
            invoices, total = self.list_invoices(
                customer_id=customer_id,
                status=status,
                date_min=date_min,
                date_max=date_max,
                include_lines=include_lines,
                include_payments=include_payments,
                page=page,
                per_page=per_page,
            )

            all_invoices.extend(invoices)

            if len(all_invoices) >= total or not invoices:
                break

            page += 1

        return all_invoices

    def get_invoice(self, invoice_id: int, include_lines: bool = True, include_payments: bool = True) -> Optional[Invoice]:
        """Get a single invoice by ID."""
        params = {}
        includes = []
        if include_lines:
            includes.append("lines")
        if include_payments:
            includes.append("payments")
        if includes:
            params["include"] = ",".join(includes)

        url = self.client.accounting_url(f"invoices/invoices/{invoice_id}")
        try:
            response = self.client.get(url, params=params)
            inv_data = response.get("response", {}).get("result", {}).get("invoice", {})

            if not inv_data:
                return None

            lines = []
            for line in inv_data.get("lines", []):
                lines.append(InvoiceLine(
                    lineid=line.get("lineid"),
                    name=line.get("name"),
                    description=line.get("description"),
                    qty=Decimal(str(line.get("qty", 1))),
                    unit_cost=Decimal(str(line["unit_cost"]["amount"])) if line.get("unit_cost") else None,
                    amount=Decimal(str(line["amount"]["amount"])) if line.get("amount") else None,
                    type=line.get("type", 0),
                ))

            payments = []
            for pay in inv_data.get("payments", []):
                payments.append(Payment(
                    paymentid=pay["paymentid"],
                    invoiceid=pay["invoiceid"],
                    amount=Decimal(str(pay["amount"]["amount"])) if isinstance(pay.get("amount"), dict) else Decimal(str(pay.get("amount", 0))),
                    date=pay.get("date", ""),
                    type=pay.get("type"),
                    note=pay.get("note"),
                    gateway=pay.get("gateway"),
                ))

            amount_val = None
            if inv_data.get("amount"):
                if isinstance(inv_data["amount"], dict):
                    amount_val = Decimal(str(inv_data["amount"]["amount"]))
                else:
                    amount_val = Decimal(str(inv_data["amount"]))

            paid_val = None
            if inv_data.get("paid"):
                if isinstance(inv_data["paid"], dict):
                    paid_val = Decimal(str(inv_data["paid"]["amount"]))
                else:
                    paid_val = Decimal(str(inv_data["paid"]))

            outstanding_val = None
            if inv_data.get("outstanding"):
                if isinstance(inv_data["outstanding"], dict):
                    outstanding_val = Decimal(str(inv_data["outstanding"]["amount"]))
                else:
                    outstanding_val = Decimal(str(inv_data["outstanding"]))

            return Invoice(
                invoiceid=inv_data["invoiceid"],
                invoice_number=inv_data.get("invoice_number"),
                customerid=inv_data["customerid"],
                create_date=inv_data.get("create_date", ""),
                due_date=inv_data.get("due_date"),
                currency_code=inv_data.get("currency_code", "USD"),
                status=inv_data.get("status", 1),
                v3_status=inv_data.get("v3_status"),
                amount=amount_val,
                paid=paid_val,
                outstanding=outstanding_val,
                fname=inv_data.get("fname"),
                lname=inv_data.get("lname"),
                organization=inv_data.get("organization"),
                lines=lines,
                payments=payments,
            )
        except Exception:
            return None

    def list_clients(self) -> list[Client]:
        """List all clients."""
        url = self.client.accounting_url("users/clients")
        params = {"per_page": 100}

        all_clients = []
        page = 1

        while True:
            params["page"] = page
            response = self.client.get(url, params=params)

            result = response.get("response", {}).get("result", {})
            clients_data = result.get("clients", [])
            total = result.get("total", len(clients_data))

            for c in clients_data:
                try:
                    client = Client(
                        userid=c["userid"],
                        fname=c.get("fname"),
                        lname=c.get("lname"),
                        organization=c.get("organization"),
                        email=c.get("email"),
                        currency_code=c.get("currency_code", "USD"),
                    )
                    all_clients.append(client)
                except (KeyError, ValueError):
                    continue

            if len(all_clients) >= total or not clients_data:
                break

            page += 1

        return all_clients

    def get_clients_by_id(self) -> dict[int, Client]:
        """Get clients indexed by ID."""
        if self._clients_cache is not None:
            return self._clients_cache

        clients = self.list_clients()
        self._clients_cache = {c.id: c for c in clients}
        return self._clients_cache

    def get_client_name(self, customer_id: int) -> str:
        """Get client display name by ID."""
        clients = self.get_clients_by_id()
        if customer_id in clients:
            return clients[customer_id].display_name
        return f"Client {customer_id}"

    def list_payments(
        self,
        invoice_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[Payment], int]:
        """List payments with optional invoice filter."""
        params = {
            "page": page,
            "per_page": per_page,
        }

        if invoice_id is not None:
            params["search[invoiceid]"] = invoice_id

        url = self.client.accounting_url("payments/payments")
        response = self.client.get(url, params=params)

        result = response.get("response", {}).get("result", {})
        payments_data = result.get("payments", [])
        total = result.get("total", len(payments_data))

        payments = []
        for pay in payments_data:
            try:
                amount = Decimal(str(pay["amount"]["amount"])) if isinstance(pay.get("amount"), dict) else Decimal(str(pay.get("amount", 0)))
                payment = Payment(
                    paymentid=pay["paymentid"],
                    invoiceid=pay["invoiceid"],
                    amount=amount,
                    date=pay.get("date", ""),
                    type=pay.get("type"),
                    note=pay.get("note"),
                    gateway=pay.get("gateway"),
                )
                payments.append(payment)
            except (KeyError, ValueError):
                continue

        return payments, total

    def clear_cache(self) -> None:
        """Clear cached client data."""
        self._clients_cache = None
