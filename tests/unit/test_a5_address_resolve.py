# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-05: IMP-0008 -- UT-SPC-05."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.address import resolve_address


def test_resolve_address_separates_resolution_from_application():
    """UT-SPC-05: `resolve_address` returns structure only -- no bytes
    touched, unlike `apply_override`."""
    resolved = resolve_address("egoDyn.vx", stage="vdy", where="<test>")
    assert resolved.stage == "vdy"
    assert resolved.port == "egoDyn"
    assert resolved.path == ("vx",)
    assert resolved.index is None
    assert resolved.all_elements is False


def test_resolve_address_bare_port():
    resolved = resolve_address("outputs", stage="aeb", where="<test>")
    assert resolved.port == "outputs"
    assert resolved.path == ()


def test_resolve_address_indexed_element():
    resolved = resolve_address("objects.list[3]", stage="fusion", where="<test>")
    assert resolved.path == ("list",)
    assert resolved.index == 3
    assert resolved.all_elements is False


def test_resolve_address_wildcard_becomes_all_elements_with_no_index():
    resolved = resolve_address("objects.list[*]", stage="fusion", where="<test>")
    assert resolved.index is None
    assert resolved.all_elements is True


def test_resolve_address_deep_field_path_with_no_mid_path_index():
    resolved = resolve_address("objects.list.speed", stage="fusion", where="<test>")
    assert resolved.path == ("list", "speed")
    assert resolved.index is None


def test_resolve_address_refuses_a_non_final_indexed_segment_rather_than_dropping_it():
    """A mid-path index (`objects.list[2].speed`) is real in `apply_override`'s
    own grammar but not representable in the flat `{path[], index}` shape --
    refused, naming the address, never silently dropped (R-SIM-25)."""
    with pytest.raises(AuthoringError):
        resolve_address("objects.list[2].speed", stage="fusion", where="<test>")
