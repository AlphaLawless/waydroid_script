"""-a/--android-version has to work on both sides of the subcommand.

Declared only on the top-level parser and only after add_subparsers(), it was
reachable as `main.py -a 11 install gapps` but not as
`main.py install -a 11 gapps` — and the second shape is what every wrapper
produces, including this repository's own pixi tasks.
"""
import argparse
import re

import pytest


def build_parser():
    """Build main()'s parser without importing main's heavy dependencies.

    main() mixes parser construction and dispatch in one function, so the
    parser cannot be imported on its own. Rather than refactor production code
    to suit the test, lift the construction block out of the source. The
    assertions below fail loudly if that block moves.
    """
    source = open("main.py").read()
    start = source.index("def main():")
    end = source.index("    args = parser.parse_args()")
    block = source[start:end].replace("def main():", "def build():", 1)
    # set_defaults(func=...) references handlers we deliberately do not import
    block = re.sub(r"^\s*\w+\.set_defaults\(func=\w+\)\s*$", "", block, flags=re.M)
    # The parser references these when declaring --spoof-profile, so the
    # extracted block cannot be exec'd without them.
    from stuff.device_spoof import DEFAULT_PROFILE, PROFILES
    namespace = {"argparse": argparse, "PROFILES": PROFILES,
                 "DEFAULT_PROFILE": DEFAULT_PROFILE}
    exec(block + "    return parser\n", namespace)
    return namespace["build"]()


def parse(argv):
    """Mirror what main() does after parse_args().

    -a is declared with default=SUPPRESS on both parsers so neither clobbers
    the other, which means the attribute is absent when the flag was not
    given at all.
    """
    args = build_parser().parse_args(argv)
    return getattr(args, "android_version", "13")


def test_parser_block_is_where_the_test_expects_it():
    source = open("main.py").read()
    assert "def main():" in source
    assert "    args = parser.parse_args()" in source


@pytest.mark.parametrize("argv,expected", [
    # The regression: this shape is what `pixi run install -a 11 gapps`
    # produces, and it used to exit 2.
    (["install", "-a", "11", "gapps"], "11"),
    (["install", "--android-version", "11", "gapps"], "11"),
    (["remove", "-a", "11", "gapps"], "11"),
    (["uninstall", "-a", "11", "gapps"], "11"),
    (["hack", "-a", "11", "nodataperm"], "11"),
    (["certified", "-a", "11"], "11"),
])
def test_flag_after_the_subcommand(argv, expected):
    assert parse(argv) == expected


@pytest.mark.parametrize("argv,expected", [
    (["-a", "11", "install", "gapps"], "11"),
    (["-a", "11", "remove", "gapps"], "11"),
    (["-a", "11", "hack", "nodataperm"], "11"),
    (["-a", "11", "certified"], "11"),
])
def test_flag_before_the_subcommand(argv, expected):
    """This shape already worked; SUPPRESS is what keeps it working.

    Without default=SUPPRESS the subparser overwrites the value the top-level
    parser already read with its own default, and this silently returns 13.
    """
    assert parse(argv) == expected


@pytest.mark.parametrize("argv", [
    ["install", "gapps"],
    ["remove", "gapps"],
    ["certified"],
    ["hack", "nodataperm"],
])
def test_default_when_the_flag_is_absent(argv):
    assert parse(argv) == "13"


def test_every_subcommand_accepts_the_flag():
    """Iterates the parser's own subcommands instead of a hand written list,
    so a subcommand added later without parents=[android_version_parser] fails
    here rather than losing -a in silence."""
    parser = build_parser()
    subparsers = [action for action in parser._actions
                  if isinstance(action, argparse._SubParsersAction)]
    assert subparsers, "main.py no longer uses subparsers"
    for name, sub in subparsers[0].choices.items():
        options = {option
                   for action in sub._actions
                   for option in action.option_strings}
        assert "-a" in options, f"subcommand {name!r} cannot take -a"
