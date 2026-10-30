"""Clipboard sharing has to say why it does not work.

Waydroid imports pyclip in its session and, when that fails, logs the reason
at debug level and turns clipboard sharing off. The usual cause is a Python
upgrade leaving a pip-installed pyclip behind in the old interpreter. The
check has to look at the interpreter Waydroid runs with, not the one running
this script.
"""
import pytest

from stuff import clipboard as clip
from stuff.clipboard import Clipboard, distro_ids, install_hint, waydroid_interpreter


@pytest.mark.parametrize("shebang,expected", [
    ("#!/usr/bin/python3\n", "/usr/bin/python3"),
    ("#!/usr/bin/python3 -I\n", "/usr/bin/python3"),
    ("#! /usr/bin/python3.14\n", "/usr/bin/python3.14"),
])
def test_interpreter_from_shebang(tmp_path, shebang, expected):
    script = tmp_path / "waydroid"
    script.write_text(shebang + "import sys\n")
    assert waydroid_interpreter(str(script)) == expected


def test_env_shebang_resolves_through_path(tmp_path, monkeypatch):
    script = tmp_path / "waydroid"
    script.write_text("#!/usr/bin/env python3\n")
    monkeypatch.setattr(clip.shutil, "which",
                        lambda name: "/opt/py/bin/" + name)
    assert waydroid_interpreter(str(script)) == "/opt/py/bin/python3"


def test_missing_or_shebangless_script(tmp_path):
    assert waydroid_interpreter(str(tmp_path / "absent")) is None
    script = tmp_path / "waydroid"
    script.write_text("print('no shebang')\n")
    assert waydroid_interpreter(str(script)) is None


def test_distro_ids_include_id_like(tmp_path):
    os_release = tmp_path / "os-release"
    os_release.write_text('NAME="CachyOS"\nID=cachyos\nID_LIKE="arch"\n')
    assert distro_ids(str(os_release)) == ["cachyos", "arch"]


def test_arch_derivatives_get_the_package(monkeypatch):
    monkeypatch.setattr(clip, "distro_ids", lambda: ["cachyos", "arch"])
    assert "pacman -S python-pyclip" in install_hint("/usr/bin/python3")


def test_unknown_distro_gets_no_guessed_package(monkeypatch):
    monkeypatch.setattr(clip, "distro_ids", lambda: ["somethingelse"])
    hint = install_hint("/usr/bin/python3")
    assert "/usr/bin/python3" in hint
    assert "pacman" not in hint


@pytest.fixture
def host(monkeypatch):
    """A host where everything is present unless a test says otherwise."""
    state = {"python": "/usr/bin/python3", "pyclip": True,
             "tools": {"wl-copy", "wl-paste"}}
    monkeypatch.setattr(clip, "waydroid_interpreter", lambda: state["python"])
    monkeypatch.setattr(clip, "can_import_pyclip", lambda python: state["pyclip"])
    monkeypatch.setattr(clip.shutil, "which",
                        lambda name: "/usr/bin/" + name if name in state["tools"] else None)
    monkeypatch.setattr(clip, "distro_ids", lambda: ["arch"])
    return state


def test_all_present(host, capsys):
    assert Clipboard().check() is True
    assert "ERROR" not in capsys.readouterr().out


def test_missing_pyclip_is_reported_with_the_fix(host, capsys):
    host["pyclip"] = False
    assert Clipboard().check() is False
    out = capsys.readouterr().out
    assert "pyclip cannot be imported by /usr/bin/python3" in out
    assert "python-pyclip" in out


def test_missing_wl_clipboard_is_reported(host, capsys):
    host["tools"] = {"wl-copy"}
    assert Clipboard().check() is False
    assert "wl-paste" in capsys.readouterr().out


def test_waydroid_not_found(host, capsys):
    host["python"] = None
    assert Clipboard().check() is False
    assert "Is Waydroid installed" in capsys.readouterr().out
