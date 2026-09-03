"""Built-in expiry dates compiled into proprietary translation layers.

libhoudini is Intel's binary translator and carries a hard expiry inside the
binary: the symbol `ibt_get_expire_date` and a timestamp constant. Once the
host clock passes that timestamp, ARM apps stop launching — they hang at the
splash screen, or the process disappears seconds after start — while Waydroid
itself and x86 apps keep working normally. Nothing in the logs points at the
translation layer, which is what makes it so hard to recognise.

Detection is by exact constant, never by scanning for anything date-shaped.
That distinction is the whole design:

  - A range scan for any plausible timestamp over lib64/libhoudini.so returns
    more than 46,000 candidates in a 9 MB file. Pure noise, useless as a check.
  - Looking for a *known* value has a measured false positive rate of zero:
    none of 40 random timestamps drawn from the same period appears anywhere
    in that binary, while the known constant appears exactly twice.

So this module can only report expiries somebody has already identified. It
does not, and cannot, discover new ones. When a new build starts failing on a
date boundary, the constant has to be found by hand and added below.
"""
import datetime
import struct

# Timestamp -> where it came from. Values are seconds since the Unix epoch.
KNOWN_EXPIRY = {
    # Confirmed in prebuilts/lib64/libhoudini.so of the supremegamers Android
    # 13 build this project installs: present exactly twice, as both a uint32
    # and a uint64, against a zero noise floor. The 32-bit library in the same
    # archive does not contain it.
    #
    # Independently identified by the reporter of upstream #285 in a different
    # libhoudini build (hpe-14, extracted from a Google Play Games image), who
    # confirmed the behaviour by moving the host clock back across the date and
    # watching ARM apps start working again.
    1788134400: "libhoudini (supremegamers A13 build, and hpe-14)",
}


def expiry_timestamps_in(path):
    """Known expiry timestamps present in the binary at `path`, ascending.

    Matches both 32-bit and 64-bit little-endian encodings: the constant is
    stored as a time_t and the width varies with the build.
    """
    try:
        with open(path, "rb") as binary:
            blob = binary.read()
    except OSError:
        return []

    found = [timestamp for timestamp in KNOWN_EXPIRY
             if struct.pack("<I", timestamp) in blob
             or struct.pack("<Q", timestamp) in blob]
    return sorted(found)


def expired_timestamps_in(path, now=None):
    """Those of the above that the clock has already passed."""
    now = now if now is not None else datetime.datetime.now(datetime.timezone.utc)
    cutoff = now.timestamp()
    return [timestamp for timestamp in expiry_timestamps_in(path)
            if timestamp <= cutoff]


def describe(timestamp):
    """Human-readable UTC date for a timestamp, for use in messages."""
    moment = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M UTC")
