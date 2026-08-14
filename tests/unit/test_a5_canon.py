# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-05: IMP-0004/IMP-0012 -- UT-SPC-03, UT-SPC-08."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import InternalError
from adas_sim.runspec.canon import RunSpec, canonical, compute_spec_sha256, diff_line_count, write_run_spec


def _spec(**overrides) -> RunSpec:
    data = {
        "diagnostics": {"cycle_trace": False},
        "schema": "adas.sim.runspec/1.0",
        "run_id": "r1",
        "spec_sha256": "",
        "grid": {"step_ns": 20_000_000},
        "sources": [],
        "stages": [{"name": "aeb", "mode": "simulate"}],
        "mutations": [],
        "order": ["aeb"],
        "coherence": {"verdict": "unknown"},
        "outputs": {},
        "limits": {"exec_timeout_ms": 250},
    }
    data.update(overrides)
    return RunSpec(data=data)


def test_top_level_keys_are_in_the_fixed_declared_order_not_sorted():
    """UT-SPC-03: `schema` must come before `diagnostics` even though 'd' <
    's' -- the top level is design §3.1's own order, never lexicographic."""
    text = canonical(_spec())
    assert text.index('"schema"') < text.index('"diagnostics"')


def test_nested_object_keys_are_sorted():
    text = canonical(_spec())
    assert text.index('"cycle_trace"') >= 0  # only key present, trivially "sorted"
    spec_with_two_keys = _spec(limits={"severity_exit": "error", "exec_timeout_ms": 250})
    text2 = canonical(spec_with_two_keys)
    assert text2.index('"exec_timeout_ms"') < text2.index('"severity_exit"')


def test_arrays_never_sorted():
    """`order` is semantic -- reversing it would silently change meaning,
    so canonical() must never touch array element order."""
    spec = _spec(order=["zzz_last", "aaa_first"])
    text = canonical(spec)
    assert text.index('"zzz_last"') < text.index('"aaa_first"')


def test_float_forbidden_outside_allowed_keys():
    bad = _spec(limits={"exec_timeout_ms": 250.0})
    with pytest.raises(InternalError):
        canonical(bad)


def test_float_allowed_under_operands_factor_offset():
    ok = _spec(mutations=[{"verb": "scale", "operands": [1.1]}])
    canonical(ok)  # no raise


def test_hash_is_computed_with_spec_sha256_blanked_and_is_stable():
    spec = _spec(spec_sha256="stale-value-should-be-ignored")
    sha = compute_spec_sha256(spec)
    again = compute_spec_sha256(_spec(spec_sha256=""))
    assert sha == again
    assert len(sha) == 64


def test_write_run_spec_writes_utf8_lf_and_returns_the_hash(tmp_path):
    path = tmp_path / "spec.json"
    sha = write_run_spec(_spec(), path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert sha in raw.decode("utf-8")


def test_a_one_field_change_produces_a_small_bounded_diff():
    """UT-SPC-08: emits two specs differing in one mode; asserts the diff's
    line count."""
    a = _spec(stages=[{"name": "aeb", "mode": "simulate"}])
    b = _spec(stages=[{"name": "aeb", "mode": "measured"}])
    assert diff_line_count(a, a) == 0
    assert 0 < diff_line_count(a, b) <= 4  # one changed line -> old + new, bounded
