"""Detail lookups tell "not found" apart from failures that must reach the user."""

import importlib
import re

import httpx
import pytest

from freshbooks_tools import exceptions
from freshbooks_tools.api.client import FreshBooksClient

from .conftest import load_fixture

DATA = load_fixture("detail_lookup_failures.json")
CASES = [(lookup, outcome) for lookup in DATA["lookups"] for outcome in DATA["outcomes"]]


def _client(mock_config) -> FreshBooksClient:
    client = FreshBooksClient(mock_config)
    client._account_id = "ABC123"
    client._business_id = 98765
    return client


@pytest.mark.parametrize(
    "lookup,outcome", CASES, ids=[f"{lookup['id']}-{outcome['id']}" for lookup, outcome in CASES]
)
def test_detail_lookup(httpx_mock, mock_config, lookup, outcome):
    url = re.compile(rf".*/accounting/account/ABC123/{lookup['path']}/7(\?.*)?$")
    if "exception" in outcome:
        httpx_mock.add_exception(getattr(httpx, outcome["exception"])("slow"), url=url)
    else:
        httpx_mock.add_response(url=url, status_code=outcome["status"], json=outcome["body"])
    api = getattr(importlib.import_module(lookup["module"]), lookup["cls"])

    with _client(mock_config) as client:
        call = getattr(api(client), lookup["method"])
        if "raises" not in outcome:
            assert call(7) is None
            return
        error = getattr(exceptions, outcome["raises"])  # NotFoundError does not exist yet
        with pytest.raises(error, match=outcome.get("match")):
            call(7)
