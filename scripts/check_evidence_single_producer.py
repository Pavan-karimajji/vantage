# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0273 / ANL-SW-44 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-24) --
SW-0273: exactly one function across `src/adas_sim/**` may construct an
`Evidence` record. `diagnostics/evidence.py::evidence` is that function;
`render_panel`/`render_text`, `cli/explain.py --at` and the GUI evidence
panel are formatters that call it and never build one themselves.

Mechanical, not structural: a literal scan for `Evidence(` outside
`diagnostics/evidence.py` itself. A second constructor call anywhere else
in the package -- however it got there -- is exactly the regression
`SW-0273`'s own Accept clause exists to catch ("a static check finds no
second code path capable of producing an evidence answer")."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
ADAS_SIM = SIM_ROOT / "src" / "adas_sim"
PRODUCER_FILE = ADAS_SIM / "diagnostics" / "evidence.py"

_CONSTRUCTOR_RE = re.compile(r"\bEvidence\s*\(")


def check_evidence_single_producer(adas_sim: Path = ADAS_SIM, producer_file: Path = PRODUCER_FILE) -> list[str]:
    findings: list[str] = []
    for path in sorted(adas_sim.rglob("*.py")):
        if path.resolve() == producer_file.resolve():
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if _CONSTRUCTOR_RE.search(text):
            try:
                shown = path.relative_to(SIM_ROOT)
            except ValueError:
                shown = path  # a test-planted tree outside SIM_ROOT (F-PLANTED)
            findings.append(f"{shown}: constructs Evidence(...) outside {producer_file.name}")
    return findings


def main(argv: list[str] | None = None) -> int:
    findings = check_evidence_single_producer()
    for f in findings:
        print(f)
    if findings:
        print(f"{len(findings)} second-producer violation(s)")
        return 1
    print("check_evidence_single_producer: clean -- one producer")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
