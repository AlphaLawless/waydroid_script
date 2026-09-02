"""images.py talks to mountpoint, e2fsck and resize2fs through run().

The regression guarded here: mountpoint answers "not a mount point" with a
non-zero exit code, its message on stdout and an empty stderr. umount()
reads .returncode to branch on that. A run() that raised on any non-zero
code would turn the ordinary "not mounted yet" path into a crash.
"""
import subprocess

import pytest

from tools import images


class FakeCompleted:
    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = b""
        self.stderr = b""
        self.args = []


def test_umount_tolerates_a_path_that_is_not_a_mount_point(tmp_path, monkeypatch):
    """mountpoint exits 32 here on this machine. Verified, not assumed."""
    calls = []

    def fake_run(args, env=None, ok_codes=(0,)):
        calls.append((args, ok_codes))
        if args[0] == "mountpoint":
            assert 32 in ok_codes, "mountpoint's non-zero answer must be allowed"
            return FakeCompleted(32)
        return FakeCompleted(0)

    monkeypatch.setattr(images, "run", fake_run)
    images.umount(str(tmp_path))

    commands = [args[0] for args, _ in calls]
    assert "mountpoint" in commands
    assert "umount" not in commands, "must not unmount what was never mounted"


def test_umount_unmounts_a_real_mount_point(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, env=None, ok_codes=(0,)):
        calls.append(args[0])
        return FakeCompleted(0)

    monkeypatch.setattr(images, "run", fake_run)
    images.umount(str(tmp_path))
    assert calls == ["mountpoint", "umount"]


def test_resize_allows_the_e2fsck_correction_codes(monkeypatch):
    """1 means errors corrected, 2 means corrected and reboot advised. Both are
    the normal outcome of fscking a dirty image, not a failure."""
    seen = {}

    def fake_run(args, env=None, ok_codes=(0,)):
        seen[args[0]] = ok_codes
        return FakeCompleted(0)

    monkeypatch.setattr(images, "run", fake_run)
    images.resize("/tmp/system.img", "2048M")

    assert set(seen) == {"e2fsck", "resize2fs"}
    assert 1 in seen["e2fsck"] and 2 in seen["e2fsck"]
    assert 4 not in seen["e2fsck"], "uncorrected errors must not be allowed"


def test_resize_does_not_shell_out_through_sudo(monkeypatch):
    """The process is already root by then; an inner sudo would send the child
    through env_reset for no reason."""
    seen = []

    def fake_run(args, env=None, ok_codes=(0,)):
        seen.append(args)
        return FakeCompleted(0)

    monkeypatch.setattr(images, "run", fake_run)
    images.resize("/tmp/system.img", "2048M")
    assert all("sudo" not in args for args in seen)


def test_resize_propagates_a_real_fsck_failure(monkeypatch):
    def fake_run(args, env=None, ok_codes=(0,)):
        if args[0] == "e2fsck":
            raise subprocess.CalledProcessError(returncode=4, cmd=args)
        return FakeCompleted(0)

    monkeypatch.setattr(images, "run", fake_run)
    with pytest.raises(subprocess.CalledProcessError):
        images.resize("/tmp/system.img", "2048M")
