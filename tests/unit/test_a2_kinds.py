# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0150/IMP-0398 -- UT-CFG-03, UT-CFG-18, INSP-SW-02."""

from __future__ import annotations

import pytest

from adas_sim.config.kinds import (
    KIND_KEYS,
    FileKind,
    check_composition_no_cross_unit_reference,
    check_disjoint_keys,
)
from adas_sim.diagnostics.errors import AuthoringError


def test_kind_keys_are_pairwise_disjoint():
    """INSP-SW-02: no two kinds may declare the same key (`version` is the
    one deliberate exception, owned by every kind alike)."""
    seen: dict[str, FileKind] = {}
    for kind, keys in KIND_KEYS.items():
        for key in keys - {"version"}:
            assert key not in seen, f"{key!r} declared by both {seen.get(key)} and {kind}"
            seen[key] = kind


@pytest.mark.parametrize("kind", list(FileKind))
def test_a_key_of_each_kind_placed_in_each_other_kind_is_refused(kind):
    """UT-CFG-03: place a key of each kind in each of the other three files."""
    own_only_key = next(iter(KIND_KEYS[kind] - {"version"}))
    for other in FileKind:
        if other is kind:
            continue
        raw = {"version": 1, own_only_key: "anything"}
        with pytest.raises(AuthoringError):
            check_disjoint_keys(other, raw, where="<test>")


def test_a_kinds_own_keys_are_accepted():
    raw = {"version": 1, "units": []}
    check_disjoint_keys(FileKind.COMPOSITION, raw, where="<test>")  # no raise


def test_composition_naming_another_unit_is_refused():
    """UT-CFG-18: author a composition file naming another unit."""
    raw = {
        "version": 1,
        "units": [
            {"name": "aeb", "impl": "dll:aeb", "ports": ["outputs"]},
            {"name": "bsd", "impl": "dll:bsd", "ports": ["aeb"]},  # names the other unit
        ],
    }
    with pytest.raises(AuthoringError):
        check_composition_no_cross_unit_reference(raw, where="<test>")


def test_composition_naming_no_other_unit_is_accepted():
    raw = {
        "version": 1,
        "units": [
            {"name": "aeb", "impl": "dll:aeb", "ports": ["outputs"]},
            {"name": "bsd", "impl": "dll:bsd", "ports": ["outputs"]},
        ],
    }
    check_composition_no_cross_unit_reference(raw, where="<test>")  # no raise
