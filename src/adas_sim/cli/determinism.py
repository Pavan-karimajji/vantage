# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`sim determinism <run-a> <run-b>` -- `S-C6` (`R-SIM-24`). Argument parsing
only (`GT-9`); the real logic is `core.determinism`. Deliberately has **no**
`--axis` flag: the axis is always derived from the two runs' own manifests --
a flag can lie, and "cross-machine verified" claimed from a pair that also
rebuilt the binary is the standard cheat this refuses."""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.determinism import AXIS_LABELS, compare_exact, compare_with_tolerance, derive_axis
from adas_sim.core.tolerance import ToleranceSet, load_tolerance
from adas_sim.io.registry import reader_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim determinism", description=__doc__)
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    parser.add_argument(
        "--tolerance", type=Path, default=None,
        help="modules/<name>/sim/tolerance.yaml -- consulted only on the two MEASURED axes "
             "(rebuilt binary, different machine); absent means default: exact everywhere",
    )
    parser.add_argument("--component", default="", help="component name the tolerance file belongs to (report only)")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    reader_a = reader_for(args.run_a)
    reader_b = reader_for(args.run_b)
    try:
        result = derive_axis(reader_a.meta(), reader_b.meta())

        if result.axis is None:
            print(f"axis: NEITHER -- differs in more than one dimension: {', '.join(result.differing_dimensions)}")
            return 1
        print(f"axis: {AXIS_LABELS[result.axis]}")

        if result.axis in ("same_process", "fresh_process"):
            divergence = compare_exact(reader_a, reader_b)
            if divergence is not None:
                print(f"FAIL at tick {divergence.tick_index}, topic '{divergence.topic}': {divergence.detail}")
                return 1
            print("PASS -- byte-identical port payloads (no tolerance field exists on this axis)")
            return 0

        tolerance = (
            load_tolerance(args.tolerance, component=args.component)
            if args.tolerance is not None
            else ToleranceSet(component=args.component, rows=(), sha256="")
        )
        divergences, headroom = compare_with_tolerance(reader_a, reader_b, tolerance)
        if divergences:
            first = divergences[0]
            print(
                f"FAIL ({len(divergences)} divergence(s)); first at tick {first.tick_index}, "
                f"topic '{first.topic}' field '{first.field}': {first.detail}"
            )
            return 1
        print(f"PASS -- within tolerance (tolerance.yaml={tolerance.sha256 or '(none, default: exact)'}, "
              f"worst headroom consumed: {headroom:.1%})")
        if headroom > 0.5:
            print("WARNING: headroom above 50% on a PASS -- fix now, before this becomes a red build "
                  "'fixed' by widening the bound further (OD-10)")
        return 0
    finally:
        reader_a.close()
        reader_b.close()
