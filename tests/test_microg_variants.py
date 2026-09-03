"""Every microG variant must carry both a URL and an md5.

The bug this guards (upstream #273): two entries were written as

    "Minimal": [
        "https://…MinMicroG-Minimal-….zip"      <- no comma
        "afb87eb64e7749cfd72c4760d85849da"
    ],

Python concatenates adjacent string literals, so the list held a single
element: the URL with the md5 glued onto its end. Two failures for the price
of one — `dl_links[variant][1]` raised IndexError, and had it not, the
download would have gone to a URL that does not exist.

A missing comma inside a list of lists is invisible on review, so this test
checks the shape rather than the punctuation.
"""
import re

import pytest

from stuff.microg import MicroG

MD5 = re.compile(r"^[0-9a-f]{32}$")

VARIANTS = sorted(MicroG.dl_links)


def test_all_variants_are_covered():
    """Fails loudly if a variant is added or renamed without updating here."""
    assert VARIANTS == ["Minimal", "MinimalIAP", "NoGoolag", "Standard", "UNLP"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_has_a_url_and_a_checksum(variant):
    entry = MicroG.dl_links[variant]
    assert len(entry) == 2, (
        f"{variant} has {len(entry)} element(s); a missing comma between two "
        f"string literals silently concatenates them into one")
    url, md5 = entry
    assert url.startswith("https://")
    assert url.endswith(".zip"), (
        f"{variant}'s URL ends with {url[-40:]!r}; an md5 glued to the end is "
        f"what a missing comma looks like")
    assert MD5.match(md5), f"{variant}'s checksum is not an md5: {md5!r}"


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_constructs(variant):
    """The reported symptom: MicroG(..., 'Minimal') raised IndexError."""
    micro_g = MicroG("13", variant)
    assert micro_g.dl_link.endswith(".zip")
    assert MD5.match(micro_g.act_md5)


def test_checksums_are_distinct():
    """A copy-paste that duplicates a checksum would pass every check above."""
    checksums = [entry[1] for entry in MicroG.dl_links.values()]
    assert len(set(checksums)) == len(checksums)
