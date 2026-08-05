# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-C6 (`R-SIM-24`) unit tests for `scripts/ci_gate.py`'s `sim check`
wiring: `evaluate_sim_check_results` is the pure, testable half of
`_run_sim_check` (`ST-C6-1`/`ST-C6-2`/`ST-C6-5`)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import ci_gate  # noqa: E402


def _result(scenario_id: str, *, skipped=False, passed=True, expectations=None) -> dict:
    return {
        "scenario_id": scenario_id, "skipped": skipped, "passed": passed,
        "expectations": expectations or [],
    }


def _failing_expectation(signal="df.aeb.outputs.ttc_s", expected=1.0, actual=1.3, detail="too late") -> dict:
    return {
        "id": "EXP-1", "doc": "", "signal": signal, "passed": False, "detail": detail,
        "actual_value": None, "actual_time_s": actual, "expected_time_s": expected,
    }


# ---------------------------------------------------------------------------
# ST-C6-1 -- job runs green on the current scenario set.
# ---------------------------------------------------------------------------


def test_all_passing_is_green():
    results = [_result("a"), _result("b"), _result("c", skipped=True, passed=True)]
    ok, detail = ci_gate.evaluate_sim_check_results(results, known_gaps={})
    assert ok is True
    assert "0 failed" in detail


# ---------------------------------------------------------------------------
# ST-C6-2 -- a deliberately broken expectation turns the job red, naming the
# scenario, the signal, and the expected/actual pair.
# ---------------------------------------------------------------------------


def test_unexpected_failure_is_red_and_names_scenario_signal_and_expected_actual():
    results = [_result("a", passed=False, expectations=[_failing_expectation()])]
    ok, detail = ci_gate.evaluate_sim_check_results(results, known_gaps={})
    assert ok is False
    assert "scenario=a" in detail
    assert "signal=df.aeb.outputs.ttc_s" in detail
    assert "expected_time_s=1.0" in detail
    assert "actual_time_s=1.3" in detail


def test_skipped_scenario_never_counts_as_a_failure():
    results = [_result("a", skipped=True, passed=True)]
    ok, _detail = ci_gate.evaluate_sim_check_results(results, known_gaps={})
    assert ok is True


# ---------------------------------------------------------------------------
# ST-C6-5-equivalent for scenarios (mirrors the pytest known_flakes
# discipline `_run_pytest` already applies): a known gap is tolerated,
# reported, and never licenses an unrelated scenario to fail quietly.
# ---------------------------------------------------------------------------


def test_known_gap_is_tolerated_and_reported_not_hidden():
    results = [_result("known_bad", passed=False, expectations=[_failing_expectation()])]
    ok, detail = ci_gate.evaluate_sim_check_results(results, known_gaps={"known_bad": "tracked elsewhere"})
    assert ok is True
    assert "event=known_scenario_gap scenario=known_bad" in detail
    assert "tracked elsewhere" in detail


def test_known_gap_does_not_suppress_a_second_unrelated_failure():
    results = [
        _result("known_bad", passed=False, expectations=[_failing_expectation()]),
        _result("new_regression", passed=False, expectations=[_failing_expectation(signal="df.bsd.outputs.warning")]),
    ]
    ok, detail = ci_gate.evaluate_sim_check_results(results, known_gaps={"known_bad": "tracked elsewhere"})
    assert ok is False
    assert "scenario=new_regression" in detail


def test_stale_known_gap_config_is_reported():
    results = [_result("a")]
    _ok, detail = ci_gate.evaluate_sim_check_results(results, known_gaps={"no_longer_run": "old note"})
    assert "event=stale_scenario_gap_config scenario=no_longer_run" in detail
