# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `UT-D6-2` unit test (`docs/sim_implementation_plan.md`):
`StageView.overridden` -- the HUD-badge half of "an override is declared,
never smuggled" (`R-SIM-15`), read directly from `Stage.overrides` rather
than from a topic's provenance tag (the design finding this stage records:
an override modifies a CONSUMING stage's own input bytes, but the RECORDED
topic is the PRODUCER's unmodified output, so no topic could legitimately
carry this tag). No Qt -- `view/` stays headless-testable; the real
rendered badge is `tests/system/test_d6_override_badge_widget.py`'s job.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline
from adas_sim.player.panels.pipeline_panel import PipelinePanelState


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _noop(dt_ns, inputs):
    del dt_ns, inputs
    return {}


def _load_pipeline(tmp_path: Path, *, overrides: dict | None = None) -> Pipeline:
    stage = {"name": "df", "mode": "simulate", "impl": "stub:df", "inputs": {"egoDyn": "source.veh_dyn"}}
    if overrides:
        stage["overrides"] = overrides
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="df", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")])
    return Pipeline.load(path, components={"df": InProcessSilComponent("df", manifest, _noop)})


def test_stage_view_is_not_overridden_with_no_declared_override(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset())
    assert state.stages()[0].overridden is False


def test_stage_view_is_overridden_when_the_stage_declares_one(tmp_path):
    pipeline = _load_pipeline(tmp_path, overrides={"egoDyn.vx": {"verb": "const", "value": 5.0}})
    state = PipelinePanelState(pipeline, known_ports=frozenset())
    assert state.stages()[0].overridden is True


def test_overridden_flag_survives_a_mode_toggle(tmp_path):
    """`Stage.overrides` is retained unchanged across `with_mode` (only
    `mode` differs) -- the badge must not silently disappear on a toggle."""
    pipeline = _load_pipeline(tmp_path, overrides={"egoDyn.vx": {"verb": "const", "value": 5.0}})
    state = PipelinePanelState(pipeline, known_ports=frozenset({"df.egoDyn"}))
    state.set_mode("df", "measured")
    assert state.stages()[0].overridden is True
