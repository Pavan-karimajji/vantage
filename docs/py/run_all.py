# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Run every design-set check and every available survey, and summarise.

This is the command to run before committing a change to the design documents.
Checks must pass; surveys may skip (the artefact they inspect is not on every
machine) but must not fail.

    python docs/py/run_all.py

Exit code is the number of failing scripts, so it can gate a hook.
"""

from __future__ import annotations

import subprocess
import sys

from _common import PY_DIR, Report

#: Ordered deliberately: cheap structural checks first, so a broken document is
#: reported before a multi-second filesystem survey runs.
CHECKS = [
    "check_doc_invariants.py",
    "check_traceability.py",
    "check_rules_coverage.py",
]
SURVEYS = [
    "FR_SIM_46_reference_tool_survey.py",
    "FR_SIM_45_argument_binding_survey.py",
]


def _run(name: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(PY_DIR / name)],
        cwd=PY_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    tail = (proc.stdout or "").strip().splitlines()
    verdict = next((ln for ln in reversed(tail) if ln.startswith("RESULT")), "RESULT  ?")
    return proc.returncode, verdict.replace("RESULT", "").strip()


def main() -> int:
    rep = Report("run_all")
    rep.line("Design-set checks and surveys")

    rows, failures = [], 0
    for kind, names in (("check", CHECKS), ("survey", SURVEYS)):
        for name in names:
            code, verdict = _run(name)
            rows.append([kind, name, verdict, "FAIL" if code else "ok"])
            if code:
                failures += 1
                rep.failures.append(name)

    rep.table(["kind", "script", "result", ""], rows)
    rep.line()
    if failures:
        rep.line(f"{failures} script(s) failed. Individual logs are in "
                 "docs/py/logs/ -- read those, not this summary.")
    else:
        rep.line("All checks pass. Surveys that skipped did so because the "
                 "artefact they inspect is not on this machine, which is not "
                 "a failure (docs/py/README.md).")
    rep.write_log()
    return failures


if __name__ == "__main__":
    sys.exit(main())
