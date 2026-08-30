# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ANL-SM-02` (`modules/viz/docs/VIZ_Sync_Plan_v0.1.md`, `SM-08`) -- no CI
image for `modules/sim` installs a graphical toolkit. `SM-12` deleted the
last Python importer of one (`adas_sim.player.shell.qt_window`'s own
`PySide6` import); this is the mechanical proof that stays true, checked
against the CI workflow files rather than trusted from memory.

Scoped to `adas_sim`'s own *engine* face -- `.github/workflows/*.yml` in
this repo -- never `modules/sim/vantage/`, which is `SM-11`'s own
in-process host and is deliberately outside this constraint (a real GLFW/
ImGui window is `vantage_app.exe`'s whole job).

Mechanical, not structural: a literal scan of every `pip install` /
`extras_require`-style line in each workflow file for a known graphical-
toolkit package or extras name. A second such install anywhere in a
workflow file -- however it got there -- is exactly the regression this
check exists to catch.

    python scripts/check_no_graphical_toolkit.py             # real repo
    python scripts/check_no_graphical_toolkit.py --root DIR  # a fixture
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
WORKFLOWS_GLOB = ".github/workflows/*.yml"

#: Known graphical-toolkit packages and the pyproject extras name that used
#: to pull one in (`viewer`, retired with it -- `SM-08`). A workflow line
#: naming any of these is the violation.
_TOOLKIT_TOKENS = ("PySide6", "PyQt5", "PyQt6", "viewer")
_TOKEN_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _TOOLKIT_TOKENS) + r")\b")


def check_no_graphical_toolkit(sim_root: Path = SIM_ROOT) -> list[str]:
    findings: list[str] = []
    workflows = sorted((sim_root).glob(WORKFLOWS_GLOB))
    for path in workflows:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = _TOKEN_RE.search(line)
            if match:
                try:
                    shown = path.relative_to(sim_root)
                except ValueError:
                    shown = path  # a test-planted tree outside sim_root
                findings.append(f"{shown}:{lineno}: installs a graphical toolkit ({match.group(1)}): {line.strip()!r}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="a fixture root, for this check's own .c1/.c2")
    args = parser.parse_args(argv)

    findings = check_no_graphical_toolkit(args.root)
    for f in findings:
        print(f)
    if findings:
        print(f"{len(findings)} graphical-toolkit install(s) found")
        return 1
    print("check_no_graphical_toolkit: clean -- no CI image installs a graphical toolkit")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
