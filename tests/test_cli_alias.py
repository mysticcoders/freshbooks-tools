"""Tests for `fb alias` and alias resolution in `fb time add`."""

import json
import re

import pytest
from click.testing import CliRunner

from freshbooks_tools.cli import cli

PROJECTS = {"projects": [{"id": 1001001, "title": "Acme Consulting", "client_id": 4}]}
PROJECT_DETAIL = {"project": {"id": 1001001, "title": "Acme Consulting", "services": [
    {"id": 2002001, "name": "Meetings"},
    {"id": 2002002, "name": "Development"},
]}}


@pytest.fixture
def env(isolated_config_dir, monkeypatch, mock_config):
    monkeypatch.setattr("freshbooks_tools.cli.load_config", lambda: mock_config)
    monkeypatch.setattr("freshbooks_tools.api.client.load_account_info", lambda: ("ACCT", 42))
    return isolated_config_dir


def mock_projects(httpx_mock):
    httpx_mock.add_response(url=re.compile(r".*/timetracking/business/42/projects.*"), json=PROJECTS)
    httpx_mock.add_response(url=re.compile(r".*/projects/business/42/project/1001001$"), json=PROJECT_DETAIL)


def test_set_by_ids_then_list(env, httpx_mock):
    mock_projects(httpx_mock)
    runner = CliRunner()

    result = runner.invoke(cli, ["alias", "set", "acme-dev", "-p", "1001001", "-s", "2002002", "--default"])
    assert result.exit_code == 0, result.output

    data = json.loads(runner.invoke(cli, ["alias", "list", "--json"]).output)
    assert data == {"default": "acme-dev", "aliases": {"acme-dev": {
        "project_id": 1001001, "project": "Acme Consulting",
        "service_id": 2002002, "service": "Development",
    }}}


def test_set_by_name_fragment(env, httpx_mock):
    mock_projects(httpx_mock)
    result = CliRunner().invoke(cli, ["alias", "set", "acme-meet", "-p", "acme", "-s", "meet"])
    assert result.exit_code == 0, result.output
    assert json.loads((env / "aliases.json").read_text())["aliases"]["acme-meet"]["service_id"] == 2002001


def test_default_and_rm(env):
    (env / "aliases.json").write_text(json.dumps({"default": "a", "aliases": {
        "a": {"project_id": 1, "project": "P"}, "b": {"project_id": 2, "project": "Q"}}}))
    runner = CliRunner()

    assert runner.invoke(cli, ["alias", "default", "b"]).exit_code == 0
    assert runner.invoke(cli, ["alias", "default", "nope"]).exit_code == 1
    assert runner.invoke(cli, ["alias", "rm", "b"]).exit_code == 0
    assert json.loads((env / "aliases.json").read_text()) == {
        "default": None, "aliases": {"a": {"project_id": 1, "project": "P"}}}


def test_time_add_uses_default_alias(env, httpx_mock):
    (env / "aliases.json").write_text(json.dumps({"default": "acme-dev", "aliases": {"acme-dev": {
        "project_id": 1001001, "project": "Acme Consulting", "service_id": 2002002, "service": "Development"}}}))
    httpx_mock.add_response(url=re.compile(r".*/timetracking/business/42/projects.*"), json=PROJECTS)
    httpx_mock.add_response(url=re.compile(r".*/auth/api/v1/users/me$"), json={"response": {"id": 5}})
    httpx_mock.add_response(url=re.compile(r".*/time_entries\?.*"), json={"time_entries": [], "meta": {"pages": 1, "total": 0}})
    httpx_mock.add_response(
        method="POST",
        url=re.compile(r".*/timetracking/business/42/time_entries$"),
        json={"time_entry": {"id": 1, "identity_id": 5, "duration": 7200, "started_at": "2026-11-05T09:00:00Z"}},
    )

    result = CliRunner().invoke(cli, ["time", "add", "-h", "2"])

    assert result.exit_code == 0, result.output
    assert "Acme Consulting" in result.output and "Development" in result.output
    sent = json.loads(httpx_mock.get_requests(method="POST")[0].content)["time_entry"]
    assert sent["project_id"] == 1001001
    assert sent["service_id"] == 2002002
    assert sent["client_id"] == 4
    assert sent["duration"] == 7200


def test_time_add_without_project_or_default_fails(env):
    result = CliRunner().invoke(cli, ["time", "add", "-h", "2"])
    assert result.exit_code == 1
    assert "no default alias" in result.output
