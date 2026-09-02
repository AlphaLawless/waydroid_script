"""run() and shell() decide failure from the exit code, not from stderr.

The bug these cover: run() used to treat any write to stderr as an error and
pass result.returncode (which was 0) to CalledProcessError, producing
"returned non-zero exit status 0". Upstream #202, #251, #271, #277.
"""
import subprocess

import pytest

from tools.helper import run


def test_success_writing_to_stderr_does_not_raise():
    """The original bug: exit 0 plus a warning on stderr was treated as failure."""
    result = run(["sh", "-c", "echo warning >&2; exit 0"])
    assert result.returncode == 0
    assert result.stderr == b"warning\n"


def test_failure_with_stderr_raises():
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run(["sh", "-c", "echo boom >&2; exit 1"])
    assert excinfo.value.returncode == 1


def test_failure_without_stderr_still_raises():
    """The mirror of the original bug.

    e2fsck writes most of its output to stdout, so a run() that required
    stderr to be non-empty would let exit code 8 (operational error) pass as
    success and let resize2fs loose on a filesystem that failed its check.
    """
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run(["sh", "-c", "echo failure detail on stdout; exit 8"])
    assert excinfo.value.returncode == 8


def test_exception_carries_the_real_return_code():
    """It used to carry 0, which is where "non-zero exit status 0" came from."""
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run(["sh", "-c", "exit 7"])
    assert excinfo.value.returncode == 7


@pytest.mark.parametrize("code", [0, 1, 2])
def test_e2fsck_success_codes_are_allowed(code):
    """e2fsck exit codes are a bitmask: 1 means it corrected errors, 2 means it
    corrected them and advises a reboot. Both are success."""
    result = run(["sh", "-c", f"echo e2fsck 1.47.10 banner >&2; exit {code}"],
                 ok_codes=(0, 1, 2))
    assert result.returncode == code


def test_e2fsck_uncorrected_errors_still_raise():
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run(["sh", "-c", "echo uncorrected >&2; exit 4"], ok_codes=(0, 1, 2))
    assert excinfo.value.returncode == 4


def test_version_banner_shape_is_irrelevant():
    """The old ignore= regex was pinned to a three component version with a
    single digit at the end, so it stopped matching at e2fsck 1.47.10. Exit
    codes do not care what the banner looks like."""
    for banner in ("e2fsck 1.46.2 (28-Feb-2021)",
                   "e2fsck 1.47.1 (20-May-2024)",
                   "e2fsck 1.47.10 (01-Jan-2026)"):
        assert run(["sh", "-c", f"echo '{banner}' >&2; exit 1"],
                   ok_codes=(0, 1, 2)).returncode == 1
