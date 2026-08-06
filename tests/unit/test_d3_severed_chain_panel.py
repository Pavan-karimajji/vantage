# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D3 slice 5 unit tests (`sim_implementation_plan.md`, `UT-D3-3`):
`PipelinePanelState` acts on a severed chain -- the same fixture topology
`test_d6_severed_chain.py` proved at the engine level
(`upstream(simulate) -> measured(measured) -> downstream(measured)`,
toggling `downstream` back to `simulate`), now driven through the panel's
own `set_mode`/`undo_last_auto_close` surface. `Pipeline.with_mode`/
`severed_chains` are not re-tested here -- this file only proves the panel
delegates to them instead of reimplementing `R-SIM-10`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.view.pipeline_panel import PipelinePanelState


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


def _pre_severed_chain_state(tmp_path: Path) -> tuple[Pipeline, PipelinePanelState]:
    upstream = _manifest(component="upstream", outputs=[PortSpec(name="out", proto_type="test.A")])
    measured = _manifest(
        component="measured", inputs=[PortSpec(name="in", proto_type="test.A")],
        outputs=[PortSpec(name="out", proto_type="test.B")],
    )
    downstream = _manifest(component="downstream", inputs=[PortSpec(name="in", proto_type="test.B")])
    stages = [
        {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}},
        {"name": "measured", "mode": "measured", "impl": "stub:measured", "inputs": {"in": "upstream.out"}},
        {"name": "downstream", "mode": "measured", "impl": "stub:downstream", "inputs": {"in": "measured.out"}},
    ]
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "test", "stages": stages}, sort_keys=False), encoding="utf-8")
    pipeline = Pipeline.load(path, components={
        "upstream": _stub("upstream", upstream), "measured": _stub("measured", measured),
        "downstream": _stub("downstream", downstream),
    })
    return pipeline, PipelinePanelState(pipeline, known_ports=frozenset())


def test_setting_mode_auto_closes_the_gap_and_names_what_it_flipped(tmp_path):
    _pipeline, state = _pre_severed_chain_state(tmp_path)
    assert state.severed_chains() == ()
    assert state.last_auto_closed == ()

    state.set_mode("downstream", "simulate")  # would sever upstream -> measured -> downstream

    views = {v.name: v for v in state.stages()}
    assert views["measured"].mode == "simulate"  # auto-closed -- the intervening stage, not the one toggled
    assert views["downstream"].mode == "simulate"
    assert not views["measured"].orphan  # gap is closed -- nothing to badge
    assert state.severed_chains() == ()
    assert state.last_auto_closed == ("measured",)
    assert state.mode_overrides == {"measured": "simulate", "downstream": "simulate"}


def test_undo_forces_the_gap_back_open_and_badges_the_orphan_stage(tmp_path):
    _pipeline, state = _pre_severed_chain_state(tmp_path)
    state.set_mode("downstream", "simulate")
    assert state.last_auto_closed == ("measured",)

    state.undo_last_auto_close()

    views = {v.name: v for v in state.stages()}
    assert views["measured"].mode == "measured"  # reverted to its pre-toggle mode
    assert views["downstream"].mode == "simulate"  # the actual toggle still stands
    assert views["measured"].orphan is True  # UT-D3-3: badged "computed, not consumed"
    assert views["upstream"].orphan is False
    assert views["downstream"].orphan is False
    assert state.severed_chains() != ()
    assert state.last_auto_closed == ()  # nothing left to undo
    # measured never explicitly toggled by the caller, but it did move --
    # still belongs in the run manifest (UT-D3-4's own contract).
    assert state.mode_overrides == {"downstream": "simulate"}


def test_a_toggle_that_severs_nothing_leaves_last_auto_closed_empty(tmp_path):
    _pipeline, state = _pre_severed_chain_state(tmp_path)

    state.set_mode("upstream", "off")  # the very start of the chain -- cannot strand anything

    assert state.last_auto_closed == ()
    assert state.severed_chains() == ()
