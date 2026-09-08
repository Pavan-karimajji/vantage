# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-04` (`launcher/cuts.py`, `SW-0345`).
`F-INDEX`-shaped fixture: hand-written `RecordingIndex`s, no file on disk.

**Plus one case that uses a REAL recording** (bottom of file). Every fixture
above hand-builds its index with the bare port keys `feasible_cuts` matches
on, so none of them could see that `resolve.probe.describe_recording` --
what a launcher actually has -- keys by TOPIC instead. Both halves were
correct and separately tested; the join was not tested at all, and a real
file therefore reported every cut infeasible in silence. That is the gap
these last two cases close."""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.graph.pipeline import Pipeline
from adas_sim.graph.feasible import RecordingIndex, RecordingTopic
from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.launcher.cuts import cuts_for_all, cuts_for_recording
from adas_sim.launcher.model import Selection
from adas_sim.plugins.registry import writer_for
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.resolve.probe import describe_recording


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


# ---------------------------------------------------------------------------
# UT-LNC-04 -- the same claim against a REAL recording, read through the
# producer a launcher actually uses (`describe_recording`). Found live
# 2026-08-28 driving the POC demo: every cut came back infeasible because
# the index is topic-keyed and `feasible_cuts` matches bare port names.
# ---------------------------------------------------------------------------


def _write_recording(path: Path, topics: dict[str, str]) -> Path:
    """A real file, written through the registered codec -- `topics` maps
    canonical topic to proto type."""
    writer = writer_for(path)
    writer.open(
        path, RunManifest(),
        {t: TopicInfo(schema_name=proto, provenance=Provenance.SIMULATED) for t, proto in topics.items()},
    )
    for t_ns in (0, 10_000_000):
        for topic in topics:
            writer.write(topic, t_ns, b"\x01", capture_time_ns=t_ns)
    writer.close()
    return path


def test_a_real_recording_carrying_both_stages_outputs_is_feasible(tmp_path):
    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    recording = _write_recording(
        tmp_path / "real_full.mcap", {"/a/out": "test.A", "/b/out2": "test.B"},
    )

    results = {r.stage: r for r in cuts_for_recording(selection, describe_recording(recording))}

    assert results["a"].feasible is True, results["a"].missing
    assert results["b"].feasible is True, results["b"].missing


def test_a_real_recording_missing_one_stages_output_reports_only_that_stage(tmp_path):
    """The planted violation (`R-REQ-9`): the case above must be able to
    fail, or it proves nothing. Same real-file path, one topic withheld."""
    selection = Selection(base_pipeline=_two_stage_pipeline(tmp_path))
    recording = _write_recording(tmp_path / "real_partial.mcap", {"/a/out": "test.A"})

    results = {r.stage: r for r in cuts_for_recording(selection, describe_recording(recording))}

    assert results["a"].feasible is True, results["a"].missing
    assert results["b"].feasible is False
    assert "out2" in results["b"].missing[0]


def test_one_stages_topic_never_satisfies_another_stages_identically_named_port(tmp_path):
    """Both stages would declare `out` if `b` did; `_bare_keyed` restricts
    each stage to the topics it actually produced, so `/a/out` cannot make
    stage `b` look feasible."""
    data = {
        "version": 1, "name": "two",
        "stages": [
            {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
            {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
        ],
    }
    path = tmp_path / "same_names.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    same = [PortSpec(name="out", proto_type="test.A")]
    comp_a = InProcessSilComponent("a", _manifest(component="a", outputs=same), lambda dt_ns, inputs: {})
    comp_a.init()
    comp_b = InProcessSilComponent("b", _manifest(component="b", outputs=same), lambda dt_ns, inputs: {})
    comp_b.init()
    selection = Selection(base_pipeline=Pipeline.load(path, components={"a": comp_a, "b": comp_b}))
    recording = _write_recording(tmp_path / "only_a.mcap", {"/a/out": "test.A"})

    results = {r.stage: r for r in cuts_for_recording(selection, describe_recording(recording))}

    assert results["a"].feasible is True, results["a"].missing
    assert results["b"].feasible is False, "stage b borrowed stage a's topic"
