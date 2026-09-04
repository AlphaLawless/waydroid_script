"""Reading and writing the [properties] section of waydroid.cfg.

Waydroid applies whatever is in that section to the Android system when the
container starts, which is the documented way to set properties — the ArchWiki
uses it for the software rendering example, and `waydroid upgrade --offline`
is what makes a change take effect.

Extracted from General.add_props/remove_props so that things which only need
to set properties, and have no files to install, can do so without pretending
to be an installable package.
"""
import configparser

WAYDROID_CFG = "/var/lib/waydroid/waydroid.cfg"
SECTION = "properties"


def _resolve(path):
    """Where the config lives, decided when called rather than when imported.

    A default argument of `path=WAYDROID_CFG` binds the value at definition
    time, so pointing the module somewhere else afterwards has no effect —
    which silently sent tests at the real /var/lib/waydroid/waydroid.cfg.
    """
    return path if path is not None else WAYDROID_CFG


def _read(path):
    cfg = configparser.ConfigParser()
    cfg.read(path)
    if not cfg.has_section(SECTION):
        cfg.add_section(SECTION)
    return cfg


def _write(cfg, path):
    with open(path, "w") as config_file:
        cfg.write(config_file)


def set_props(props, path=None):
    """Set each key, leaving the rest of the file alone.

    Falsy values are skipped rather than written empty, matching what
    General.add_props has always done.
    """
    path = _resolve(path)
    cfg = _read(path)
    for key, value in props.items():
        if value:
            cfg.set(SECTION, key, value)
    _write(cfg, path)


def unset_props(keys, path=None):
    """Remove each key. Keys that are not there are not an error."""
    path = _resolve(path)
    cfg = _read(path)
    for key in keys:
        cfg.remove_option(SECTION, key)
    _write(cfg, path)


def get_props(path=None):
    """Current contents of the section, as a plain dict."""
    return dict(_read(_resolve(path)).items(SECTION))
