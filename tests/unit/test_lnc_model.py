# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-01` (`launcher/model.py::Selection`,
`SW-0341`). Same four-stage chain fixture as `test_grf_coherence.py`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph.build import Pipeline
from adas_sim.launcher.model import Selection
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


def _chain_pipeline(tmp_path: Path) -> Pipeline:
    stages = []
    components = {}
    for i, name in enumerate(_CHAIN_NAMES):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": "simulate", "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return Pipeline.load(path, components=components)


def test_mode_and_impl_are_selected_independently(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    selection = selection.set_mode("perception", "measured")
    selection = selection.set_impl("perception", "stub:perception-v2")

    working = selection.working_pipeline
    perception = next(s for s in working.stages if s.name == "perception")
    assert perception.mode == "measured"
    assert perception.impl == "stub:perception-v2"


def test_setting_mode_never_discards_a_previously_set_impl(tmp_path):
    """`UT-LNC-01`'s own case: set a module `measured`; read whether its
    implementation survived."""
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    selection = selection.set_impl("fusion", "stub:fusion-v2")
    selection = selection.set_mode("fusion", "measured")

    fusion = next(s for s in selection.working_pipeline.stages if s.name == "fusion")
    assert fusion.mode == "measured"
    assert fusion.impl == "stub:fusion-v2"


def test_every_declared_combination_is_reachable(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    for mode in ("simulate", "measured", "off"):
        selection = selection.set_mode("aeb", mode)
        assert next(s for s in selection.working_pipeline.stages if s.name == "aeb").mode == mode


def test_set_mode_on_an_undeclared_stage_raises(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    with pytest.raises(AuthoringError):
        selection.set_mode("nobody", "measured")


def test_set_impl_on_an_undeclared_stage_raises(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    with pytest.raises(AuthoringError):
        selection.set_impl("nobody", "stub:x")


def test_setters_return_a_new_selection_the_original_is_untouched(tmp_path):
    original = Selection(base_pipeline=_chain_pipeline(tmp_path))
    changed = original.set_mode("vdy", "measured")

    assert changed is not original
    assert original.mode_overrides == {}
    assert changed.mode_overrides == {"vdy": "measured"}


def test_adding_recordings_and_a_layout_is_possible_in_the_launcher(tmp_path):
    """`SW-0346`: one screen -- add recordings, pick a layout -- reachable
    purely through `Selection`, with no Qt anywhere in this path."""
    rec_a = tmp_path / "a.mcap"
    rec_b = tmp_path / "b.mcap"
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    selection = selection.add_recording(rec_a).add_recording(rec_b).set_layout("2x2")
    selection = selection.select_recording(rec_b)

    assert selection.recordings == (rec_a, rec_b)
    assert selection.selected_recording == rec_b
    assert selection.layout == "2x2"


def test_selecting_a_recording_never_added_raises(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path))
    with pytest.raises(ValueError):
        selection.select_recording(tmp_path / "never_added.mcap")
