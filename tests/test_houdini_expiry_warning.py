"""Houdini.copy() warns before installing a build that has already expired.

The warning has to reach the user at install time. Finding out later means
diagnosing "ARM apps do not start" from scratch, which is what upstream #285,
#257 and #237 all are.
"""
import datetime
import struct

import pytest

from stuff.houdini import Houdini
from tools import expiry

HOUDINI_EXPIRY = 1788134400


@pytest.fixture
def prebuilts(tmp_path):
    """A prebuilts/ tree shaped like the one inside the real archive."""
    def _make(include_constant):
        for subdir in ("lib", "lib64"):
            directory = tmp_path / subdir
            directory.mkdir()
            blob = bytearray(b"\x7fELF" + b"\x00" * 2048)
            if include_constant and subdir == "lib64":
                # Only the 64-bit library carries it in the real archive.
                blob += struct.pack("<Q", HOUDINI_EXPIRY)
            (directory / "libhoudini.so").write_bytes(bytes(blob))
        return str(tmp_path)
    return _make


def houdini():
    """Skip __init__: it only resolves the download URL, which is irrelevant."""
    return Houdini.__new__(Houdini)


def test_warns_when_the_build_has_expired(prebuilts, capsys, monkeypatch):
    monkeypatch.setattr(
        expiry, "expired_timestamps_in",
        lambda path, now=None: ([HOUDINI_EXPIRY]
                                if path.endswith("lib64/libhoudini.so") else []))
    houdini().warn_if_expired(prebuilts(include_constant=True))
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "2026-08-31" in out
    assert "libndk" in out, "the warning should name the alternative"


def test_silent_when_the_build_has_not_expired(prebuilts, capsys, monkeypatch):
    monkeypatch.setattr(expiry, "expired_timestamps_in",
                        lambda path, now=None: [])
    houdini().warn_if_expired(prebuilts(include_constant=True))
    assert capsys.readouterr().out == ""


def test_warns_once_even_though_two_libraries_are_checked(prebuilts, capsys,
                                                          monkeypatch):
    monkeypatch.setattr(expiry, "expired_timestamps_in",
                        lambda path, now=None: [HOUDINI_EXPIRY])
    houdini().warn_if_expired(prebuilts(include_constant=True))
    assert capsys.readouterr().out.count("WARN") == 1


def test_missing_prebuilts_directory_is_not_fatal(capsys):
    """An archive laid out differently should not take the install down before
    it has a chance to fail on something meaningful."""
    houdini().warn_if_expired("/definitely/not/here/4f2a")
    assert capsys.readouterr().out == ""


def test_copy_checks_before_copying():
    """Order matters: warning after the files are in place is advice about
    something that already happened."""
    source = open("stuff/houdini.py").read()
    assert source.index("self.warn_if_expired(prebuilts)") < \
        source.index("shutil.copytree(prebuilts")


def test_the_install_is_not_blocked():
    """No exit, no raise. Refusing would leave the user with no translator at
    all rather than a broken one they can reason about."""
    source = open("stuff/houdini.py").read()
    body = source[source.index("def warn_if_expired"):source.index("def copy")]
    assert "sys.exit" not in body
    assert "raise" not in body
