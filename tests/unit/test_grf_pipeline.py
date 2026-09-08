# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-05` (`SW-0167`): the graph is built from
module manifests plus the pipeline's own active stage list, and no file
enumerates a specific processing chain. `ANL-SW-35` (`scripts/
check_invariants.py`) is the static half of the same requirement; this is
the dynamic half -- two pipelines, differing only in their own `stages:`
list, produce differently-ordered/differently-sized `Pipeline.stages`,
proving the result tracks the YAML rather than a literal `graph/pipeline.py`
never has in the first place."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec


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


def _pipeline_from_stage_names(tmp_path: Path, filename: str, stage_names: tuple[str, ...]) -> Pipeline:
    """A chain of `len(stage_names)` stages, each wired to the previous
    one's own output -- `stage_names` is the ONLY thing that varies between
    calls, so a differing result proves the build tracks it."""
    stages = []
    components = {}
    for i, name in enumerate(stage_names):
        inputs = {} if i == 0 else {"in": f"{stage_names[i - 1]}.out"}
        in_ports = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=in_ports, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": "simulate", "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    path = tmp_path / filename
    path.write_text(
        yaml.safe_dump({"version": 1, "name": filename, "stages": stages}, sort_keys=False), encoding="utf-8",
    )
    return Pipeline.load(path, components=components)


def test_ut_grf_05_the_built_graph_tracks_the_manifest_not_a_literal(tmp_path):
    """`UT-GRF-05`: two pipelines built from DIFFERENT stage lists produce
    DIFFERENT `Pipeline.stages` -- reordering/replacing the chain in the
    YAML alone changes the result (`SW-0167`'s own Accept clause: "a
    configuration change only"). A hard-coded chain anywhere in
    `graph/pipeline.py` would make one of these two assertions fail."""
    three_stage = _pipeline_from_stage_names(tmp_path, "three.yaml", ("vdy", "perception", "aeb"))
    assert [s.name for s in three_stage.stages] == ["vdy", "perception", "aeb"]

    reordered = _pipeline_from_stage_names(tmp_path, "reordered.yaml", ("perception", "vdy", "gateway"))
    assert [s.name for s in reordered.stages] == ["perception", "vdy", "gateway"]

    # The two builds share zero stage NAMES in common at index 1/2 (aeb vs.
    # vdy/gateway) -- if `graph/pipeline.py` ever hard-coded a chain, at least
    # one of these two pipelines would have been forced onto it and this
    # would fail.
    assert [s.name for s in three_stage.stages] != [s.name for s in reordered.stages]


# --------------------------------------------------------------------------
# UT-GRF-07 (SW-0169/SYS-0040) -- an unfed required input names every
# candidate considered and why each failed
# --------------------------------------------------------------------------


def _pipeline_yaml(tmp_path: Path, filename: str, stages: list[dict]) -> Path:
    path = tmp_path / filename
    path.write_text(yaml.safe_dump({"version": 1, "name": filename, "stages": stages}, sort_keys=False), encoding="utf-8")
    return path


def test_an_unfed_required_input_names_a_type_matching_earlier_candidate(tmp_path):
    """`IMP-0169`: `a` produces a port whose type matches `b`'s required
    input, but `b`'s own `inputs:` entry for it was never written -- the
    refusal's own message lists `a`'s port as a real candidate, annotated
    "type matches", not just a bare count."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    b_manifest = _manifest(component="b", inputs=[PortSpec(name="in", proto_type="test.Objects")])
    components = {"a": _stub("a", a_manifest), "b": _stub("b", b_manifest)}
    path = _pipeline_yaml(
        tmp_path, "unfed.yaml",
        [
            {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
            {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
        ],
    )

    with pytest.raises(AuthoringError) as exc_info:
        Pipeline.load(path, components=components)

    message = str(exc_info.value)
    assert "candidates considered" in message
    assert "a.objects" in message
    assert "type matches" in message


def test_an_unfed_required_input_names_a_type_mismatched_candidate_with_its_reason(tmp_path):
    """The mismatch case: `a`'s own output exists and is a real candidate,
    but its type differs -- the message says so, naming both types,
    rather than silently omitting a candidate that would not have worked."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="veh_dyn", proto_type="test.VehDyn")])
    b_manifest = _manifest(component="b", inputs=[PortSpec(name="in", proto_type="test.Objects")])
    components = {"a": _stub("a", a_manifest), "b": _stub("b", b_manifest)}
    path = _pipeline_yaml(
        tmp_path, "mismatch.yaml",
        [
            {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
            {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
        ],
    )

    with pytest.raises(AuthoringError) as exc_info:
        Pipeline.load(path, components=components)

    message = str(exc_info.value)
    assert "a.veh_dyn" in message
    assert "test.VehDyn" in message
    assert "test.Objects" in message


def test_an_unfed_required_input_with_no_earlier_stage_says_so_honestly(tmp_path):
    """The first stage in a pipeline has no earlier stage at all -- the
    candidate list is a real, honest "none", never a guessed suggestion."""
    b_manifest = _manifest(component="b", inputs=[PortSpec(name="in", proto_type="test.Objects")])
    components = {"b": _stub("b", b_manifest)}
    path = _pipeline_yaml(tmp_path, "first.yaml", [{"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}}])

    with pytest.raises(AuthoringError, match="no earlier active stage"):
        Pipeline.load(path, components=components)


def test_an_off_stage_is_never_offered_as_a_candidate(tmp_path):
    """An `off` stage never executes -- its own declared outputs are not
    real candidates, and offering one would be a suggestion nobody could
    actually wire successfully (an `off` stage produces nothing)."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    b_manifest = _manifest(component="b", inputs=[PortSpec(name="in", proto_type="test.Objects")])
    components = {"a": _stub("a", a_manifest), "b": _stub("b", b_manifest)}
    path = _pipeline_yaml(
        tmp_path, "off_stage.yaml",
        [
            {"name": "a", "mode": "off", "impl": "stub:a", "inputs": {}},
            {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
        ],
    )

    with pytest.raises(AuthoringError, match="no earlier active stage"):
        Pipeline.load(path, components=components)
