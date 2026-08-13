# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim batch <recordings> --pipeline <p.yaml>` -- run a pipeline over a set.

One subprocess per recording, so a component that crashes or hangs costs one
row rather than the run. `-j` sets parallelism, `--timeout-s` bounds a hung
library. `--report` writes per-recording outcomes, keeping `fail`, `crash` and
`timeout` distinct.
"""

# Design refs: `GT-9` (no logic here -- `core/batch.py` is the engine) · `R-SIM-19` fault containment

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.orchestrate.batch import expand_recordings, run_batch, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim batch", description=__doc__)
    parser.add_argument("recordings", nargs="+", help="recording path(s), a glob, or a list.txt")
    parser.add_argument("--pipeline", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="write a markdown report here")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="max concurrent subprocesses (default 1)")
    parser.add_argument("--search", type=Path, action="append", default=[], help="dll:/stubdll: search directory")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--timeout-s", type=float, default=300.0, help="per-recording subprocess timeout")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    recordings = expand_recordings(args.recordings)
    if not recordings:
        print("sim batch: no recordings matched")
        return 2

    results = run_batch(
        recordings, args.pipeline, search=args.search, config=args.config, jobs=args.jobs,
        timeout_s=args.timeout_s,
    )

    if args.report is not None:
        write_report(results, args.report)
        print(f"wrote {args.report}")

    for r in results:
        print(f"[{r.outcome}] {r.recording} ({r.duration_s:.2f}s)" + (f" -- {r.error}" if r.error else ""))
    ok_count = sum(1 for r in results if r.outcome == "ok")
    print(f"sim batch complete: {ok_count}/{len(results)} ok")

    # Exit code reflects failure without hiding the successes (ST-D7-5) --
    # a non-zero exit still leaves every recording's own outcome printed
    # above and in --report, never merely "something failed."
    return 0 if ok_count == len(results) else 1
