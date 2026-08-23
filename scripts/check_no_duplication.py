# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0020 / ANL-SW-10 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
`SW-0019`/`SW-0020`: no capability survives a **phase boundary** with two
implementations. This is the mechanism -- `CAPABILITY_HOMES`/
`KNOWN_PENDING_DUPLICATION` below are empty today (`WP-16` closed the last
of the six historically duplicated capabilities, see the 2026-08-23 note
below); the check itself stays, ready for a future migration to populate.

**How it works, for the next migration that needs it.** A capability with
two real homes and no `KNOWN_PENDING_DUPLICATION` entry is an immediate
failure. Naming it in `KNOWN_PENDING_DUPLICATION` (with a reason) is how a
tracked, temporary migration window is declared without either blocking
every commit until the migration finishes or training everyone to ignore a
permanently-red check -- checked in both directions exactly like
`docs/v2/py/trace_check.py`'s `KNOWN_UNPARENTED`: an entry whose homes have
already converged (only one remains) is a stale entry and must be removed,
and a capability that develops a *second* real duplication beyond its one
known pair is still a failure.

**Retired 2026-08-23 (`WP-16`).** All six of Design SS14.2's historically
duplicated capabilities (pipeline load/validate, ingest-map parse,
component host, recording read/group, library resolve, multi-rate
scheduler) paired a `modules/sim` Python home against a `modules/sil_host`
C++ home -- the SAME implementation, ported, proven equal at `WP-15a`
(`scripts/prove_equal.py`, 7/7 PASS) and then deleted from `sil_host`,
followed by `sil_host` itself being unlinked as a submodule (nothing else
in the superproject required it). `CAPABILITY_HOMES`/
`KNOWN_PENDING_DUPLICATION` are cleared rather than left with six "closed"
notes pointing at a path that no longer exists.

`DD-04`'s codec was briefly considered a seventh entry (`WP-15a`,
2026-08-22) but corrected out 2026-08-23, found auditing `WP-16` before
executing it: its C++ home was always `simcore/io/codecs/mcap.cpp`, inside
`modules/sim` itself, never `sil_host` -- and `WP-15b`'s "subprocess, not
in-process" decision (`engine/bridge.py`'s own docstring: `simcore` builds
static-only, no in-process ABI artifact to bind) means `adas_sim.io.mcap`
is permanent: every rewired call site launches `simengine` as a child
process and reads its output back through exactly this code, forever. Two
implementations that will never converge because they serve two different,
permanently separate consumers is not the phase-boundary duplication this
check is for.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
ADAS_SIM = SIM_ROOT / "src" / "adas_sim"

# capability -> (python home, cpp home). A "home" is real if the file
# exists and is non-empty; either side may not exist yet. Empty since
# 2026-08-23 (WP-16 closed the last entry) -- see this file's own docstring.
CAPABILITY_HOMES: dict[str, tuple[Path, Path]] = {}

# A capability leaving this set without both homes agreeing (one deleted) is
# a regression; one staying after its homes agree is a stale entry -- both
# are checked, same discipline as trace_check.py's KNOWN_UNPARENTED. Empty
# since 2026-08-23 -- see this file's own docstring.
KNOWN_PENDING_DUPLICATION: dict[str, str] = {}


def _is_real(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def check_no_duplication(
    homes: dict[str, tuple[Path, Path]] = CAPABILITY_HOMES,
    known_pending: dict[str, str] = KNOWN_PENDING_DUPLICATION,
) -> tuple[list[str], list[str], int]:
    """Return (findings, notes, checked). `checked` is always `len(homes)` --
    every capability is evaluated every run, never skipped."""
    findings: list[str] = []
    notes: list[str] = []
    for name, (py_home, cpp_home) in sorted(homes.items()):
        both = _is_real(py_home) and _is_real(cpp_home)
        if name in known_pending:
            if both:
                notes.append(f"{name}: known pending duplication -- {known_pending[name]}")
            else:
                findings.append(
                    f"{name}: listed in KNOWN_PENDING_DUPLICATION but only one home remains -- "
                    f"remove the entry (py={_is_real(py_home)}, cpp={_is_real(cpp_home)})"
                )
        elif both:
            findings.append(
                f"{name}: two implementations found -- {py_home} and {cpp_home} -- "
                f"SW-0019/SW-0020: no capability survives a phase boundary with two"
            )
    for name in sorted(set(known_pending) - set(homes)):
        findings.append(f"{name}: in KNOWN_PENDING_DUPLICATION but not a named capability")
    return findings, notes, len(homes)


def main(argv: list[str] | None = None) -> int:
    findings, notes, checked = check_no_duplication()
    for n in notes:
        print(f"note: {n}")
    for f in findings:
        print(f)
    print(f"\n{checked} capabilities checked")
    if findings:
        print(f"{len(findings)} duplication violation(s)")
        return 1
    print("check_no_duplication: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
