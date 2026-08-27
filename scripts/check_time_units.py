# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0046 / ANL-SW-14 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-07) --
SW-0046: no time quantity inside the engine is a floating-point type. A
type scan over `include/simcore/**` and `src/simcore/**` (plus their
`simengine` siblings, once those gain content) for a `float`/`double`
member or local whose name ends `_s`, `_ms` or `_time` -- exactly the
boundary SW-0046's own text draws: "float seconds survive only at CLI,
YAML and label boundaries", which are outside this scan's roots on
purpose.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent

#: The engine only -- the same boundary ANL-SW-02/ANL-SW-03/ANL-SW-04 scan
#: (design §3.2's own enforcement table). `simengine` has no content yet
#: (WP-14) but is listed now so this check's scope grows with it silently,
#: never by someone remembering to add a line later.
DEFAULT_ROOTS: tuple[Path, ...] = (
    SIM_ROOT / "include" / "simcore",
    SIM_ROOT / "src" / "simcore",
    SIM_ROOT / "include" / "simengine",
    SIM_ROOT / "src" / "simengine",
)

_SCAN_SUFFIXES = (".hpp", ".h", ".cpp")

# A `float`/`double` declaration whose identifier ends in one of the three
# float-seconds spellings SW-0046 names, immediately followed by `;` or
# `=` (a declaration/definition, not e.g. a cast or a comment mentioning
# the word).
_FLOAT_TIME_MEMBER = re.compile(r"\b(?:float|double)\s+\w*(?:_s|_ms|_time)\b\s*[;=]")

# SW-0046 permits float seconds "at CLI, YAML and label boundaries". That list
# was written before the engine had either of the two boundaries it cannot
# avoid crossing with a float, and both are fixed by contracts sim does not
# own:
#   * the component DLL ABI -- `exec(dtS)` and `AdasPort::ageS` are float
#     seconds by R-ARCH-4, which predates this requirement;
#   * a file format whose own time column is a double (`.erg`), read at the
#     codec seam and converted to integer ns immediately.
# A blanket allow-list keyed on path would silence those files forever,
# including code written next year. So the exemption is per line, must state
# a reason, and greps out in one command:
#     grep -rn "TIME-BOUNDARY:" include/simcore src/simcore
# Anything else -- a float second that merely travels between two interior
# functions -- still fails, which is the whole point of SW-0046.
_BOUNDARY_MARKER = re.compile(r"//\s*TIME-BOUNDARY:\s*\S")


def _scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        code = line.split("//", 1)[0]  # a same-line trailing comment must not trigger a false positive
        if _FLOAT_TIME_MEMBER.search(code) and not _BOUNDARY_MARKER.search(line):
            findings.append(f"{path}:{lineno}: {line.strip()}")
    return findings


def check_time_units(roots: tuple[Path, ...] = DEFAULT_ROOTS) -> list[str]:
    findings: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in _SCAN_SUFFIXES:
                findings.extend(_scan_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    findings = check_time_units()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} floating-point time member(s)")
        return 1
    print("check_time_units: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
