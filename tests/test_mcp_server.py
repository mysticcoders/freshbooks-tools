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
