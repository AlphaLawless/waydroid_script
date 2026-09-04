"""Presenting the container as a real phone.

Waydroid identifies itself with a generic build fingerprint signed with
test-keys, and plenty of Play Store apps refuse to start when they read that.
Writing a real device's properties into waydroid.cfg makes it claim to be that
phone instead.

Every test drives a temporary config file. Nothing here touches
/var/lib/waydroid/waydroid.cfg.
"""
import pytest

from stuff.device_spoof import (DEFAULT_PROFILE, PROFILES, DeviceSpoof,
                                spoofed_keys)
from tools import props

REQUIRED_KEYS = [
    "ro.product.brand", "ro.product.manufacturer", "ro.product.model",
    "ro.product.name", "ro.product.device", "ro.build.fingerprint",
    "ro.build.version.release", "ro.build.version.sdk", "ro.build.tags",
]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A waydroid.cfg with a pre-existing section and unrelated settings."""
    path = tmp_path / "waydroid.cfg"
    path.write_text(
        "[waydroid]\n"
        "arch = x86_64\n"
        "images_path = /var/lib/waydroid/images\n"
        "\n"
        "[properties]\n"
        "ro.hardware.gralloc = default\n"
        "persist.waydroid.multi_windows = true\n"
    )
    monkeypatch.setattr(props, "WAYDROID_CFG", str(path))
    return path


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_every_profile_is_complete(name):
    """A profile missing ro.build.tags or the fingerprint is worse than none:
    it changes the model name while leaving the tell in place."""
    profile = PROFILES[name]
    for key in REQUIRED_KEYS:
        assert key in profile, f"{name} is missing {key}"
        assert profile[key], f"{name} has an empty {key}"


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_no_profile_claims_test_keys(name):
    """test-keys is the signature apps look for. A profile that keeps it
    defeats the purpose of applying one."""
    profile = PROFILES[name]
    assert profile["ro.build.tags"] == "release-keys"
    assert profile["ro.build.fingerprint"].endswith("release-keys")
    assert "test-keys" not in profile["ro.build.fingerprint"]


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_fingerprint_agrees_with_the_rest_of_the_profile(name):
    """A fingerprint naming a different device than ro.product.device is an
    inconsistency an app can notice."""
    profile = PROFILES[name]
    brand, _, rest = profile["ro.build.fingerprint"].partition("/")
    assert brand == profile["ro.product.brand"]
    assert profile["ro.product.device"] in rest
    assert ":{}/".format(profile["ro.build.version.release"]) in rest


def test_default_profile_exists():
    assert DEFAULT_PROFILE in PROFILES


def test_unknown_profile_is_rejected_by_name():
    with pytest.raises(ValueError, match="nokia_3310"):
        DeviceSpoof("nokia_3310")


def test_install_writes_the_properties(cfg):
    DeviceSpoof("pixel6").install()
    written = props.get_props(str(cfg))
    assert written["ro.product.model"] == "Pixel 6"
    assert written["ro.build.tags"] == "release-keys"


def test_install_leaves_unrelated_settings_alone(cfg):
    """Read-modify-write on a config file the user also edits by hand."""
    DeviceSpoof("pixel6").install()
    body = cfg.read_text()
    assert "arch = x86_64" in body
    assert "images_path = /var/lib/waydroid/images" in body
    written = props.get_props(str(cfg))
    assert written["ro.hardware.gralloc"] == "default"
    assert written["persist.waydroid.multi_windows"] == "true"


def test_uninstall_removes_every_spoofed_key(cfg):
    DeviceSpoof("pixel6").install()
    DeviceSpoof().uninstall()
    remaining = props.get_props(str(cfg))
    for key in PROFILES["pixel6"]:
        assert key not in remaining


def test_uninstall_keeps_what_it_did_not_set(cfg):
    DeviceSpoof("pixel6").install()
    DeviceSpoof().uninstall()
    remaining = props.get_props(str(cfg))
    assert remaining["ro.hardware.gralloc"] == "default"
    assert remaining["persist.waydroid.multi_windows"] == "true"


def test_uninstall_cleans_up_after_a_different_profile(cfg, monkeypatch):
    """uninstall() takes no profile argument, so it has to remove the union of
    every profile's keys, not just the default one's.

    Today both shipped profiles set exactly the same keys, so removing only
    the default profile's would pass by coincidence. A profile with a key the
    others lack is what makes this test discriminate — and is what a third
    profile would look like the moment somebody adds one.
    """
    extra = dict(PROFILES["samsung_s21"])
    extra["ro.product.first_api_level"] = "30"
    monkeypatch.setitem(PROFILES, "with_extra_key", extra)

    DeviceSpoof("with_extra_key").install()
    assert "ro.product.first_api_level" in props.get_props(str(cfg))

    DeviceSpoof().uninstall()
    remaining = props.get_props(str(cfg))
    for key in extra:
        assert key not in remaining, f"{key} survived uninstall"


def test_uninstall_on_a_clean_config_is_not_an_error(cfg):
    DeviceSpoof().uninstall()
    assert props.get_props(str(cfg))["ro.hardware.gralloc"] == "default"


def test_switching_profiles_leaves_no_mixture(cfg):
    """Applying a second profile over a first must not leave Samsung values
    next to Google ones."""
    DeviceSpoof("samsung_s21").install()
    DeviceSpoof().uninstall()
    DeviceSpoof("pixel6").install()
    written = props.get_props(str(cfg))
    assert written["ro.product.brand"] == "google"
    assert written["ro.product.manufacturer"] == "Google"
    assert "samsung" not in written["ro.build.fingerprint"]


def test_spoofed_keys_is_the_union():
    union = spoofed_keys()
    for profile in PROFILES.values():
        for key in profile:
            assert key in union


def test_wired_into_the_cli():
    source = open("main.py").read()
    assert "device_spoof" in source
    assert "--spoof-profile" in source
    assert "DeviceSpoof(getattr(args" in source


def test_spoof_does_not_join_the_install_list():
    """It writes properties and touches no files, so it must not drag the
    image mounting the other installables need."""
    source = open("main.py").read()
    assert "install_list.append(DeviceSpoof" not in source
