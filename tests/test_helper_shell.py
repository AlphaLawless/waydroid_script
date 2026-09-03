"""shell() runs commands inside the container the way the docs describe.

The Waydroid documentation tells users to run container commands as

    waydroid shell -- sh -c "<command>"

This used to be three subprocess.Popen calls piping `echo` output into the
stdin of a fourth. Besides being hard to follow, it could not report a
failure: it read stderr twice and never waited, so the exception said
"exit status None".

shell_command() exists so the argv can be asserted without spawning
anything — there is no Waydroid container in CI.
"""
import subprocess

import pytest

from tools.helper import shell, shell_command


def test_uses_the_documented_form():
    argv = shell_command("id")
    assert argv[:4] == ["waydroid", "shell", "--", "sh"]
    assert argv[4] == "-c"
    assert len(argv) == 6


def test_no_sudo_prefix():
    """check_root() guarantees the process is already root; an inner sudo
    would only send the child through env_reset."""
    assert "sudo" not in shell_command("id")


def test_command_is_one_argument_not_a_shell_string():
    """Passing the command as argv means the host shell never re-parses it,
    so quoting in the command is the container shell's business alone."""
    argv = shell_command('echo "hello world"')
    assert argv[-1].endswith('echo "hello world"')


def test_bootclasspath_is_exported():
    """`waydroid shell` does not set up the Android environment, so anything
    running on ART needs BOOTCLASSPATH."""
    script = shell_command("id")[-1]
    assert script.startswith("export BOOTCLASSPATH=")
    assert "/apex/com.android.art/javalib/core-oj.jar" in script


def test_extra_env_is_exported_before_the_command():
    # A distinctive command: "id" also occurs inside "android" all over the
    # BOOTCLASSPATH, so ordering assertions need a marker that does not.
    marker = "zzmarkerzz"
    script = shell_command(marker, env="ANDROID_DATA=/data FOO=bar")[-1]
    assert "export ANDROID_DATA=/data FOO=bar" in script
    assert script.index("export ANDROID_DATA") < script.index(marker)


def test_globs_survive_to_the_container_shell():
    """sh -c means the container expands the glob. The documented android_id
    query depends on that."""
    script = shell_command("sqlite3 /data/data/*/*/gservices.db 'select 1;'")[-1]
    assert "/data/data/*/*/gservices.db" in script


def test_failure_raises_instead_of_returning_empty(monkeypatch):
    """The old implementation could not tell a failure from an empty result.
    run() raises on a non-zero exit, so shell() does too."""
    import tools.helper as helper

    def fake_run(args, env=None, ok_codes=(0,)):
        raise subprocess.CalledProcessError(returncode=1, cmd=args,
                                            stderr=b"container not running")

    monkeypatch.setattr(helper, "run", fake_run)
    with pytest.raises(subprocess.CalledProcessError):
        shell("id")


def test_stdout_is_returned_decoded(monkeypatch):
    import tools.helper as helper

    class Result:
        stdout = b"1234567890\n"

    monkeypatch.setattr(helper, "run", lambda *a, **k: Result())
    assert shell("id") == "1234567890\n"
