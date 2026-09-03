"""nodataperm is only published for x86_64, and has to say so cleanly.

Upstream #246: an unsupported architecture raised KeyError out of __init__,
so the user got a traceback. The reported symptom on x86_64 was fixed by
15020ec, but the raise remained for every ARM user.
"""
import re

import pytest

from stuff import nodataperm
from stuff.general import General
from stuff.nodataperm import Nodataperm

MD5 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def arch(monkeypatch):
    """Pretend to be on a given architecture."""
    def _set(name):
        monkeypatch.setattr(General, "arch", (name, 64))
    return _set


def test_supported_combination_builds(arch):
    arch("x86_64")
    hack = Nodataperm("13")
    assert hack.dl_link.endswith(".zip")
    assert MD5.match(hack.act_md5)


@pytest.mark.parametrize("android_version", ["11", "13"])
def test_every_advertised_version_works_on_x86_64(arch, android_version):
    arch("x86_64")
    assert Nodataperm(android_version).dl_link.startswith("https://")


@pytest.mark.parametrize("machine", ["arm64-v8a", "armeabi-v7a", "x86"])
def test_unsupported_arch_exits_cleanly(arch, machine, capsys):
    """The regression: this used to raise KeyError and print a traceback."""
    arch(machine)
    with pytest.raises(SystemExit) as excinfo:
        Nodataperm("13")
    assert excinfo.value.code == 1
    # One readouterr() call: it drains the capture, so a second would come
    # back empty. Logger writes to stdout.
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert machine in captured.out, (
        f"the message should name the architecture; got {captured.out!r}")


def test_unsupported_android_version_exits_cleanly(arch):
    arch("x86_64")
    with pytest.raises(SystemExit) as excinfo:
        Nodataperm("99")
    assert excinfo.value.code == 1


def test_no_debug_output_on_construction(arch, capsys):
    """__init__ carried a bare print("ok"), which showed up in bug reports
    right before the traceback."""
    arch("x86_64")
    Nodataperm("13")
    assert capsys.readouterr().out.strip() == ""


def test_source_has_no_stray_print():
    source = open("stuff/nodataperm.py").read()
    assert 'print("ok")' not in source


def test_hack_option_passes_the_selected_android_version():
    """main.py's hack_option called Nodataperm() with no argument, so it used
    the class default of "11" whatever -a said, while remove_app passed the
    real value. Installing and removing could therefore disagree."""
    source = open("main.py").read()
    assert "hack_list.append(Nodataperm(args.android_version))" in source
    assert "hack_list.append(Nodataperm())" not in source
