# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C0 -- the automatic gate (docs/sim_implementation_plan.md #0a/#S-C0).

One entry point for the three checks a stage already owes: pytest,
scripts/check_invariants.py, docs/py/run_all.py. Invoked identically by hand
and by .github/workflows/sim-ci.yml, so "the job passes" and "this script
exits 0" are the same claim -- there is no second, hand-rolled version of
what the job runs.

    python scripts/ci_gate.py [--since GIT_REF] [--artifact-dir DIR]

Exit code 0 = pass, 1 = fail.

--since restricts the skip decision: if every path changed since GIT_REF is
a document (under docs/ or *.md), pytest and check_invariants.py are skipped
with a named reason -- docs/py/run_all.py always runs regardless, because a
docs commit is fast but never unchecked. Omit --since to always run in full
(the safe default for a local, ad hoc invocation).

The known-flake tolerance and the pytest floor are read from
scripts/ci_gate_config.yaml, not hard-coded here, so bumping the floor after
a genuine test-count increase never touches this file.
"""

from __future__ import annotations

import argparse
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
        print(f"skip reason: docs-only push -- pytest and check_invariants.py skipped, "
              f"docs/py/run_all.py still required")
    else:
        pytest_ok, pytest_detail = _run_pytest(artifact_dir)
        print(pytest_detail)
        ok = ok and pytest_ok

        inv_ok, inv_detail = _run_subprocess_check(
            [sys.executable, "scripts/check_invariants.py"], SIM_ROOT, artifact_dir, "check_invariants.txt"
        )
        print(f"check_invariants.py: {inv_detail}")
        ok = ok and inv_ok

    docs_ok, docs_detail = _run_subprocess_check(
        [sys.executable, "docs/py/run_all.py"], SIM_ROOT, artifact_dir, "run_all.txt"
    )
    print(f"docs/py/run_all.py: {docs_detail}")
    ok = ok and docs_ok

    status = "pass" if ok else "fail"
    print(f"event=ci_gate_result run={run_id} status={status} mode={mode}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
