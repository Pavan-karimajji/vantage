# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 `UT-C2-9` (`docs/sim_implementation_plan.md`): "a resim against a
recording whose port manifest differs is a hard error; a differing library
hash is a warning -- the two are not the same severity and must not be
merged." A real, previously-unbuilt gap (not a stale checkbox): `Pipeline.
load`'s own `recording=` parameter cannot make the hard-error claim for a
real resim (it expects bare, non-ingest-mapped topic keys nothing in this
codebase's real CLI ever supplies), and no mechanism at all produced the
warning half before this pass.

`tests.support.resim_for_tests._validate_measured_stages_against_recording`
(`WP-16` moved this here from `core.resim` alongside `resim_pipeline` itself
-- see that module's own docstring) is the hard-error half (a real gap:
`resim_pipeline` used to silently feed an empty `measured` dict for a
missing/mismatched port and produce neutral-looking wrong output with no
symptom). `core.manifest.check_library_provenance` is the warning half,
deliberately the DEFAULT (unconditional) sibling of `--pin-builds`'s opt-in
hard refusal (`UT-D7-9`).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline, Stage
from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning
from adas_sim.runspec.manifest import check_library_provenance
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import writer_for

from tests.support.resim_for_tests import resim_pipeline

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec


def _manifest(*, component: str, outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _measured_pipeline(tmp_path: Path) -> Pipeline:
    manifest = _manifest(component="df", outputs=[PortSpec(name="outputs", proto_type="test.Outputs")])
    stage = Stage(name="df", mode="measured", impl="stub:df", inputs={})
    return Pipeline(name="test", stages=(stage,), version=1, components={"df": _stub("df", manifest)})


def _write_recording(tmp_path: Path, name: str, topics: dict[str, TopicInfo]) -> Path:
    path = tmp_path / f"{name}.mcap"
    writer = writer_for(path)
    writer.open(path, RunManifest(manifest_version=2), topics)
    for topic in topics:
        writer.write(topic, 0, b"", capture_time_ns=0)
    writer.close()
    return path


# ---------------------------------------------------------------------------
# The hard-error half
# ---------------------------------------------------------------------------


def test_resim_refuses_a_measured_stage_missing_from_the_recording_naming_it(tmp_path):
    pipeline = _measured_pipeline(tmp_path)
    recording = _write_recording(tmp_path, "empty", {})

    with pytest.raises(AuthoringError) as exc_info:
        resim_pipeline(pipeline, recording)
    message = str(exc_info.value)
    assert "df" in message
    assert "outputs" in message


def test_resim_refuses_a_schema_mismatch_naming_both_types(tmp_path):
    pipeline = _measured_pipeline(tmp_path)
    recording = _write_recording(tmp_path, "wrong_schema", {
        "df/outputs": TopicInfo(schema_name="test.SomethingElse", provenance=Provenance.SIMULATED),
    })

    with pytest.raises(AuthoringError) as exc_info:
        resim_pipeline(pipeline, recording)
    message = str(exc_info.value)
    assert "test.Outputs" in message
    assert "test.SomethingElse" in message


def test_resim_proceeds_when_the_measured_stage_matches(tmp_path):
    pipeline = _measured_pipeline(tmp_path)
    recording = _write_recording(tmp_path, "matching", {
        "df/outputs": TopicInfo(schema_name="test.Outputs", provenance=Provenance.SIMULATED),
    })

    outputs = resim_pipeline(pipeline, recording)
    assert outputs == [(0, {"df": {"outputs": b""}})]


# ---------------------------------------------------------------------------
# The warning half -- core.manifest.check_library_provenance
# ---------------------------------------------------------------------------


def _pipeline_with_library(tmp_path: Path) -> tuple[Pipeline, Path]:
    lib_path = tmp_path / "fake_lib.bin"
    lib_path.write_bytes(b"stand-in bytes -- component_build_shas only hashes them")
    manifest = _manifest(component="df")
    component = InProcessSilComponent("df", manifest, lambda dt_ns, inputs: {})
    stage = Stage(name="df", mode="simulate", impl="dll:fake", inputs={})
    pipeline = Pipeline(
        name="test", stages=(stage,), version=1, components={"df": component}, library_paths={"df": lib_path},
    )
    return pipeline, lib_path


def _write_meta_only_recording(tmp_path: Path, name: str, *, library_sha256: str) -> Path:
    path = tmp_path / f"{name}.mcap"
    meta = RunManifest(
        manifest_version=2, components=(ComponentBuildInfo(name="df", library_sha256=library_sha256),),
    )
    writer = writer_for(path)
    writer.open(path, meta, {})
    writer.close()
    return path


def test_check_library_provenance_warns_on_a_real_mismatch(tmp_path):
    pipeline, _ = _pipeline_with_library(tmp_path)
    recording = _write_meta_only_recording(tmp_path, "stale", library_sha256="d" * 64)

    with pytest.warns(ProvenanceWarning, match="library_sha256"):
        check_library_provenance(pipeline, recording)


def test_check_library_provenance_is_silent_on_a_match(tmp_path):
    pipeline, _ = _pipeline_with_library(tmp_path)
    current_sha = pipeline.component_build_shas()["df"]
    recording = _write_meta_only_recording(tmp_path, "matching", library_sha256=current_sha)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_library_provenance(pipeline, recording)  # must not raise/warn


def test_check_library_provenance_is_silent_on_an_unknown_recorded_hash(tmp_path):
    """A recording that never recorded a library_sha256 (the overwhelming
    majority made before UT-D7-9) is a missing fact, not a contradicting
    one -- never warned about by default."""
    pipeline, _ = _pipeline_with_library(tmp_path)
    recording = _write_meta_only_recording(tmp_path, "unknown", library_sha256="")

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_library_provenance(pipeline, recording)  # must not raise/warn
