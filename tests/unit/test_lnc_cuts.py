# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-04` (`launcher/cuts.py`, `SW-0345`).
`F-INDEX`-shaped fixture: hand-written `RecordingIndex`s, no file on disk."""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.graph.build import Pipeline
from adas_sim.graph.feasible import RecordingIndex, RecordingTopic
from adas_sim.launcher.cuts import cuts_for_all, cuts_for_recording
from adas_sim.launcher.model import Selection
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec


def _manifest(*, component: str, outputs) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _two_stage_pipeline(tmp_path: Path) -> Pipeline:
    data = {
        "version": 1, "name": "two",
        "stages": [
            {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
            {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
        ],
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    comp_a = InProcessSilComponent(
        "a", _manifest(component="a", outputs=[PortSpec(name="out", proto_type="test.A")]), lambda dt_ns, inputs: {},
    )
    comp_a.init()
    comp_b = InProcessSilComponent(
        "b", _manifest(component="b", outputs=[PortSpec(name="out2", proto_type="test.B")]), lambda dt_ns, inputs: {},
    )
    comp_b.init()
    return Pipeline.load(path, components={"a": comp_a, "b": comp_b})


# ---------------------------------------------------------------------------
# UT-LNC-04 -- SW-0345: per recording, which stages could be measured
# ---------------------------------------------------------------------------


def test_a_recording_carrying_both_topics_makes_both_stages_feasible(tmp_path):
    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    index = RecordingIndex(topics={
        "out": RecordingTopic(proto_type="test.A"),
        "out2": RecordingTopic(proto_type="test.B"),
    })

    results = {r.stage: r for r in cuts_for_recording(selection, index)}
    assert results["a"].feasible is True
    assert results["b"].feasible is True


def test_a_recording_missing_one_topic_reports_only_that_stage_infeasible(tmp_path):
    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    index = RecordingIndex(
        topics={"out": RecordingTopic(proto_type="test.A")},
        absent={"out2": "this family never records stage b's output"},
    )

    results = {r.stage: r for r in cuts_for_recording(selection, index)}
    assert results["a"].feasible is True
    assert results["b"].feasible is False
    assert "this family never records stage b's output" in results["b"].missing[0]


def test_cuts_for_all_reports_per_recording(tmp_path):
    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    full = RecordingIndex(topics={
        "out": RecordingTopic(proto_type="test.A"), "out2": RecordingTopic(proto_type="test.B"),
    })
    partial = RecordingIndex(topics={"out": RecordingTopic(proto_type="test.A")})
    rec_full = tmp_path / "full.mcap"
    rec_partial = tmp_path / "partial.mcap"

    per_recording = cuts_for_all(selection, {rec_full: full, rec_partial: partial})

    assert all(r.feasible for r in per_recording[rec_full])
    assert not all(r.feasible for r in per_recording[rec_partial])


def test_the_set_shown_equals_what_is_computed_headlessly(tmp_path):
    """`SW-0345`'s own `Accept`: the launcher is a second caller, never a
    second implementation -- compared directly against `graph.feasible.
    feasible_cuts` on the same inputs."""
    from adas_sim.graph.feasible import ModuleManifest, feasible_cuts

    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    index = RecordingIndex(topics={"out": RecordingTopic(proto_type="test.A")})

    via_launcher = cuts_for_recording(selection, index)
    pipeline = selection.working_pipeline
    manifests = {s.name: ModuleManifest(name=s.name, outputs=pipeline.manifest_for(s.name).outputs) for s in pipeline.stages}
    via_graph = feasible_cuts(index, manifests)

    assert via_launcher == via_graph
