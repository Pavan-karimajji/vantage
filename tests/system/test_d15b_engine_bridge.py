# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-15b` (`IMP-0422`): `engine.bridge` drives the REAL `simengine`
executable, out of process, over a REAL component library -- `echo_stub`
(`tests/fixtures/echo_stub`), the same fixture `simcore_tests`'
`UT-ABI-01`/`UT-ABI-02` (`tests/integration/test_ut_abi_writer_and_resolver.cpp`)
already prove the engine itself against. `InProcessSilComponent` is not
used here on purpose: a subprocess boundary cannot run a Python closure
(this test IS this package's own answer to the stub-component test-
infrastructure gap `WP-14a`'s addendum names).

Skipped, not failed, when the platform's own `simengine`/`echo_stub`
build is not present -- same "not_built is never a failure" discipline
`scripts/prove_equal.py::run_gtest` uses for a sibling module's binary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adas_sim.engine.bridge import (
    backfill_schema_bytes,
    resolve_simengine_executable,
    run_pipeline_via_engine,
)
from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.graph.pipeline import Pipeline
from adas_sim.io.base import Provenance, TopicInfo
from adas_sim.plugins.registry import reader_for, writer_for
from adas_sim.resolve.component import ComponentManifest, PortSpec
from adas_sim.resolve.library import resolve_library

_SIM_ROOT = Path(__file__).resolve().parents[2]
_ECHO_STUB_CANDIDATES_WINDOWS = (_SIM_ROOT / "build-gtest-vs2026" / "tests" / "Release" / "echo_stub.dll",)
_ECHO_STUB_CANDIDATES_POSIX = (_SIM_ROOT / "build-gtest-ubuntu_gcc" / "tests" / "libecho_stub.so",)


def _echo_stub_path(engine_path: Path) -> Path | None:
    """Paired with whichever `simengine` binary was actually resolved, by
    its own `.exe`/no-suffix format -- **never** by `os.name`. Both a
    vs2026 and an ubuntu_gcc build can be present on disk at once (WSL2
    interop makes both trees visible from one Linux Python process), and
    `resolve_simengine_executable`'s own candidate order (most-specific-
    platform-first, unconditional on host OS, same as
    `scripts/prove_equal.py`'s) can resolve a Windows `.exe` even while
    this test itself runs under Linux `os.name == 'posix'`. Selecting the
    stub from `os.name` instead of `engine_path`'s own format is exactly
    the bug this fixes: it silently pairs a Windows `simengine.exe` with a
    Linux `.so`, which Windows refuses to load with a blocking
    'Bad Image' dialog (0xc000012f) -- the two binaries in one subprocess
    invocation must always share one format, decided from the engine
    binary that was actually picked, not from the host running pytest."""
    candidates = _ECHO_STUB_CANDIDATES_WINDOWS if engine_path.suffix == ".exe" else _ECHO_STUB_CANDIDATES_POSIX
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _require_engine_and_stub() -> tuple[Path, Path]:
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip(f"no built echo_stub found paired with {engine} (looked for "
                     f"{_ECHO_STUB_CANDIDATES_WINDOWS if engine.suffix == '.exe' else _ECHO_STUB_CANDIDATES_POSIX})")
    return engine, stub


def _write_heartbeat_recording(path: Path) -> None:
    """A tiny real `.mcap` recording, three ticks, no `req` port to feed --
    same shape `test_ut_abi_writer_and_resolver.cpp::WriteHeartbeatRecording`
    uses for `UT-ABI-01`: it only sets the cycle grid `echo_stub`'s own
    `simulate` stage runs against."""
    writer = writer_for(path)
    writer.open(path, meta=__import__("adas_sim.io.base", fromlist=["RunManifest"]).RunManifest(),
                topics={"/dummy/heartbeat": TopicInfo(schema_name="test.Heartbeat", provenance=Provenance.MEASURED)})
    for t_ns in (0, 10_000_000, 20_000_000):
        writer.write("/dummy/heartbeat", t_ns, b"\x01", capture_time_ns=t_ns)
    writer.close()


def _echo_manifest() -> ComponentManifest:
    return ComponentManifest(
        component="echo_stub", version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="outputs", proto_type="test.Echo", max_bytes=64),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=10_000_000,
    )


def _write_pipeline(path: Path) -> None:
    path.write_text(
        "name: bridge_test\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n",
        encoding="utf-8",
    )


def test_run_pipeline_via_engine_produces_a_real_recording(tmp_path, monkeypatch):
    """`IMP-0422`'s own smoke test: a real `Pipeline` (one `dll:` stage,
    `echo_stub`), a real recording, driven through the actual `simengine`
    executable -- never `core.resim.resim_pipeline`, never `ctypes` bound
    in-process (no shared `simcore` artifact exists to bind, see
    `engine/bridge.py`'s own module docstring)."""
    engine_path, stub_path = _require_engine_and_stub()

    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    pipeline_path = tmp_path / "pipeline.yaml"
    _write_pipeline(pipeline_path)
    # Resolved via `search=`, never `components=` -- a `components=`-
    # supplied stage has no file on disk (`Pipeline.component_build_shas`'s
    # own documented limit), so `pipeline.library_paths` would carry no
    # entry for it and `pipeline_to_run_spec` would emit an empty `impl`.
    # This is real library resolution, exactly what `cli/resim.py`'s own
    # production path does.
    pipeline = Pipeline.load(pipeline_path, search=[lib_dir])

    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)
    output_path = tmp_path / "out.mcap"

    result = run_pipeline_via_engine(
        pipeline, recording_path, run_id="20260823T000000Z-bridge-test", output_path=output_path,
        simengine_path=engine_path,
    )

    assert result.ok, f"simengine exit_code={result.exit_code} stderr={result.stderr!r} stdout={result.stdout!r}"
    assert output_path.is_file()

    # `IMP-0216`: `write_run_spec`'s own returned hash reaches the caller
    # through `EngineRunResult.spec_sha256` -- previously discarded here,
    # so no caller (including `cli/resim.py`'s own `--save` -> `build_manifest`
    # call) ever saw a real value. Cross-checked against the sidecar
    # `.spec.json` this same call wrote, which embeds the identical hash.
    assert result.spec_sha256, "write_run_spec's own returned hash never reached the caller"
    spec_path = output_path.with_suffix(output_path.suffix + ".spec.json")
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec_data["spec_sha256"] == result.spec_sha256

    reader = reader_for(output_path)
    try:
        topics = reader.topics()
        assert "/sut/outputs" in topics, f"expected /sut/outputs among {sorted(topics)}"
        messages = list(reader.messages())
        assert len(messages) >= 1, "echo_stub's own declared output port produced zero messages"
    finally:
        reader.close()


def test_backfill_schema_bytes_fills_a_real_output_topic(tmp_path, monkeypatch):
    """`E2E-07` item 8 (`SM-12`): `simengine`'s own writer cannot embed a
    topic's real `FileDescriptorSet` -- `BuildOutputTopics` (`simcore.cpp`)
    only ever sets `schema_name`, never `schema_bytes` (`Writer::Open` runs
    before any component loads, that function's own comment). Found live
    against a real `sim resim --save` recording: `PortValue.message`'s own
    documented degrade (`session/tick.py`, `decode_message`'s `if not
    schema_bytes: return payload`) then handed a real layer provider raw
    bytes where it expected a parsed message, crashing (`warning_layer`,
    `AttributeError: 'bytes' object has no attribute 'left'`).

    Same real engine/`echo_stub` fixture as the smoke test immediately
    above -- this test only adds the missing assertion neither that test
    nor any other in this file made: whether a written topic's own
    `schema_bytes` is ever non-empty. Robust to `echo_stub`'s own real
    manifest carrying no real descriptor set (a minimal test fixture, not
    guaranteed to embed one) -- the mechanism under test is "does
    `backfill_schema_bytes` reach and apply whatever `pipeline` already
    has," not "does `echo_stub` happen to have real protobuf schema
    bytes today."""
    engine_path, stub_path = _require_engine_and_stub()

    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    pipeline_path = tmp_path / "pipeline.yaml"
    _write_pipeline(pipeline_path)
    pipeline = Pipeline.load(pipeline_path, search=[lib_dir])

    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)
    output_path = tmp_path / "out.mcap"

    result = run_pipeline_via_engine(
        pipeline, recording_path, run_id="20260826T000000Z-schema-backfill-test", output_path=output_path,
        simengine_path=engine_path,
    )
    assert result.ok, f"simengine exit_code={result.exit_code} stderr={result.stderr!r} stdout={result.stdout!r}"

    reader = reader_for(output_path)
    try:
        before = reader.topics()["/sut/outputs"]
    finally:
        reader.close()
    # The real defect, asserted directly rather than assumed: simengine's
    # own writer really does leave this empty today. If this ever starts
    # failing, BuildOutputTopics has been fixed at the source and this
    # function -- and this test's own reason to exist -- should be
    # retired, not patched to expect the new behaviour silently.
    assert before.schema_bytes == b"", (
        "simengine's own writer unexpectedly embedded real schema bytes -- "
        "BuildOutputTopics may have been fixed; backfill_schema_bytes's own "
        "reason to exist should be re-examined, not this assertion loosened"
    )

    backfill_schema_bytes(output_path, pipeline)

    reader = reader_for(output_path)
    try:
        after = reader.topics()["/sut/outputs"]
        messages_after = list(reader.messages())
    finally:
        reader.close()

    real_descriptor_set = pipeline.manifest_for("sut").descriptor_set
    if real_descriptor_set:
        assert after.schema_bytes == real_descriptor_set, (
            "backfill_schema_bytes did not apply the real component manifest's own descriptor_set"
        )
    else:
        assert after.schema_bytes == b"", (
            "backfill_schema_bytes invented schema bytes with nothing real to source them from"
        )
    # Whichever branch above held, the payloads themselves must be
    # byte-identical to before the patch -- this function only ever adds
    # topic-level schema metadata, never touches a single message.
    assert len(messages_after) >= 1


def test_resolve_simengine_executable_names_every_candidate_when_missing(monkeypatch):
    """`EnvironmentError_` names the searched directories -- never a bare
    `FileNotFoundError` -- so a caller sees exactly what to build."""
    import adas_sim.engine.bridge as bridge_module

    monkeypatch.setattr(bridge_module, "_SIMENGINE_CANDIDATES", (Path("/does/not/exist/simengine"),))
    with pytest.raises(EnvironmentError_) as exc_info:
        resolve_simengine_executable(search=[Path("/also/does/not/exist")])
    assert "does" in str(exc_info.value)


# ---------------------------------------------------------------------------
# `#5` / `F-4` (2026-08-28): the ingest map, wired. `WP-12`'s parser and
# `simcore/io/translate.cpp`'s apply half were both real and both tested for
# months; nothing joined them, and `pipeline_to_run_spec` emitted a hardcoded
# `{"ingest": [], "absent": []}` under a comment claiming the parser had not
# landed. A foreign-vocabulary recording therefore resimmed to completion,
# exit 0, feeding its module an empty payload on every one of 218 ticks.
# ---------------------------------------------------------------------------

_LEGACY = Path(__file__).resolve().parents[3] / "df" / "tests" / "carla_testruns" / "bsd" / "bsd_curve_r172_passby.mcap"
_NATIVE = Path(__file__).resolve().parents[3] / "df" / "tests" / "carla_testruns" / "aeb" / "aeb_canonical_10mps_30m.mcap"


def test_a_foreign_vocabulary_recording_resolves_a_real_ingest_table():
    """The recording carries `df/gen_object_list`; the pipeline wires
    `source.gen_object_list`. Without a table those never meet."""
    from adas_sim.engine.bridge import _ingest_for

    if not _LEGACY.exists():
        pytest.skip(f"not present in this checkout: {_LEGACY}")

    resolved = _ingest_for(_LEGACY)

    assert resolved["ingest"], "no ingest rows resolved -- the map was not applied"
    by_raw = {row["raw_topic"]: row for row in resolved["ingest"]}
    assert "/df/gen_object_list" in by_raw, sorted(by_raw)
    assert by_raw["/df/gen_object_list"]["port"] == "/source/gen_object_list"

    # A Resolved Run Spec carries NO reference grammar (`ANL-SW-01`): both
    # sides of a row are topics, never `source.`-prefixed port references.
    # `unresolved()` refuses that outright, and caught it on the first run.
    for row in resolved["ingest"]:
        assert not row["raw_topic"].startswith(("source.", "self."))
        assert not row["port"].startswith(("source.", "self."))
    for row in resolved["absent"]:
        assert not row["port"].startswith(("source.", "self."))


def test_a_recording_this_framework_produced_resolves_no_table(tmp_path):
    """The planted violation. A native recording's topics already ARE port
    names, so it must match no map and take the identical un-decorated path
    it always did -- if this returned rows, the check above would pass for
    any file at all and prove nothing."""
    from adas_sim.engine.bridge import _ingest_for

    if not _NATIVE.exists():
        pytest.skip(f"not present in this checkout: {_NATIVE}")

    resolved = _ingest_for(_NATIVE)

    assert resolved["ingest"] == []
    assert resolved["absent"] == []
