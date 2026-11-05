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


class FakeClient:
    """Counts project-detail fetches; services come from the class attribute."""
    calls = 0
    services = [{"id": 9, "name": "Dev"}]

    def projects_url(self, path):
        return path

    def get(self, url, params=None):
        FakeClient.calls += 1
        return {"project": {"id": 1, "title": "P", "services": FakeClient.services}}


@pytest.fixture
def fake_client():
    FakeClient.calls = 0
    FakeClient.services = [{"id": 9, "name": "Dev"}]
    return FakeClient


def test_service_cache_persists_across_runs(fake_client):
    from freshbooks_tools.api.projects import ProjectsAPI

    assert ProjectsAPI(fake_client()).service_name(1, 9) == "Dev"
    assert ProjectsAPI(fake_client()).service_name(1, 9) == "Dev"  # new "run": read from disk
    assert fake_client.calls == 1


def test_service_cache_miss_refreshes_once(fake_client):
    from freshbooks_tools.api.projects import ProjectsAPI

    ProjectsAPI(fake_client()).service_name(1, 9)
    fake_client.services = [{"id": 9, "name": "Dev"}, {"id": 10, "name": "Meetings"}]

    api = ProjectsAPI(fake_client())
    assert api.service_name(1, 10) == "Meetings"  # unknown id -> refetch
    assert api.service_name(1, 99) is None  # still unknown, but no second refetch this run
    assert fake_client.calls == 2
    assert ProjectsAPI(fake_client()).service_name(1, 10) == "Meetings"  # saved
    assert fake_client.calls == 2
