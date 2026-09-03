"""The Magisk binaries have to be executable in both copies.

Upstream #283: `install magisk` gives working root but Zygisk never
initialises, and nothing says why. The Magisk app just reports "Zygisk: No".

General.install() runs copy() -> extra1() -> set_perm(), in that order.
setup() (reached through extra1) copies the overlay tree into
<data_dir>/adb/magisk, and set_perm() afterwards walks only self.files, which
are paths under copy_dir. So the overlay copy gets fixed and the /data/adb one
keeps whatever mode it was created with.

Magisk overrides set_path_perm() to give 0755 to anything with a "magisk"
path component, which is why root works from the overlay copy while
/data/adb/magisk/magisk64 stays 0644 and magisk_env() bails at post-fs-data.
"""
import os
import stat

import pytest

from stuff import magisk as magisk_module
from stuff.magisk import Magisk

BINARIES = ["magisk64", "magiskinit", "magiskpolicy", "magiskboot"]
ASSETS = ["addon.d.sh", "boot_patch.sh", "stub.apk", "util_functions.sh"]


@pytest.fixture
def staged(tmp_path, monkeypatch):
    """A Magisk instance pointed at a fake extracted apk and empty overlay."""
    extract_to = tmp_path / "unpack"
    lib_dir = extract_to / "lib" / "x86_64"
    lib_dir.mkdir(parents=True)
    for name in BINARIES:
        # 0644 is what unzip leaves behind, and what copyfile would reproduce.
        target = lib_dir / f"lib{name}.so"
        target.write_bytes(b"\x7fELF fake")
        target.chmod(0o644)

    assets = extract_to / "assets"
    (assets / "chromeos").mkdir(parents=True)
    for name in ASSETS:
        (assets / name).write_text("#!/bin/sh\n")

    apk = tmp_path / "magisk.apk"
    apk.write_bytes(b"PK fake")

    copy_dir = tmp_path / "overlay"
    (copy_dir / "system" / "etc" / "init").mkdir(parents=True)

    data_dir = tmp_path / "data"
    (data_dir / "adb").mkdir(parents=True)
    monkeypatch.setattr(magisk_module, "get_data_dir", lambda: str(data_dir))

    # copy_dir, download_loc and arch are read-only properties on General,
    # each reaching for real state (the waydroid overlay, the user's download
    # cache, the host CPU). Subclass to point them at the fixture instead, and
    # skip General.__init__ so nothing touches the real home directory.
    #
    # Bound to separate names first: a class body does not close over the
    # enclosing scope, so `copy_dir = str(copy_dir)` inside it would refer to
    # the attribute being defined rather than to the fixture's variable.
    staged_copy_dir, staged_apk = str(copy_dir), str(apk)
    staged_extract_to = str(extract_to)

    class StagedMagisk(Magisk):
        copy_dir = staged_copy_dir
        download_loc = staged_apk
        arch = ("x86_64", 64)
        extract_to = staged_extract_to

    return StagedMagisk.__new__(StagedMagisk), copy_dir, data_dir


def is_executable(path):
    return bool(os.stat(path).st_mode & stat.S_IXUSR)


@pytest.mark.parametrize("binary", BINARIES)
def test_overlay_copy_is_executable(staged, binary):
    instance, copy_dir, _ = staged
    instance.copy()
    path = copy_dir / instance.magisk_dir / binary
    assert is_executable(path), f"{binary} in the overlay is not executable"


@pytest.mark.parametrize("binary", BINARIES)
def test_data_dir_copy_is_executable(staged, binary):
    """The regression. This copy is made before set_perm() ever runs, so it
    only comes out right if copy() created the files executable."""
    instance, _, data_dir = staged
    instance.copy()
    instance.setup()
    path = data_dir / "adb" / "magisk" / binary
    assert path.exists(), f"{binary} was not copied into the data dir"
    assert is_executable(path), (
        f"/data/adb/magisk/{binary} is not executable; magisk_env() aborts at "
        f"post-fs-data and Zygisk silently never initialises")


def test_both_copies_agree(staged):
    """Whatever the mode is, the two copies must not disagree — a difference
    between them is what made this bug so hard to diagnose."""
    instance, copy_dir, data_dir = staged
    instance.copy()
    instance.setup()
    for binary in BINARIES:
        overlay = os.stat(copy_dir / instance.magisk_dir / binary).st_mode
        data = os.stat(data_dir / "adb" / "magisk" / binary).st_mode
        assert stat.S_IMODE(overlay) == stat.S_IMODE(data), binary


def test_set_path_perm_never_clears_a_bit():
    """set_path_perm ORs the mode, so it can add permissions but never remove
    them. That is why fixing this after the fact does not work: a file created
    0644 stays 0644 no matter how often set_perm runs over it."""
    source = open("stuff/general.py").read()
    assert "mode |= perms[2]" in source
    assert "mode |= perms[3]" in source
