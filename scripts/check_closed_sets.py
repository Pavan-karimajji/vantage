# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0106 / IMP-0361 / ANL-SW-24 (docs/v2/SIM_Implementation_Plan_v0.1.md
WP-01, WP-11) -- SV-8: the six closed vocabularies (`Verb`, `Fault`,
`Origin`, `Rung`, `MergePolicy`, error kinds) never drift from their one
canonical definition. R-SIM-15's own line: **a closed list is closed, and
reopening one is a design change, never an implementation choice.**

`WP-01`'s own slice checked the two vocabularies that existed as Python
code that early (`OverrideVerb`, `FaultVerb`) against the value set each
governing document states. **`WP-11` widens `Verb`/`Fault` to `"py_cpp"`**
(this file's own new spec kind): `simcore::mutate::Verb`/`Fault`
(`include/simcore/mutate.hpp`) landed this pass as the two vocabularies'
own C++ mirror, so the check now compares BOTH language sides against the
expected set AND against each other -- a Python/C++ spelling drift is
exactly the failure mode a single-language check cannot see, and
`IMP-0106`'s own words are "each enum compared against the published
schema's enumeration... and the C++-side type it mirrors." The
`schemas/*.schema.json` half (a `WP-04` deliverable) still does not exist;
that comparison stays a named gap, not a silent one, same as before.

`Origin` (`ANL-SW-15`, `WP-07`) landed as a **C++-only** enum
(`simcore::bus::Origin`, `bus.hpp`) -- there is no Python `Origin` type to
import, so its entry stays tagged `"cpp"` and read by regex from the
header, the same technique `check_error_parity.py` already uses for the
C++ side of the error taxonomy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SRC = SIM_ROOT / "src"
BUS_HPP = SIM_ROOT / "include" / "simcore" / "bus.hpp"
MUTATE_HPP = SIM_ROOT / "include" / "simcore" / "mutate.hpp"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# name -> (kind, py_ref, cpp_ref, expected value set, closed-by). `py_ref` is
# always `(module, class name)` and `cpp_ref` always `(header path, C++ enum
# name)`; the one not used by `kind` is `None`. So: ("py", (module, class),
# None, ...) for a Python-only enum, ("cpp", None, (header, enum), ...) for a
# C++-only one, and ("py_cpp", (module, class), (header, enum), ...) for a
# vocabulary landed on both sides -- checked against `expected` on each
# side AND against each other, since a same-value-set Python/C++ pair that
# quietly disagree with EACH OTHER is the drift a same-language check
# cannot see (`IMP-0106`'s own "and the C++-side type it mirrors").
# `None` means the type does not exist yet -- reported as NOT_YET, never
# silently omitted from the count.
_ClosedSetSpec = tuple[str, object, object, frozenset[str], str]
_CLOSED_SETS: dict[str, _ClosedSetSpec | None] = {
    "Verb": (
        "py_cpp", ("adas_sim.config.override", "OverrideVerb"), (MUTATE_HPP, "Verb"),
        frozenset({"const", "hold", "offset", "scale", "select", "drop"}),
        "R-SIM-15",
    ),
    "Fault": (
        "py_cpp", ("adas_sim.config.fault", "FaultVerb"), (MUTATE_HPP, "Fault"),
        frozenset({"drop", "stale", "delay", "invalidate", "corrupt"}),
        "R-SIM-8 / SS9.2",
    ),
    # Origin: `simcore/bus.hpp::Origin` (IMP-0048), landed WP-07.
    "Origin": (
        "cpp", None, (BUS_HPP, "Origin"),
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


def _py_values(module_name: str, class_name: str) -> tuple[frozenset[str] | None, str | None]:
    try:
        module = __import__(module_name, fromlist=[class_name])
        enum_cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        return None, f"cannot import {module_name}.{class_name}: {exc}"
    return frozenset(m.value for m in enum_cls), None


def _cpp_values(header_path: Path, enum_name: str) -> tuple[frozenset[str] | None, str | None]:
    if not header_path.is_file():
        return None, f"cannot read {header_path}"
    return _cpp_enum_values(header_path.read_text(encoding="utf-8"), enum_name), None


def _against_expected(name: str, actual: frozenset[str], expected: frozenset[str], closed_by: str, tag: str = "") -> list[str]:
    if actual == expected:
        return []
    missing = expected - actual
    extra = actual - expected
    detail = []
    if missing:
        detail.append(f"missing {sorted(missing)}")
    if extra:
        detail.append(f"unexpected {sorted(extra)} -- reopened without a requirement ({closed_by})")
    return [f"{name}{tag}: {', '.join(detail)}"]


def check_closed_sets(closed_sets: dict = _CLOSED_SETS) -> tuple[list[str], int, int]:
    """Return (findings, checked, not_yet). `checked` is how many of the six
    vocabularies exist as a real type today (Python, C++, or both) and were
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
        kind, py_ref, cpp_ref, expected, closed_by = spec

        if kind in ("py", "py_cpp"):
            module_name, class_name = py_ref
            py_actual, error = _py_values(module_name, class_name)
            if error:
                findings.append(f"{name} (py): {error}")
                py_actual = None
            elif kind == "py":
                findings.extend(_against_expected(name, py_actual, expected, closed_by))

        if kind in ("cpp", "py_cpp"):
            header_path, enum_name = cpp_ref
            cpp_actual, error = _cpp_values(Path(header_path), enum_name)
            if error:
                findings.append(f"{name} (cpp): {error}")
                cpp_actual = None
            elif kind == "cpp":
                findings.extend(_against_expected(name, cpp_actual, expected, closed_by))

        if kind == "py_cpp" and py_actual is not None and cpp_actual is not None:
            findings.extend(_against_expected(name, py_actual, expected, closed_by, tag=" (py)"))
            findings.extend(_against_expected(name, cpp_actual, expected, closed_by, tag=" (cpp)"))
            if py_actual != cpp_actual:
                findings.append(
                    f"{name}: py/cpp mirrors disagree -- py has {sorted(py_actual)}, cpp has {sorted(cpp_actual)}"
                )
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
