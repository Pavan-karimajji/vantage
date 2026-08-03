# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`report.md` / `report.json` (`sim_scenarios_and_expectations.md` SS5.4):
one evaluator (`check/expect.py`), three consumers -- the timeline (`S-D6`,
not yet built), `sim check`'s exit code, and this module's report. This
module only formats a `check.runner.ScenarioCheckResult` sequence; it never
re-derives pass/fail, so the report and the exit code can never disagree.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from adas_sim.check.expect import ExpectationResult
from adas_sim.check.runner import ScenarioCheckResult


def _mark(passed: bool) -> str:
    return "✓" if passed else "✗"


def _expectation_line(result: ExpectationResult) -> str:
    return f"  {_mark(result.passed)} {result.id:<10} {result.signal:<32} {result.detail}"


def format_scenario_report(result: ScenarioCheckResult) -> str:
    """One scenario's block -- SS5.4's own example line shape (`N/5 PASS`,
    one `✓`/`✗` line per expectation)."""
    if result.skipped:
        return f"{result.scenario_id:<50} SKIPPED ({result.skip_reason})"
    passed = sum(1 for r in result.results if r.passed)
    total = len(result.results)
    state = "PASS" if passed == total else "FAIL"
    header = f"{result.scenario_id:<50} {passed}/{total} {state}"
    return "\n".join([header, *(_expectation_line(r) for r in result.results)])


def format_report_md(results: Sequence[ScenarioCheckResult]) -> str:
    return "\n\n".join(format_scenario_report(r) for r in results) + "\n"


def _json_safe(value: object) -> object:
    """`ExpectationResult.actual_value` carries whatever a port's field
    resolved to -- a plain scalar in every predicate this vocabulary
    supports today, but never assumed: anything not JSON-native is its
    `repr()`, so a future signal type degrades to a readable string rather
    than a `TypeError` mid-report."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _expectation_json(result: ExpectationResult) -> dict[str, object]:
    return {
        "id": result.id, "doc": result.doc, "signal": result.signal, "passed": result.passed,
        "detail": result.detail, "actual_value": _json_safe(result.actual_value),
        "actual_time_s": result.actual_time_s, "expected_time_s": result.expected_time_s,
    }


def format_report_json(results: Sequence[ScenarioCheckResult]) -> str:
    payload = [
        {
            "scenario_id": r.scenario_id, "scenario_path": str(r.scenario_path),
            "skipped": r.skipped, "skip_reason": r.skip_reason, "passed": r.passed,
            "expectations": [_expectation_json(e) for e in r.results],
        }
        for r in results
    ]
    return json.dumps(payload, indent=2)


def write_report(results: Sequence[ScenarioCheckResult], path: Path) -> None:
    """`.json` by extension, `.md`/anything else as text -- explicit
    newline (`P-4`): a report built on Windows and one built on Linux must
    read identically, or a diff between two CI runs is noise."""
    text = format_report_json(results) if path.suffix == ".json" else format_report_md(results)
    path.write_text(text, encoding="utf-8", newline="\n")


def suite_passed(results: Sequence[ScenarioCheckResult]) -> bool:
    return all(r.passed for r in results)
