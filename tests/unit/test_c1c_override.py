# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c override tests: UT-C1c-17 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.config.override import Override, OverrideVerb, parse_override_verb
from adas_sim.diagnostics.errors import AuthoringError


def test_const_returns_its_value_regardless_of_current_or_first():
    """UT-C1c-17."""
    override = Override(verb=OverrideVerb.CONST, value=10.0)
    assert override.apply(current=1.0, first=2.0) == 10.0


def test_hold_returns_first_regardless_of_current_and_needs_no_value():
    """UT-C1c-17."""
    override = Override(verb=OverrideVerb.HOLD)  # must not raise: hold needs no value:
    assert override.apply(current=99.0, first=3.5) == 3.5


def test_offset_adds_to_current():
    """UT-C1c-17."""
    override = Override(verb=OverrideVerb.OFFSET, value=2.5)
    assert override.apply(current=10.0, first=0.0) == 12.5


def test_scale_multiplies_current():
    """UT-C1c-17."""
    override = Override(verb=OverrideVerb.SCALE, value=1.5)
    assert override.apply(current=10.0, first=0.0) == 15.0


@pytest.mark.parametrize("verb", [OverrideVerb.CONST, OverrideVerb.OFFSET, OverrideVerb.SCALE])
def test_a_value_requiring_verb_without_a_value_raises(verb):
    """UT-C1c-17: only `hold` may omit value:."""
    with pytest.raises(AuthoringError):
        Override(verb=verb)


def test_parse_override_verb_accepts_every_closed_member():
    """UT-C1c-17."""
    for verb in OverrideVerb:
        assert parse_override_verb(verb.value, where="test") == verb


def test_parse_override_verb_outside_the_closed_four_is_a_load_error_not_a_warning():
    """UT-C1c-17 / UT-D6-1: a verb outside the closed four is an
    `AuthoringError` (`R-SIM-15`) -- never a silently-accepted extension
    point."""
    with pytest.raises(AuthoringError) as excinfo:
        parse_override_verb("interpolate", where="stage 'df' overrides 'egoDyn.vx'")
    message = str(excinfo.value)
    assert "interpolate" in message
    assert "const" in message and "hold" in message and "offset" in message and "scale" in message
