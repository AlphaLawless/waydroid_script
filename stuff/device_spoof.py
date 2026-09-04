"""Present the container as a real phone instead of a generic Waydroid device.

Waydroid identifies itself with a generic build fingerprint signed with
test-keys. Plenty of Play Store apps read those properties to decide whether
they are running on a supported device, and refuse to start when they see it —
the fingerprint and the key type are the usual tells.

Writing a real device's properties into waydroid.cfg makes the container claim
to be that phone. Nothing is patched or intercepted: these are the same
properties Waydroid already exposes for configuration, and the ArchWiki
documents the mechanism for software rendering.

Two known limits, both worth knowing before reaching for this:

  - Whether the override actually takes for build fingerprint properties is
    not something this code can guarantee. Waydroid applies [properties] at
    container start, but ro.* properties are also set from the image's
    build.prop during boot. Verify with `waydroid prop get ro.product.model`
    after restarting.
  - An app doing real attestation, rather than reading properties, is not
    fooled by this. Play Integrity checks the bootloader and a signed
    hardware-backed attestation, neither of which a property can supply.
"""
from tools import props
from tools.logger import Logger

PROFILES = {
    "pixel6": {
        "ro.product.brand": "google",
        "ro.product.manufacturer": "Google",
        "ro.product.model": "Pixel 6",
        "ro.product.name": "oriole",
        "ro.product.device": "oriole",
        "ro.product.board": "oriole",
        "ro.build.product": "oriole",
        "ro.build.fingerprint":
            "google/oriole/oriole:13/TQ3A.230901.001/10750268:user/release-keys",
        "ro.build.description":
            "oriole-user 13 TQ3A.230901.001 10750268 release-keys",
        "ro.build.version.release": "13",
        "ro.build.version.sdk": "33",
        "ro.build.type": "user",
        "ro.build.tags": "release-keys",
    },
    "samsung_s21": {
        "ro.product.brand": "samsung",
        "ro.product.manufacturer": "samsung",
        "ro.product.model": "SM-G991B",
        "ro.product.name": "o1sxeea",
        "ro.product.device": "o1s",
        "ro.product.board": "lahaina",
        "ro.build.product": "o1s",
        "ro.build.fingerprint":
            "samsung/o1sxeea/o1s:13/TP1A.220624.014/G991BXXU5EWCA:user/release-keys",
        "ro.build.description":
            "o1sxeea-user 13 TP1A.220624.014 G991BXXU5EWCA release-keys",
        "ro.build.version.release": "13",
        "ro.build.version.sdk": "33",
        "ro.build.type": "user",
        "ro.build.tags": "release-keys",
    },
}

DEFAULT_PROFILE = "pixel6"


def spoofed_keys():
    """Every property any profile sets.

    The union rather than one profile's keys: removing a spoof has to clean up
    after whichever profile was applied, and profiles are free to differ.
    """
    keys = set()
    for profile in PROFILES.values():
        keys.update(profile)
    return sorted(keys)


class DeviceSpoof:
    id = "device_spoof"

    def __init__(self, profile_name=DEFAULT_PROFILE) -> None:
        if profile_name not in PROFILES:
            raise ValueError(
                "Unknown device profile {!r}. Available: {}".format(
                    profile_name, ", ".join(sorted(PROFILES))))
        self.profile_name = profile_name
        self.apply_props = PROFILES[profile_name]

    def install(self):
        props.set_props(self.apply_props)
        Logger.info(
            "Device now reports as {} ({}).".format(
                self.apply_props["ro.product.model"], self.profile_name))
        Logger.info(
            "Restart Waydroid to apply, then check it took with: "
            "waydroid prop get ro.product.model")

    def uninstall(self):
        props.unset_props(spoofed_keys())
        Logger.info(
            "Device spoof removed; the container reports itself again. "
            "Restart Waydroid to apply.")
