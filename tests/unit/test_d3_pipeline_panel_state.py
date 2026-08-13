# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-D3 slice 1 unit tests (`sim_implementation_plan.md`): `UT-D3-1`
(discovery, partial -- stages and impl from the pipeline, not yet the
on-disk manifest scan for alternative impls) and `UT-D3-2` (`measured`
disabled with a reason when the recording lacks the topics). No Qt --
`view/` stays headless-testable, same bar `test_b3_layers.py` sets for
`LayerTreeState`.

In-process components (`InProcessSilComponent`), same reasoning
`test_c2_record_resim.py` gives: no compiled SIL library needed here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline
from adas_sim.player.panels.pipeline_panel import PipelinePanelState


def _manifest(*, component: str, outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


_UPSTREAM_MANIFEST = _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
_DOWNSTREAM_MANIFEST = _manifest(component="downstream", outputs=[PortSpec(name="verdict", proto_type="test.Verdict")])


def _noop(dt_ns, inputs):
    del dt_ns, inputs
    return {}


def _load_pipeline(tmp_path: Path) -> Pipeline:
    path = tmp_path / "d3_fixture.yaml"
    path.write_text(yaml.safe_dump({
        "name": "d3_fixture",
        "stages": [
            {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}},
            {"name": "downstream", "mode": "simulate", "impl": "stub:downstream", "inputs": {}},
        ],
    }, sort_keys=False), encoding="utf-8")
    upstream = InProcessSilComponent("upstream", _UPSTREAM_MANIFEST, _noop)
    upstream.init()
    downstream = InProcessSilComponent("downstream", _DOWNSTREAM_MANIFEST, _noop)
    downstream.init()
    return Pipeline.load(path, components={"upstream": upstream, "downstream": downstream})


def test_ut_d3_1_stages_discovered_from_the_pipeline_with_their_declared_mode_and_impl(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset())

    views = {v.name: v for v in state.stages()}
    assert set(views) == {"upstream", "downstream"}
    assert views["upstream"].mode == "simulate"
    assert views["upstream"].impl == "stub:upstream"


def test_ut_d3_2_measured_disabled_with_a_reason_naming_the_missing_qualified_port_when_absent(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    # Only upstream.objects is in this recording -- downstream.verdict is not.
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects"}))

    views = {v.name: v for v in state.stages()}
    assert views["upstream"].measured_available is True
    assert views["upstream"].measured_unavailable_reason == ""

    assert views["downstream"].measured_available is False
    assert "downstream.verdict" in views["downstream"].measured_unavailable_reason


def test_ut_d3_2_measured_available_when_every_declared_output_is_in_the_recording(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects", "downstream.verdict"}))

    views = {v.name: v for v in state.stages()}
    assert views["downstream"].measured_available is True
    assert views["downstream"].measured_unavailable_reason == ""


def test_flipping_mode_never_discards_impl(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects", "downstream.verdict"}))

    state.set_mode("upstream", "measured")
    view = {v.name: v for v in state.stages()}["upstream"]
    assert view.mode == "measured"
    assert view.impl == "stub:upstream"  # unchanged, still there to flip back to

    state.set_mode("upstream", "simulate")
    view = {v.name: v for v in state.stages()}["upstream"]
    assert view.mode == "simulate"
    assert view.impl == "stub:upstream"


def test_setting_measured_on_a_stage_the_recording_cannot_satisfy_raises(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset())  # nothing available

    with pytest.raises(ValueError, match="downstream"):
        state.set_mode("downstream", "measured")


def test_an_invalid_mode_string_raises(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset())

    with pytest.raises(ValueError, match="mode must be one of"):
        state.set_mode("upstream", "not_a_real_mode")
