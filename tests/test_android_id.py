"""`certified` has to say something when it cannot get the Android ID.

Upstream #259: running it produced no output at all. get_id() wrapped the
container call in a bare `except: return`, so every failure — container not
reachable, sqlite3 missing, database absent — came back as silence. Nothing
to report, nothing to search for, which is why the issue has no detail in it.

The query itself was also wrong in two ways against the documented one:
it hardcoded com.google.android.gsf rather than globbing, so it could not
find the database under microG; and it selected * and then stripped the
"android_id|" prefix off the result by hand.
"""
import subprocess

import pytest

from stuff import android_id as android_id_module
from stuff.android_id import QUERY, AndroidId


@pytest.fixture
def running(monkeypatch):
    monkeypatch.setattr(android_id_module.container, "is_running", lambda: True)


def fake_shell(result=None, error=None):
    def _shell(arg, env=None):
        if error is not None:
            raise error
        return result
    return _shell


def test_query_globs_the_package(running):
    """GApps and microG do not put gservices.db under the same package."""
    assert "/data/data/*/*/gservices.db" in QUERY
    assert "com.google.android.gsf" not in QUERY


def test_query_selects_the_value_column(running):
    """Selecting * meant stripping an "android_id|" prefix back off."""
    assert "select value from main" in QUERY


def test_prints_the_id(running, monkeypatch, capsys):
    monkeypatch.setattr(android_id_module, "shell",
                        fake_shell(result="3234567890123456789\n"))
    AndroidId().get_id()
    out = capsys.readouterr().out
    assert "3234567890123456789" in out
    assert "google.com/android/uncertified" in out


def test_container_not_running_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(android_id_module.container, "is_running", lambda: False)
    AndroidId().get_id()
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "not running" in out


def test_shell_failure_is_reported_not_swallowed(running, monkeypatch, capsys):
    """The regression. A bare except made this silent."""
    error = subprocess.CalledProcessError(
        returncode=1, cmd=["waydroid", "shell"],
        stderr=b"sqlite3: not found")
    monkeypatch.setattr(android_id_module, "shell", fake_shell(error=error))
    AndroidId().get_id()
    out = capsys.readouterr().out
    assert "ERROR" in out, "a failure here used to produce no output at all"
    assert "sqlite3: not found" in out, "the underlying cause should reach the user"


def test_empty_result_explains_why(running, monkeypatch, capsys):
    """An empty database is not an error, but printing a blank line and a
    registration URL is useless. Say what is missing."""
    monkeypatch.setattr(android_id_module, "shell", fake_shell(result="\n"))
    AndroidId().get_id()
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "microG" in out or "Play Services" in out
    assert "google.com/android/uncertified" not in out


def test_no_bare_except_remains():
    """Parsed rather than grepped: the docstring above quotes the old
    `except: return`, and a text search would match its own explanation."""
    import ast

    tree = ast.parse(open("stuff/android_id.py").read())
    bare = [node for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and node.type is None]
    assert not bare, (
        f"bare except at line {bare[0].lineno if bare else '?'}; catching "
        f"everything and returning is what made #259 impossible to diagnose")
