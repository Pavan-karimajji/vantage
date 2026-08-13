# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `UT-D7-9` unit tests (`docs/sim_implementation_plan.md`, `OQ-9`/
`NR-SIM-24`, `sim_resim_and_recording.md` "Pinning a resim to the build
that produced it"): `Pipeline.component_build_shas` and `core.manifest.
verify_pinned_builds`.

A plain temp file stands in for a resolved library throughout -- both
functions under test hash/compare bytes on disk and never care what is
inside them, so proving the mechanism needs no real `dll:`/`stubdll:`
build (unlike `test_c1c_component.py`, which loads a real `df_sil.dll` to
prove the ABI itself). `Pipeline` is constructed directly (bypassing
`Pipeline.load`'s `ctypes.CDLL` call) with a `components=`-supplied
`InProcessSilComponent` plus an explicit `library_paths=` -- the same
"a components=-supplied stage never sees a file path" split `_resolve_
components` already documents, just driven from the test side instead of
via a real `impl: dll:` load.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent
from adas_sim.graph.build import Pipeline, Stage
from adas_sim.diagnostics.errors import ContractError
from adas_sim.runspec.manifest import verify_pinned_builds
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.plugins.registry import writer_for

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec


def _manifest() -> ComponentManifest:
    return ComponentManifest(
        component="echo", version="test", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _pipeline_with_library(tmp_path: Path, *, mode: str = "simulate") -> tuple[Pipeline, Path]:
    lib_path = tmp_path / "fake_lib.bin"
    lib_path.write_bytes(b"not a real dll -- component_build_shas only hashes bytes on disk")
    component = InProcessSilComponent(name="echo", manifest=_manifest(), fn=lambda dt_ns, inputs: {})
    stage = Stage(name="echo", mode=mode, impl="dll:fake", inputs={})
    pipeline = Pipeline(
        name="test", stages=(stage,), version=1, components={"echo": component}, library_paths={"echo": lib_path},
    )
    return pipeline, lib_path


def _write_recording(tmp_path: Path, name: str, *, library_sha256: str) -> Path:
    path = tmp_path / f"{name}.mcap"
    meta = RunManifest(
        manifest_version=2, run_id="r", run_kind="resim",
        components=(ComponentBuildInfo(name="echo", library_sha256=library_sha256),),
    )
    writer = writer_for(path)
    writer.open(path, meta, {})
    writer.close()
    return path


# ---------------------------------------------------------------------------
# Pipeline.component_build_shas
# ---------------------------------------------------------------------------


def test_component_build_shas_matches_a_direct_hash_of_the_resolved_library(tmp_path):
    pipeline, lib_path = _pipeline_with_library(tmp_path)
    expected = hashlib.sha256(lib_path.read_bytes()).hexdigest()
    assert pipeline.component_build_shas() == {"echo": expected}


def test_component_build_shas_omits_a_components_supplied_stage_with_no_file(tmp_path):
    """A `components=`-supplied stage (a test's `InProcessSilComponent`, or
    a real `stub:` stage once S-C2's registry exists) has no file on disk --
    absent from the result, never an empty-string placeholder (`R-SIM-25`/
    `NR-SIM-4`)."""
    component = InProcessSilComponent(name="echo", manifest=_manifest(), fn=lambda dt_ns, inputs: {})
    stage = Stage(name="echo", mode="simulate", impl=None, inputs={})
    pipeline = Pipeline(name="test", stages=(stage,), version=1, components={"echo": component})
    assert pipeline.component_build_shas() == {}


# ---------------------------------------------------------------------------
# core.manifest.verify_pinned_builds -- UT-D7-9
# ---------------------------------------------------------------------------


def test_pin_builds_passes_when_the_resolved_library_matches_the_recording(tmp_path):
    pipeline, _ = _pipeline_with_library(tmp_path)
    recorded_sha = pipeline.component_build_shas()["echo"]
    recording = _write_recording(tmp_path, "ok", library_sha256=recorded_sha)
    verify_pinned_builds(pipeline, recording)  # must not raise


def test_pin_builds_refuses_on_a_hash_mismatch_naming_both(tmp_path):
    pipeline, _ = _pipeline_with_library(tmp_path)
    current_sha = pipeline.component_build_shas()["echo"]
    stale_sha = "d" * 64
    recording = _write_recording(tmp_path, "mismatch", library_sha256=stale_sha)

    with pytest.raises(ContractError) as exc_info:
        verify_pinned_builds(pipeline, recording)

    message = str(exc_info.value)
    assert stale_sha in message
    assert current_sha in message
    assert "echo" in message


def test_pin_builds_refuses_as_unpinnable_when_the_recording_carries_no_hash(tmp_path):
    """The honest limit is a refusal, not a silent pass: a recording with no
    verifiable `library_sha256` for a stage (predates a real resim of it, or
    predates this manifest field entirely) must not be treated as a match
    (`R-SIM-25`/`NR-SIM-4`)."""
    pipeline, _ = _pipeline_with_library(tmp_path)
    recording = _write_recording(tmp_path, "unpinnable", library_sha256="")

    with pytest.raises(ContractError) as exc_info:
        verify_pinned_builds(pipeline, recording)

    assert "unpinnable" in str(exc_info.value)


def test_pin_builds_skips_a_measured_stage(tmp_path):
    """Only a `mode: simulate` stage executes its OWN library this resim --
    a `measured` stage's bytes come from the recording regardless of
    whichever library is nominally wired to it (`R-SIM-10`), so its build is
    irrelevant to `--pin-builds`. Proven by a recording that WOULD refuse
    (empty `library_sha256`) if the skip did not hold."""
    pipeline, _ = _pipeline_with_library(tmp_path, mode="measured")
    recording = _write_recording(tmp_path, "measured", library_sha256="")
    verify_pinned_builds(pipeline, recording)  # must not raise -- stage is measured, skipped
