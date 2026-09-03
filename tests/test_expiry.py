"""Detecting the expiry compiled into libhoudini.

Upstream #285. libhoudini carries a timestamp inside the binary and stops
translating once the host clock passes it: ARM apps hang at the splash screen
or vanish seconds after launch, while Waydroid and x86 apps are unaffected and
nothing in the logs mentions the translator. The reporter proved it by moving
the host clock back across the date and watching the apps work again.

The design point these tests protect is that detection is by *known* constant.
A range scan for anything timestamp-shaped finds over 46,000 candidates in the
9 MB library; looking for a value somebody has already identified finds it
against a zero noise floor.
"""
import datetime
import struct

import pytest

from tools import expiry

# 2026-08-31 00:00:00 UTC, confirmed present twice in the lib64 library of the
# Android 13 build this project installs.
HOUDINI_EXPIRY = 1788134400
BEFORE = datetime.datetime(2026, 8, 30, tzinfo=datetime.timezone.utc)
AFTER = datetime.datetime(2026, 9, 3, tzinfo=datetime.timezone.utc)


def write_binary(tmp_path, *values, width="<I", padding=4096):
    """A file with some constants buried in filler, like a real library."""
    blob = bytearray(b"\x7fELF" + b"\x00" * padding)
    for value in values:
        blob += struct.pack(width, value) + b"\x00" * 128
    target = tmp_path / "libhoudini.so"
    target.write_bytes(bytes(blob))
    return str(target)


def test_finds_a_known_constant_stored_as_uint32(tmp_path):
    path = write_binary(tmp_path, HOUDINI_EXPIRY, width="<I")
    assert expiry.expiry_timestamps_in(path) == [HOUDINI_EXPIRY]


def test_finds_a_known_constant_stored_as_uint64(tmp_path):
    """The width varies with the build, so both encodings have to match."""
    path = write_binary(tmp_path, HOUDINI_EXPIRY, width="<Q")
    assert expiry.expiry_timestamps_in(path) == [HOUDINI_EXPIRY]


def test_finds_nothing_in_a_binary_without_the_constant(tmp_path):
    path = write_binary(tmp_path, 1234567890, 1600000000)
    assert expiry.expiry_timestamps_in(path) == []


def test_unrelated_timestamps_are_not_reported(tmp_path):
    """The measured property this whole approach rests on: a nearby date that
    is not a known marker must not trip the check. Anything looser would fire
    constantly — a range scan finds 46,000 candidates in the real library."""
    neighbours = [HOUDINI_EXPIRY - 86400, HOUDINI_EXPIRY + 86400,
                  HOUDINI_EXPIRY - 1, HOUDINI_EXPIRY + 1]
    path = write_binary(tmp_path, *neighbours)
    assert expiry.expiry_timestamps_in(path) == []


def test_missing_file_is_not_an_error(tmp_path):
    """A build without a 32-bit library is normal; the caller checks both."""
    assert expiry.expiry_timestamps_in(str(tmp_path / "absent.so")) == []


def test_expired_only_reports_dates_the_clock_has_passed(tmp_path):
    path = write_binary(tmp_path, HOUDINI_EXPIRY)
    assert expiry.expired_timestamps_in(path, now=BEFORE) == []
    assert expiry.expired_timestamps_in(path, now=AFTER) == [HOUDINI_EXPIRY]


def test_the_boundary_counts_as_expired(tmp_path):
    path = write_binary(tmp_path, HOUDINI_EXPIRY)
    exactly = datetime.datetime.fromtimestamp(HOUDINI_EXPIRY,
                                              datetime.timezone.utc)
    assert expiry.expired_timestamps_in(path, now=exactly) == [HOUDINI_EXPIRY]


def test_describe_is_readable_and_utc():
    assert expiry.describe(HOUDINI_EXPIRY) == "2026-08-31 00:00 UTC"


def test_the_table_documents_where_each_value_came_from():
    """A bare list of magic numbers would be unmaintainable: whoever adds the
    next one needs to know how this one was established."""
    assert HOUDINI_EXPIRY in expiry.KNOWN_EXPIRY
    for timestamp, provenance in expiry.KNOWN_EXPIRY.items():
        assert isinstance(timestamp, int)
        assert provenance and "libhoudini" in provenance
