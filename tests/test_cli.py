from pathlib import Path

import pytest

from synthetic_human.cli import desktop_lock


@pytest.fixture(autouse=True)
def isolated_login_home(tmp_path, monkeypatch):
    # Verify per-user locking without taking a real running demo's desktop lease.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "login-home"))


def test_global_desktop_lock_excludes_different_run_directories(tmp_path):
    with desktop_lock(tmp_path / "one"):
        with pytest.raises(RuntimeError, match="another"):
            with desktop_lock(tmp_path / "two"):
                pass
    with desktop_lock(tmp_path / "two"):
        pass


def test_different_launcher_tempdirs_cannot_bypass_desktop_lock(tmp_path, monkeypatch):
    temporary = tmp_path / "launcher-temp"
    temporary.mkdir()
    with desktop_lock(tmp_path / "first"):
        monkeypatch.setenv("TMPDIR", str(temporary))
        with pytest.raises(RuntimeError, match="another"):
            with desktop_lock(tmp_path / "second"):
                pass
