"""Tests for parse_month (bare month = current year) and `fb projects list`."""

import json
import re
from datetime import datetime

import click
import pytest
from click.testing import CliRunner

from freshbooks_tools.cli import cli, parse_month


class TestParseMonth:
    def test_full_form(self):
        assert parse_month("2024-01") == (2024, 1)

    def test_bare_month_uses_current_year(self):
        assert parse_month("10") == (datetime.now().year, 10)

    @pytest.mark.parametrize("bad", ["13", "0", "abc", "2024-13", ""])
    def test_invalid(self, bad):
        with pytest.raises(click.BadParameter):
            parse_month(bad)


class TestProjectsList:
    def test_json_includes_client_and_services(self, httpx_mock, mock_config, monkeypatch):
        monkeypatch.setattr("freshbooks_tools.cli.load_config", lambda: mock_config)
        monkeypatch.setattr("freshbooks_tools.api.client.load_account_info", lambda: ("ACCT", 42))

        httpx_mock.add_response(
            url=re.compile(r".*/timetracking/business/42/projects.*"),
            json={"projects": [
                {"id": 2, "title": "Zeta", "client_id": 7},
                {"id": 1, "title": "alpha", "client_id": None},
                {"id": 3, "title": "Internal", "internal": True},
            ]},
        )
        httpx_mock.add_response(
            url=re.compile(r".*/projects/business/42/project/1$"),
            json={"project": {"id": 1, "title": "alpha", "services": []}},
        )
        httpx_mock.add_response(
            url=re.compile(r".*/projects/business/42/project/2$"),
            json={"project": {"id": 2, "title": "Zeta", "services": [{"id": 9, "name": "Dev"}]}},
        )
        httpx_mock.add_response(
            url=re.compile(r".*/accounting/account/ACCT/users/clients.*"),
            json={"response": {"result": {"clients": [{"userid": 7, "organization": "Acme"}], "total": 1}}},
        )

        result = CliRunner().invoke(cli, ["projects", "list", "--json"])

        assert result.exit_code == 0, result.output
        projects = json.loads(result.output)["projects"]
        assert [p["title"] for p in projects] == ["alpha", "Zeta"]  # sorted, internal excluded
        assert projects[0]["client"] is None
        assert projects[1]["client"] == "Acme"
        assert projects[1]["services"] == [{"id": 9, "name": "Dev", "billable": True}]


PROJECT_URL = re.compile(r".*/projects/business/42/project/1$")


@pytest.fixture
def fb_client(mock_config, monkeypatch):
    from freshbooks_tools.api.client import FreshBooksClient

    monkeypatch.setattr("freshbooks_tools.api.client.load_account_info", lambda: ("ACCT", 42))
    return lambda: FreshBooksClient(mock_config)


def project_detail(*services):
    return {"project": {"id": 1, "title": "P", "services": [{"id": i, "name": n} for i, n in services]}}


def test_lookup_cache_persists_across_runs(fb_client, httpx_mock):
    from freshbooks_tools.api.projects import ProjectsAPI

    httpx_mock.add_response(url=PROJECT_URL, json=project_detail((9, "Dev")))
    assert ProjectsAPI(fb_client()).service_name(1, 9) == "Dev"
    assert ProjectsAPI(fb_client()).service_name(1, 9) == "Dev"  # new "run": read from disk
    assert len(httpx_mock.get_requests()) == 1


def test_lookup_cache_expires(fb_client, httpx_mock, monkeypatch):
    from freshbooks_tools.api import client as client_module
    from freshbooks_tools.api.projects import ProjectsAPI

    httpx_mock.add_response(url=PROJECT_URL, json=project_detail((9, "Dev")), is_reusable=True)
    ProjectsAPI(fb_client()).service_name(1, 9)
    now = client_module.time.time()
    monkeypatch.setattr(client_module.time, "time", lambda: now + client_module.LOOKUP_TTL_SECONDS + 1)
    ProjectsAPI(fb_client()).service_name(1, 9)
    assert len(httpx_mock.get_requests()) == 2


def test_service_miss_refreshes_once(fb_client, httpx_mock):
    from freshbooks_tools.api.projects import ProjectsAPI

    httpx_mock.add_response(url=PROJECT_URL, json=project_detail((9, "Dev")))
    ProjectsAPI(fb_client()).service_name(1, 9)

    httpx_mock.add_response(url=PROJECT_URL, json=project_detail((9, "Dev"), (10, "Meetings")))
    api = ProjectsAPI(fb_client())
    assert api.service_name(1, 10) == "Meetings"  # unknown id -> refetch
    assert api.service_name(1, 99) is None  # still unknown, but no second refetch this run
    assert len(httpx_mock.get_requests()) == 2
    assert ProjectsAPI(fb_client()).service_name(1, 10) == "Meetings"  # saved
    assert len(httpx_mock.get_requests()) == 2


def test_unknown_client_refreshes_once(fb_client, httpx_mock):
    from freshbooks_tools.api.invoices import InvoicesAPI

    clients_url = re.compile(r".*/accounting/account/ACCT/users/clients.*")
    httpx_mock.add_response(url=clients_url, json={"response": {"result": {"clients": [{"userid": 7, "organization": "Acme"}], "total": 1}}})
    assert InvoicesAPI(fb_client()).get_client_name(7) == "Acme"

    httpx_mock.add_response(url=clients_url, json={"response": {"result": {"clients": [
        {"userid": 7, "organization": "Acme"}, {"userid": 8, "organization": "Beta"}], "total": 2}}})
    api = InvoicesAPI(fb_client())
    assert api.get_client_name(7) == "Acme"  # cached, no request
    assert api.get_client_name(8) == "Beta"  # miss -> refetch
    assert api.get_client_name(99) == "Client 99"  # no second refetch
    assert len(httpx_mock.get_requests()) == 2


def test_unknown_teammate_refreshes_once(fb_client, httpx_mock):
    from freshbooks_tools.api.team import TeamAPI

    team_url = re.compile(r".*/auth/api/v1/businesses/42/team_members$")
    staff_url = re.compile(r".*/accounting/account/ACCT/users/staffs$")
    projects_url = re.compile(r".*/timetracking/business/42/projects\?.*")
    member = {"uuid": "u5", "identity_id": 5, "first_name": "Ann", "last_name": "A"}

    httpx_mock.add_response(url=team_url, json={"team_members": [member]})
    assert TeamAPI(fb_client()).get_team_member_name(5) == "Ann A"

    httpx_mock.add_response(url=team_url, json={"team_members": [
        member, {"uuid": "u6", "identity_id": 6, "first_name": "Bob", "last_name": "B"}]})
    httpx_mock.add_response(url=staff_url, json={"response": {"result": {"staffs": []}}})
    httpx_mock.add_response(url=projects_url, json={"projects": []})
    api = TeamAPI(fb_client())
    assert api.get_team_member_name(5) == "Ann A"  # cached
    assert api.get_team_member_name(6) == "Bob B"  # miss: staff + project members checked, then refetch
    assert len(httpx_mock.get_requests(url=team_url)) == 2
