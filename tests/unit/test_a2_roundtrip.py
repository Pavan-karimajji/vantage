# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0155 -- UT-CFG-08."""

from __future__ import annotations

from adas_sim.config.roundtrip import round_trip

_FIXTURE = (
    "# a leading comment\n"
    "version: 1\n"
    'name: "quoted value"   # inline comment\n'
    "list:\n"
    "  - a\n"
    "  - b\n"
    "nested:\n"
    "  key: value  # nested comment\n"
    "unquoted: bare\n"
)


def test_read_each_file_and_write_it_back_unchanged(tmp_path):
    """UT-CFG-08: read each file and write it back unchanged; compare
    bytes, comments and key order."""
    path = tmp_path / "fixture.yaml"
    path.write_bytes(_FIXTURE.encode("utf-8"))

    result = round_trip(path)

    assert result == _FIXTURE.encode("utf-8")


def test_key_order_is_preserved(tmp_path):
    path = tmp_path / "ordered.yaml"
    path.write_text("z: 1\na: 2\nm: 3\n", encoding="utf-8")

    result = round_trip(path).decode("utf-8")

    assert result.index("z:") < result.index("a:") < result.index("m:")
