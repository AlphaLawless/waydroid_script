"""Tell the user when the ARM translator does not match their CPU.

The Waydroid page on the ArchWiki is explicit: libndk on AMD, libhoudini on
Intel. libhoudini is Intel's own binary translator, so it is the weaker
choice on AMD silicon. Nothing in this tool ever said so, and ARM
translation is the largest cluster of open reports upstream.

Advice, not enforcement. The same page notes that some apps run on one layer
and not the other, so the install still proceeds.
"""
import pytest

from tools import helper


@pytest.fixture
def vendor(monkeypatch, tmp_path):
    """Fake /proc/cpuinfo for a given vendor_id, or omit the field."""
    def _set(vendor_id):
        cpuinfo = tmp_path / "cpuinfo"
        body = "processor\t: 0\n"
        if vendor_id is not None:
            body += f"vendor_id\t: {vendor_id}\n"
        body += "flags\t\t: fpu sse4_2\n"
        cpuinfo.write_text(body)

        real_open = open

        def fake_open(path, *args, **kwargs):
            if path == "/proc/cpuinfo":
                return real_open(cpuinfo, *args, **kwargs)
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)
    return _set


@pytest.mark.parametrize("vendor_id,expected", [
    ("GenuineIntel", "intel"),
    ("AuthenticAMD", "amd"),
    ("CentaurHauls", None),
    (None, None),
])
def test_cpu_vendor(vendor, vendor_id, expected):
    vendor(vendor_id)
    assert helper.cpu_vendor() == expected


def test_cpu_vendor_survives_an_unreadable_cpuinfo(monkeypatch):
    """Containers and odd kernels do not always expose it. Not knowing is a
    fine answer; crashing is not."""
    def boom(path, *args, **kwargs):
        raise OSError("nope")
    monkeypatch.setattr("builtins.open", boom)
    assert helper.cpu_vendor() is None


@pytest.mark.parametrize("vendor_id,chosen", [
    ("GenuineIntel", "libhoudini"),
    ("AuthenticAMD", "libndk"),
])
def test_no_warning_when_the_choice_matches(vendor, capsys, vendor_id, chosen):
    vendor(vendor_id)
    helper.warn_if_translator_mismatched(chosen)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("vendor_id,chosen,recommended", [
    ("GenuineIntel", "libndk", "libhoudini"),
    ("AuthenticAMD", "libhoudini", "libndk"),
])
def test_warns_when_the_choice_is_the_other_one(vendor, capsys, vendor_id,
                                                chosen, recommended):
    vendor(vendor_id)
    helper.warn_if_translator_mismatched(chosen)
    out = capsys.readouterr().out
    assert "WARN" in out
    assert recommended in out
    assert chosen in out


def test_unknown_vendor_says_nothing(vendor, capsys):
    """Guessing wrong is worse than staying quiet."""
    vendor("CentaurHauls")
    helper.warn_if_translator_mismatched("libhoudini")
    assert capsys.readouterr().out == ""


def test_the_warning_does_not_block_the_install():
    """It returns None either way; main.py appends to install_list after
    calling it. Some apps only run on the layer that is not recommended."""
    source = open("main.py").read()
    for translator, cls in (("libndk", "Ndk"), ("libhoudini", "Houdini")):
        warn = f'helper.warn_if_translator_mismatched("{translator}")'
        assert warn in source
        assert source.index(warn) < source.index(f"install_list.append({cls}(")


def test_both_vendors_are_mapped():
    assert helper.PREFERRED_TRANSLATOR == {"intel": "libhoudini", "amd": "libndk"}
