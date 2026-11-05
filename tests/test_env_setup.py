"""Tests for locating credentials outside the repo (fb auth setup)."""

import stat

import pytest
from click.testing import CliRunner

from freshbooks_tools import config
from freshbooks_tools.cli import cli


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    d = tmp_path / "config"
    monkeypatch.setattr(config, "CONFIG_DIR", d)
    monkeypatch.setattr(config, "ENV_FILE", d / ".env")
    monkeypatch.setattr("freshbooks_tools.cli.ENV_FILE", d / ".env")
    return d


def test_setup_copies_env_with_private_permissions(config_dir, tmp_path):
    src = tmp_path / "repo.env"
    src.write_text("FRESHBOOKS_CLIENT_ID=id\nFRESHBOOKS_CLIENT_SECRET=secret\n")

    result = CliRunner().invoke(cli, ["auth", "setup", str(src)])

    assert result.exit_code == 0, result.output
    target = config_dir / ".env"
    assert target.read_text() == src.read_text()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_setup_rejects_env_without_credentials(config_dir, tmp_path):
    src = tmp_path / "bad.env"
    src.write_text("FRESHBOOKS_CLIENT_ID=id\n")

    result = CliRunner().invoke(cli, ["auth", "setup", str(src)])

    assert result.exit_code == 1
    assert "FRESHBOOKS_CLIENT_SECRET" in result.output
    assert not (config_dir / ".env").exists()


def test_setup_asks_before_overwriting(config_dir, tmp_path):
    config_dir.mkdir()
    (config_dir / ".env").write_text("old")
    src = tmp_path / "repo.env"
    src.write_text("FRESHBOOKS_CLIENT_ID=id\nFRESHBOOKS_CLIENT_SECRET=secret\n")

    CliRunner().invoke(cli, ["auth", "setup", str(src)], input="n\n")

    assert (config_dir / ".env").read_text() == "old"


def test_env_loaded_from_config_dir(config_dir, monkeypatch, tmp_path):
    for k in ("FRESHBOOKS_CLIENT_ID", "FRESHBOOKS_CLIENT_SECRET", "FRESHBOOKS_REDIRECT_URI"):
        monkeypatch.delenv(k, raising=False)
    config_dir.mkdir()
    (config_dir / ".env").write_text("FRESHBOOKS_CLIENT_ID=cid\nFRESHBOOKS_CLIENT_SECRET=csec\n")
    monkeypatch.chdir(tmp_path)  # no ./.env here

    assert config.load_env_config()[:2] == ("cid", "csec")
