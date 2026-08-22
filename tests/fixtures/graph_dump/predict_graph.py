# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IT-10`'s configuration-layer half (`IMP-0131`, `WP-15`): reads a
Resolved Run Spec JSON file -- the SAME file the C++ engine loads via
`simcore::LoadRunSpec` -- and independently predicts the stage/port graph
the engine SHOULD construct from it, in the identical line-oriented text
`simcore::diagnostics::DumpGraphText` emits. This is a deliberately
separate implementation (plain `json`, no import of anything under
`adas_sim`) so the comparison is worth something: two independent readings
of the same file agreeing is the actual claim `IT-10` makes, not one side
re-printing the other.

A "simulate" stage is PREDICTED to load its own declared `impl.path` (this
layer has no way to know a load will fail at run time -- that is exactly
the disagreement `IT-10` exists to catch when the engine's own dump
instead says "unloaded").
"""

from __future__ import annotations

import json
import sys


def dump_graph_text(spec: dict) -> str:
    lines = [f"run_id: {spec['run_id']}", f"grid_step_ns: {spec['grid']['step_ns']}"]
    for stage in spec["stages"]:
        mode = stage["mode"]
        impl = stage["impl"]["path"] if mode == "simulate" else mode
        lines.append(f"stage: {stage['name']} mode={mode} impl={impl}")
        input_lines = sorted(
            f"{inp['port']} = {inp['producer']}.{inp['producer_port']}" for inp in stage["inputs"]
        )
        lines.extend(f"  input: {line}" for line in input_lines)
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: predict_graph.py <run_spec.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    sys.stdout.write(dump_graph_text(spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
