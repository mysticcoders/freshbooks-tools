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


def test_service_name_from_project_is_cached():
    from freshbooks_tools.api.projects import ProjectsAPI

    class FakeClient:
        calls = 0
        def projects_url(self, path):
            return path
        def get(self, url, params=None):
            FakeClient.calls += 1
            return {"project": {"id": 1, "title": "P", "services": [{"id": 9, "name": "Dev"}]}}

    api = ProjectsAPI(FakeClient())
    assert api.service_name(1, 9) == "Dev"
    assert api.service_name(1, 99) is None
    assert FakeClient.calls == 1
