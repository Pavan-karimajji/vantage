# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `ST-D6-1` (`docs/sim_implementation_plan.md`, `FR-SIM-46`): "day
one, end to end" -- a fresh component library with only a manifest is
probed, wired into a five-line pipeline, run against `tiny.mcap`, and its
outputs appear in a recording, with **no edit anywhere in modules/sim**.
Every piece already existed and was exercised individually (`sim probe`
against `echo_stub.c` in `test_d6_probe.py`, `resim_pipeline_merged`
elsewhere) -- this is the chain, in one walkthrough, proving `R-SIM-16`'s
"a component onboards itself" and `GT-9`'s "every capability reachable in
~3 lines from a plain script" for the one case that matters most: a
component this framework has never heard of.

`echo_stub.c` (the `sim probe` fixture) declares zero ports, so it cannot
prove the "outputs appear" half; `echo_stub_with_output.c` is the same
zero-dependency, hand-encoded-manifest technique with exactly one real
output port -- see that file's own header comment for the manifest byte
layout.

`GT-8`'s own timed-newcomer measurement is a SEPARATE claim (a real person,
not a self-timed session, per `S-D6`'s own note) and is not attempted
here -- this test proves the chain WORKS, not how long a human takes to
run it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.cli.probe import run as probe_run
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest
from adas_sim.core.resim import resim_pipeline_merged
from adas_sim.core.session import Session
from adas_sim.io.registry import reader_for

_FIXTURE_SRC = Path(__file__).resolve().parents[1] / "fixtures" / "echo_stub" / "echo_stub_with_output.c"
_INTERFACES_INCLUDE = Path(__file__).resolve().parents[3] / "interfaces" / "include"
_TINY = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"

pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX .so path only -- see test_d6_probe.py's own identical boundary: the Windows "
        "dlopen equivalent is proven wherever a real MSVC build exists",
    ),
    pytest.mark.skipif(shutil.which("gcc") is None, reason="no C toolchain (gcc) available"),
    pytest.mark.skipif(not _INTERFACES_INCLUDE.is_dir(), reason="interfaces submodule not checked out"),
]


def _compile_fixture(out_dir: Path) -> Path:
    lib_path = out_dir / "libecho_stub_with_output.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(lib_path), str(_FIXTURE_SRC), f"-I{_INTERFACES_INCLUDE}"],
        check=True, capture_output=True, text=True,
    )
    return lib_path


def _five_line_pipeline(path: Path) -> None:
    path.write_text(
        "version: 1\n"
        "name: day_one\n"
        "stages:\n"
        "  - name: echo_stub_with_output\n"
        "    mode: simulate\n"
        '    impl: "dll:echo_stub_with_output"\n'
        "    inputs: {}\n",
        encoding="utf-8",
    )


def test_day_one_walkthrough_probe_pipeline_resim_recording(tmp_path, capsys):
    # Step 1: probe -- a developer's actual first action on a library they
    # have never seen (sim_player.md SS4: "the day-one screen").
    lib_path = _compile_fixture(tmp_path)
    exit_code = probe_run([str(lib_path)])
    probed = capsys.readouterr().out
    assert exit_code == 0
    assert "component        echo_stub_with_output" in probed
    assert "outputs (1):" in probed
    assert "echo.Echo" in probed  # the output port's own proto_type, probe just found it

    # Step 2: a five-line pipeline naming that same library by stem.
    pipeline_path = tmp_path / "pipeline.yaml"
    _five_line_pipeline(pipeline_path)
    pipeline = Pipeline.load(pipeline_path, search=[tmp_path])
    pipeline.init_components(None)  # the stub's own adasInit ignores configPath entirely
    try:
        # Step 3: run against tiny.mcap, writing a full merged recording --
        # this IS "outputs appear in a recording" (core.resim.
        # resim_pipeline_merged, R-SIM-6/R-SIM-13's one way a Session is
        # ever built).
        out_path = tmp_path / "day_one_result.mcap"
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=pipeline_path, run_kind="resim",
            source_kind="mcap", recording_path=_TINY,
        )
        resim_pipeline_merged(pipeline, _TINY, out_path, meta=meta)
    finally:
        pipeline.shutdown_components()

    # Step 4: the result is a REAL recording, readable the one way any
    # recording is (no special-cased reader for this walkthrough).
    assert out_path.is_file()
    reader = reader_for(out_path)
    try:
        topics = reader.topics()
        assert "echo_stub_with_output/echo" in topics
        # messages() yields (topic, log_time_ns, capture_time_ns, payload).
        payloads = [payload for topic, _log_ns, _cap_ns, payload in reader.messages()
                    if topic == "echo_stub_with_output/echo"]
    finally:
        reader.close()
    assert payloads, "the echo port's bytes never reached the recording"
    assert all(p == bytes.fromhex("deadbeef") for p in payloads)

    # Step 5: the same file loads as a Session -- the one and only path
    # this framework ever builds one through (R-SIM-13).
    session = Session.open(out_path)
    assert len(session) > 0
    assert "echo_stub_with_output.echo" in session.known_ports
