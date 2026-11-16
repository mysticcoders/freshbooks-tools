"""Tests for choosing the config directory and moving files from the old macOS folder."""

import stat
import sys

import pytest

from freshbooks_tools import config


@pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps %APPDATA%")
def test_defaults_to_dot_config(monkeypatch, tmp_path):
    monkeypatch.delenv("FRESHBOOKS_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert config.default_config_dir() == tmp_path / ".config" / "freshbooks-tools"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps %APPDATA%")
def test_respects_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.delenv("FRESHBOOKS_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert config.default_config_dir() == tmp_path / "xdg" / "freshbooks-tools"


def test_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("FRESHBOOKS_CONFIG_DIR", str(tmp_path / "custom"))

    assert config.default_config_dir() == tmp_path / "custom"


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """A legacy folder and an empty new config folder, wired into the config module."""
    legacy = tmp_path / "Application Support" / "freshbooks-tools"
    legacy.mkdir(parents=True)
    new = tmp_path / ".config" / "freshbooks-tools"
    monkeypatch.setattr(config, "LEGACY_CONFIG_DIR", legacy)
    monkeypatch.setattr(config, "CONFIG_DIR", new)
    return legacy, new


def test_migration_moves_files_and_removes_old_folder(dirs, capsys):
    legacy, new = dirs
    (legacy / "tokens.json").write_text("{}")
    (legacy / "aliases.json").write_text("{}")
    (legacy / "tokens.lock").write_text("")

    moved = config.migrate_legacy_config()

    assert sorted(moved) == ["aliases.json", "tokens.json"]
    assert (new / "tokens.json").read_text() == "{}"
    assert stat.S_IMODE((new / "tokens.json").stat().st_mode) == 0o600
    assert not (new / "tokens.lock").exists()
    assert not legacy.exists()
    err = capsys.readouterr()
    assert "moved aliases.json, tokens.json" in err.err
    assert err.out == ""


def test_migration_keeps_files_the_new_folder_already_has(dirs, capsys):
    legacy, new = dirs
    new.mkdir(parents=True)
    (new / ".env").write_text("NEW")
    (legacy / ".env").write_text("OLD")
    (legacy / "tokens.json").write_text("{}")

    moved = config.migrate_legacy_config()

    assert moved == ["tokens.json"]
    assert (new / ".env").read_text() == "NEW"
    assert (legacy / ".env").read_text() == "OLD"
    assert "left .env in" in capsys.readouterr().err


def test_migration_does_nothing_without_old_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEGACY_CONFIG_DIR", tmp_path / "missing")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "new")

    assert config.migrate_legacy_config() == []
    assert not (tmp_path / "new").exists()


def test_world_readable_env_is_tightened(isolated_config_dir, monkeypatch):
    for k in ("FRESHBOOKS_CLIENT_ID", "FRESHBOOKS_CLIENT_SECRET", "FRESHBOOKS_REDIRECT_URI"):
        monkeypatch.delenv(k, raising=False)
    env = isolated_config_dir / ".env"
    env.write_text("FRESHBOOKS_CLIENT_ID=cid\nFRESHBOOKS_CLIENT_SECRET=csec\n")
    env.chmod(0o644)

    config.load_env_config()

    assert stat.S_IMODE(env.stat().st_mode) == 0o600
