# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-04` tests: `UT-specasm-01`, `UT-specasm-02`, `UT-selmodel-03`,
`UT-selview-02` (`docs/v2/parity/PARITY_Test_Spec.md` §5.4/5.5).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.graph.build import Pipeline
from adas_sim.launcher.model import Selection
from adas_sim.launcher.write import reproduce_line, to_run_config
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.runspec.canon import RunSpec, canonical, canonical_sources, compute_spec_sha256
from adas_sim.runspec.sources import NamedSource, SourceSet

_STAGE_NAMES = ("stage_a", "stage_b", "stage_c")


def _manifest(*, component: str) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="out", proto_type="test.A"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _model_pipeline(tmp_path: Path, *, filename: str = "pipeline.yaml") -> tuple[Pipeline, dict]:
    stages = []
    components = {}
    for name in _STAGE_NAMES:
        manifest = _manifest(component=name)
        stages.append({"name": name, "mode": "simulate", "impl": f"stub:{name}", "inputs": {}})
        component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
        component.init()
        components[name] = component
    data = {"version": 1, "name": "model3", "stages": stages}
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return Pipeline.load(path, components=components), components


# ---------------------------------------------------------------------------
# 5.4 specasm
# ---------------------------------------------------------------------------


def test_order_of_selection_does_not_matter_ut_specasm_01(tmp_path):
    """UT-specasm-01."""
    a = tmp_path / "a.mcap"
    b = tmp_path / "b.mcap"

    forward = SourceSet(sources={
        "primary": NamedSource(recording=a, default=True),
        "secondary": NamedSource(recording=b),
    }, assignments={"port.x": "secondary", "port.y": "primary"})
    backward = SourceSet(sources={
        "secondary": NamedSource(recording=b),
        "primary": NamedSource(recording=a, default=True),
    }, assignments={"port.y": "primary", "port.x": "secondary"})

    spec_forward = RunSpec(data={"schema": "test", "sources": canonical_sources(forward)})
    spec_backward = RunSpec(data={"schema": "test", "sources": canonical_sources(backward)})

    assert canonical(spec_forward) == canonical(spec_backward)  # .c1


def test_the_hash_is_stable_and_sensitive_ut_specasm_02(tmp_path):
    """UT-specasm-02."""
    sources = SourceSet(sources={"primary": NamedSource(recording=tmp_path / "a.mcap", default=True)})
    spec = RunSpec(data={"schema": "test", "sources": canonical_sources(sources)})

    first = compute_spec_sha256(spec)
    reemitted = RunSpec(data=dict(spec.data))
    second = compute_spec_sha256(reemitted)
    assert first == second  # .c1: re-emission leaves the hash unchanged

    changed_sources = SourceSet(sources={"primary": NamedSource(recording=tmp_path / "b.mcap", default=True)})
    changed_spec = RunSpec(data={"schema": "test", "sources": canonical_sources(changed_sources)})
    assert compute_spec_sha256(changed_spec) != first  # .c2: altering a field changes it


# ---------------------------------------------------------------------------
# 5.5 selmodel / selview
# ---------------------------------------------------------------------------


def test_file_and_memory_yield_the_same_model_ut_selmodel_03(tmp_path):
    """UT-selmodel-03."""
    pipeline, components = _model_pipeline(tmp_path, filename="base.yaml")
    recording = tmp_path / "run.mcap"
    recording.write_bytes(b"")

    in_memory = Selection(base_pipeline=pipeline, project="fx", selected_recording=recording)
    in_memory = in_memory.set_mode("stage_b", "measured")

    written = tmp_path / "written.yaml"
    to_run_config(in_memory, written)
    from_file = Selection.from_spec(written, components=components)

    def _projection(selection: Selection) -> dict:
        pipeline = selection.working_pipeline
        return {
            "modes": {s.name: (s.mode, s.impl) for s in pipeline.stages},
            "project": selection.project,
            "recording": selection.selected_recording,
        }

    assert _projection(in_memory) == _projection(from_file)  # .c1


def test_the_invocation_comes_from_the_model_ut_selview_02(tmp_path):
    """UT-selview-02."""
    pipeline, _ = _model_pipeline(tmp_path)
    selection = Selection(base_pipeline=pipeline)
    baseline = reproduce_line(selection)

    changed = selection.set_mode("stage_a", "measured")
    assert reproduce_line(changed) != baseline  # .c1: model change moves it

    labeled = selection.set_layout("grid")
    assert reproduce_line(labeled) == baseline  # .c2: a label change does not
