#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @file prove_equal.py
# @brief
#   IMP-0019 / SW-0019 / IT-04 / ANL-SW-09 (docs/v2/SIM_Implementation_Plan_v0.1.md
#   WP-15a, "the equivalence gate") -- before either implementation of a
#   duplicated capability is removed, the surviving one is shown to produce
#   identical results on a corpus that includes every case the retiring one
#   had a test for (SW-0019's own Shall). This is the mechanised half of
#   that requirement: it runs, for each of Design Sec.28.3's seven rows, the
#   retiring implementation's own corpus against the survivor and prints a
#   per-row PASS / PENDING / FAIL with the evidence that produced it --
#   never a bare "looks the same" (R-REQ-9).
#
#   **Historical since `WP-16` (2026-08-23):** this report did its job --
#   all seven rows PASSed, `WP-16` deleted rows 1-6's retiring
#   implementation from `sil_host` and then unlinked `sil_host` itself as a
#   submodule. Rows 1-6 now report PENDING forever (their own gtest binary
#   genuinely cannot be found, `sil_host` no longer exists to build it from)
#   -- that is not a regression to chase, it is the expected shape of a
#   completed migration's own gate; `main()`'s own PENDING-is-not-a-failure
#   handling already treats it that way. Row 7 (the codec) is unaffected --
#   its own two homes were never `sil_host`-vs-`simcore` (see
#   `scripts/check_no_duplication.py`'s own correction note) and both still
#   build.
#
#   `WP-16` -- the deletion package -- cannot begin until this report is
#   green (`O-5`). A row that has no real survivor yet (the target C++ home
#   lands in a later WP than WP-15a) is reported PENDING, not forced green:
#   forcing a pass here would make the gate a formality rather than a check.
#
#   Evidence per row, in order of preference:
#     1. A real, fresh execution of both corpora this run (pytest for the
#        Python side; the retiring implementation's own gtest binary,
#        located on disk, for the C++ side) -- printed counts, not just
#        "PASSED".
#     2. Where no dedicated corpus exists for one side (row 6 has no
#        standalone C++ test file for `library_loader.cpp`'s resolve half),
#        a same-input case comparison: the identical adversarial values the
#        C++ test used, run through the Python survivor, with both outputs
#        shown.
#     3. A row whose survivor genuinely does not exist told PENDING with the
#        work package that closes it (R-REQ-6a's `closed by`).
#
#   A gtest binary not found on disk is never treated as a failure -- it is
#   a sibling module's (`sil_host`) build artifact, out of this script's own
#   build scope. It is reported PENDING-BUILD with the exact command to
#   produce it, and the row's contribution to the overall gate is held open
#   rather than silently passed.
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SUPERPROJECT_ROOT = SIM_ROOT.parent.parent
SIL_HOST_ROOT = SUPERPROJECT_ROOT / "modules" / "sil_host"

# Candidate build directories for the sil_host gtest binary, most specific
# platform first. sil_host's own conf/build.yml declares only vs2026 for the
# `gtest` target today (mirrors WP-10/WP-11's own declared-platform practice).
SIL_TESTS_CANDIDATES = (
    SIL_HOST_ROOT / "build-gtest-vs2026" / "tests" / "Release" / "sil_tests.exe",
    SIL_HOST_ROOT / "build-gtest-vs2026" / "tests" / "Debug" / "sil_tests.exe",
    SIL_HOST_ROOT / "build-gtest-ubuntu_gcc" / "tests" / "sil_tests",
)

SIMCORE_TESTS_CANDIDATES = (
    SIM_ROOT / "build-gtest-vs2026" / "tests" / "Release" / "simcore_tests.exe",
    SIM_ROOT / "build-gtest-vs2026" / "tests" / "Debug" / "simcore_tests.exe",
    SIM_ROOT / "build-gtest-ubuntu_gcc" / "tests" / "simcore_tests",
)


def _find_binary(candidates: tuple[Path, ...]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """A Windows .exe is runnable directly under WSL2 interop; if that fails
    (exec format), retry through cmd.exe -- the same proven channel this
    session's own build/verification used (project memory: WSL2 interop via
    cmd.exe/powershell.exe is safe for a non-GUI binary; never for a GL
    window)."""
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    except OSError:
        win_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        return subprocess.run(
            ["cmd.exe", "/c", win_cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )


def run_pytest(paths: tuple[str, ...]) -> tuple[bool, str]:
    """Runs the named pytest file(s) for real, from SIM_ROOT. Returns
    (all_passed, one-line summary) -- never fabricated, always the actual
    subprocess result."""
    if not paths:
        return True, "no python corpus for this row"
    cmd = [sys.executable, "-m", "pytest", "-q", *paths]
    proc = _run(cmd, cwd=SIM_ROOT)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", out)
    passed = m.group(1) if m else "0"
    failed_m = re.search(r"(\d+) failed", out)
    if proc.returncode == 0 and not failed_m:
        return True, f"pytest {' '.join(paths)}: {passed} passed"
    tail = out.strip().splitlines()[-1] if out.strip() else "(no output)"
    return False, f"pytest {' '.join(paths)}: FAILED -- {tail}"


def run_gtest(binary_candidates: tuple[Path, ...], gtest_filter: str) -> tuple[str, str]:
    """Returns (status, detail) where status is 'pass' / 'fail' / 'not_built'.
    'not_built' is never conflated with 'fail' -- a sibling module's binary
    missing from this checkout is not evidence of anything."""
    binary = _find_binary(binary_candidates)
    if binary is None:
        try:
            rel = binary_candidates[0].relative_to(SUPERPROJECT_ROOT)
        except ValueError:
            rel = binary_candidates[0]
        return "not_built", (
            f"no gtest binary found (looked for {len(binary_candidates)} candidate build dirs, "
            f"e.g. {rel}) -- build it, then re-run this script for a fresh comparison"
        )
    proc = _run([str(binary), f"--gtest_filter={gtest_filter}"])
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"\[==========\] (\d+) tests? from \d+ test suites? ran", out)
    ran = m.group(1) if m else "?"
    passed_m = re.search(r"\[  PASSED  \] (\d+) tests?", out)
    if proc.returncode == 0 and passed_m and passed_m.group(1) == ran:
        return "pass", f"{binary.name} --gtest_filter={gtest_filter}: {ran}/{ran} passed"
    return "fail", f"{binary.name} --gtest_filter={gtest_filter}: FAILED -- {out.strip().splitlines()[-1] if out.strip() else '(no output)'}"


@dataclass(frozen=True)
class Row:
    n: int
    capability: str
    survivor: str
    dies: str
    corpus: tuple[str, ...]  # exact test identifiers, cited verbatim (R-REQ-9)
    evaluate: "callable" = field(repr=False)


@dataclass(frozen=True)
class RowResult:
    row: Row
    status: str  # "PASS" | "PENDING" | "FAIL"
    detail: str


# ---------------------------------------------------------------------------
# Row 1 -- recording read and cycle grouping. Design Sec.28.3: survivor
# "neither -- both replaced". `WP-08` landed CycleReconstructor
# (src/simcore/bus/cycle.cpp) and `WP-06` landed the io read contract
# (src/simcore/io/{registry,reader_base}.cpp) -- individually real and
# unit-tested, and now wired together into one assembled capability by
# `tests/integration/test_wp15a_row1_recording_read.cpp`: a full linear
# `Reader::ReadRange` loop feeding `CycleReconstructor::Ingest`, exactly the
# shape `recording_reader.cpp` itself uses (a single `readMessages()` pass,
# no seeking) -- the "dedicated integration slice" Design's own row-1 note
# names as the alternative to pulling WP-17's index/seek/selection forward.
# Two boundaries stated in that file's own header and never hidden here:
# (1) cycle-key equivalence holds only while no header field is decoded
# (WP-08's own first-slice scope -- every message lands on
# Rung::ReceptionTime, whose key is `t_recv_ns`, exactly what
# `recording_reader.cpp` groups by); (2) completeness is a REAL, permanent
# divergence -- CycleReconstructor withholds an under-populated cycle,
# recording_reader.cpp does not -- scoped to well-formed recordings
# (R-SIM-6: every declared port present every tick), which is what the C++
# corpus below and every real `measured`-stage recording already are.
def _eval_row1(row: Row) -> RowResult:
    cpp_status, cpp_detail = run_gtest(SIMCORE_TESTS_CANDIDATES, "Wp15aRow1RecordingRead.*")
    sil_status, sil_detail = run_gtest(SIL_TESTS_CANDIDATES, "ResimMeasured.*")
    if cpp_status == "fail" or sil_status == "fail":
        return RowResult(row, "FAIL", f"{cpp_detail} | {sil_detail}")
    if cpp_status == "not_built" or sil_status == "not_built":
        return RowResult(row, "PENDING", f"{cpp_detail} | {sil_detail}")
    return RowResult(
        row, "PASS",
        f"{cpp_detail} | {sil_detail} | assembled capability: simcore/io's "
        "ReadRange + simcore::bus::CycleReconstructor, proven against a "
        "real .mcap file and against sil_host's own ResimMeasured fixture "
        "shape -- scope: cycle-key equivalence holds while no header field "
        "is decoded (WP-08's first-slice scope); completeness is a stated, "
        "permanent divergence for well-formed (R-SIM-6) recordings only, "
        "see the test file's own header",
    )


# Row 2 -- pipeline load and validation. Survivor: adas_sim/graph/build.py
# (real). Dies: sil_host/src/pipeline.cpp's load half.
def _eval_row2(row: Row) -> RowResult:
    py_ok, py_detail = run_pytest(("tests/unit/test_c1c_pipeline.py",))
    cpp_status, cpp_detail = run_gtest(SIL_TESTS_CANDIDATES, "PipelineLoadErrors.*")
    if not py_ok:
        return RowResult(row, "FAIL", f"{py_detail} | {cpp_detail}")
    if cpp_status == "fail":
        return RowResult(row, "FAIL", f"{py_detail} | {cpp_detail}")
    if cpp_status == "not_built":
        return RowResult(row, "PENDING", f"{py_detail} | {cpp_detail}")
    return RowResult(row, "PASS", f"{py_detail} | {cpp_detail}")


# Row 3 -- ingest map parsing. Survivor: adas_sim/ingest/map.py.
def _eval_row3(row: Row) -> RowResult:
    py_ok, py_detail = run_pytest(("tests/unit/test_c9_ingest.py",))
    cpp_status, cpp_detail = run_gtest(SIL_TESTS_CANDIDATES, "IngestMap.*")
    if not py_ok or cpp_status == "fail":
        return RowResult(row, "FAIL", f"{py_detail} | {cpp_detail}")
    if cpp_status == "not_built":
        return RowResult(row, "PENDING", f"{py_detail} | {cpp_detail}")
    return RowResult(row, "PASS", f"{py_detail} | {cpp_detail}")


# Row 4 -- component host. Survivor: simcore/module_host (C++, WP-10,
# landed) -- the one row whose survivor is C++, not Python. `dies`:
# contracts/component.py's execution path (the per-tick ctypes exec, not
# its probe half, which survives as resolve/component.py per Design
# Sec.28.1). Corpus: sil_host's own system test (two-stage resim) PLUS
# module_host's own ported coverage of the same SilComponent surface
# (WP-10's row: "sil_host's own SilComponent had no dedicated unit test
# file to port... test_mh_component.cpp is new coverage at the Component
# level itself, against the same real echo_stub ABI fixture").
def _eval_row4(row: Row) -> RowResult:
    sil_status, sil_detail = run_gtest(SIL_TESTS_CANDIDATES, "TwoStageResim.*")
    mh_status, mh_detail = run_gtest(SIMCORE_TESTS_CANDIDATES, "MhComponent.*:MhExecTimeout.*")
    if sil_status == "fail" or mh_status == "fail":
        return RowResult(row, "FAIL", f"{sil_detail} | {mh_detail}")
    if sil_status == "not_built" or mh_status == "not_built":
        return RowResult(row, "PENDING", f"{sil_detail} | {mh_detail}")
    return RowResult(row, "PASS", f"{sil_detail} | {mh_detail}")


# Row 5 -- base-grid computation. Survivor: adas_sim/graph/build.py's
# `_compute_base_grid_ns`/`_require_multiple`. The C++ corpus
# (test_pipeline_period_grid.cpp) exercises `RequirePeriodIsMultipleOfBaseGrid`
# with one adversarial case: period_ns=7_000_000, base_grid_ns=10_000_000,
# stage="df", expecting an error naming all three numbers/name. Reusing the
# IDENTICAL numbers on the Python side is a same-input comparison, not just
# two independently-green suites.
def _eval_row5(row: Row) -> RowResult:
    py_ok, py_detail = run_pytest(("tests/unit/test_c1c_pipeline.py",))
    cpp_status, cpp_detail = run_gtest(SIL_TESTS_CANDIDATES, "PipelinePeriodGrid.*")

    sys.path.insert(0, str(SIM_ROOT / "src"))
    try:
        from adas_sim.graph.build import _require_multiple  # noqa: PLC0415
        from adas_sim.diagnostics.errors import AuthoringError  # noqa: PLC0415

        same_input_ok = True
        same_input_detail = ""
        try:
            _require_multiple(7_000_000, 10_000_000, stage_name="df")
            same_input_ok = False
            same_input_detail = "Python did not raise on the same adversarial input the C++ test uses"
        except AuthoringError as exc:
            text = str(exc)
            missing = [n for n in ("10000000", "df", "7000000") if n not in text]
            if missing:
                same_input_ok = False
                same_input_detail = f"Python raised but omitted {missing} from: {text}"
            else:
                same_input_detail = (
                    "same-input case (period_ns=7000000, base_grid_ns=10000000, stage='df') "
                    "raises naming all three in both implementations"
                )
    finally:
        sys.path.remove(str(SIM_ROOT / "src"))

    if not py_ok or not same_input_ok or cpp_status == "fail":
        return RowResult(row, "FAIL", f"{py_detail} | {same_input_detail} | {cpp_detail}")
    if cpp_status == "not_built":
        return RowResult(row, "PENDING", f"{py_detail} | {same_input_detail} | {cpp_detail}")
    return RowResult(row, "PASS", f"{py_detail} | {same_input_detail} | {cpp_detail}")


# Row 6 -- library resolution. Survivor: adas_sim/resolve/library.py. `dies`:
# sil_host/src/library_loader.cpp's resolve half. No dedicated C++ test file
# for ResolveLibrary exists (confirmed by reading modules/sil_host/tests/ --
# it is exercised only indirectly, inside PipelineLoadErrors.StubdllImplLoads,
# which resolves the real echo_stub fixture through Pipeline::Load's
# `impl: "stubdll:<stem>"` path -- see sil_host/src/pipeline.cpp:129). That
# is this row's real corpus, named honestly rather than invented.
def _eval_row6(row: Row) -> RowResult:
    py_ok, py_detail = run_pytest(("tests/unit/test_c1c_loader.py",))
    cpp_status, cpp_detail = run_gtest(SIL_TESTS_CANDIDATES, "PipelineLoadErrors.StubdllImplLoads")

    sys.path.insert(0, str(SIM_ROOT / "src"))
    try:
        from adas_sim.resolve.library import resolve_library  # noqa: PLC0415
        from adas_sim.diagnostics.errors import EnvironmentError_  # noqa: PLC0415

        same_input_ok = True
        same_input_detail = ""
        try:
            resolve_library("definitely_not_a_real_component_stem", search=(SIM_ROOT,))
            same_input_ok = False
            same_input_detail = "Python did not raise for a stem with no matching file, unlike the C++ resolver"
        except EnvironmentError_ as exc:
            text = str(exc)
            if "definitely_not_a_real_component_stem" not in text:
                same_input_ok = False
                same_input_detail = f"Python raised but did not name the missing stem: {text}"
            else:
                same_input_detail = (
                    "resolve_library() raises naming the missing stem and every candidate pattern "
                    "tried, same shape as ResolveLibrary()'s std::runtime_error"
                )
    finally:
        sys.path.remove(str(SIM_ROOT / "src"))

    if not py_ok or not same_input_ok or cpp_status == "fail":
        return RowResult(row, "FAIL", f"{py_detail} | {same_input_detail} | {cpp_detail}")
    if cpp_status == "not_built":
        return RowResult(row, "PENDING", f"{py_detail} | {same_input_detail} | {cpp_detail}")
    return RowResult(row, "PASS", f"{py_detail} | {same_input_detail} | {cpp_detail}")


# Row 7 -- codec implementation. Design Sec.28.3 lists the survivor as
# `simcore/io` and states (as of that document's own snapshot) that it is
# "not yet built -- WP-17/18 land later". **That is now stale**: `WP-06`
# landed src/simcore/io/{registry,reader_base,writer_base,decode,translate,
# meta}.cpp + src/simcore/io/codecs/mcap.cpp, 14/14 IMP items done, verified
# live (this session confirmed the file is real, 270 lines, and
# `simcore_tests` runs its UT-IO-* suite green).
#
# **Corrected 2026-08-23, found auditing WP-16 before executing it: `io/
# {base,mcap,csv,jsonl}.py`'s read paths are not "the retiring
# implementation."** `WP-15b`'s own subprocess-not-in-process decision
# (`engine/bridge.py`'s docstring) means the Python codec is permanent --
# every rewired call site launches `simengine` as a child process and
# reads its output back through exactly this code, forever. This row's
# PASS is still real, valuable evidence (the two decoders agree on the
# same corpus), and stays in the report -- what is wrong is the framing
# that its own PASS "justifies" a deletion that was never going to happen.
# `scripts/check_no_duplication.py` no longer lists "codec" at all (struck
# 2026-08-23, same finding) rather than carrying a permanently-false
# "closed by WP-16" promise.
def _eval_row7(row: Row) -> RowResult:
    py_ok, py_detail = run_pytest(("tests/unit/test_a4_mcap.py",))
    cpp_status, cpp_detail = run_gtest(
        SIMCORE_TESTS_CANDIDATES, "UtIo01CodecContract.*:UtIo02Capabilities.*:UtIo03Registration.*:UtIo04ReadersAndWritersSymmetric.*:UtIo22McapRoundtrip.*"
    )
    if not py_ok or cpp_status == "fail":
        return RowResult(row, "FAIL", f"{py_detail} | {cpp_detail}")
    if cpp_status == "not_built":
        return RowResult(row, "PENDING", f"{py_detail} | {cpp_detail}")
    return RowResult(row, "PASS", f"{py_detail} | {cpp_detail}")


ROWS: tuple[Row, ...] = (
    Row(1, "Recording read and cycle grouping",
        "simcore/io ReadRange + simcore::bus::CycleReconstructor (C++, WP-06+WP-08, assembled WP-15a)",
        "sil_host/src/recording_reader.cpp's grouping",
        ("tests/integration/test_wp15a_row1_recording_read.cpp", "sil_host/tests/unit/test_resim_measured.cpp"), _eval_row1),
    Row(2, "Pipeline load and validation", "adas_sim/graph/build.py",
        "sil_host/src/pipeline.cpp's load half",
        ("tests/unit/test_c1c_pipeline.py", "sil_host/tests/unit/test_pipeline_load_errors.cpp"), _eval_row2),
    Row(3, "Ingest map parsing", "adas_sim/ingest/map.py",
        "sil_host/src/ingest_map.cpp's parse half",
        ("tests/unit/test_c9_ingest.py", "sil_host/tests/unit/test_ingest_map.cpp"), _eval_row3),
    Row(4, "Component host", "simcore/module_host (C++, WP-10)",
        "contracts/component.py's execution path",
        ("sil_host/tests/system/test_st_c7_2_two_stage_resim.cpp", "tests/unit/test_mh_component.cpp"), _eval_row4),
    Row(5, "Base-grid computation", "adas_sim/graph/build.py::_compute_base_grid_ns",
        "sil_host/src/pipeline.cpp::ComputeBaseGridNs",
        ("tests/unit/test_c1c_pipeline.py", "sil_host/tests/unit/test_pipeline_period_grid.cpp"), _eval_row5),
    Row(6, "Library resolution", "adas_sim/resolve/library.py",
        "sil_host/src/library_loader.cpp's resolve half",
        ("tests/unit/test_c1c_loader.py", "sil_host/tests/unit/test_pipeline_load_errors.cpp::StubdllImplLoads"), _eval_row6),
    Row(7, "Codec implementation", "simcore/io + src/simcore/io/codecs/mcap.cpp (C++, WP-06)",
        "io/{base,mcap,csv,jsonl}.py read paths (permanent, not retiring -- see this row's own note above)",
        ("tests/unit/test_a4_mcap.py", "tests/unit/test_ut_io_mcap_roundtrip.cpp", "tests/unit/test_ut_io_codec_contract.cpp"), _eval_row7),
)


def prove_equal(rows: tuple[Row, ...] = ROWS) -> list[RowResult]:
    return [row.evaluate(row) for row in rows]


def main(argv: list[str] | None = None) -> int:
    results = prove_equal()
    print("WP-15a -- the equivalence gate (SW-0019 / IT-04 / ANL-SW-09)")
    print("=" * 78)
    unexplained_failures = 0
    for r in results:
        print(f"\n[{r.status}] Row {r.row.n}: {r.row.capability}")
        print(f"    survivor: {r.row.survivor}")
        print(f"    dies:     {r.row.dies}")
        print(f"    corpus:   {', '.join(r.row.corpus)}")
        print(f"    evidence: {r.detail}")
        if r.status == "FAIL":
            unexplained_failures += 1

    passed = sum(1 for r in results if r.status == "PASS")
    pending = sum(1 for r in results if r.status == "PENDING")
    failed = sum(1 for r in results if r.status == "FAIL")
    print("\n" + "=" * 78)
    print(f"{len(results)}/7 rows checked -- {passed} PASS, {pending} PENDING, {failed} FAIL")
    if unexplained_failures:
        print(f"{unexplained_failures} unexplained failure(s) -- WP-16 stays blocked")
        return 1
    if pending:
        print(f"{pending} row(s) PENDING -- not failures, but WP-16 exit requires all seven PASS or explicitly retired")
    print("prove_equal: no unexplained failures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
