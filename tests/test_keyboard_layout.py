"""Setting Android's layout for the host's physical keyboard.

Android maps Waydroid's keyboard with its own layout, English (US) by
default, whatever the host uses. The layout is stored per keyboard in
/data/system/input-manager-state.xml, keyed by the descriptor `dumpsys input`
reports, so the hack has to find the right descriptors and write a file
PersistentDataStore will accept.

The dumpsys samples follow EventHub::dump() in AOSP: the Classes line is a hex
bitmask on Android 11 and a list of flag names on Android 13. Nothing here
touches a container; shell() is replaced.
"""
import base64
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from stuff import keyboard_layout as kl
from stuff.keyboard_layout import (LAYOUTS, ORIGINAL_FILE, STATE_FILE,
                                   KeyboardLayout, is_alphabetic,
                                   keyboard_layout_keys, layout_key, state_xml)

DUMPSYS_13 = """\
INPUT MANAGER (dumpsys input)

Input Manager State:
  Interactive: true
Event Hub State:
  BuiltInKeyboardId: -2
  Devices:
    -1: Virtual
      Classes: KEYBOARD | ALPHAKEY | DPAD | VIRTUAL
      Path: <virtual>
      Enabled: true
      Descriptor: a718a782d34bc767f4689c232d64d527998ea7fd
    2: Waydroid Touch
      Classes: TOUCH | TOUCH_MT
      Path: /dev/input/event2
      Enabled: true
      Descriptor: 0c1f2e3d4c5b6a79881726354453627180918273
    3: Waydroid Keyboard
      Classes: KEYBOARD | ALPHAKEY
      Path: /dev/input/event3
      Enabled: true
      Identifier: bus=0x0000, vendor=0x0001, product=0x0001, version=0x0000
      Descriptor: 5d2c2cbbc3f9a4a8d3fbc4cba0c3ef0d3f1a5b88
      Location:
Input Reader State (Nums of device: 3):
  Device 3: Waydroid Keyboard
      Descriptor: should-not-be-read-from-here
"""

DUMPSYS_11 = """\
Event Hub State:
  BuiltInKeyboardId: -2
  Devices:
    -1: Virtual
      Classes: 0x40000023
      Path: <virtual>
      Descriptor: a718a782d34bc767f4689c232d64d527998ea7fd
    3: Waydroid Keyboard
      Classes: 0x00000003
      Path: /dev/input/event3
      Identifier: bus=0x0000, vendor=0x0001, product=0x0001, version=0x0000
      Descriptor: 5d2c2cbbc3f9a4a8d3fbc4cba0c3ef0d3f1a5b88
    4: Power Button
      Classes: 0x00000001
      Path: /dev/input/event4
      Descriptor: 9e0e9b1b1d6d4b8c64a1e1b0a2d4e2f1a1b2c3d4
Input Reader State:
"""

DESCRIPTOR = "5d2c2cbbc3f9a4a8d3fbc4cba0c3ef0d3f1a5b88"
# Waydroid's keyboard is vendor 1, product 1, so Android files its
# layout under this key and never under the descriptor.
KEYBOARD = "vendor:1,product:1"


@pytest.mark.parametrize("classes,expected", [
    ("KEYBOARD | ALPHAKEY", True),
    ("KEYBOARD | ALPHAKEY | DPAD | VIRTUAL", False),
    ("KEYBOARD", False),
    ("TOUCH | TOUCH_MT", False),
    ("0x00000003", True),
    ("0x40000023", False),
    ("0x00000001", False),
    ("not a number", False),
])
def test_is_alphabetic(classes, expected):
    assert is_alphabetic(classes) is expected


@pytest.mark.parametrize("dumpsys", [DUMPSYS_13, DUMPSYS_11],
                         ids=["android13", "android11"])
def test_finds_only_the_real_keyboard(dumpsys):
    """Not the virtual keyboard, not the power button, not the touchscreen,
    and nothing from the Input Reader section that follows."""
    assert keyboard_layout_keys(dumpsys) == [KEYBOARD]


def test_keyed_by_vendor_and_product_not_descriptor():
    """The regression found on a real device. Keyed by the descriptor the
    file was valid and Android ignored it, keeping Waydroid's guess."""
    assert DESCRIPTOR not in keyboard_layout_keys(DUMPSYS_13)


@pytest.mark.parametrize("identifier,expected", [
    ("bus=0x0000, vendor=0x0001, product=0x0001, version=0x0000",
     "vendor:1,product:1"),
    # Decimal in the key, hex in dumpsys.
    ("bus=0x0003, vendor=0x046d, product=0xc52b, version=0x0111",
     "vendor:1133,product:50475"),
    ("bus=0x0000, vendor=0x0000, product=0x0000, version=0x0000", "desc"),
    ("", "desc"),
])
def test_layout_key_mirrors_get_layout_descriptor(identifier, expected):
    assert layout_key("desc", identifier) == expected


def test_no_event_hub_section_finds_nothing():
    assert keyboard_layout_keys("Input Reader State:\n  Device 3: x\n") == []


def test_state_xml_is_what_persistent_data_store_reads():
    root = ET.fromstring(state_xml([KEYBOARD], LAYOUTS["br"]).split("\n", 1)[1])
    assert root.tag == "input-manager-state"
    devices = root.findall("./input-devices/input-device")
    assert [d.get("descriptor") for d in devices] == [KEYBOARD]
    layouts = devices[0].findall("keyboard-layout")
    assert len(layouts) == 1
    assert layouts[0].get("current") == "true"
    assert layouts[0].get("descriptor") == (
        "com.android.inputdevices/com.android.inputdevices.InputDeviceReceiver/"
        "keyboard_layout_brazilian")


def test_backup_does_not_use_an_atomicfile_suffix():
    """AtomicFile reads FILE.bak in preference to FILE, so a copy kept there
    would silently replace what the hack writes."""
    assert not ORIGINAL_FILE.endswith((".bak", ".new"))


def test_unknown_layout_is_rejected():
    with pytest.raises(ValueError, match="Available"):
        KeyboardLayout("klingon")


@pytest.fixture
def running(monkeypatch):
    monkeypatch.setattr(kl.container, "is_running", lambda: True)


@pytest.fixture
def commands(monkeypatch):
    sent = []

    def fake_shell(arg, env=None):
        sent.append(arg)
        return DUMPSYS_13 if arg == "dumpsys input" else ""
    monkeypatch.setattr(kl, "shell", fake_shell)
    return sent


def test_install_writes_the_layout_for_the_keyboard(running, commands):
    assert KeyboardLayout("br").install() is True
    assert commands[0] == "dumpsys input"
    write = commands[1]
    payload = re.search(r"echo (\S+) \| base64 -d", write).group(1)
    written = base64.b64decode(payload).decode()
    assert KEYBOARD in written
    assert "keyboard_layout_brazilian" in written
    assert "cp -p {} {}".format(STATE_FILE, ORIGINAL_FILE) in write
    assert "[ ! -f {} ]".format(ORIGINAL_FILE) in write, \
        "a second run must not overwrite the user's original file"


def test_install_without_a_keyboard_writes_nothing(running, monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(kl, "shell",
                        lambda arg, env=None: sent.append(arg) or "Event Hub State:\n")
    assert KeyboardLayout("br").install() is False
    assert sent == ["dumpsys input"]
    assert "ERROR" in capsys.readouterr().out


def test_install_needs_the_container(monkeypatch, capsys):
    monkeypatch.setattr(kl.container, "is_running", lambda: False)
    assert KeyboardLayout("br").install() is False
    assert "not running" in capsys.readouterr().out


def test_shell_failure_is_reported(running, monkeypatch, capsys):
    def failing(arg, env=None):
        raise subprocess.CalledProcessError(
            1, ["waydroid", "shell"], stderr=b"dumpsys: not found")
    monkeypatch.setattr(kl, "shell", failing)
    assert KeyboardLayout("br").install() is False
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "dumpsys: not found" in out


def test_uninstall_restores_the_original(running, commands):
    assert KeyboardLayout().uninstall() is True
    assert "mv {} {}".format(ORIGINAL_FILE, STATE_FILE) in commands[0]
