"""Tests for the MCP server tools."""

import asyncio
import json
import re

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from freshbooks_tools import mcp_server
from freshbooks_tools.config import Config, RatesConfig, save_aliases

ME = re.compile(r".*/auth/api/v1/users/me$")
ENTRIES = re.compile(r".*/timetracking/business/42/time_entries\?.*")
PROJECTS = re.compile(r".*/timetracking/business/42/projects\?.*")
ACME = re.compile(r".*/projects/business/42/project/1$")
CLIENTS = re.compile(r".*/accounting/account/ACCT/users/clients.*")
CREATE = re.compile(r".*/timetracking/business/42/time_entries$")

PROJECT_LIST = {"projects": [
    {"id": 1, "title": "Acme Consulting", "client_id": 4},
    {"id": 2, "title": "Acme Labs", "client_id": 4},
]}
ACME_DETAIL = {"project": {"id": 1, "title": "Acme Consulting", "services": [
    {"id": 10, "name": "Development"}, {"id": 11, "name": "Discovery"}, {"id": 12, "name": "Meetings"}]}}


def entry(i, service_id, hours, day):
    return {"id": i, "identity_id": 5, "project_id": 1, "service_id": service_id,
            "duration": int(hours * 3600), "started_at": f"2026-11-0{day}T09:00:00Z"}


@pytest.fixture(autouse=True)
def logged_in(monkeypatch, mock_config):
    monkeypatch.setattr(mcp_server, "load_config", lambda: mock_config)
    monkeypatch.setattr("freshbooks_tools.api.client.load_account_info", lambda: ("ACCT", 42))


def created(httpx_mock):
    return json.loads(httpx_mock.get_requests(method="POST")[0].content)["time_entry"]


def no_existing(httpx_mock):
    httpx_mock.add_response(url=ME, json={"response": {"id": 5}})
    httpx_mock.add_response(url=ENTRIES, json={"time_entries": [], "meta": {"pages": 1, "total": 0}})


def mock_create(httpx_mock):
    httpx_mock.add_response(method="POST", url=CREATE, json={"time_entry": {
        "id": 99, "identity_id": 5, "duration": 7200, "started_at": "2026-11-05T09:00:00Z"}})


def test_tools_registered_with_write_tools_marked():
    tools = {t.name: t for t in asyncio.run(mcp_server.server.list_tools())}
    assert {"time_habits", "add_time_entry", "set_alias", "list_projects"} <= set(tools)
    assert tools["add_time_entry"].annotations.read_only_hint is False
    assert tools["time_habits"].annotations.read_only_hint is True


def test_time_habits_ranks_services_by_hours(httpx_mock):
    httpx_mock.add_response(url=ME, json={"response": {"id": 5}})
    httpx_mock.add_response(url=ENTRIES, json={"time_entries": [
        entry(1, 10, 2, 5), entry(2, 10, 5, 3), entry(3, 11, 1, 1)], "meta": {"pages": 1, "total": 3}})
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ACME, json=ACME_DETAIL)
    httpx_mock.add_response(url=CLIENTS, json={"response": {"result": {"clients": [{"userid": 4, "organization": "Mystic"}], "total": 1}}})

    habits = mcp_server.time_habits()

    [project] = habits["projects"]
    assert project["project"] == "Acme Consulting"
    assert project["client"] == "Mystic"
    assert project["hours"] == 8.0
    assert project["usual_service"] == {"service_id": 10, "service": "Development", "hours": 7.0}
    assert project["last_logged"] == "2026-11-05"
    assert "identity_id=5" in str(httpx_mock.get_requests(url=ENTRIES)[0].url)


def test_add_time_entry_by_name_and_service(httpx_mock):
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ACME, json=ACME_DETAIL)
    no_existing(httpx_mock)
    mock_create(httpx_mock)

    result = mcp_server.add_time_entry(hours=2, project="acme consulting", service="dev", date="2026-11-05", note="api work")

    assert result["project"] == "Acme Consulting" and result["service"] == "Development"
    sent = created(httpx_mock)
    assert (sent["project_id"], sent["service_id"], sent["client_id"], sent["duration"]) == (1, 10, 4, 7200)
    assert sent["started_at"] == "2026-11-05T09:00:00"
    assert sent["note"] == "api work"


def test_add_time_entry_uses_default_alias(httpx_mock):
    save_aliases({"default": "acme-dev", "aliases": {"acme-dev": {
        "project_id": 1, "project": "Acme Consulting", "service_id": 10, "service": "Development"}}})
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    no_existing(httpx_mock)
    mock_create(httpx_mock)

    result = mcp_server.add_time_entry(hours=2)

    assert result["service"] == "Development"
    assert (created(httpx_mock)["project_id"], created(httpx_mock)["service_id"]) == (1, 10)


def test_add_time_entry_ambiguous_project_lists_candidates(httpx_mock):
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)

    with pytest.raises(ToolError, match=r"Acme Consulting \(id 1\).*Acme Labs \(id 2\)"):
        mcp_server.add_time_entry(hours=1, project="acme")
    assert not httpx_mock.get_requests(method="POST")


@pytest.mark.parametrize("hours", [0, -1, 25])
def test_add_time_entry_rejects_bad_hours(hours):
    with pytest.raises(ToolError, match="hours"):
        mcp_server.add_time_entry(hours=hours, project="acme consulting")


def test_set_alias_saves_ids(httpx_mock):
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ACME, json=ACME_DETAIL)

    result = mcp_server.set_alias("acme-dev", project="Acme Consulting", service="development", make_default=True)

    assert result["default"] is True
    assert mcp_server.list_aliases()["aliases"]["acme-dev"]["service_id"] == 10


def test_not_logged_in(monkeypatch):
    monkeypatch.setattr(mcp_server, "load_config", lambda: Config("id", "secret", "uri", None, RatesConfig()))
    with pytest.raises(ToolError, match="fb auth login"):
        mcp_server.list_projects()


def test_api_errors_reach_the_llm(httpx_mock):
    httpx_mock.add_response(url=PROJECTS, status_code=403, json={"error": "insufficient_scope"})
    with pytest.raises(ToolError, match="insufficient_scope"):
        mcp_server.list_projects()


def test_list_invoices_filters_by_client(httpx_mock):
    httpx_mock.add_response(url=CLIENTS, json={"response": {"result": {"clients": [
        {"userid": 4, "organization": "Acme"}, {"userid": 5, "organization": "Beta"}], "total": 2}}})
    httpx_mock.add_response(url=re.compile(r".*/accounting/account/ACCT/invoices/invoices.*"), json={"response": {"result": {
        "invoices": [{"invoiceid": 1, "customerid": 4, "create_date": "2026-10-01", "status": 2,
                      "amount": {"amount": "100.00"}, "outstanding": {"amount": "60.00"}, "organization": "Acme"}],
        "total": 1, "pages": 1}}})

    result = mcp_server.list_invoices(client="acme")

    assert httpx_mock.get_requests()[-1].url.params["search[customerid]"] == "4"
    assert result["outstanding_in_results"] == "60.00"
    assert result["invoices"][0]["client"] == "Acme"


def test_unbilled_time_totals_by_client_and_project(httpx_mock, monkeypatch):
    from decimal import Decimal

    monkeypatch.setattr("freshbooks_tools.api.rates.RatesAPI.get_billable_rate",
                        lambda self, identity_id, service_id=None, project_id=None: Decimal("100") if service_id == 10 else None)
    httpx_mock.add_response(url=ENTRIES, json={"time_entries": [
        {**entry(1, 10, 2, 5), "client_id": 4}, {**entry(2, 11, 1, 4), "client_id": 4}], "meta": {"pages": 1, "total": 2}})
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=CLIENTS, json={"response": {"result": {"clients": [{"userid": 4, "organization": "Mystic"}], "total": 1}}})

    result = mcp_server.unbilled_time()

    assert result["by_client_and_project"] == [{"client": "Mystic", "project": "Acme Consulting",
                                                "hours": 3.0, "amount": "200.00", "hours_without_rate": 1.0}]
    url = str(httpx_mock.get_requests(url=ENTRIES)[0].url)
    assert "billed=false" in url and "billable=true" in url


def test_time_habits_cli_json(monkeypatch):
    from click.testing import CliRunner
    from freshbooks_tools.cli import cli

    monkeypatch.setattr(mcp_server, "time_habits", lambda days: {"today": "2026-11-05", "days": days,
                                                                 "default_alias": None, "aliases": {}, "projects": []})
    result = CliRunner().invoke(cli, ["time", "habits", "--days", "7", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["days"] == 7


UPDATE = re.compile(r".*/timetracking/business/42/time_entries/\d+$")


def alias_dev():
    save_aliases({"default": "dev", "aliases": {"dev": {
        "project_id": 1, "project": "Acme Consulting", "service_id": 10, "service": "Development"}}})


def test_add_time_entry_adds_to_matching_entry(httpx_mock):
    alias_dev()
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ME, json={"response": {"id": 5}})
    httpx_mock.add_response(url=ENTRIES, json={"time_entries": [
        {**entry(7, 10, 2, 5), "note": "morning"},
        {**entry(8, 10, 1, 5), "billed": True},          # billed: never touched
        {**entry(9, 11, 3, 5)},                          # other service
        {**entry(6, 10, 4, 4)},                          # other day
    ], "meta": {"pages": 1, "total": 4}})
    httpx_mock.add_response(method="PUT", url=UPDATE, json={"time_entry": {}})

    result = mcp_server.add_time_entry(hours=1, date="2026-11-05", note="afternoon")

    assert (result["action"], result["entry_id"], result["hours_before"], result["hours_now"]) == ("updated", 7, 2.0, 3.0)
    put = httpx_mock.get_requests(method="PUT")[0]
    assert str(put.url).endswith("/time_entries/7")
    assert json.loads(put.content)["time_entry"] == {"duration": 3 * 3600, "note": "morning; afternoon"}
    assert not httpx_mock.get_requests(method="POST")


def test_add_time_entry_new_entry_skips_merge(httpx_mock):
    alias_dev()
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ME, json={"response": {"id": 5}})
    mock_create(httpx_mock)

    result = mcp_server.add_time_entry(hours=1, new_entry=True)

    assert result["action"] == "created"
    assert not httpx_mock.get_requests(url=ENTRIES)


def test_cli_time_add_reports_update(httpx_mock, monkeypatch, mock_config):
    from datetime import date
    from click.testing import CliRunner
    from freshbooks_tools.cli import cli

    monkeypatch.setattr("freshbooks_tools.cli.load_config", lambda: mock_config)
    alias_dev()
    httpx_mock.add_response(url=PROJECTS, json=PROJECT_LIST)
    httpx_mock.add_response(url=ME, json={"response": {"id": 5}})
    httpx_mock.add_response(url=ENTRIES, json={"time_entries": [
        {"id": 7, "identity_id": 5, "project_id": 1, "service_id": 10, "duration": 7200,
         "started_at": f"{date.today().isoformat()}T09:00:00Z"}], "meta": {"pages": 1, "total": 1}})
    httpx_mock.add_response(method="PUT", url=UPDATE, json={"time_entry": {}})

    result = CliRunner().invoke(cli, ["time", "add", "-h", "1"])

    assert result.exit_code == 0, result.output
    assert "2.00h -> 3.00h" in result.output


@pytest.mark.parametrize("project, expected", [
    ({"billing_method": "project_rate", "rate": "140.00"}, "140.00"),
    ({"billing_method": "team_member_rate", "group": {"members": [{"identity_id": 5, "rate": "110"}]}}, "110"),
    ({"billing_method": "project_rate", "rate": None}, None),   # hidden from members: fall through
    ({"billing_method": "business_rate"}, None),
])
def test_billable_rate_follows_project_billing_method(httpx_mock, project, expected):
    from decimal import Decimal
    from freshbooks_tools.api.client import FreshBooksClient
    from freshbooks_tools.api.rates import RatesAPI
    from freshbooks_tools.api.team import TeamAPI

    config = mcp_server.load_config()
    httpx_mock.add_response(url=ACME, json={"project": {"id": 1, **project}})
    with FreshBooksClient(config) as fb:
        rates = RatesAPI(fb, TeamAPI(fb), config.rates)
        assert rates.get_project_rate(1, 5, 10) == (Decimal(expected) if expected else None)


def test_rates_yaml_project_override_wins(isolated_config_dir, monkeypatch):
    from decimal import Decimal
    from freshbooks_tools import config as config_module
    from freshbooks_tools.api.rates import RatesAPI

    (isolated_config_dir / "rates.yaml").write_text("projects:\n  1:\n    billable_rate: 125\n")
    monkeypatch.setattr(config_module, "RATES_FILE", isolated_config_dir / "rates.yaml")
    rates_config = config_module.load_rates_config()

    class NoNetwork:
        def __getattr__(self, name):
            raise AssertionError("should not hit the API")

    assert RatesAPI(NoNetwork(), NoNetwork(), rates_config).get_billable_rate(5, 10, 1) == Decimal("125")
