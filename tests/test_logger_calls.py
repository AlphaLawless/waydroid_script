"""Every Logger call has to name a method that exists.

Logger defines error, info and warning. main.py called Logger.warn, which
does not exist, so the two paths meant to explain "not supported on your
CPU" raised AttributeError instead — a traceback exactly where the code was
trying to be helpful.

Static rather than dynamic: these branches only run on non-x86_64 hardware,
so a test that called them would be skipped on the machines that run CI.
"""
import ast

from tools.logger import Logger

SOURCES = ["main.py", "tools/helper.py", "tools/images.py", "tools/container.py",
           "stuff/android_id.py", "stuff/general.py", "stuff/gapps.py",
           "stuff/magisk.py", "stuff/microg.py", "stuff/nodataperm.py"]


def logger_calls(path):
    """Every attribute accessed on Logger in a source file."""
    tree = ast.parse(open(path).read())
    return {node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Logger"}


def test_logger_exposes_what_it_is_expected_to():
    for name in ("error", "info", "warning"):
        assert callable(getattr(Logger, name))


def test_no_source_calls_a_missing_logger_method():
    available = {name for name in dir(Logger) if not name.startswith("_")}
    for path in SOURCES:
        for called in logger_calls(path):
            assert called in available, (
                f"{path} calls Logger.{called}, which does not exist; "
                f"Logger has {sorted(available)}")


def test_warn_is_not_used_anywhere():
    """The specific mistake: warn is the logging-module spelling, warning is
    this project's."""
    for path in SOURCES:
        assert "warn" not in logger_calls(path), f"{path} still calls Logger.warn"
