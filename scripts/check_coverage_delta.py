#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @file check_coverage_delta.py
# @brief
#   ANL-SW-09 (docs/v2/SIM_Software_Test_Spec_v0.1.md, serves SW-0019;
#   docs/v2/SIM_Implementation_Plan_v0.1.md WP-15a) -- "coverage does not
#   decrease across the deletion". `WP-16` is the package that deletes
#   `sil_host`; this script is what it invokes to fail the build if that
#   deletion drops coverage. WP-16 has not happened yet (`prove_equal.py`'s
#   own PENDING row 1 says so), so this script's job **today** is only to
#   establish the baseline mechanism -- record, right now, how many test
#   cases exercise each of Design Sec.28.3's seven rows in both homes, with
#   the measurement's provenance beside it (same discipline `measure.py`
#   uses for a benchmark number: a count with no provenance cannot be
#   refuted, only believed).
#
#   Coverage here means **test-case count**, not a line-coverage
#   percentage -- consistent with `prove_equal.py`'s own row-by-row
#   evidence (SW-0019's Accept clause is about the corpus, not gcov). A
#   line-coverage tool may be added later without changing this file's
#   contract: the baseline format has a `metric` field naming what was
#   counted.
#
#   Usage:
#     python scripts/check_coverage_delta.py --write-baseline
#       Measures every row's retiring + survivor test-case count right now
#       and writes scripts/coverage_baseline.json. Run once, ahead of
#       WP-16, and committed -- this is the number the deletion is checked
#       against.
#     python scripts/check_coverage_delta.py --check
#       Re-measures every row's SURVIVOR count and fails (exit 1) if any
#       row's survivor count is lower than its baseline's survivor count.
#       This is the call `WP-16` makes after deleting `sil_host`: the
#       retiring implementation's tests are gone by then, so only the
#       survivor side is comparable, and it must not have shrunk.
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from measure import measure_provenance  # noqa: E402
from prove_equal import ROWS, SIL_TESTS_CANDIDATES, SIMCORE_TESTS_CANDIDATES, _find_binary, _run, run_pytest  # noqa: E402

BASELINE_PATH = SCRIPT_DIR / "coverage_baseline.json"

# Per row: (python corpus paths, cpp binary candidates, cpp gtest filter) --
# the SAME corpus prove_equal.py compares, so a coverage baseline can never
# silently diverge from what the equivalence gate actually checked.
_ROW_CPP_FILTER: dict[int, tuple[tuple[Path, ...], str]] = {
    2: (SIL_TESTS_CANDIDATES, "PipelineLoadErrors.*"),
    3: (SIL_TESTS_CANDIDATES, "IngestMap.*"),
    4: (SIL_TESTS_CANDIDATES, "TwoStageResim.*"),
    5: (SIL_TESTS_CANDIDATES, "PipelinePeriodGrid.*"),
    6: (SIL_TESTS_CANDIDATES, "PipelineLoadErrors.StubdllImplLoads"),
    7: (SIMCORE_TESTS_CANDIDATES, "UtIo01CodecContract.*:UtIo02Capabilities.*:UtIo03Registration.*:UtIo04ReadersAndWritersSymmetric.*:UtIo22McapRoundtrip.*"),
}
_ROW_SURVIVOR_CPP_FILTER: dict[int, tuple[tuple[Path, ...], str]] = {
    # Row 4's survivor is C++ (simcore/module_host), not Python -- its own
    # ported coverage, not the retiring sil_host corpus.
    4: (SIMCORE_TESTS_CANDIDATES, "MhComponent.*:MhExecTimeout.*"),
}


def _pytest_case_count(paths: tuple[str, ...]) -> int | None:
    """Real count via `pytest --collect-only -q`, not a guess from the pass
    line (which is silent on a file with zero tests)."""
    if not paths:
        return None
    proc = _run([sys.executable, "-m", "pytest", "--collect-only", "-q", *paths], cwd=SCRIPT_DIR.parent)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) tests? collected", out)
    return int(m.group(1)) if m else None


def _gtest_case_count(binary_candidates: tuple[Path, ...], gtest_filter: str) -> int | None:
    binary = _find_binary(binary_candidates)
    if binary is None:
        return None
    proc = _run([str(binary), f"--gtest_filter={gtest_filter}", "--gtest_list_tests"])
    out = proc.stdout or ""
    # gtest_list_tests prints one "SuiteName." header line then one
    # indented "  CaseName" line per case -- count only the indented lines.
    return sum(1 for line in out.splitlines() if line.startswith("  ") and not line.startswith("   "))


def measure_row(row_n: int) -> dict:
    row = next(r for r in ROWS if r.n == row_n)
    py_paths = tuple(c for c in row.corpus if c.endswith(".py"))
    retiring_cpp = _ROW_CPP_FILTER.get(row_n)
    survivor_cpp = _ROW_SURVIVOR_CPP_FILTER.get(row_n)

    retiring_count = _pytest_case_count(py_paths) if row_n != 4 else _gtest_case_count(*_ROW_CPP_FILTER[4])
    if retiring_cpp and row_n != 4:
        cpp_n = _gtest_case_count(*retiring_cpp)
        if cpp_n is not None:
            retiring_count = (retiring_count or 0) + cpp_n

    if survivor_cpp:
        survivor_count = _gtest_case_count(*survivor_cpp)
    else:
        survivor_count = _pytest_case_count(py_paths)

    return {
        "row": row_n,
        "capability": row.capability,
        "metric": "test_case_count",
        "retiring_count": retiring_count,
        "survivor_count": survivor_count,
    }


def write_baseline(path: Path = BASELINE_PATH) -> dict:
    rows = [measure_row(r.n) for r in ROWS]
    provenance = measure_provenance()
    payload = {
        "provenance": {
            "platform": provenance.platform, "shell": provenance.shell, "cpu": provenance.cpu,
            "build_type": provenance.build_type, "python": provenance.python,
        },
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def check_against_baseline(path: Path = BASELINE_PATH) -> list[str]:
    """WP-16's own call, made now so the mechanism exists before it is
    needed. Returns a list of findings -- empty means no regression."""
    if not path.is_file():
        return [f"no baseline at {path} -- run --write-baseline first (this is WP-15a's own exit condition)"]
    baseline = json.loads(path.read_text(encoding="utf-8"))
    findings: list[str] = []
    for entry in baseline["rows"]:
        row_n = entry["row"]
        baseline_survivor = entry["survivor_count"]
        if baseline_survivor is None:
            continue
        fresh = measure_row(row_n)
        fresh_survivor = fresh["survivor_count"]
        if fresh_survivor is None:
            findings.append(f"row {row_n} ({entry['capability']}): survivor no longer measurable (binary/corpus missing)")
        elif fresh_survivor < baseline_survivor:
            findings.append(
                f"row {row_n} ({entry['capability']}): survivor coverage decreased "
                f"{baseline_survivor} -> {fresh_survivor}"
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--check" in argv:
        findings = check_against_baseline()
        for f in findings:
            print(f)
        if findings:
            print(f"{len(findings)} coverage regression(s) -- ANL-SW-09 fails the build")
            return 1
        print("check_coverage_delta --check: no regression against baseline")
        return 0

    # Default (and --write-baseline): establish/refresh the baseline. Real
    # today, ahead of WP-16, per this script's own file-header contract.
    payload = write_baseline()
    print(f"wrote {BASELINE_PATH}")
    for entry in payload["rows"]:
        print(f"  row {entry['row']} ({entry['capability']}): retiring={entry['retiring_count']} survivor={entry['survivor_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
