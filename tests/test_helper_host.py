"""host() maps the machine's architecture to Android's ABI names."""
import pytest

from tools import helper


@pytest.mark.parametrize("machine,expected", [
    ("i686", ("x86", 32)),
    ("x86_64", ("x86_64", 64)),
    ("aarch64", ("arm64-v8a", 64)),
    ("armv7l", ("armeabi-v7a", 32)),
    ("armv8l", ("armeabi-v7a", 32)),
])
def test_known_architectures(machine, expected, monkeypatch):
    monkeypatch.setattr(helper.platform, "machine", lambda: machine)
    assert helper.host() == expected


def test_unknown_architecture_raises(monkeypatch):
    monkeypatch.setattr(helper.platform, "machine", lambda: "sparc64")
    with pytest.raises(ValueError, match="not supported"):
        helper.host()
