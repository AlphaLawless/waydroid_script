"""Check what Waydroid needs to share the clipboard with the host.

Waydroid's session imports pyclip to read and write the host clipboard, and
pyclip on Wayland shells out to wl-copy and wl-paste. When the import fails
Waydroid logs the reason at debug level and turns clipboard sharing off, so
from the user's side copy and paste just stops working with nothing said
anywhere (tools/services/clipboard_manager.py upstream).

The usual way to lose it is a Python upgrade on a rolling distro: pyclip
installed with pip lives in the old interpreter's site-packages, and the new
one cannot see it.

Everything here only reads. Nothing is installed; the user is told what to
install for their distribution instead.
"""
import os
import shutil
import subprocess
from typing import List, Optional

from tools.helper import invoking_user
from tools.logger import Logger

WAYLAND_TOOLS = ["wl-copy", "wl-paste"]

# Only distributions whose package name has been checked. Anything else gets
# the generic advice rather than a guessed package name that may not exist.
INSTALL_COMMANDS = {
    "arch": "sudo pacman -S python-pyclip",
}


def waydroid_interpreter(waydroid: Optional[str] = None) -> Optional[str]:
    """The Python that runs Waydroid, read from the waydroid script's shebang.

    That interpreter, not the one running this script, is the one that has to
    import pyclip: this script runs from pixi's own environment.
    """
    waydroid = waydroid or shutil.which("waydroid") or "/usr/bin/waydroid"
    try:
        with open(waydroid, "rb") as script:
            first = script.readline().decode("utf-8", "replace").strip()
    except OSError:
        return None
    if not first.startswith("#!"):
        return None
    parts = first[2:].split()
    if not parts:
        return None
    # "#!/usr/bin/env python3" names the interpreter in its argument.
    if os.path.basename(parts[0]) == "env":
        names = [p for p in parts[1:] if not p.startswith("-")]
        return shutil.which(names[0]) if names else None
    return parts[0]


def distro_ids(os_release: str = "/etc/os-release") -> List[str]:
    """ID followed by ID_LIKE from os-release, so derivatives match their base."""
    ids = []
    try:
        with open(os_release) as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                if key in ("ID", "ID_LIKE"):
                    ids.extend(value.strip('"').split())
    except OSError:
        pass
    return ids


def install_hint(python: str) -> str:
    for distro in distro_ids():
        if distro in INSTALL_COMMANDS:
            return "Install it with: {}".format(INSTALL_COMMANDS[distro])
    return ("Install pyclip for {} from your distribution's packages if it "
            "has one, otherwise with pip for that interpreter.".format(python))


def can_import_pyclip(python: str) -> bool:
    """Try the import as the invoking user, the way the session will.

    The Waydroid session runs as the desktop user, not as root. Running the
    check as root would miss a pyclip installed in that user's site-packages.
    """
    cmd = [python, "-c", "import pyclip"]
    user = invoking_user()
    if os.geteuid() == 0 and user and user != "root":
        cmd = ["sudo", "-u", user, "--"] + cmd
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


class Clipboard:
    id = "clipboard"

    def check(self) -> bool:
        """Report each requirement, and return whether all of them are met."""
        ok = True

        python = waydroid_interpreter()
        if python is None:
            Logger.error(
                "Could not find the Python interpreter Waydroid runs with. "
                "Is Waydroid installed?")
            return False

        if can_import_pyclip(python):
            Logger.info("pyclip is importable by {}".format(python))
        else:
            ok = False
            Logger.error(
                "pyclip cannot be imported by {}, the Python Waydroid runs "
                "with. Waydroid turns clipboard sharing off without saying "
                "so.".format(python))
            Logger.error(install_hint(python))

        missing = [tool for tool in WAYLAND_TOOLS if shutil.which(tool) is None]
        if missing:
            ok = False
            Logger.error(
                "{} not found. pyclip needs wl-clipboard to reach the Wayland "
                "clipboard.".format(", ".join(missing)))
        else:
            Logger.info("wl-clipboard is installed")

        if ok:
            Logger.info(
                "Clipboard sharing has what it needs. If it still does not "
                "work, restart the session: waydroid session stop")
        else:
            Logger.info(
                "After fixing the above, restart the session: "
                "waydroid session stop")
        return ok
