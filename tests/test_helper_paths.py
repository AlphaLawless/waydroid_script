"""Who owns what this program writes, and where it writes it.

The program runs as root, so anything it creates under the user's home is
owned by root unless it hands ownership back.
"""
import os
import pwd

import pytest

from tools import helper


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("SUDO_USER", "SUDO_UID", "SUDO_GID", "XDG_CACHE_HOME", "USER"):
        monkeypatch.delenv(var, raising=False)


def test_sudo_user_wins_over_user(monkeypatch):
    monkeypatch.setenv("USER", "root")
    monkeypatch.setenv("SUDO_USER", "someone")
    assert helper.invoking_user() == "someone"


def test_falls_back_to_user(monkeypatch):
    monkeypatch.setenv("USER", "someone")
    assert helper.invoking_user() == "someone"


def test_missing_user_env_does_not_raise():
    """os.environ["USER"] used to be indexed directly, raising KeyError in
    containers, CI and some systemd contexts."""
    assert helper.invoking_user() == pwd.getpwuid(os.getuid()).pw_name


def test_home_comes_from_passwd(monkeypatch):
    """It used to be '/home/' + user, which is wrong on Fedora Silverblue and
    the Universal Blue images, where homes live under /var/home."""
    me = pwd.getpwuid(os.getuid())
    monkeypatch.setenv("SUDO_USER", me.pw_name)
    assert helper.invoking_user_home() == me.pw_dir


def test_unknown_user_falls_back(monkeypatch):
    monkeypatch.setenv("SUDO_USER", "no-such-user-hopefully-4f2a")
    assert helper.invoking_user_home() == os.path.expanduser("~")


def test_give_back_is_a_noop_without_sudo_uid(tmp_path):
    """No SUDO_UID means the caller was already root; nobody to hand back to."""
    target = tmp_path / "f"
    target.write_text("x")
    before = target.stat().st_uid
    helper.give_back_to_user(str(target))
    assert target.stat().st_uid == before


def test_give_back_chowns_when_sudo_uid_is_set(tmp_path, monkeypatch):
    target = tmp_path / "f"
    target.write_text("x")
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    helper.give_back_to_user(str(target))
    assert target.stat().st_uid == os.getuid()


def test_give_back_survives_a_missing_path(monkeypatch):
    """Best effort: a failed chown warns, it does not abort an install."""
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    helper.give_back_to_user("/definitely/not/here/4f2a")


def test_xdg_cache_home_is_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert helper.get_download_dir() == str(
        tmp_path / "waydroid-script" / "downloads")


def test_download_dir_defaults_under_the_users_home(tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "invoking_user_home", lambda: str(tmp_path))
    assert helper.get_download_dir() == str(
        tmp_path / ".cache" / "waydroid-script" / "downloads")
