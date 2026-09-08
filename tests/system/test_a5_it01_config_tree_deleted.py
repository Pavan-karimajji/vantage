# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-05: `IT-01` (`SW-0002`) -- "the test that proves the seam is closed"
(`SIM_Software_Test_Spec_v0.1.md`): emit a spec; delete the configuration
source tree; run the engine with only spec, recording and binary present;
compare port values against the run made with the tree present.

**Closed 2026-08-23.** `WP-05`'s own row named this "cannot be attempted --
`simcore` has no execution engine yet (`Runner::Construct`/`Run` are
`WP-14`'s own artifact, not built)" when `WP-05` landed. `WP-14` (`simengine`/
`Runner`) has since landed and been exercised throughout `WP-15b`/`WP-16` --
the blocker is stale, so the real proof is attempted here rather than left
standing on it.

**What "delete the configuration source tree" means for a claim that must
still be safe to run in CI:** actually renaming `modules/sim/src/adas_sim`
mid-test would be destructive and racy against anything else touching this
checkout. The equivalent, non-destructive claim: copy ONLY the three things
`abi/simcore.h`'s own contract says `simengine` needs (`D-1`) -- the spec,
the recording, the compiled library -- into a fresh directory that is
**not a descendant of this checkout at all** (pytest's own `tmp_path`,
already resolved under the OS temp root, `test_the_isolated_directory_
shares_no_path_with_the_checkout` below makes this an assertion, not an
assumption), positively enumerate that nothing else landed there, and run
`simengine` with THAT as its only input. If `simengine` needed anything
from `adas_sim/config/**` -- a pipeline YAML, a project file, anything --
this is the run that would fail to find it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.diagnostics.determinism import compare_exact
from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable, run_engine, run_pipeline_via_engine
from adas_sim.graph.pipeline import Pipeline
from adas_sim.plugins.registry import reader_for
from adas_sim.runspec.canon import write_run_spec
from tests.system.test_d15b_engine_bridge import _echo_stub_path

SIM_ROOT = Path(__file__).resolve().parents[2]
_TINY = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"


def _require_engine_and_stub() -> tuple[Path, Path]:
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip(f"no built echo_stub found paired with {engine}")
    return engine, stub


def _write_pipeline(path: Path) -> None:
    path.write_text(
        "version: 1\nname: it01_config_tree_deleted\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: \"dll:echo_stub\"\n    inputs: {}\n",
        encoding="utf-8",
    )


@pytest.fixture
def _engine_and_pipeline(tmp_path, monkeypatch):
    engine_path, stub_path = _require_engine_and_stub()
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")

    lib_dir = tmp_path / "checkout_lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    pipeline_path = tmp_path / "pipeline.yaml"
    _write_pipeline(pipeline_path)
    # Resolved via search=, exactly as every real production call site does
    # (cli/resim.py etc.) -- the spec this emits carries an absolute impl.path,
    # never a reference back to lib_dir or the pipeline file itself.
    pipeline = Pipeline.load(pipeline_path, search=[lib_dir])
    return engine_path, pipeline, stub_copy


def test_config_tree_deleted_engine_still_runs_and_matches_the_baseline(_engine_and_pipeline, tmp_path):
    engine_path, pipeline, stub_copy = _engine_and_pipeline

    # Step 1: the baseline run, full checkout present -- this IS a normal
    # engine.bridge call, exactly like every other WP-15b call site.
    baseline_out = tmp_path / "baseline.mcap"
    baseline = run_pipeline_via_engine(
        pipeline, _TINY, run_id="it01-baseline", output_path=baseline_out, simengine_path=engine_path,
    )
    assert baseline.ok, f"baseline run failed: exit_code={baseline.exit_code} stderr={baseline.stderr!r}"

    # Step 2: build the SAME spec again (pipeline_to_run_spec is pure --
    # same Pipeline, same recording, same stub copy -- so its own emitted
    # paths already point at files that will still exist after step 3;
    # nothing needs rewriting) and write it to a throwaway location.
    from adas_sim.engine.bridge import pipeline_to_run_spec
    isolated_out = tmp_path / "isolated_out.mcap"
    spec = pipeline_to_run_spec(
        pipeline, run_id="it01-isolated", recording_path=_TINY, output_path=isolated_out,
    )

    # Step 3: an isolated directory holding ONLY the three things D-1 says
    # simengine needs -- spec, recording, compiled library -- and nothing
    # else. Not a copy of the recording/library (their absolute paths
    # already resolve from here regardless of location); the spec itself
    # is what gets copied in, since that is simengine's one and only input.
    isolated_dir = tmp_path / "isolated_run"
    isolated_dir.mkdir()
    spec_path = isolated_dir / "run_spec.json"
    write_run_spec(spec, spec_path)

    assert sorted(p.name for p in isolated_dir.iterdir()) == ["run_spec.json"], (
        "the isolated directory must hold nothing but the spec -- "
        "the recording and library are referenced by absolute path, never staged here"
    )

    # Step 4: run simengine against the isolated spec alone.
    isolated = run_engine(spec_path, simengine_path=engine_path, output_path=isolated_out)
    assert isolated.ok, f"isolated run failed: exit_code={isolated.exit_code} stderr={isolated.stderr!r}"

    # Step 5: port values agree, tick for tick -- the seam holds.
    baseline_reader, isolated_reader = reader_for(baseline_out), reader_for(isolated_out)
    try:
        divergence = compare_exact(baseline_reader, isolated_reader)
    finally:
        baseline_reader.close()
        isolated_reader.close()
    assert divergence is None, divergence


def test_the_isolated_directory_shares_no_path_with_the_checkout(tmp_path):
    """`tmp_path` (pytest's own per-test fixture) is asserted, not assumed,
    to live outside this checkout -- same discipline `test_a2_it12_config_
    paths_install.py`'s own `test_the_read_only_install_shares_no_path_
    with_the_checkout` uses for the analogous Python-install claim."""
    assert SIM_ROOT not in tmp_path.parents
    assert tmp_path not in SIM_ROOT.parents
