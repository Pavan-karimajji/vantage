# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-01`, `UT-GRF-02`, `UT-GRF-10`, `UT-GRF-11`
(`graph/grid.py`, `graph/build.py`'s relocated grid logic). Fixture style
matches `test_c1c_pipeline.py`'s own (`InProcessSilComponent`, synthetic
components, no DLL)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.graph import grid
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph.build import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec


def _manifest(*, component: str, inputs=(), outputs=(), period_ns: int = 0) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=period_ns,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _write_pipeline(tmp_path: Path, stages: list[dict], *, extra: dict | None = None) -> Path:
    data: dict[str, object] = {"version": 1, "name": "test", "stages": stages, **(extra or {})}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# UT-GRF-01 -- SW-0063: a period not an integer multiple of the derived step
# ---------------------------------------------------------------------------


def test_a_period_not_a_multiple_of_the_derived_step_raises():
    with pytest.raises(AuthoringError) as excinfo:
        grid.check_period_multiples(25_000_000, 10_000_000, stage_name="a")
    message = str(excinfo.value)
    assert "a" in message
    assert "10000000" in message.replace("_", "")


def test_a_period_that_is_a_multiple_of_the_derived_step_does_not_raise():
    grid.check_period_multiples(20_000_000, 10_000_000, stage_name="a")  # must not raise


# ---------------------------------------------------------------------------
# UT-GRF-02 -- SW-0074: a zero-delay cycle is refused; a one-step delay
# (today: no cycle at all, since the wiring grammar cannot express one)
# loads.
# ---------------------------------------------------------------------------


def test_a_same_tick_cycle_is_refused_naming_the_loop():
    with pytest.raises(AuthoringError) as excinfo:
        grid.check_zero_delay_cycles(
            ["a", "b"],
            {"a": {"in": "b.out"}, "b": {"in": "a.out"}},
        )
    message = str(excinfo.value)
    assert "a" in message and "b" in message


def test_a_three_stage_cycle_names_every_member_in_traversal_order():
    with pytest.raises(AuthoringError) as excinfo:
        grid.check_zero_delay_cycles(
            ["a", "b", "c"],
            {"a": {"in": "c.out"}, "b": {"in": "a.out"}, "c": {"in": "b.out"}},
        )
    message = str(excinfo.value)
    for name in ("a", "b", "c"):
        assert name in message


def test_an_acyclic_graph_does_not_raise():
    grid.check_zero_delay_cycles(
        ["a", "b", "c"],
        {"a": {}, "b": {"in": "a.out"}, "c": {"in": "b.out"}},
    )  # must not raise


def test_a_source_fed_stage_is_never_part_of_a_cycle():
    grid.check_zero_delay_cycles(["a"], {"a": {"in": "source.out"}})  # must not raise


def test_pipeline_load_refuses_a_wiring_grammar_that_cannot_express_a_cycle_today(tmp_path):
    """The wiring grammar's own forward-reference check (`build.py::
    _validate_wiring`) already refuses any reference to a stage not
    declared strictly earlier -- so `Pipeline.load` can never reach
    `check_zero_delay_cycles` with an actual cycle. This proves the
    invariant end to end: the load-time refusal fires from the EARLIER,
    more specific forward-reference check, not from a same-tick cycle
    manifesting."""
    a_manifest = _manifest(component="a", inputs=[PortSpec(name="in", proto_type="test.A")])
    b_manifest = _manifest(component="b", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {"in": "b.out"}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages)
    with pytest.raises(AuthoringError):
        Pipeline.load(path, components={"a": _stub("a", a_manifest), "b": _stub("b", b_manifest)})


# ---------------------------------------------------------------------------
# UT-GRF-10 -- SW-0172: the base grid is derived, never configured
# ---------------------------------------------------------------------------


def test_derive_step_is_the_gcd_of_declared_periods():
    assert grid.derive_step([20_000_000, 30_000_000]) == 10_000_000


def test_derive_step_ignores_undeclared_zero_periods():
    assert grid.derive_step([0, 20_000_000, 30_000_000]) == 10_000_000


def test_derive_step_with_no_declared_periods_is_zero():
    assert grid.derive_step([0, 0]) == 0


def test_a_base_grid_key_in_the_pipeline_file_has_no_effect(tmp_path):
    """No configuration key sets the grid (`SW-0172`'s own Accept clause) --
    `Pipeline.load` never reads a `base_grid:` key at all, so one present in
    the file is silently inert rather than refused; the derived value (the
    GCD of the two declared periods) is what actually governs scheduling
    either way."""
    a = _manifest(component="a", period_ns=20_000_000)
    b = _manifest(component="b", period_ns=30_000_000)
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages, extra={"base_grid": 5_000_000})

    pipeline = Pipeline.load(path, components={"a": _stub("a", a), "b": _stub("b", b)})

    assert pipeline.base_grid_ns == 10_000_000


# ---------------------------------------------------------------------------
# UT-GRF-11 -- SW-0173: no snap/tolerance function or schema key exists
# ---------------------------------------------------------------------------


def test_grid_module_declares_no_snap_function():
    assert not hasattr(grid, "snap")
    assert not any(name.lower() == "snap" for name in dir(grid))


def test_grid_module_declares_no_tolerance_constant_or_function():
    assert not any("tolerance" in name.lower() for name in dir(grid))
