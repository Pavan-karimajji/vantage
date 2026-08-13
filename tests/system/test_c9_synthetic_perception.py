# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ST-C9-2` (`docs/sim_implementation_plan.md`, `R-SIM-23`, `FR-SIM-66`):
"dimension 2, proven with a second shape" -- every other S-C9 test drives
`df`'s own real `carla_legacy.yaml` ingest map (an object-list-shaped
recording). This is the OTHER axis: a synthetic recording carrying a
DIFFERENT stage's raw topics (perception-shaped, no `df`-style objects at
all) drives a real two-stage pipeline with the perception stage `measured`
and a consumer stage `simulate`, using only its own ingest map -- proving
the ingest mechanism generalises to an arbitrary depth-2 cut, not just the
one family every other test happens to exercise.

Deliberately synthetic (no real perception-core recording exists yet, the
plan's own scope note) -- says so in the test's own name, never disguised
as a real fixture. Drives the REAL `core.resim.resim_pipeline` (the exact
function `cli/resim.py`/`sim resim` calls), with `discover_ingest_maps`
monkeypatched to this test's own in-memory `IngestMap` -- the mechanism
under test is `IngestRecordingReader`/`resim_pipeline`, not the real
filesystem scan `S-C9`'s own docstring already covers via `df`'s checked-in
`carla_legacy.yaml`, and a synthetic, framework-agnostic component
("perception") has no real ingest map on disk to write one for."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline
from adas_sim.core.resim import resim_pipeline
from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.ingest.map import IngestMap, ProvidedPort
from adas_sim.plugins.registry import writer_for

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

_PROTO_TYPE = "test.perception.Objects"


def _write_synthetic_perception_recording(path: Path, *, tick_count: int) -> None:
    """One raw topic, `perception/raw_objects` -- deliberately NOT already
    shaped like `<stage>.<port>` (the ingest map's whole job is closing
    that gap). Each tick's payload is a distinct byte, so a test can tell
    "the recorded value for THIS tick" apart from any other tick's."""
    writer = writer_for(path)
    writer.open(path, RunManifest(), {
        "perception/raw_objects": TopicInfo(schema_name=_PROTO_TYPE, provenance=Provenance.UNKNOWN),
    })
    for i in range(1, tick_count + 1):
        writer.write("perception/raw_objects", i * 50_000_000, bytes([i]))
    writer.close()


def _perception_consumer_pipeline(tmp_path: Path) -> tuple[Pipeline, list[bytes | None]]:
    perception_manifest = ComponentManifest(
        component="perception", version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="objects", proto_type=_PROTO_TYPE),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    consumer_manifest = ComponentManifest(
        component="consumer", version="1", abi_version=1, build_id="test",
        inputs=(PortSpec(name="in", proto_type=_PROTO_TYPE),), outputs=(),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )

    received: list[bytes | None] = []

    def consumer_fn(dt_ns: int, inputs: dict) -> dict:
        del dt_ns
        received.append(inputs.get("in"))
        return {}

    perception = InProcessSilComponent("perception", perception_manifest, lambda dt_ns, inputs: {})
    consumer = InProcessSilComponent("consumer", consumer_manifest, consumer_fn)
    perception.init()
    consumer.init()

    pipeline_path = tmp_path / "perception_consumer.yaml"
    pipeline_path.write_text(
        "version: 1\n"
        "name: perception_consumer\n"
        "stages:\n"
        "  - name: perception\n"
        "    mode: measured\n"
        "    impl: \"stub:perception\"\n"
        "  - name: consumer\n"
        "    mode: simulate\n"
        "    impl: \"stub:consumer\"\n"
        "    inputs:\n"
        "      in: perception.objects\n",
        encoding="utf-8",
    )
    pipeline = Pipeline.load(pipeline_path, components={"perception": perception, "consumer": consumer})
    return pipeline, received


def test_synthetic_perception_recording_drives_a_two_stage_pipeline_through_its_own_ingest_map(tmp_path, monkeypatch):
    ingest_map = IngestMap(
        family="test.perception_synthetic",
        match_any_topic=frozenset({"perception/raw_objects"}),
        provides=(
            ProvidedPort(
                topic="perception/raw_objects", port="perception.objects", manifest_port="objects",
                proto_type=_PROTO_TYPE, origin=Provenance.MEASURED, family="test.perception_synthetic",
            ),
        ),
        absent=(),
        path=Path("<synthetic, in-memory -- ST-C9-2 test fixture, no real component owns this>"),
    )
    monkeypatch.setattr("adas_sim.core.resim.discover_ingest_maps", lambda: (ingest_map,))

    recording_path = tmp_path / "synthetic_perception.mcap"
    _write_synthetic_perception_recording(recording_path, tick_count=3)

    pipeline, received = _perception_consumer_pipeline(tmp_path)
    results = resim_pipeline(pipeline, recording_path)

    assert len(results) == 3
    # The consumer's real input, for every tick, IS the recording's own
    # per-tick byte -- proof the measured injection travelled through the
    # ingest map's rename (raw topic -> perception.objects) into a real
    # `mode: simulate` stage's own exec() call, not just into the outer
    # `outputs` dict `resim_pipeline` returns.
    assert received == [bytes([1]), bytes([2]), bytes([3])]
    for _t_ns, outputs in results:
        assert "perception" in outputs  # the measured stage's own recorded output is still reported


def test_synthetic_perception_recording_reports_the_measured_cut_as_feasible(tmp_path, monkeypatch):
    """The `R-SIM-23` query half (`Session.feasible_cuts`, `CR-SIM-21`
    "becoming a query instead of an assertion") over the SAME synthetic
    family: the perception stage's declared output IS in the recording
    via the ingest map, so `sim probe`/the Bench start page would report
    its cut feasible -- the same fact `resim_pipeline` above acted on,
    now asked as a question rather than exercised as a run."""
    from adas_sim.core.runner import build_session_from_recording

    ingest_map = IngestMap(
        family="test.perception_synthetic",
        match_any_topic=frozenset({"perception/raw_objects"}),
        provides=(
            ProvidedPort(
                topic="perception/raw_objects", port="perception.objects", manifest_port="objects",
                proto_type=_PROTO_TYPE, origin=Provenance.MEASURED, family="test.perception_synthetic",
            ),
        ),
        absent=(),
        path=Path("<synthetic, in-memory -- ST-C9-2 test fixture>"),
    )
    monkeypatch.setattr("adas_sim.core.runner.discover_ingest_maps", lambda: (ingest_map,))

    recording_path = tmp_path / "synthetic_perception_probe.mcap"
    _write_synthetic_perception_recording(recording_path, tick_count=1)

    pipeline, _received = _perception_consumer_pipeline(tmp_path)
    session = build_session_from_recording(recording_path)
    cuts = {cut.stage: cut for cut in session.feasible_cuts(pipeline)}

    assert cuts["perception"].feasible is True
    assert cuts["perception"].missing == ()
