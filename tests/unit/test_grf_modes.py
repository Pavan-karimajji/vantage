# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-21`, `UT-GRF-22`, `UT-GRF-25` (`graph/
modes.py`). Same four-stage chain fixture as `test_grf_coherence.py`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph import coherence, modes
from adas_sim.graph.pipeline import Pipeline, Stage
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec

_CHAIN_NAMES = ("vdy", "perception", "fusion", "aeb")


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _chain_pipeline(tmp_path: Path, modes_: tuple[str, str, str, str]) -> Pipeline:
    stages = []
    components = {}
    for i, (name, mode) in enumerate(zip(_CHAIN_NAMES, modes_)):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": mode, "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    any_measured = "measured" in modes_

    class _FakeRecording:
        def topics(self):
            return {"out": None} if any_measured else {}

    return Pipeline.load(path, components=components, recording=_FakeRecording() if any_measured else None)


# ---------------------------------------------------------------------------
# UT-GRF-21 -- SW-0183: toggle with gap closing on, then off
# ---------------------------------------------------------------------------


def test_toggling_with_close_gaps_on_closes_the_transitive_chain(tmp_path):
    """`vdy`/`perception` start `simulate`, `fusion` is already `measured`,
    `aeb` (`simulate`) consumes `fusion`. Toggling `perception` to
    `measured` too creates exactly `vdy -> perception(measured) ->
    fusion(measured) -> aeb(simulate)` -- the transitive broken case.
    `close_gaps=True` (default) must auto-promote `perception` right back
    to `simulate` to close it, using the transitive fix rather than the
    one-hop scan (which would see nothing to close here)."""
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    toggled = pipeline.with_mode("perception", "measured", close_gaps=True)

    assert toggled.stages[1].mode == "simulate"  # perception was auto-promoted right back
    assert coherence.classify(toggled) == ()


def test_toggling_with_close_gaps_off_leaves_the_gap_and_warns(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "measured", "simulate"))

    with pytest.warns(Warning, match="computed, not consumed"):
        toggled = pipeline.with_mode("perception", "measured", close_gaps=False)

    assert toggled.stages[1].mode == "measured"  # left as requested, not auto-promoted
    findings = coherence.classify(toggled)
    assert len(findings) == 1
    assert findings[0].verdict is coherence.Verdict.BROKEN


def test_with_mode_uses_the_transitive_fix_not_the_one_hop_scan(tmp_path):
    """The exact case Phase 2 proved `severed_chains()` misses:
    `simulate -> measured -> measured -> simulate`, reached here by
    toggling the SECOND stage of an already-measured third stage."""
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    toggled = pipeline.with_mode("perception", "measured", close_gaps=False)
    assert toggled.severed_chains() == ()  # the old one-hop scan still finds nothing
    assert len(coherence.classify(toggled)) == 1  # the transitive fix does


# ---------------------------------------------------------------------------
# UT-GRF-22 -- SW-0184: with_mode returns a new Pipeline, original untouched
# ---------------------------------------------------------------------------


def test_with_mode_does_not_mutate_the_original_pipeline(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    toggled = pipeline.with_mode("perception", "measured", close_gaps=False)

    assert toggled is not pipeline
    assert toggled.stages[1].mode == "measured"
    assert pipeline.stages[1].mode == "simulate"  # untouched


# ---------------------------------------------------------------------------
# UT-GRF-25 -- SW-0400: override mode on one output port
# ---------------------------------------------------------------------------


def test_with_port_mode_overrides_only_the_named_port(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    overridden = modes.with_port_mode(pipeline, "perception", "out", "measured")

    assert overridden.stages[1].port_modes == {"out": "measured"}
    assert overridden.stages[1].mode == "simulate"  # the stage's own mode is untouched
    assert pipeline.stages[1].port_modes == {}  # original untouched


def test_with_port_mode_survives_a_yaml_round_trip(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    overridden = modes.with_port_mode(pipeline, "perception", "out", "measured")

    reloaded_path = tmp_path / "roundtrip.yaml"
    reloaded_path.write_text(overridden.to_yaml(), encoding="utf-8")
    reparsed = Pipeline.parse_stages(reloaded_path)

    assert reparsed[1].port_modes == {"out": "measured"}


def test_with_port_mode_on_an_undeclared_stage_raises():
    manifest = _manifest(component="solo", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = (Stage(name="solo", mode="simulate", impl="stub:solo", inputs={}),)
    pipeline = Pipeline(name="p", stages=stages, version=1, components={"solo": _stub("solo", manifest)})

    with pytest.raises(AuthoringError):
        modes.with_port_mode(pipeline, "nobody", "out", "measured")
