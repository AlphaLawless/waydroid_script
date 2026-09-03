import subprocess

from tools import container
from tools.helper import shell
from tools.logger import Logger

REGISTER_URL = "https://www.google.com/android/uncertified"

# The query the Waydroid documentation gives users, verbatim in shape:
#
#   sqlite3 /data/data/*/*/gservices.db "select value from main where name = 'android_id';"
#
# Two details matter and this used to get both wrong. The path is a glob
# rather than a fixed com.google.android.gsf, because GApps and microG do not
# put gservices.db under the same package. And it selects `value` rather than
# `*`, so there is no "android_id|" prefix to strip back off afterwards.
QUERY = ('sqlite3 /data/data/*/*/gservices.db '
         '"select value from main where name = \'android_id\';"')

# waydroid shell does not set up the Android environment. Kept from the
# previous implementation: the documented one-liner does not export these, but
# there is no way to test here whether sqlite3 in the container needs them, and
# removing something that currently works to match a doc more closely is a bad
# trade.
ENV = ("ANDROID_RUNTIME_ROOT=/apex/com.android.runtime "
       "ANDROID_DATA=/data "
       "ANDROID_TZDATA_ROOT=/apex/com.android.tzdata "
       "ANDROID_I18N_ROOT=/apex/com.android.i18n")


class AndroidId:
    def get_id(self):
        if not container.is_running():
            Logger.error(
                "Waydroid is not running. Start it with `waydroid session start`, "
                "then try again.")
            return

        try:
            android_id = shell(QUERY, env=ENV).strip()
        except subprocess.CalledProcessError as err:
            # This used to be a bare `except: return`, so every failure here
            # produced no output at all: no id, no error, no hint. Whatever
            # went wrong, the user saw an empty prompt come back.
            detail = (err.stderr or b"").decode("utf-8", "replace").strip()
            Logger.error("Could not read the Android ID from the container.")
            if detail:
                Logger.error(detail)
            return

        if not android_id:
            Logger.error(
                "No Android ID found. gservices.db exists only once Google "
                "Play Services or microG has been installed and has run at "
                "least once. Install one, open the Play Store, then try again.")
            return

        print(android_id)
        print("   ^----- Open {}".format(REGISTER_URL))
        print("          Log in with your Google account and submit the ID above.")
        print("          Give Google a few minutes, then restart Waydroid.")
