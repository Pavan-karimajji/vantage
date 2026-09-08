# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-22` `SI-14 runspec` -- `UT-SPC-09` through `UT-SPC-22` covering
`runspec/manifest.py`'s own WP-22 additions: `write_manifest` (standalone,
atomic, zero-exporter-capable), the coherence/divergence/outcome/
delay_steps fields (`IMP-0224`/`IMP-0222`/`IMP-0402`), the tolerance hash
(`IMP-0226`) and the published, version-gated schema (`IMP-0228`).

`UT-SPC-01`..`08`/`23`/`24` (`WP-05`, `runspec/emit.py`) and `UT-SPC-11`/
`12`/`14` (already `DONE` before this `WP`, covered by `core/determinism.py`
and `tests/unit/test_c2_manifest.py`) are out of this file's own scope."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import ContractError
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.runspec.manifest import (
    RUN_MANIFEST_FILENAME,
    build_manifest,
    check_manifest_version,
    validate_manifest,
    write_manifest,
)
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION, manifest_from_dict, manifest_to_dict

_CLOCK = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


#: The same `vdy -> perception -> fusion -> aeb` `F-CHAIN4` shape
#: `test_grf_coherence.py` uses -- reused here rather than re-invented, so
#: this file's own broken-chain case is provably the same fixture the
#: coherence package itself was tested against.
_CHAIN_NAMES = ("vdy", "perception", "fusion", "aeb")


def _chain_pipeline(tmp_path: Path, modes: tuple[str, str, str, str]) -> Pipeline:
    stages = []
    components = {}
    for i, (name, mode) in enumerate(zip(_CHAIN_NAMES, modes)):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": mode, "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    any_measured = "measured" in modes

    class _FakeRecording:
        def topics(self):
            return {"out": None} if any_measured else {}

    return Pipeline.load(path, components=components, recording=_FakeRecording() if any_measured else None)


def _simple_pipeline(tmp_path: Path) -> Pipeline:
    stage = {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {}}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="under_test", outputs=[PortSpec(name="out", proto_type="test.A")])
    return Pipeline.load(path, components={"under_test": _stub("under_test", manifest)})


# ---------------------------------------------------------------------------
# UT-SPC-09 -- SW-0215: every run produces a machine-readable manifest
# ---------------------------------------------------------------------------


def test_write_manifest_produces_a_readable_json_file(tmp_path):
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    out_dir = tmp_path / "run"
    path = write_manifest(manifest, out_dir)
    assert path == out_dir / RUN_MANIFEST_FILENAME
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_kind"] == "sim"
    assert data["manifest_version"] == CAPTURE_TIME_MANIFEST_VERSION


# ---------------------------------------------------------------------------
# UT-SPC-13 -- SW-0220: an unfillable field reads "unknown", never a guess
# ---------------------------------------------------------------------------


def test_coherence_and_divergence_read_unknown_with_no_pipeline():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.coherence_verdict == "unknown"
    assert manifest.coherence_findings == ()
    assert manifest.divergence == "unknown"


# ---------------------------------------------------------------------------
# UT-SPC-15 -- SW-0222: a manifest is written for every one of the four
# outcomes, carrying the outcome and the last completed cycle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", ["completed", "failed", "crashed", "timeout"])
def test_manifest_carries_every_outcome(tmp_path, outcome):
    manifest = build_manifest(
        run_kind="sim", source_kind="synthetic", clock=_CLOCK,
        outcome=outcome, last_completed_cycle=7,
    )
    assert manifest.outcome == outcome
    assert manifest.last_completed_cycle == 7
    path = write_manifest(manifest, tmp_path / outcome)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["outcome"] == outcome
    assert data["last_completed_cycle"] == 7


def test_cancelled_is_recorded_distinctly_from_outcome():
    """`IMP-0235`: `cancelled` is a real field alongside `outcome`, never a
    fifth `outcome` value (`R-SIM-19`) -- `outcome` stays one of the closed
    four ("failed" for a cancelled run) and `cancelled=True` is the fact a
    reader checks separately, same distinguish-by-field pattern
    `orchestrate/batch.py::RecordingOutcome.cancelled`/`limit_breach`
    already use at the batch-report layer."""
    manifest = build_manifest(
        run_kind="resim", source_kind="mcap", clock=_CLOCK, outcome="failed", cancelled=True,
    )
    assert manifest.outcome == "failed"
    assert manifest.cancelled is True
    data = manifest_to_dict(manifest)
    assert data["cancelled"] is True
    restored = manifest_from_dict(data)
    assert restored.cancelled is True

    default = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert default.cancelled is False


def test_read_error_and_reset_policy_round_trip():
    """`IMP-0252`/`IMP-0253`/`IMP-0251`: `read_error`/`read_retry_attempts`/
    `reset_mode`/`reset_when` all round-trip the same way `cancelled` does
    above -- one more instance of the distinguish-by-field pattern, not a
    special case."""
    manifest = build_manifest(
        run_kind="resim", source_kind="mcap", clock=_CLOCK, outcome="failed",
        read_error="abort_batch", read_retry_attempts=3, reset_mode="reset_init", reset_when="entry",
    )
    assert manifest.read_error == "abort_batch"
    assert manifest.read_retry_attempts == 3
    assert manifest.reset_mode == "reset_init"
    assert manifest.reset_when == "entry"
    data = manifest_to_dict(manifest)
    restored = manifest_from_dict(data)
    assert restored.read_error == "abort_batch"
    assert restored.read_retry_attempts == 3
    assert restored.reset_mode == "reset_init"
    assert restored.reset_when == "entry"

    default = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert default.read_error == ""
    assert default.read_retry_attempts == 0
    assert default.reset_mode == ""
    assert default.reset_when == ""


def test_error_kind_round_trips():
    """`IMP-0128`: one more instance of the same distinguish-by-field
    pattern `cancelled`/`read_error`/`reset_mode` already use."""
    manifest = build_manifest(run_kind="resim", source_kind="mcap", clock=_CLOCK, outcome="failed", error_kind="contract")
    assert manifest.error_kind == "contract"
    restored = manifest_from_dict(manifest_to_dict(manifest))
    assert restored.error_kind == "contract"

    default = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert default.error_kind == ""


def test_skipped_packages_round_trips():
    """`IMP-0252`: one more instance of the same distinguish-by-field
    pattern `cancelled`/`read_error`/`error_kind` already use -- a run that
    skipped damaged mcap chunks under `ReadError.SKIP_PACKAGE` carries the
    count, never conflated with a clean run's default `0`."""
    manifest = build_manifest(run_kind="resim", source_kind="mcap", clock=_CLOCK, skipped_packages=2)
    assert manifest.skipped_packages == 2
    restored = manifest_from_dict(manifest_to_dict(manifest))
    assert restored.skipped_packages == 2

    default = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert default.skipped_packages == 0


# ---------------------------------------------------------------------------
# UT-SPC-16 -- SW-0223: a run with zero exporters still writes a manifest
# ---------------------------------------------------------------------------


def test_write_manifest_needs_no_recorder_or_exporter(tmp_path):
    """`build_manifest`/`write_manifest` never touch a `Recorder` or any
    exporter -- calling them with no pipeline and no recording (the
    "nothing was produced" case) still leaves a complete manifest as the
    directory's only content."""
    out_dir = tmp_path / "run"
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    write_manifest(manifest, out_dir)
    assert [p.name for p in out_dir.iterdir()] == [RUN_MANIFEST_FILENAME]


# ---------------------------------------------------------------------------
# UT-SPC-17 -- SW-0224: coherence classification and divergence point
# ---------------------------------------------------------------------------


def test_manifest_carries_the_broken_coherence_classification(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    manifest = build_manifest(pipeline=pipeline, pipeline_path=None, run_kind="resim", source_kind="mcap", clock=_CLOCK)
    assert manifest.coherence_verdict == "broken"
    assert len(manifest.coherence_findings) == 1
    assert "aeb" in manifest.coherence_findings[0]


def test_manifest_carries_the_normal_coherence_classification(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    manifest = build_manifest(pipeline=pipeline, pipeline_path=None, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.coherence_verdict == "normal"
    assert manifest.coherence_findings == ()


def test_manifest_carries_a_supplied_divergence_point():
    manifest = build_manifest(run_kind="resim", source_kind="mcap", clock=_CLOCK, divergence="tick=42,stage=aeb,port=out")
    assert manifest.divergence == "tick=42,stage=aeb,port=out"


# ---------------------------------------------------------------------------
# UT-SPC-19 -- SW-0226: the tolerance declaration's hash is in the manifest
# ---------------------------------------------------------------------------


def test_manifest_carries_per_component_tolerance_hash(tmp_path):
    pipeline = _simple_pipeline(tmp_path)
    manifest = build_manifest(
        pipeline=pipeline, pipeline_path=None, run_kind="sim", source_kind="synthetic", clock=_CLOCK,
        component_tolerance_shas={"under_test": "deadbeef"},
    )
    assert manifest.components[0].tolerance_sha256 == "deadbeef"


def test_manifest_tolerance_hash_is_empty_when_not_supplied(tmp_path):
    pipeline = _simple_pipeline(tmp_path)
    manifest = build_manifest(pipeline=pipeline, pipeline_path=None, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.components[0].tolerance_sha256 == ""


# ---------------------------------------------------------------------------
# UT-SPC-20 -- SW-0227: the manifest is written atomically
# ---------------------------------------------------------------------------


def test_interrupted_write_never_leaves_a_partial_manifest(tmp_path, monkeypatch):
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    original = (out_dir / RUN_MANIFEST_FILENAME)
    original.write_text('{"run_id": "previous"}', encoding="utf-8")

    def _boom(*_a, **_k):
        raise OSError("simulated interruption between tmp write and replace")

    import adas_sim.runspec.manifest as manifest_module
    monkeypatch.setattr(manifest_module.os, "replace", _boom)

    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    with pytest.raises(OSError):
        write_manifest(manifest, out_dir)

    # The reader-visible file is untouched -- either the previous manifest
    # or nothing, never a truncated write-in-progress one.
    assert json.loads(original.read_text(encoding="utf-8")) == {"run_id": "previous"}


# ---------------------------------------------------------------------------
# UT-SPC-21 -- SW-0228: the manifest schema is versioned and published
# ---------------------------------------------------------------------------


def test_validate_manifest_accepts_a_real_manifest():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    validate_manifest(manifest)  # raises on failure


def test_check_manifest_version_refuses_outside_the_supported_range_naming_both():
    with pytest.raises(ContractError) as exc_info:
        check_manifest_version({"manifest_version": 99})
    message = str(exc_info.value)
    assert "99" in message
    assert str(CAPTURE_TIME_MANIFEST_VERSION) in message


def test_check_manifest_version_accepts_the_supported_range():
    check_manifest_version({"manifest_version": CAPTURE_TIME_MANIFEST_VERSION})  # raises on failure


# ---------------------------------------------------------------------------
# UT-SPC-22 -- SW-0402: the per-edge delay_steps map in force
# ---------------------------------------------------------------------------


def test_manifest_carries_a_delay_steps_entry_per_wired_edge(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    manifest = build_manifest(pipeline=pipeline, pipeline_path=None, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    edges = {d.edge: d.delay_steps for d in manifest.delay_steps}
    # vdy has no inputs; the other three each wire one "in" port.
    assert edges == {"perception.in": 0, "fusion.in": 0, "aeb.in": 0}


def test_manifest_delay_steps_is_empty_with_no_pipeline():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.delay_steps == ()


# ---------------------------------------------------------------------------
# IT-16 (partial) -- SW-0216: the resolved spec's hash travels with the
# manifest, the one piece reachable without a real engine run in this pass
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# UT-SPC-10 -- SW-0217: every artifact embeds the manifest (dict round trip,
# the shape both `io/mcap.py` and `io/jsonl.py` embed through)
# ---------------------------------------------------------------------------


def test_new_wp22_fields_round_trip_through_the_shared_dict_codec(tmp_path):
    from adas_sim.io.base import manifest_from_dict

    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    manifest = build_manifest(
        pipeline=pipeline, pipeline_path=None, run_kind="resim", source_kind="mcap", clock=_CLOCK,
        component_tolerance_shas={"vdy": "tol123"}, run_spec_sha256="spec456",
        divergence="tick=9", outcome="failed", last_completed_cycle=3,
    )
    restored = manifest_from_dict(manifest_to_dict(manifest))
    assert restored.coherence_verdict == "broken"
    assert restored.coherence_findings == manifest.coherence_findings
    assert restored.divergence == "tick=9"
    assert restored.outcome == "failed"
    assert restored.last_completed_cycle == 3
    assert restored.run_spec_sha256 == "spec456"
    assert restored.delay_steps == manifest.delay_steps
    assert restored.components[0].tolerance_sha256 == "tol123"
    assert restored.grid_step_ns == manifest.grid_step_ns
    assert restored.components[0].period_ns == manifest.components[0].period_ns


def test_manifest_carries_the_grid_step_and_per_component_period(tmp_path):
    pipeline = _simple_pipeline(tmp_path)
    manifest = build_manifest(pipeline=pipeline, pipeline_path=None, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    # `_manifest()`'s own fixture components all declare `period_ns=0`
    # (undeclared -- runs every base-grid tick), so the derived grid is `0`
    # too (`grid.derive_step`'s own "no declared periods -> no grid").
    assert manifest.components[0].period_ns == 0
    assert manifest.grid_step_ns == 0


def test_manifest_carries_the_run_spec_hash():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK, run_spec_sha256="abc123")
    assert manifest.run_spec_sha256 == "abc123"
    data = manifest_to_dict(manifest)
    assert data["run_spec_sha256"] == "abc123"
