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


def test_sse42_fallback_actually_runs(monkeypatch, tmp_path):
    """The guard read `mapping[machine] == "x86_64"`, comparing a tuple to a
    string. Always False, so an x86_64 CPU without SSE4.2 was never demoted
    to x86 and got a translation layer it cannot execute."""
    monkeypatch.setattr(helper.platform, "machine", lambda: "x86_64")
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("flags\t: fpu vme de pse tsc msr\n")   # no sse4_2

    real_open = open
    def fake_open(path, *args, **kwargs):
        if path == "/proc/cpuinfo":
            return real_open(cpuinfo, *args, **kwargs)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    assert helper.host() == ("x86", 32)


def test_sse42_present_keeps_x86_64(monkeypatch, tmp_path):
    monkeypatch.setattr(helper.platform, "machine", lambda: "x86_64")
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("flags\t: fpu vme de pse tsc msr sse4_2 avx\n")

    real_open = open
    def fake_open(path, *args, **kwargs):
        if path == "/proc/cpuinfo":
            return real_open(cpuinfo, *args, **kwargs)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    assert helper.host() == ("x86_64", 64)
