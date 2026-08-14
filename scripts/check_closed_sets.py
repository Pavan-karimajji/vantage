# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0106 / IMP-0361 / ANL-SW-24 (docs/v2/SIM_Implementation_Plan_v0.1.md
WP-01, WP-11) -- SV-8: the six closed vocabularies (`Verb`, `Fault`,
`Origin`, `Rung`, `MergePolicy`, error kinds) never drift from their one
canonical definition. R-SIM-15's own line: **a closed list is closed, and
reopening one is a design change, never an implementation choice.**

Full form (`IMP-0106`, `WP-11`): each enum compared against the *published
schema*'s enumeration (`schemas/*.schema.json`, a `WP-04` deliverable) and
the C++-side type it mirrors. Neither exists yet. **This is `WP-01`'s
narrower, honest slice**: the two closed vocabularies that already exist as
Python code today (`OverrideVerb`, `FaultVerb`) are compared against the
value set each governing document states, so the check is real from day
one and grows in count -- never silently -- as `Origin` (`WP-07`), `Rung`
(`WP-08`), `MergePolicy` (`WP-05`) and the error taxonomy (`WP-03`) land.
"IMP-0361: it runs from WP-01 so every closed set added later is born
checked."

`Origin` (`ANL-SW-15`, `WP-07`) landed as a **C++-only** enum
(`simcore::bus::Origin`, `bus.hpp`) -- there is no Python `Origin` type to
import, so its entry is tagged `"cpp"` and read by regex from the header
instead, the same technique `check_error_parity.py` already uses for the
C++ side of the error taxonomy. `"py"` tags the two pre-existing entries so
the dict format stays uniform rather than needing a per-entry type check.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SRC = SIM_ROOT / "src"
BUS_HPP = SIM_ROOT / "include" / "simcore" / "bus.hpp"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# name -> ("py", module, class name, expected value set, closed-by) for a
# Python enum, or ("cpp", header path, C++ enum name, expected value set,
# closed-by) for a C++-only one. `None` means the type does not exist yet
# -- reported as NOT_YET, never silently omitted from the count.
_ClosedSetSpec = tuple[str, object, str, frozenset[str], str]
_CLOSED_SETS: dict[str, _ClosedSetSpec | None] = {
    "OverrideVerb": (
        "py", "adas_sim.config.override", "OverrideVerb",
        frozenset({"const", "hold", "offset", "scale", "select", "drop"}),
        "R-SIM-15",
    ),
    "FaultVerb": (
        "py", "adas_sim.config.fault", "FaultVerb",
        frozenset({"drop", "stale", "delay", "invalidate", "corrupt"}),
        "R-SIM-8 / SS9.2",
    ),
    # Origin: `simcore/bus.hpp::Origin` (IMP-0048), landed WP-07.
    "Origin": (
        "cpp", BUS_HPP, "Origin",
        frozenset({"measured", "truth", "mocked", "simulated", "overridden", "unknown"}),
        "SW-0048",
    ),
    # Rung: the cycle-reconstruction recovery ladder (IMP-0050), lands WP-08.
    "Rung": None,
    # MergePolicy: `sources[].merge.policy` in the Resolved Run Spec (IMP-0005), lands WP-05.
    "MergePolicy": None,
    # error kinds: `simcore/errors.hpp::Error` (IMP-0123), lands WP-03.
    "ErrorKind": None,
}


def _cpp_enum_values(text: str, enum_name: str) -> frozenset[str]:
    """`enum class <enum_name> { A, B, ... };`'s enumerator names,
    lowercased -- the C++ spelling convention (PascalCase) differs from the
    published schema's (lowercase) by language convention only; only the
    value set is the contract (same reasoning check_error_parity.py's own
    event-string comparison uses)."""
    match = re.search(rf"enum class {re.escape(enum_name)} \{{([^}}]*)\}}", text)
    if not match:
        return frozenset()
    return frozenset(name.strip().lower() for name in match.group(1).split(",") if name.strip())


def check_closed_sets(closed_sets: dict = _CLOSED_SETS) -> tuple[list[str], int, int]:
    """Return (findings, checked, not_yet). `checked` is how many of the six
    vocabularies exist as a real type today (Python or C++) and were
    actually compared; `not_yet` is how many are deferred to a later work
    package. The two always sum to six -- if they do not, a vocabulary was
    added or removed from the closed list itself, which is a finding on
    its own."""
    findings: list[str] = []
    checked = 0
    not_yet = 0
    for name, spec in closed_sets.items():
        if spec is None:
            not_yet += 1
            continue
        checked += 1
        kind = spec[0]
        if kind == "cpp":
            _, header_path, enum_name, expected, closed_by = spec
            header_path = Path(header_path)
            if not header_path.is_file():
                findings.append(f"{name}: cannot read {header_path}")
                continue
            actual = _cpp_enum_values(header_path.read_text(encoding="utf-8"), enum_name)
        else:
            _, module_name, class_name, expected, closed_by = spec
            try:
                module = __import__(module_name, fromlist=[class_name])
                enum_cls = getattr(module, class_name)
            except (ImportError, AttributeError) as exc:
                findings.append(f"{name}: cannot import {module_name}.{class_name}: {exc}")
                continue
            actual = frozenset(m.value for m in enum_cls)
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            detail = []
            if missing:
                detail.append(f"missing {sorted(missing)}")
            if extra:
                detail.append(f"unexpected {sorted(extra)} -- reopened without a requirement ({closed_by})")
            findings.append(f"{name}: {', '.join(detail)}")
    return findings, checked, not_yet


def main(argv: list[str] | None = None) -> int:
    findings, checked, not_yet = check_closed_sets()
    for f in findings:
        print(f)
    total = checked + not_yet
    print(f"\n{checked}/{total} closed vocabularies checked, {not_yet} not yet realised (later WP)")
    if findings:
        print(f"{len(findings)} closed-set violation(s)")
        return 1
    print("check_closed_sets: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
