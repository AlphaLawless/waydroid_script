"""The interactive menu must not offer an action that cannot run.

Upstream #264: picking "Hack" on Android 13 crashed inside InquirerPy,
because the hack options only exist for Android 11 and the checkbox was
handed an empty choices list.

interact() drives a terminal UI and calls into installers, so it cannot be
run here. What can be checked is the decision it makes: which actions the
menu offers for a given Android version. That logic is lifted out of the
source the same way test_cli_args.py lifts the parser, and the assertions
below fail if it moves.
"""
import textwrap

import pytest


def menu_actions(android_version):
    """Replay interact()'s action-list construction for one Android version."""
    source = open("main.py").read()
    start = source.index('    install_choices = ["gapps"')
    end = source.index("    action = inquirer.select(")
    # The block lives inside interact(), so it arrives indented and has to be
    # dedented before exec() will accept it as a module body.
    block = textwrap.dedent(source[start:end])
    namespace = {"android_version": android_version}
    exec(block, namespace)
    return namespace["actions"], namespace["hack_choices"]


def test_the_block_is_where_the_test_expects_it():
    source = open("main.py").read()
    assert '    install_choices = ["gapps"' in source
    assert "    action = inquirer.select(" in source


def test_android_11_offers_hack():
    actions, hack_choices = menu_actions("11")
    assert "Hack" in actions
    assert hack_choices == ["nodataperm", "hidestatusbar"]


def test_android_13_does_not_offer_hack():
    """The regression. Offering it led to inquirer.checkbox(choices=[])."""
    actions, hack_choices = menu_actions("13")
    assert hack_choices == []
    assert "Hack" not in actions


@pytest.mark.parametrize("android_version", ["11", "13"])
def test_the_other_actions_are_always_offered(android_version):
    actions, _ = menu_actions(android_version)
    for always in ("Install", "Remove", "Get Google Device ID to Get Certified"):
        assert always in actions


@pytest.mark.parametrize("android_version", ["11", "13"])
def test_hack_is_offered_exactly_when_there_is_something_to_pick(android_version):
    """The invariant, rather than the two cases: the action appears if and
    only if the checkbox behind it would have choices."""
    actions, hack_choices = menu_actions(android_version)
    assert ("Hack" in actions) == bool(hack_choices)
