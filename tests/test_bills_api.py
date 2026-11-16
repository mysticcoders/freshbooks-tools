"""Unit tests for BillsAPI."""

import re
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from freshbooks_tools.api.bills import BillsAPI
from freshbooks_tools.api.client import FreshBooksClient

BILLS_URL = re.compile(r".*/accounting/account/ABC123/bills/bills(\?.*)?$")


def _bill(bill_id: int, **overrides) -> dict:
    """A bill as the FreshBooks API returns it, with money as {amount, code} objects."""
    bill = {
        "id": bill_id,
        "bill_number": f"B-{bill_id}",
        "amount": {"amount": "150.00", "code": "USD"},
        "outstanding": {"amount": "50.00", "code": "USD"},
        "paid": {"amount": "100.00", "code": "USD"},
        "issue_date": "2026-10-01",
        "due_date": "2026-10-31",
        "status": "partial",
        "vendor": {"vendorid": 7, "vendor_name": "Acme Supplies"},
        "lines": [
            {
                "id": 1,
                "description": "Paper",
                "amount": {"amount": "150.00", "code": "USD"},
                "quantity": "3",
                "unit_cost": {"amount": "50.00", "code": "USD"},
                "category": {"category": "Office Supplies"},
                "tax_name1": "GST",
                "tax_amount1": {"amount": "7.50", "code": "USD"},
            }
        ],
    }
    bill.update(overrides)
    return bill


def _response(bills: list[dict], total: int) -> dict:
    return {"response": {"result": {"bills": bills, "total": total}}}


def _client(mock_config) -> FreshBooksClient:
    client = FreshBooksClient(mock_config)
    client._account_id = "ABC123"
    client._business_id = 98765
    return client


def test_list_parses_money_vendor_and_lines(httpx_mock, mock_config):
    httpx_mock.add_response(url=BILLS_URL, json=_response([_bill(1)], 1))

    with _client(mock_config) as client:
        bills, total = BillsAPI(client).list()

    assert total == 1
    bill = bills[0]
    assert bill.amount == Decimal("150.00")
    assert bill.outstanding == Decimal("50.00")
    assert bill.paid == Decimal("100.00")
    assert bill.currency_code == "USD"
    assert bill.display_vendor == "Acme Supplies"
    assert bill.display_status == "Partial"
    line = bill.lines[0]
    assert line.quantity == Decimal("3")
    assert line.unit_cost == Decimal("50.00")
    assert line.category == "Office Supplies"
    assert line.tax_amount1 == Decimal("7.50")


def test_list_sends_filters(httpx_mock, mock_config):
    httpx_mock.add_response(url=BILLS_URL, json=_response([], 0))

    with _client(mock_config) as client:
        BillsAPI(client).list(date_min="2026-10-01", date_max="2026-10-31", vendor_name="Acme", status="overdue")

    params = parse_qs(urlparse(str(httpx_mock.get_request().url)).query)
    assert params["search[date_min]"] == ["2026-10-01"]
    assert params["search[date_max]"] == ["2026-10-31"]
    assert params["search[vendor_name]"] == ["Acme"]
    assert params["search[status]"] == ["overdue"]
    assert params["include[]"] == ["vendor"]


def test_list_all_follows_pages(httpx_mock, mock_config):
    httpx_mock.add_response(url=BILLS_URL, json=_response([_bill(i) for i in range(100)], 101))
    httpx_mock.add_response(url=BILLS_URL, json=_response([_bill(100)], 101))

    with _client(mock_config) as client:
        bills = BillsAPI(client).list_all()

    assert len(bills) == 101
    pages = [parse_qs(urlparse(str(r.url)).query)["page"] for r in httpx_mock.get_requests()]
    assert pages == [["1"], ["2"]]


def test_display_vendor_falls_back_to_id(httpx_mock, mock_config):
    httpx_mock.add_response(url=BILLS_URL, json=_response([_bill(2, vendor={"vendorid": 9})], 1))

    with _client(mock_config) as client:
        bills, _ = BillsAPI(client).list()

    assert bills[0].display_vendor == "Vendor 9"


def test_get_returns_none_when_missing(httpx_mock, mock_config):
    httpx_mock.add_response(
        url=re.compile(r".*/accounting/account/ABC123/bills/bills/404.*"),
        json={"response": {"result": {}}},
    )

    with _client(mock_config) as client:
        assert BillsAPI(client).get(404) is None
