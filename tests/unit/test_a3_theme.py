# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 `render/theme.py` tests: UT-A3-4, UT-A3-5 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.render.theme import THEMES, all_tokens, resolve


def test_unknown_style_token_raises_no_silent_default_colour():
    """UT-A3-4: a silent default is how a debug layer ends up looking
    authoritative."""
    with pytest.raises(AuthoringError):
        resolve("not.a.registered.token", "dark")


def test_every_token_resolves_in_all_four_themes():
    """UT-A3-5."""
    tokens = all_tokens()
    assert tokens, "expected at least one registered token"
    for token in tokens:
        for theme in THEMES:
            style = resolve(token, theme)
            assert style.color.startswith("#")
