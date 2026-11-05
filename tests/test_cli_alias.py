"""Tests for `fb alias` and alias resolution in `fb time add`."""

import json
import re

import pytest
from click.testing import CliRunner

from freshbooks_tools import config as config_module
from freshbooks_tools.cli import cli

PROJECTS = {"projects": [{"id": 13383459, "title": "ZeroE Consulting", "client_id": 4}]}
PROJECT_DETAIL = {"project": {"id": 13383459, "title": "ZeroE Consulting", "services": [
    {"id": 4478824, "name": "Meetings"},
    {"id": 4478828, "name": "Development"},
]}}


@pytest.fixture
def env(tmp_path, monkeypatch, mock_config):
    monkeypatch.setattr(config_module, "ALIASES_FILE", tmp_path / "aliases.json")
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("freshbooks_tools.cli.load_config", lambda: mock_config)
    monkeypatch.setattr("freshbooks_tools.api.client.load_account_info", lambda: ("ACCT", 42))
    return tmp_path


def mock_projects(httpx_mock):
    httpx_mock.add_response(url=re.compile(r".*/timetracking/business/42/projects.*"), json=PROJECTS)
    httpx_mock.add_response(url=re.compile(r".*/projects/business/42/project/13383459$"), json=PROJECT_DETAIL)


def test_set_by_ids_then_list(env, httpx_mock):
    mock_projects(httpx_mock)
    runner = CliRunner()

    result = runner.invoke(cli, ["alias", "set", "zeroe-dev", "-p", "13383459", "-s", "4478828", "--default"])
    assert result.exit_code == 0, result.output

    data = json.loads(runner.invoke(cli, ["alias", "list", "--json"]).output)
    assert data == {"default": "zeroe-dev", "aliases": {"zeroe-dev": {
        "project_id": 13383459, "project": "ZeroE Consulting",
        "service_id": 4478828, "service": "Development",
    }}}


def test_set_by_name_fragment(env, httpx_mock):
    mock_projects(httpx_mock)
    result = CliRunner().invoke(cli, ["alias", "set", "zeroe-meet", "-p", "zero", "-s", "meet"])
    assert result.exit_code == 0, result.output
    assert json.loads((env / "aliases.json").read_text())["aliases"]["zeroe-meet"]["service_id"] == 4478824


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
    (env / "aliases.json").write_text(json.dumps({"default": "zeroe-dev", "aliases": {"zeroe-dev": {
        "project_id": 13383459, "project": "ZeroE Consulting", "service_id": 4478828, "service": "Development"}}}))
    httpx_mock.add_response(url=re.compile(r".*/timetracking/business/42/projects.*"), json=PROJECTS)
    httpx_mock.add_response(
        method="POST",
        url=re.compile(r".*/timetracking/business/42/time_entries$"),
        json={"time_entry": {"id": 1, "identity_id": 5, "duration": 7200, "started_at": "2026-11-05T09:00:00Z"}},
    )

    result = CliRunner().invoke(cli, ["time", "add", "-h", "2"])

    assert result.exit_code == 0, result.output
    assert "ZeroE Consulting" in result.output and "Development" in result.output
    sent = json.loads(httpx_mock.get_requests(method="POST")[0].content)["time_entry"]
    assert sent["project_id"] == 13383459
    assert sent["service_id"] == 4478828
    assert sent["client_id"] == 4
    assert sent["duration"] == 7200


def test_time_add_without_project_or_default_fails(env):
    result = CliRunner().invoke(cli, ["time", "add", "-h", "2"])
    assert result.exit_code == 1
    assert "no default alias" in result.output
