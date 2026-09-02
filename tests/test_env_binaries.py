"""lzip and tar must come from the environment, not from PATH.

Under sudo, PATH is replaced by secure_path, so anything resolved through
PATH inside a sudo'd process comes from the host rather than from the
environment the lockfile pinned. Absolute paths sidestep that entirely.
"""
import os
import shutil
import subprocess
import sys

import pytest

from tools.helper import env_binary, tar_lzip_command

BARE_PATH = "/usr/bin:/bin"


def test_env_binary_prefers_the_environment_copy():
    resolved = env_binary("python")
    assert resolved == os.path.join(sys.prefix, "bin", "python")
    assert os.path.isabs(resolved)


def test_env_binary_falls_back_to_the_bare_name():
    """A checkout run outside pixi keeps behaving the way it always did."""
    assert env_binary("definitely-not-in-this-env-4f2a") == \
        "definitely-not-in-this-env-4f2a"


def test_host_only_tools_are_left_to_path():
    """e2fsck and friends stay host dependencies; they are not in the lockfile
    and must not be resolved into the env."""
    assert env_binary("e2fsck") == "e2fsck"


def test_tar_lzip_command_pins_the_compressor_too():
    """`tar --lzip` shells out to lzip through PATH, so pinning tar alone is
    not enough. --use-compress-program is the only form that pins both."""
    argv = tar_lzip_command("/tmp/a.tar.lz", "/tmp/out")
    assert argv[0] == env_binary("tar")
    assert argv[1] == "--use-compress-program=" + env_binary("lzip")
    assert "--lzip" not in argv


@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.prefix, "bin", "lzip")),
                    reason="needs the pixi environment's lzip")
def test_extraction_works_with_a_bare_path(tmp_path):
    """The regression this whole design exists to prevent.

    Runs the real command with a PATH that has no lzip on it, the way it
    looks inside a sudo'd process on a machine without a distro lzip.
    """
    payload = tmp_path / "payload.txt"
    payload.write_text("waydroid")
    archive = tmp_path / "a.tar.lz"
    subprocess.run(
        [env_binary("tar"), "--use-compress-program=" + env_binary("lzip"),
         "-cf", str(archive), "-C", str(tmp_path), "payload.txt"],
        check=True)
    payload.unlink()

    dest = tmp_path / "out"
    dest.mkdir()
    result = subprocess.run(tar_lzip_command(str(archive), str(dest)),
                            env={"PATH": BARE_PATH}, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert (dest / "payload.txt").read_text() == "waydroid"


@pytest.mark.skipif(shutil.which("lzip", path=BARE_PATH) is not None,
                    reason="host has lzip, so PATH resolution would succeed")
@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.prefix, "bin", "lzip")),
                    reason="needs the pixi environment's lzip")
def test_the_old_form_would_have_failed(tmp_path):
    """Proves the previous test is testing something.

    `tar --lzip` with the same bare PATH cannot find lzip and fails, which is
    exactly what would happen under sudo before this change.
    """
    payload = tmp_path / "payload.txt"
    payload.write_text("waydroid")
    archive = tmp_path / "a.tar.lz"
    subprocess.run(
        [env_binary("tar"), "--use-compress-program=" + env_binary("lzip"),
         "-cf", str(archive), "-C", str(tmp_path), "payload.txt"],
        check=True)

    dest = tmp_path / "out"
    dest.mkdir()
    result = subprocess.run(
        [env_binary("tar"), "--lzip", "-xf", str(archive), "-C", str(dest)],
        env={"PATH": BARE_PATH}, capture_output=True)
    assert result.returncode != 0
    assert b"lzip" in result.stderr
