"""Set the layout Android uses for the host's physical keyboard.

Waydroid passes the host's key presses into Android as a physical keyboard,
and Android maps them with its own layout, which defaults to English (US).
The host's layout is not consulted, so on a Brazilian ABNT2 keyboard ç, the
accents and the extra /? key all come out wrong. The fix inside Android is
Settings > System > Keyboard > Physical keyboard, and it is lost every time
the container's data is reset.

Android keeps that choice in /data/system/input-manager-state.xml, one
<input-device> per keyboard keyed by its descriptor, read by
PersistentDataStore at boot. This writes that file with the chosen layout
for every alphabetic keyboard `dumpsys input` reports, keeping a copy of
the previous file so removing the hack can put it back.

The file is replaced, not merged: Android 12 and later may store it as
binary XML, which cannot be edited from a shell. On Waydroid it normally
holds nothing but keyboard layouts.

Checked against AOSP android11-release and android13-release: the file
format, the layout names in packages/InputDevices/res/xml/keyboard_layouts.xml
and the EventHub section of `dumpsys input` (Classes is hex on 11 and a flag
list on 13).
"""
import base64
import re
import subprocess
from typing import List
from xml.sax.saxutils import quoteattr

from tools import container
from tools.helper import shell
from tools.logger import Logger

STATE_FILE = "/data/system/input-manager-state.xml"
# AtomicFile treats STATE_FILE + ".bak" as a backup that wins over the file
# itself, and ".new" as an unfinished write. The copy kept here must use
# neither suffix or Android would read it instead of the new file.
ORIGINAL_FILE = STATE_FILE + ".waydroid_script.orig"

LAYOUT_PREFIX = ("com.android.inputdevices/"
                 "com.android.inputdevices.InputDeviceReceiver/")

LAYOUTS = {
    "br": "keyboard_layout_brazilian",
    "pt": "keyboard_layout_portuguese",
    "us": "keyboard_layout_english_us",
    "us_intl": "keyboard_layout_english_us_intl",
    "uk": "keyboard_layout_english_uk",
    "de": "keyboard_layout_german",
    "fr": "keyboard_layout_french",
    "es": "keyboard_layout_spanish",
    "latam": "keyboard_layout_spanish_latin",
    "it": "keyboard_layout_italian",
}

# EventHub's InputDeviceClass bits, from inputflinger/reader/include/EventHub.h.
CLASS_ALPHAKEY = 0x00000002
CLASS_VIRTUAL = 0x40000000

DEVICE_LINE = re.compile(r"^    (-?\d+): (.*)$")
FIELD_LINE = re.compile(r"^      (Classes|Descriptor): (.*)$")


def is_alphabetic(classes: str) -> bool:
    """Whether an EventHub Classes value describes a full, real keyboard.

    Android 11 prints the bitmask as hex; Android 13 prints flag names.
    """
    classes = classes.strip()
    if classes.startswith("0x"):
        try:
            bits = int(classes, 16)
        except ValueError:
            return False
        return bool(bits & CLASS_ALPHAKEY) and not bits & CLASS_VIRTUAL
    flags = {flag.strip() for flag in classes.split("|")}
    return "ALPHAKEY" in flags and "VIRTUAL" not in flags


def keyboard_descriptors(dumpsys: str) -> List[str]:
    """Descriptors of the alphabetic keyboards in `dumpsys input` output.

    Only the Event Hub section is read: it is the one that lists Classes and
    Descriptor together for each device.
    """
    descriptors = []
    in_event_hub = False
    device_id = None
    fields = {}

    def flush():
        if device_id is not None and device_id >= 0 \
                and "Descriptor" in fields \
                and is_alphabetic(fields.get("Classes", "")):
            if fields["Descriptor"] not in descriptors:
                descriptors.append(fields["Descriptor"])

    for line in dumpsys.splitlines():
        if line.startswith("Event Hub State:"):
            in_event_hub = True
            continue
        if in_event_hub and line and not line.startswith(" "):
            break
        if not in_event_hub:
            continue
        device = DEVICE_LINE.match(line)
        if device:
            flush()
            device_id, fields = int(device.group(1)), {}
            continue
        field = FIELD_LINE.match(line)
        if field and device_id is not None:
            fields[field.group(1)] = field.group(2).strip()
    flush()
    return descriptors


def state_xml(descriptors: List[str], layout: str) -> str:
    layout_descriptor = quoteattr(LAYOUT_PREFIX + layout)
    lines = ["<?xml version='1.0' encoding='utf-8' standalone='yes' ?>",
             "<input-manager-state>",
             "  <input-devices>"]
    for descriptor in descriptors:
        lines += ['    <input-device descriptor={}>'.format(quoteattr(descriptor)),
                  '      <keyboard-layout descriptor={} current="true" />'.format(
                      layout_descriptor),
                  "    </input-device>"]
    lines += ["  </input-devices>", "</input-manager-state>", ""]
    return "\n".join(lines)


def write_command(content: str) -> str:
    """Shell command that installs `content` as the state file.

    The content travels base64 encoded so no quoting can break it. The
    previous file is kept once, on the first run, so running the hack again
    with another layout does not overwrite the user's original. Leftover .bak
    and .new files are removed because AtomicFile would prefer them.
    """
    encoded = base64.b64encode(content.encode()).decode()
    return (
        "if [ -f {f} ] && [ ! -f {orig} ]; then cp -p {f} {orig}; fi; "
        "echo {data} | base64 -d > {f}.tmp && "
        "chown 1000:1000 {f}.tmp && chmod 600 {f}.tmp && "
        "rm -f {f}.bak {f}.new && mv {f}.tmp {f} && "
        "(restorecon {f} 2>/dev/null; true)"
    ).format(f=STATE_FILE, orig=ORIGINAL_FILE, data=encoded)


def restore_command() -> str:
    return (
        "rm -f {f}.bak {f}.new; "
        "if [ -f {orig} ]; then mv {orig} {f}; else rm -f {f}; fi"
    ).format(f=STATE_FILE, orig=ORIGINAL_FILE)


def _report(err: subprocess.CalledProcessError, what: str) -> None:
    Logger.error(what)
    detail = (err.stderr or b"").decode("utf-8", "replace").strip()
    if detail:
        Logger.error(detail)


class KeyboardLayout:
    id = "keyboard"

    def __init__(self, layout_name: str = "us") -> None:
        if layout_name not in LAYOUTS:
            raise ValueError(
                "Unknown keyboard layout {!r}. Available: {}".format(
                    layout_name, ", ".join(sorted(LAYOUTS))))
        self.layout_name = layout_name
        self.layout = LAYOUTS[layout_name]

    def install(self) -> bool:
        if not container.is_running():
            Logger.error(
                "Waydroid is not running. Start it with `waydroid show-full-ui`, "
                "then try again: the keyboard has to be connected to be found.")
            return False

        try:
            dumpsys = shell("dumpsys input")
        except subprocess.CalledProcessError as err:
            _report(err, "Could not list the input devices from the container.")
            return False

        descriptors = keyboard_descriptors(dumpsys)
        if not descriptors:
            Logger.error(
                "`dumpsys input` reported no physical keyboard. Click inside "
                "the Waydroid window, press a key and try again.")
            return False

        try:
            shell(write_command(state_xml(descriptors, self.layout)))
        except subprocess.CalledProcessError as err:
            _report(err, "Could not write {}.".format(STATE_FILE))
            return False

        Logger.info("Keyboard layout set to {} for {} keyboard(s).".format(
            self.layout, len(descriptors)))
        Logger.info(
            "Restart the session to apply: waydroid session stop, then "
            "start Waydroid again.")
        return True

    def uninstall(self) -> bool:
        if not container.is_running():
            Logger.error(
                "Waydroid is not running. Start it with `waydroid show-full-ui`, "
                "then try again.")
            return False
        try:
            shell(restore_command())
        except subprocess.CalledProcessError as err:
            _report(err, "Could not restore {}.".format(STATE_FILE))
            return False
        Logger.info(
            "Keyboard layout hack removed. Restart the session to apply: "
            "waydroid session stop, then start Waydroid again.")
        return True
