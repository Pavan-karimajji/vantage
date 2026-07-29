# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The six-check palette validator (sim_visualization_spec.md §3.4), runnable
as `python -m adas_sim.render.palette_check`. Ported from this session's own
data-visualization design-system skill's `validate_palette.py` (its color
math and thresholds are the standard this framework's own tokens are held
to, not re-derived here) plus one addition specific to this project: any
categorical pair landing in the 6-8 ΔE floor band must have a **named**
secondary encoding recorded in `render/theme.py`'s table, or it fails rather
than merely warns -- "assumed" is not "named" (`sim_visualization_spec.md`
§3.4's own acceptance criterion).

This is a computable check, so it is computed, not argued.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence

from adas_sim.core.console import reconfigure_console_utf8
from adas_sim.render.theme import CATEGORICAL_SETS, THEMES, Theme, resolve

# ── thresholds (identical to the data-viz skill's validator) ────────────────
BAND = {"light": (0.43, 0.77), "dark": (0.48, 0.67)}  # OKLCH L
CHROMA_FLOOR = 0.10  # OKLCH C
# ΔE is Euclidean distance in OKLab ×100, calibrated to the
# Machado-Oliveira-Fernandes (2009) severity-1.0 simulation below.
CVD_TARGET, CVD_FLOOR = 8.0, 6.0
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0
DEFAULT_SURFACE = {"light": "#fcfcfb", "dark": "#1a1a19"}

MACHADO = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _hex2srgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _s2lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin(h: str) -> tuple[float, float, float]:
    return tuple(_s2lin(c) for c in _hex2srgb(h))  # type: ignore[return-value]


def _relative_luminance(h: str) -> float:
    r, g, b = _lin(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(h1: str, h2: str) -> float:
    a, b = sorted((_relative_luminance(h1), _relative_luminance(h2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _lin2oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    big_l = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return big_l, a, bb


def oklch(h: str) -> tuple[float, float]:
    big_l, a, bb = _lin2oklab(*_lin(h))
    return big_l, math.hypot(a, bb)


def _simulate(h: str, kind: str) -> tuple[float, float, float]:
    r, g, b = _lin(h)
    m = MACHADO[kind]
    return tuple(max(0.0, min(1.0, m[row][0] * r + m[row][1] * g + m[row][2] * b)) for row in range(3))  # type: ignore[return-value]


def delta_e(h1: str, h2: str, kind: str | None = None) -> float:
    """Euclidean distance in OKLab, ×100. `kind=None` -> unsimulated vision."""
    a = _lin2oklab(*(_simulate(h1, kind) if kind else _lin(h1)))
    b = _lin2oklab(*(_simulate(h2, kind) if kind else _lin(h2)))
    return 100 * math.dist(a, b)


def validate(palette: Sequence[str], mode: str, surface: str) -> tuple[list[tuple[str, object, str]], bool]:
    """The five checks measurable from color alone (numbered per
    sim_visualization_spec.md §3.4): lightness band, chroma floor, CVD
    separation, the normal-vision floor, and contrast vs. surface."""
    lo, hi = BAND[mode]
    report: list[tuple[str, object, str]] = []
    ok = True

    offband = [(c, round(oklch(c)[0], 3)) for c in palette if not (lo <= oklch(c)[0] <= hi)]
    if offband:
        ok = False
    report.append(("Lightness band", not offband,
                    f"all {len(palette)} inside L {lo}-{hi}" if not offband else f"outside band: {offband}"))

    lowc = [(c, round(oklch(c)[1], 3)) for c in palette if oklch(c)[1] < CHROMA_FLOOR]
    if lowc:
        ok = False
    report.append(("Chroma floor", not lowc,
                    f"all {len(palette)} >= {CHROMA_FLOOR}" if not lowc else f"below floor (reads gray): {lowc}"))

    n = len(palette)
    pairlist = [(i, i + 1) for i in range(n - 1)]
    worst = None
    for kind in ("protan", "deutan"):
        for i, j in pairlist:
            d = delta_e(palette[i], palette[j], kind)
            if worst is None or d < worst[0]:
                worst = (d, kind, palette[i], palette[j])
    wd = worst[0] if worst else 99.0
    cvd_state = "pass" if wd >= CVD_TARGET else ("floor" if wd >= CVD_FLOOR else "fail")
    if cvd_state == "fail":
        ok = False
    report.append(("CVD separation", cvd_state,
                    f"worst adjacent {worst[3]}<->{worst[2]} dE {wd:.1f} ({worst[1]})" if worst else "n/a"))

    nworst = None
    for i, j in pairlist:
        d = delta_e(palette[i], palette[j])
        if nworst is None or d < nworst[0]:
            nworst = (d, palette[i], palette[j])
    nd = nworst[0] if nworst else 99.0
    normal_state = "pass" if nd >= NORMAL_FLOOR else "fail"
    if normal_state == "fail":
        ok = False
    report.append(("Normal-vision floor", normal_state,
                    f"worst adjacent {nworst[2]}<->{nworst[1]} dE {nd:.1f}" if nworst else "n/a"))

    low = [(c, round(contrast(c, surface), 2)) for c in palette if contrast(c, surface) < CONTRAST_MIN]
    report.append(("Contrast vs surface", "pass" if not low else "relief",
                    f"all {len(palette)} >= {CONTRAST_MIN}:1" if not low else f"below {CONTRAST_MIN}:1: {low}"))

    return report, ok


def check_named_secondary_encoding(set_name: str, tokens: Sequence[str], theme: Theme) -> tuple[str, bool, str]:
    """The one addition beyond the generic validator: a pair in the 6-8 ΔE
    floor band is legal only because it **already** carries a secondary
    encoding, named in `render/theme.py` -- never assumed
    (sim_visualization_spec.md §3.4). Checked whenever any pair in `tokens`
    lands in that band, under either CVD-simulated vision."""
    styles = [resolve(token, theme) for token in tokens]
    hexes = [s.color for s in styles]
    unnamed = []
    for i in range(len(hexes) - 1):
        worst_pair = min(
            (delta_e(hexes[i], hexes[i + 1], kind) for kind in ("protan", "deutan")), default=99.0
        )
        if CVD_FLOOR <= worst_pair < CVD_TARGET:
            for idx in (i, i + 1):
                if styles[idx].secondary_encoding is None:
                    unnamed.append(tokens[idx])
    ok = not unnamed
    detail = (f"every 6-8 floor-band token in {set_name!r} carries a named secondary encoding" if ok
              else f"missing a named secondary encoding: {sorted(set(unnamed))}")
    return f"Named secondary encoding ({set_name})", ok, detail


def check_theme(theme: Theme) -> tuple[list[tuple[str, object, str]], bool]:
    surface = DEFAULT_SURFACE[theme] if theme in DEFAULT_SURFACE else DEFAULT_SURFACE["light"]
    report: list[tuple[str, object, str]] = []
    ok = True
    mode = theme if theme in BAND else "light"
    for set_name, tokens in CATEGORICAL_SETS.items():
        hexes = [resolve(token, theme).color for token in tokens]
        set_report, set_ok = validate(hexes, mode, surface)
        report.extend((f"{name} ({set_name})", state, detail) for name, state, detail in set_report)
        ok = ok and set_ok
        name, enc_ok, detail = check_named_secondary_encoding(set_name, tokens, theme)
        report.append((name, enc_ok, detail))
        ok = ok and enc_ok
    return report, ok


def main(argv: list[str] | None = None) -> int:
    reconfigure_console_utf8()
    overall_ok = True
    for theme in ("dark", "light"):
        report, ok = check_theme(theme)  # type: ignore[arg-type]
        overall_ok = overall_ok and ok
        print(f"\ntheme={theme}")
        for name, state, detail in report:
            glyph = "PASS" if state in (True, "pass") else "WARN" if state in ("floor", "relief") else "FAIL"
            print(f"  [{glyph:4}] {name:38} {detail}")
    print(f"\n{'ALL CHECKS PASS' if overall_ok else 'FAILED -- fix the marked checks'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
