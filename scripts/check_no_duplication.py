# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0020 / ANL-SW-10 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
`SW-0019`/`SW-0020`: no capability survives a **phase boundary** with two
implementations. Names the six historically duplicated capabilities
(Concept SS21.3's four, SwReq's six -- Design SS14.2; `DD-04`'s codec was
briefly a seventh, removed 2026-08-23, see this file's own correction note
below) and fails when both of a capability's two homes hold real
code **outside the migration's own, named, tracked window**.

**Why this does not fail today.** Four of the six pre-existing duplications
(pipeline load/validate, ingest-map parse, component host, recording
read/group) already exist in both `modules/sil_host` (C++) and
`modules/sim` (Python) *right now* -- that coexistence is the whole reason
`MP-1`/`MP-2` exist, and it is retired by `WP-16`'s deletion ledger
(Design SS2.2/SS28.1), not by this script. Reporting it as a fresh failure
here would either block every commit until `WP-16` or train everyone to
ignore a permanently-red check -- so it is listed in
`KNOWN_PENDING_DUPLICATION`, checked in both directions exactly like
`docs/v2/py/trace_check.py`'s `KNOWN_UNPARENTED`: an entry that gains a
second-implementation resolution (only one home left) must be removed, and
a capability that develops a *second* real duplication beyond its one known
pair is still a failure.

**Updated 2026-08-22 (`WP-15a`):** the seventh, the codec (`DD-04`), no
longer has zero known-pending entries -- `WP-06` landed
`src/simcore/io/codecs/mcap.cpp` (real, 270 lines, `UT-IO-*` green) while
`adas_sim/io/mcap.py` is still real too, so this is now a live duplication
by this check's own definition. `scripts/prove_equal.py`'s row 7 proves the
two produce identical results on the same corpus (`tests/unit/test_a4_mcap.py`
+ `test_ut_io_mcap_roundtrip.cpp`/`test_ut_io_codec_contract.cpp`), which is
exactly the evidence `SW-0019` requires before a pending duplication is
allowed to sit here rather than fail the build -- so "codec" moves into
`KNOWN_PENDING_DUPLICATION`, closed by `WP-16` the same as the other six.

**Corrected 2026-08-23, found auditing `WP-16` before executing it: "codec"
is not actually one of the six.** The other six pair a Python home against
`modules/sil_host`'s own C++ -- the SAME implementation, ported, with the
`sil_host` half scheduled for outright deletion. "codec"'s C++ home is
`simcore/io/codecs/mcap.cpp`, in THIS module, not `sil_host` -- and
`WP-15b`'s own "subprocess, not in-process" decision (`engine/bridge.py`'s
docstring: `simcore` builds static-only, no in-process ABI artifact to
bind) means `adas_sim.io.mcap` is never going away: every rewired call site
launches `simengine` as a child process and reads its output back into
Python through this exact codec, permanently. Two real implementations
that will never converge because they serve two different, permanently
separate consumers (the C++ engine; the Python tooling/bridge reading its
subprocess output) is not the phase-boundary duplication `SW-0019`/
`SW-0020` are about -- so "codec" is removed from `CAPABILITY_HOMES`
entirely rather than left in `KNOWN_PENDING_DUPLICATION` making a "closed
by WP-16" promise that would still be false the day every other row here
is.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SUPERPROJECT_ROOT = SIM_ROOT.parent.parent
SIL_HOST = SUPERPROJECT_ROOT / "modules" / "sil_host" / "src"
ADAS_SIM = SIM_ROOT / "src" / "adas_sim"

# capability -> (python home, cpp home). A "home" is real if the file
# exists and is non-empty; either side may not exist yet.
CAPABILITY_HOMES: dict[str, tuple[Path, Path]] = {
    "pipeline_load_validate": (ADAS_SIM / "graph" / "build.py", SIL_HOST / "pipeline.cpp"),
    "ingest_map_parse": (ADAS_SIM / "ingest" / "map.py", SIL_HOST / "ingest_map.cpp"),
    "component_host": (ADAS_SIM / "resolve" / "component.py", SIL_HOST / "sil_component.cpp"),
    "recording_read_group": (ADAS_SIM / "io" / "base.py", SIL_HOST / "recording_reader.cpp"),
    "library_resolve": (ADAS_SIM / "resolve" / "library.py", SIL_HOST / "library_loader.cpp"),
    "multi_rate_scheduler": (ADAS_SIM / "core" / "runner.py", SIL_HOST / "pipeline.cpp"),
}

# Retired one at a time as WP-16 deletes each `sil_host` half (Design SS2.2).
# A capability leaving this set without both homes agreeing (one deleted) is
# a regression; one staying after its homes agree is a stale entry -- both
# are checked, same discipline as trace_check.py's KNOWN_UNPARENTED.
KNOWN_PENDING_DUPLICATION: dict[str, str] = {
    "pipeline_load_validate": "closed by WP-16 -- sil_host/pipeline.cpp's load/validate/grid/Exec() half deleted",
    "ingest_map_parse": "closed by WP-16 -- sil_host/ingest_map.cpp's parse half deleted",
    "component_host": "closed by WP-16 -- sil_host/sil_component.cpp deleted (survivor moved to simcore/module_host at WP-10)",
    "recording_read_group": "closed by WP-16 -- sil_host/recording_reader.cpp deleted (survivor split across simcore/io + simcore/bus/cycle.cpp at WP-06/WP-08)",
    "library_resolve": "closed by WP-16 -- sil_host/library_loader.cpp's resolve half deleted",
    "multi_rate_scheduler": "closed by WP-16 -- sil_host/pipeline.cpp's Step() deleted (survivor is simcore/scheduler/due.cpp from WP-09)",
}


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
    print(f"\n{checked}/6 capabilities checked")
    if findings:
        print(f"{len(findings)} duplication violation(s)")
        return 1
    print("check_no_duplication: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
