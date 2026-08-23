# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D4's "a source emits camera stimulus, declared through `emits()`" box
(`sim_implementation_plan.md`): the one half of "camera/radar" that has a
real consumer to prove it against today. `perception-core`'s own real,
compiled `perception_core_sil.dll` declares an input port `frame`,
`adas.isp.ProcessedFrame` -- "the project's first genuinely BULK port"
(`conf/ports.yaml`'s own comment). **Radar is deliberately not attempted**:
no real component declares a radar-shaped input port anywhere in this repo
yet, so a radar stimulus test would have nothing to validate the wiring
against -- exactly the "asserts whatever the code happens to do" shape a review warned this class of work is prone to. Camera stays a
real, falsifiable claim; radar would not be.

`SyntheticSource` (`S-C2`) already IS a general-purpose emitter -- its
`emits()` is the union of whatever port names a caller's script declares
(`sources/synthetic.py`), so no new `Source` implementation is needed. What
was NOT proven before this test: that a source's declared `frame`/`egoDyn`
ports are genuinely usable against a REAL component's REAL declared input
-- `Pipeline.load`'s wiring validation checks the port NAME exists in
`emits()`, but never checked that the BYTES flowing through actually
survive to the recording unmodified. This test proves both, using message
classes built from the DLL's OWN `descriptor_set` (`R-SIM-11` -- no
generated bindings, no `interfaces` import here).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from adas_sim.resolve.component import resolve_message_classes
from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import build_manifest
from adas_sim.plugins.registry import reader_for
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource
from adas_sim.config.scenario import (
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
PERCEPTION_CORE_ROOT = MODULES_ROOT / "perception-core"

_DLL_DIR = MODULES_ROOT.parent / "ws" / "perception-core-base-sil-vs2026" / "src" / "platform" / "perception_core_sil" / "Release"
_CONFIG_PATH = PERCEPTION_CORE_ROOT / "tests" / "fixtures" / "perception_core_params_test.yaml"

_SKIP_REASON = (
    "needs a real perception_core_sil.dll build here (scripts/build.py perception-core -t sil -p vs2026 -P base) "
    "and modules/perception-core/tests/fixtures/perception_core_params_test.yaml"
)


@pytest.fixture(autouse=True)
def _require_real_environment():
    if sys.platform != "win32":
        pytest.skip("Windows-only build path (perception_core_sil.dll)")
    if not (_DLL_DIR / "perception_core_sil.dll").is_file():
        pytest.skip(f"{_SKIP_REASON}: perception_core_sil.dll not found at {_DLL_DIR}")
    if not _CONFIG_PATH.is_file():
        pytest.skip(f"{_SKIP_REASON}: {_CONFIG_PATH} not found")


def _write_pipeline(path: Path) -> None:
    path.write_text(
        "version: 1\n"
        "name: camera_source\n"
        "stages:\n"
        "  - name: perception_core\n"
        "    mode: simulate\n"
        '    impl: "dll:perception_core_sil"\n'
        "    inputs:\n"
        "      frame: source.frame\n"
        "      egoDyn: source.egoDyn\n",
        encoding="utf-8",
    )


def _open_scenario_kwargs() -> Scenario:
    return Scenario(
        schema=2, id="t", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def test_a_source_emitting_camera_stimulus_reaches_a_real_component_and_records_round_trip(tmp_path):
    """The claim: a source can genuinely emit `adas.isp.ProcessedFrame`
    camera stimulus, `Pipeline.load` validates it against a real
    component's real declared `frame` input, the real DLL executes against
    it without error, and the recorded bytes decode back to EXACTLY what
    was scripted -- not merely non-empty, but byte-for-byte the frame this
    tick actually carried (would fail if the wiring silently dropped,
    truncated, or misrouted the payload)."""
    pipeline_path = tmp_path / "pipeline.yaml"
    _write_pipeline(pipeline_path)

    # A throwaway Pipeline just to resolve message classes from the real
    # manifest -- discarded before init (message resolution needs no
    # adasInit).
    probe_pipeline = Pipeline.load(pipeline_path, search=[_DLL_DIR])
    manifest = probe_pipeline.manifest_for("perception_core")
    classes = resolve_message_classes(manifest)
    ProcessedFrame = classes["adas.isp.ProcessedFrame"]
    VehDyn = classes["adas.common.VehDyn"]

    # Three ticks, each with DISTINCT frame/egoDyn content -- a bug that
    # returned tick 0's bytes on every later tick would still pass a
    # weaker "non-empty" assertion but fails this one.
    widths = (8, 16, 24)
    velocities = (1.0, 2.5, 9.9)
    script = []
    for width, velocity in zip(widths, velocities):
        frame = ProcessedFrame(
            width=width, height=4, channels=3, format=1,  # FORMAT_RGB8
            pixel_data=bytes(range(width % 256)) * 3,
        )
        veh_dyn = VehDyn()
        veh_dyn.longitudinal.velocity = velocity
        script.append({"frame": frame.SerializeToString(), "egoDyn": veh_dyn.SerializeToString()})

    source = SyntheticSource(script)
    assert source.emits() == {"frame", "egoDyn"}

    pipeline = Pipeline.load(pipeline_path, search=[_DLL_DIR], source=source)
    pipeline.init_components(_CONFIG_PATH)
    try:
        recording_path = tmp_path / "camera_source.mcap"
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=pipeline_path, run_kind="sim", source_kind="synthetic",
        )
        recorder = Recorder(pipeline, source, recording_path, meta=meta)
        recorder.open(_open_scenario_kwargs())
        for _ in script:
            recorder.tick(50_000_000)
        recorder.close()
    finally:
        pipeline.shutdown_components()

    reader = reader_for(recording_path)
    try:
        topics = reader.topics()
        assert "/source/frame" in topics
        assert "/source/egoDyn" in topics
        frame_payloads = [
            payload for topic, _log_ns, _cap_ns, payload in reader.messages() if topic == "/source/frame"
        ]
        egodyn_payloads = [
            payload for topic, _log_ns, _cap_ns, payload in reader.messages() if topic == "/source/egoDyn"
        ]
    finally:
        reader.close()

    assert len(frame_payloads) == len(widths)
    assert len(egodyn_payloads) == len(velocities)

    for payload, expected_width in zip(frame_payloads, widths):
        decoded = ProcessedFrame()
        decoded.ParseFromString(payload)
        assert decoded.width == expected_width
        assert decoded.pixel_data == bytes(range(expected_width % 256)) * 3

    for payload, expected_velocity in zip(egodyn_payloads, velocities):
        decoded = VehDyn()
        decoded.ParseFromString(payload)
        assert decoded.longitudinal.velocity == pytest.approx(expected_velocity)


def test_a_source_dot_reference_outside_emits_is_a_load_error():
    """`emits()` is genuinely load-validated, not decorative: a pipeline
    naming a `source.<port>` outside what the source declares is refused
    at `Pipeline.load`, never discovered later as a silent absence
    (`R-SIM-10`)."""
    source = SyntheticSource([{"frame": b"\x00"}])
    assert "egoDyn" not in source.emits()

    stages = [{
        "name": "perception_core", "mode": "simulate", "impl": "dll:perception_core_sil",
        "inputs": {"frame": "source.frame", "egoDyn": "source.egoDyn"},
    }]
    with tempfile.TemporaryDirectory() as td:
        pipeline_path = Path(td) / "bad_pipeline.yaml"
        pipeline_path.write_text(
            yaml.safe_dump({"version": 1, "name": "bad", "stages": stages}, sort_keys=False), encoding="utf-8",
        )
        with pytest.raises(AuthoringError, match="egoDyn"):
            Pipeline.load(pipeline_path, search=[_DLL_DIR], source=source)
