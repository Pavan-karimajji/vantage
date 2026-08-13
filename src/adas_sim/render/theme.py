# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The token table for `dark`/`light`/`print`/`forced` (sim_implementation_plan.md
S-A3, sim_visualization_spec.md §3). A layer provider writes `style="zone.entry"`
and never a colour (`R-SIM-2`); this module is the **one place** a hex literal
is legal in the whole framework -- everywhere else, `_HEX_STYLE` in
`scene/types.py` refuses one on sight.

**Scope: the framework-owned namespaces only** (`frame.* ego.* object.*
status.* sensor.* truth.* measure.*`, sim_visualization_spec.md §3.2). A
component's own `<fn>.*` tokens are that component's own data, registered
from its own `modules/<name>/sim/` at `S-B1` -- this module must never
contain a function name (`R-SIM-1`).

**Colour provenance.** `object.classification.*`'s five hues and
`status.good/warning/serious/critical`'s four are the validated categorical
and status steps from this session's own data-visualization reference
palette, reused verbatim (already cleared every adjacent-pairlist gate in
both `dark` and `light`, `render/palette_check.py` re-confirms it here
rather than re-deriving it). Every other token is a single, non-categorical
role (an axis, a body fill, a ruler) and is not subject to the six-check
validator's pairwise gates -- only `render/palette_check.py`'s categorical
sets are (`sim_visualization_spec.md` §3.4: "every **categorical set**").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from adas_sim.diagnostics.errors import AuthoringError

Theme = Literal["dark", "light", "print", "forced"]
THEMES: tuple[Theme, ...] = ("dark", "light", "print", "forced")


@dataclass(frozen=True, slots=True)
class TokenStyle:
    #: The one place a colour literal is legal.
    color: str
    hatch: str | None = None
    marker: str | None = None
    #: Filled in whenever this token's worst pairing within its categorical
    #: set lands in the 6-8 ΔE floor band -- states, in words, what makes
    #: that legal (a hatch, a marker, a mandatory label). Never assumed.
    secondary_encoding: str | None = None

    def __repr__(self) -> str:
        return f"<TokenStyle color={self.color!r}>"


# ---------------------------------------------------------------------------
# object.classification.* -- session's reference palette, categorical slots
# 1/2/3/4/5 (blue/orange/aqua/yellow/magenta), adjacent-pairlist validated in
# both dark and light (references/palette.md, this session's data-viz work).
# ---------------------------------------------------------------------------
_CLASSIFICATION_LIGHT = {
    "car": "#2a78d6", "truck": "#eb6834", "two_wheeler": "#1baf7a",
    "pedestrian": "#eda100", "unknown": "#e87ba4",
}
_CLASSIFICATION_DARK = {
    "car": "#3987e5", "truck": "#d95926", "two_wheeler": "#199e70",
    "pedestrian": "#c98500", "unknown": "#d55181",
}
#: Slots 4 (pedestrian) and 5 (unknown) sit in the 6-8 floor band against
#: their neighbour on at least one surface -- legal because every object
#: already carries a text label in the layer that draws it (S-B1).
_CLASSIFICATION_SECONDARY = "paired with the object's text label (always drawn)"

# ---------------------------------------------------------------------------
# status.* -- reference palette's fixed status steps, theme-invariant by
# design (a warning looks the same whichever function raised it).
# ---------------------------------------------------------------------------
_STATUS_FIXED = {
    "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
    "inactive": "#8a8781", "unknown": "#52514e",
}
_STATUS_SECONDARY = "paired with an icon and a text label (never colour alone, sim_visualization_spec.md §3.2)"


def _classification_tokens(colors: dict[str, str]) -> dict[str, TokenStyle]:
    return {
        f"object.classification.{name}": TokenStyle(color=hex_, secondary_encoding=_CLASSIFICATION_SECONDARY)
        for name, hex_ in colors.items()
    }


def _status_tokens() -> dict[str, TokenStyle]:
    return {
        f"status.{name}": TokenStyle(color=hex_, secondary_encoding=_STATUS_SECONDARY)
        for name, hex_ in _STATUS_FIXED.items()
    }


def _build_dark() -> dict[str, TokenStyle]:
    return {
        "frame.origin": TokenStyle(color="#ffffff"),
        "frame.axis": TokenStyle(color="#c3c2b7"),
        "frame.grid": TokenStyle(color="#2c2c2a"),
        "frame.grid_label": TokenStyle(color="#898781"),
        "frame.scale_legend": TokenStyle(color="#c3c2b7"),
        "ego.body": TokenStyle(color="#c9d6e3"),
        "ego.body_edge": TokenStyle(color="#33475b"),
        "ego.rear_axle": TokenStyle(color="#ffffff"),
        "ego.wheel": TokenStyle(color="#0d0d0d"),
        "ego.mirror": TokenStyle(color="#8a8781"),
        "object.default": TokenStyle(color="#c3c2b7"),
        "object.selected": TokenStyle(color="#ffffff"),
        "object.ghost": TokenStyle(color="#52514e"),
        "object.assumed_geometry": TokenStyle(color="#898781", hatch="xx"),
        "object.label": TokenStyle(color="#ffffff"),
        **_classification_tokens(_CLASSIFICATION_DARK),
        **_status_tokens(),
        "sensor.fov": TokenStyle(color="#3987e5"),
        "sensor.range_ring": TokenStyle(color="#52514e"),
        "sensor.blind": TokenStyle(color="#383835", hatch="xx"),
        "sensor.housing": TokenStyle(color="#898781"),
        "truth.body": TokenStyle(color="#199e70"),
        "truth.track": TokenStyle(color="#199e70"),
        "truth.trace": TokenStyle(color="#199e70"),
        "measure.ruler": TokenStyle(color="#ffffff"),
        "measure.cursor": TokenStyle(color="#ffffff"),
        "measure.annotation": TokenStyle(color="#c3c2b7"),
    }


def _build_light() -> dict[str, TokenStyle]:
    return {
        "frame.origin": TokenStyle(color="#0b0b0b"),
        "frame.axis": TokenStyle(color="#52514e"),
        "frame.grid": TokenStyle(color="#e1e0d9"),
        "frame.grid_label": TokenStyle(color="#898781"),
        "frame.scale_legend": TokenStyle(color="#52514e"),
        "ego.body": TokenStyle(color="#c9d6e3"),
        "ego.body_edge": TokenStyle(color="#33475b"),
        "ego.rear_axle": TokenStyle(color="#0b0b0b"),
        "ego.wheel": TokenStyle(color="#333333"),
        "ego.mirror": TokenStyle(color="#898781"),
        "object.default": TokenStyle(color="#52514e"),
        "object.selected": TokenStyle(color="#0b0b0b"),
        "object.ghost": TokenStyle(color="#c3c2b7"),
        "object.assumed_geometry": TokenStyle(color="#898781", hatch="xx"),
        "object.label": TokenStyle(color="#0b0b0b"),
        **_classification_tokens(_CLASSIFICATION_LIGHT),
        **_status_tokens(),
        "sensor.fov": TokenStyle(color="#2a78d6"),
        "sensor.range_ring": TokenStyle(color="#898781"),
        "sensor.blind": TokenStyle(color="#e1e0d9", hatch="xx"),
        "sensor.housing": TokenStyle(color="#52514e"),
        "truth.body": TokenStyle(color="#1baf7a"),
        "truth.track": TokenStyle(color="#1baf7a"),
        "truth.trace": TokenStyle(color="#1baf7a"),
        "measure.ruler": TokenStyle(color="#0b0b0b"),
        "measure.cursor": TokenStyle(color="#0b0b0b"),
        "measure.annotation": TokenStyle(color="#52514e"),
    }


def _build_print() -> dict[str, TokenStyle]:
    # White surface, higher contrast, hatches on every fill (sim_visualization_spec.md §3.3).
    base = _build_light()
    return {
        name: (style if style.hatch else TokenStyle(color=style.color, hatch="//", marker=style.marker,
                                                      secondary_encoding=style.secondary_encoding))
        for name, style in base.items()
    }


def _build_forced() -> dict[str, TokenStyle]:
    # High-contrast, texture-first (sim_visualization_spec.md §3.3): every
    # non-neutral role collapses to black/white, distinguished by hatch/marker.
    return {
        name: TokenStyle(
            color="#000000" if name not in ("frame.origin", "measure.ruler", "measure.cursor") else "#ffffff",
            hatch="//" if "assumed" in name or "blind" in name else style.hatch,
            marker=style.marker,
            secondary_encoding=style.secondary_encoding or "forced-colors: shape/label only, never hue",
        )
        for name, style in _build_light().items()
    }


_TABLE: dict[Theme, dict[str, TokenStyle]] = {
    "dark": _build_dark(),
    "light": _build_light(),
    "print": _build_print(),
    "forced": _build_forced(),
}

#: object.classification.* validated adjacent (order matters: this is the
#: order slots were validated in, sim_visualization_spec.md §3.4).
#:
#: **`status.*` is deliberately not a gated categorical set here.**
#: sim_visualization_spec.md §3.4 names three examples needing the six-check
#: gate -- "object classifications, function namespaces, timeline signal
#: lanes" -- and status is not one of them: it is validated by convention
#: (contrast vs. surface, distinctness from the categorical slots) in the
#: reference palette this session's colours are drawn from, never by the
#: OKLCH lightness-band/chroma-floor/CVD-pairwise gate, which is tuned for a
#: themed data series, not a fixed four-step alert convention.
CATEGORICAL_SETS: dict[str, tuple[str, ...]] = {
    "object.classification": tuple(f"object.classification.{name}" for name in _CLASSIFICATION_LIGHT),
}


#: Component-registered tokens (`<fn>.*`, a driving function's own namespaced
#: style tokens, sim_visualization_spec.md §3.2), discovered
#: **by import** the same way `scene/registry.py`'s layer providers are
#: (`R-VAR-2`): a component's own `sim/layers/<fn>.py` calls
#: `register_component_token` at import time. Kept separate from `_TABLE`
#: (the framework's own static set) so this module never has to hardcode a
#: function's name to know its tokens exist (`GT-1`).
_COMPONENT_TOKENS: dict[Theme, dict[str, TokenStyle]] = {theme: {} for theme in THEMES}


def register_component_token(token: str, styles: Mapping[Theme, TokenStyle]) -> None:
    """Registers one `<fn>.*` token with its appearance in every theme it
    supplies. A duplicate registration overwrites -- component modules are
    expected to be imported once; re-importing re-declares the same data."""
    missing = set(THEMES) - set(styles)
    if missing:
        raise AuthoringError(
            expected=f"a style for every theme {THEMES}", found=f"missing {sorted(missing)}",
            where=f"adas_sim.render.theme.register_component_token({token!r})",
            hint="every token must resolve in all four themes (UT-A3-5)",
        )
    for theme, style in styles.items():
        _COMPONENT_TOKENS[theme][token] = style


def resolve(token: str, theme: Theme) -> TokenStyle:
    """No silent default colour (`UT-A3-4`): an unregistered token raises,
    naming the theme and a few registered tokens to search from. Checks the
    framework's own static table first, then component-registered tokens."""
    table = _TABLE.get(theme)
    if table is None:
        raise AuthoringError(
            expected=f"one of {THEMES}", found=repr(theme),
            where="adas_sim.render.theme.resolve", hint="",
        )
    style = table.get(token) or _COMPONENT_TOKENS[theme].get(token)
    if style is None:
        known = sorted(table)[:5] + sorted(_COMPONENT_TOKENS[theme])[:5]
        raise AuthoringError(
            expected="a registered style token", found=repr(token),
            where=f"adas_sim.render.theme (theme={theme!r})",
            hint=f"did you mean one of: {known}... ({len(table) + len(_COMPONENT_TOKENS[theme])} registered)",
        )
    return style


def all_tokens() -> frozenset[str]:
    return frozenset(_TABLE["dark"])
