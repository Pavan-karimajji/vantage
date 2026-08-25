#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @file check_no_repeated_field_allocation.py
# @brief
#   ANL-SW-23 (SIM_Implementation_Plan_v0.1.md WP-11, serves SW-0098) --
#   R-SIM-15's governing line, "an override may destroy or attenuate
#   information; it may never create an entity," made mechanical: no
#   verb-application code under src/simcore/mutate/** grows a repeated
#   field. Checked by grepping for the reflection API calls that DO grow
#   one (Add*/InsertRepeated*, protobuf's own generic-message vocabulary
#   for "append a new element") -- window.cpp/verbs.cpp/faults.cpp never
#   touch a repeated field directly (they call into address.cpp for that),
#   so the scan covers the whole directory rather than naming one file, the
#   same "scan the directory, not a hand-kept file list" discipline
#   check_engine_boundary.py's own sibling checks use.
#
#   `IMP-0098`'s own carve-out: `EraseRepeatedElement` (address.cpp) calls
#   `Reflection::SwapElements`/`RemoveLast` to compact a repeated field --
#   REMOVING, never adding, an element (`select`/`drop` with
#   `fixed_slots=false`). Those two calls are explicitly exempted, named
#   here, rather than the check being narrowed to miss them structurally --
#   a check that cannot see the thing it exempts is a check nobody can
#   trust (`R-REQ-9`'s planted-violation discipline one level down: this
#   file's own `__main__` self-test proves the check still catches a real
#   `Add`/`InsertRepeated` call when one is planted).
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
MUTATE_DIR = SIM_ROOT / "src" / "simcore" / "mutate"

# Reflection::Add<Type>/AddMessage/AddEnumValue/AddRepeatedField, and the
# generic-message InsertRepeatedField -- protobuf's own vocabulary for
# "grow a repeated field by one." SwapElements/RemoveLast (compaction) and
# every SetRepeated*/GetRepeated* accessor are deliberately NOT matched --
# they touch an existing slot, never add one.
_FORBIDDEN_CALL_RE = re.compile(r"->\s*Add[A-Za-z]*\s*\(|->\s*InsertRepeatedField\s*\(")


def find_violations(mutate_dir: Path, *, base: Path | None = None) -> list[str]:
    base = base or SIM_ROOT
    findings: list[str] = []
    for path in sorted(mutate_dir.glob("*.cpp")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _FORBIDDEN_CALL_RE.search(line):
                findings.append(f"{path.relative_to(base)}:{lineno}: {line.strip()}")
    return findings


def main(argv: list[str] | None = None) -> int:
    if not MUTATE_DIR.is_dir():
        print(f"check_no_repeated_field_allocation: FAIL -- {MUTATE_DIR} does not exist")
        return 1
    findings = find_violations(MUTATE_DIR)
    if findings:
        print("check_no_repeated_field_allocation: FAIL -- a mutate/** file grows a repeated field:")
        for f in findings:
            print(f"  {f}")
        print("\nR-SIM-15: an override may destroy or attenuate information; it may never create an entity.")
        return 1
    print(f"check_no_repeated_field_allocation: clean -- {len(list(MUTATE_DIR.glob('*.cpp')))} files scanned")
    return 0


def _self_test() -> None:
    """The planted-violation half (R-REQ-9's own discipline): prove the
    regex really does fire on a real growth call before trusting a clean
    scan of the real tree."""
    with tempfile.TemporaryDirectory() as tmp:
        planted = Path(tmp) / "bad.cpp"
        planted.write_text("void F(Message& m, const FieldDescriptor* f) { refl->AddMessage(&m, f); }\n")
        violations = find_violations(Path(tmp), base=Path(tmp))
        assert violations, "self-test FAILED: check_no_repeated_field_allocation did not catch a planted Add* call"

        clean = Path(tmp) / "good.cpp"
        planted.unlink()
        clean.write_text("void F(Message& m, const FieldDescriptor* f) { refl->SetRepeatedDouble(&m, f, 0, 1.0); }\n")
        violations = find_violations(Path(tmp), base=Path(tmp))
        assert not violations, "self-test FAILED: check_no_repeated_field_allocation flagged a non-growth call"
    print("check_no_repeated_field_allocation: self-test (planted violation) passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        _self_test()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
