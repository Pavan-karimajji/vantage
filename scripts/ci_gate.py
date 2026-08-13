# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C0 -- the automatic gate (docs/sim_implementation_plan.md #0a/#S-C0).

One entry point for the checks a stage already owes: pytest,
scripts/check_invariants.py, scripts/check_headers.py,
scripts/check_closed_sets.py, scripts/check_no_duplication.py,
scripts/check_artifact_kinds.py, scripts/check_trace.py. Invoked identically
by hand and by .github/workflows/sim-ci.yml, so "the job passes" and "this
script exits 0" are the same claim -- there is no second, hand-rolled
version of what the job runs.

    python scripts/ci_gate.py [--since GIT_REF] [--artifact-dir DIR]

Exit code 0 = pass, 1 = fail.

--since restricts the skip decision: if every path changed since GIT_REF is
a document (under docs/ or *.md), pytest and the WP-01 harness checks are
skipped with a named reason -- scripts/check_trace.py always runs
regardless, because a docs commit is fast but never unchecked. Omit --since
to always run in full (the safe default for a local, ad hoc invocation).

**`docs/py/run_all.py` (v1) is no longer wired in here.** It scans
`docs/sim_*.md`, superseded by `docs/v2/` (`modules/sim/CLAUDE.md`'s own
"known-red since the v1/v2 restructure" note); `scripts/check_trace.py`
is its v2 replacement and is what this gate treats as authoritative
(WP-01 item, per that same CLAUDE.md pointer: "repointing or retiring the
v1 checks is a WP-01 item" -- retired, not repointed, because `docs/v1/`
is frozen evidence, never an authority, and its five sub-checks would
otherwise duplicate what `trace_check.py` already does correctly for v2).

The known-flake tolerance and the pytest floor are read from
scripts/ci_gate_config.yaml, not hard-coded here, so bumping the floor after
a genuine test-count increase never touches this file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "ci_gate_config.yaml"

# S-C6: the real scenario set S-C3 built. One path, not a CLI flag -- the
# gate always checks the same set a local `sim check` would, so "the job
# passes" and "this script exits 0" stay one claim (this file's own opening
# comment, extended from pytest to the scenario set). `ST-C3-1`: this is the
# real path that loads all 18 scenarios under v2 -- no dedicated test
# duplicates the load, this run against the real files IS the proof.
DF_SCENARIO_SET = SIM_ROOT.parent / "df" / "tests" / "carla_scenarios"
_DF_SIL_SEARCH_DIRS = [
    SIM_ROOT.parent / "df" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release",
    SIM_ROOT.parent / "df" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Debug",
    SIM_ROOT.parent / "df" / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Release",
    SIM_ROOT.parent / "df" / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Debug",
]


def _run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]


def _changed_paths(since: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", since, "HEAD"],
        cwd=SIM_ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        # Can't resolve the ref (e.g. shallow clone, first commit) -- fail
        # open to "full", never silently skip real checks.
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _is_docs_only(paths: list[str]) -> bool:
    return bool(paths) and all(p.startswith("docs/") or p.endswith(".md") for p in paths)


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _run_pytest(artifact_dir: Path) -> tuple[bool, str]:
    """Returns (ok, detail_line). Writes junit xml + stdout into artifact_dir."""
    junit_path = artifact_dir / "pytest-junit.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", f"--junit-xml={junit_path}"],
        cwd=SIM_ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    (artifact_dir / "pytest-stdout.txt").write_text(
        proc.stdout + proc.stderr, encoding="utf-8", newline="\n"
    )

    config = _load_config()
    floor = int(config["pytest_floor"]["count"])
    flake_notes = {f["id"]: f["note"] for f in config.get("known_flakes", [])}
    known_flakes = set(flake_notes)

    suite = ET.parse(junit_path).getroot()
    if suite.tag != "testsuite":
        suite = suite.find("testsuite")
    total = int(suite.get("tests", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))

    failed_ids, collected_ids = [], []
    for case in suite.iter("testcase"):
        test_id = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}"
        collected_ids.append(test_id)
        if case.find("failure") is not None or case.find("error") is not None:
            failed_ids.append(test_id)

    unexpected = [f for f in failed_ids if f not in known_flakes]
    tolerated = [f for f in failed_ids if f in known_flakes]
    stale_flakes = [f for f in known_flakes if f not in collected_ids]

    # Denominator excludes every known-flake id (present or not) so the floor
    # comparison is stable regardless of which way the flake landed today --
    # its outcome is never held against, or credited to, the count.
    denominator = total - len(known_flakes)
    passed = denominator - errors - skipped - len(unexpected)

    lines = [f"pytest: {total} collected, {passed} counted toward floor (floor={floor})"]
    for f in tolerated:
        lines.append(f"event=known_flake test={f} note={flake_notes[f]!r} -- tolerated, not hidden")
    for f in stale_flakes:
        lines.append(f"event=stale_flake_config test={f} -- listed as a known flake but was not collected this run")
    for f in unexpected:
        lines.append(f"event=unexpected_failure test={f}")

    if unexpected:
        return False, "\n".join(lines)
    if passed < floor:
        lines.append(f"event=pytest_floor_regressed passed={passed} floor={floor}")
        return False, "\n".join(lines)
    return True, "\n".join(lines)


def _find_df_sil() -> Path | None:
    lib_name = "df_sil.dll" if sys.platform == "win32" else "libdf_sil.so"
    for d in _DF_SIL_SEARCH_DIRS:
        if (d / lib_name).is_file():
            return d
    return None


def _first_failing_expectation(result: dict) -> dict | None:
    for expectation in result.get("expectations", []):
        if not expectation["passed"]:
            return expectation
    return None


def evaluate_sim_check_results(results: list[dict], known_gaps: dict[str, str]) -> tuple[bool, str]:
    """The pure, testable half of `_run_sim_check`: given `sim check`'s own
    parsed JSON report (`check.report.format_report_json`'s shape) and the
    `known_scenario_gaps` mapping, decides pass/fail exactly like
    `_run_pytest`'s `known_flakes` handling does for pytest ids -- a
    tolerated scenario is reported, never hidden, and never licenses any
    OTHER scenario to fail quietly (`ST-C6-2`). An unexpected failure names
    the scenario, its first failing expectation's signal, and the expected/
    actual pair -- not just an id, so the failure is diagnosable from the
    gate's own log alone."""
    failed = [r["scenario_id"] for r in results if not r["skipped"] and not r["passed"]]
    unexpected = [s for s in failed if s not in known_gaps]
    tolerated = [s for s in failed if s in known_gaps]
    stale_gaps = [s for s in known_gaps if s not in {r["scenario_id"] for r in results}]
    by_id = {r["scenario_id"]: r for r in results}

    lines = [f"sim check: {len(results)} scenario(s), {len(failed)} failed ({len(tolerated)} known, {len(unexpected)} unexpected)"]
    for s in tolerated:
        lines.append(f"event=known_scenario_gap scenario={s} note={known_gaps[s]!r} -- tolerated, not hidden")
    for s in stale_gaps:
        lines.append(f"event=stale_scenario_gap_config scenario={s} -- listed as a known gap but not in this run")
    for s in unexpected:
        expectation = _first_failing_expectation(by_id[s])
        detail = (
            f"signal={expectation['signal']} expected_time_s={expectation['expected_time_s']} "
            f"actual_time_s={expectation['actual_time_s']} detail={expectation['detail']!r}"
            if expectation is not None else "(no expectation detail available)"
        )
        lines.append(f"event=unexpected_scenario_failure scenario={s} {detail}")

    return not unexpected, "\n".join(lines)


def _run_sim_check(artifact_dir: Path) -> tuple[bool, str]:
    """S-C6's own stated purpose: `sim check <scenario-set>` on every push.
    Skipped, with a named reason, when no component library is built here
    (today's ubuntu-only CI runner, before a C++ toolchain job exists --
    `plan.md` item 20's scope, deliberately not grown into by this stage) --
    that keeps the repo green for a docs-only change, and honest otherwise."""
    lib_dir = _find_df_sil()
    if lib_dir is None:
        return True, "sim check: skipped -- no df_sil build found (not built on this runner yet)"
    if not DF_SCENARIO_SET.is_dir():
        return True, f"sim check: skipped -- scenario set not found at {DF_SCENARIO_SET} (partial clone)"

    report_path = artifact_dir / "sim_check_report.json"
    # Not `-m adas_sim.cli`: that runs cli/__init__.py as a script without
    # calling main() (no __main__ guard there -- it is a library entry
    # point, `sim = adas_sim.cli:main`'s console-script target, GT-9's own
    # "the CLI is argument parsing and dispatch only" extended to "and it is
    # invoked the same way a real `sim` install is invoked").
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; from adas_sim.cli import main; sys.exit(main(sys.argv[1:]))",
         "check", str(DF_SCENARIO_SET), "--search", str(lib_dir), "--report", str(report_path)],
        cwd=SIM_ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    (artifact_dir / "sim_check_stdout.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8", newline="\n")

    if not report_path.is_file():
        return False, f"sim check: no report written -- see sim_check_stdout.txt (exit {proc.returncode})"

    results = json.loads(report_path.read_text(encoding="utf-8"))
    config = _load_config()
    gap_notes = {g["id"]: g["note"] for g in config.get("known_scenario_gaps", [])}
    return evaluate_sim_check_results(results, gap_notes)


def _run_subprocess_check(cmd: list[str], cwd: Path, artifact_dir: Path, log_name: str) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    (artifact_dir / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8", newline="\n")
    tail = (proc.stdout or "").strip().splitlines()
    detail = tail[-1] if tail else ""
    return proc.returncode == 0, detail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=None, help="git ref to diff against for the docs-only skip decision")
    parser.add_argument("--artifact-dir", default=None, help="where to write check logs (default: logs/ci_gate/<run_id>)")
    args = parser.parse_args(argv)

    run_id = _run_id()
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else SIM_ROOT / "logs" / "ci_gate" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    docs_only = _is_docs_only(_changed_paths(args.since)) if args.since else False
    mode = "docs_only" if docs_only else "full"

    ok = True
    if docs_only:
        print(f"skip reason: docs-only push -- pytest and the WP-01 harness checks skipped, "
              f"scripts/check_trace.py still required")
    else:
        pytest_ok, pytest_detail = _run_pytest(artifact_dir)
        print(pytest_detail)
        ok = ok and pytest_ok

        for script, log_name in (
            ("scripts/check_invariants.py", "check_invariants.txt"),
            ("scripts/check_headers.py", "check_headers.txt"),
            ("scripts/check_closed_sets.py", "check_closed_sets.txt"),
            ("scripts/check_no_duplication.py", "check_no_duplication.txt"),
            ("scripts/check_artifact_kinds.py", "check_artifact_kinds.txt"),
        ):
            check_ok, check_detail = _run_subprocess_check(
                [sys.executable, script], SIM_ROOT, artifact_dir, log_name
            )
            print(f"{script}: {check_detail}")
            ok = ok and check_ok

        sim_check_ok, sim_check_detail = _run_sim_check(artifact_dir)
        print(sim_check_detail)
        ok = ok and sim_check_ok

    docs_ok, docs_detail = _run_subprocess_check(
        [sys.executable, "scripts/check_trace.py"], SIM_ROOT, artifact_dir, "check_trace.txt"
    )
    print(f"scripts/check_trace.py: {docs_detail}")
    ok = ok and docs_ok

    status = "pass" if ok else "fail"
    print(f"event=ci_gate_result run={run_id} status={status} mode={mode}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
