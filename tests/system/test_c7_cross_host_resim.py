# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`ST-C7-1` (`sim_implementation_plan.md` S-C7): one unmodified pipeline
file runs under `sim resim` (this process) and under `sil_host` (a real
`sil.exe` subprocess), and the two produce byte-identical outputs for the
same recording -- "one concept, two hosts" made a fact, not a slogan.

Drives a fresh, framework-produced recording (`SyntheticSource` +
`Recorder`, no pipeline -- `R-SIM-6`: its topics already equal port names,
`source/gen_object_list` -> `source.gen_object_list`), so this test needs
no `R-SIM-23` ingest map -- `sil_host`'s `RecordingReader` does not have
one yet (found and recorded separately in this stage's own status note;
not this test's job to cover). Skips with a named reason if no real
`df_sil`/`sil_host` build exists here, same pattern
`test_c8_relocatability_installed.py` already uses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.contracts.pipeline import Pipeline
from adas_sim.contracts.scenario import EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef
from adas_sim.core.manifest import build_manifest
from adas_sim.core.resim import resim_pipeline
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
SUPERPROJECT_ROOT = MODULES_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"

_DF_SIL_DIR = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
_SIL_HOST_EXE = SUPERPROJECT_ROOT / "ws" / "sil_host-base-sil-vs2026" / "Release" / "sil.exe"
_PIPELINE_PATH = DF_ROOT / "sim" / "pipelines" / "df_only.yaml"

_SKIP_REASON = (
    "needs a real df_sil.dll AND sil.exe build here "
    "(scripts/build.py df -t sil -p vs2026 -P base; scripts/build.py sil_host -t sil -p vs2026 -P base)"
)


@pytest.fixture(autouse=True)
def _require_real_builds():
    if sys.platform != "win32":
        pytest.skip("Windows-only build paths (df_sil.dll / sil.exe) -- ST-C7-1's cross-host proof needs a real MSVC/Conan build")
    if not (_DF_SIL_DIR / "df_sil.dll").is_file():
        pytest.skip(f"{_SKIP_REASON}: df_sil.dll not found at {_DF_SIL_DIR}")
    if not _SIL_HOST_EXE.is_file():
        pytest.skip(f"{_SKIP_REASON}: sil.exe not found at {_SIL_HOST_EXE}")


def _scenario() -> Scenario:
    return Scenario(
        schema=2, id="st_c7_1_cross_host", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        world={}, sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def _record_synthetic(path: Path, ticks: int) -> None:
    """Empty-but-valid protobuf ticks (proto3's own empty-message encoding
    is `b""`) on `source.gen_object_list`/`source.veh_dyn` -- `df_only.yaml`'s
    own two inputs. What the bytes mean is irrelevant to this test (the
    claim is byte-identity across hosts, not AEB correctness); only that
    both hosts see the SAME bytes."""
    source = SyntheticSource([{"gen_object_list": b"", "veh_dyn": b""} for _ in range(ticks)])
    meta = build_manifest(run_kind="sim", source_kind=source.name, project="base")
    recorder = Recorder(None, source, path, meta=meta)
    recorder.open(_scenario())
    try:
        for _ in range(ticks):
            recorder.tick(50_000_000)
    finally:
        recorder.close()


def _parse_sil_host_dump(stdout: str) -> dict[int, dict[str, dict[str, bytes]]]:
    results: dict[int, dict[str, dict[str, bytes]]] = {}
    current_tick: int | None = None
    for line in stdout.splitlines():
        if line.startswith("[sil]"):
            continue
        if line.startswith("tick "):
            current_tick = int(line.split(" ", 1)[1])
            results[current_tick] = {}
            continue
        if line.startswith("  ") and current_tick is not None:
            qualified, _, hex_bytes = line.strip().partition(" ")
            stage, _, port = qualified.partition(".")
            results[current_tick].setdefault(stage, {})[port] = bytes.fromhex(hex_bytes)
    return results


def test_st_c7_1_sil_host_and_sim_resim_produce_byte_identical_outputs(tmp_path):
    recording_path = tmp_path / "recording.mcap"
    _record_synthetic(recording_path, ticks=10)

    # Python side: the same primitive `sim resim` itself calls.
    pipeline = Pipeline.load(_PIPELINE_PATH, search=[_DF_SIL_DIR])
    pipeline.init_components(_DF_SIL_DIR / "config")
    try:
        py_results = resim_pipeline(pipeline, recording_path)
    finally:
        pipeline.shutdown_components()
    py_by_tick = {t_ns: outputs for t_ns, outputs in py_results}

    # C++ side: the unmodified sil.exe binary, --dump-outputs (stdout-only,
    # no mcap writer -- S-C7's own "must not grow a recorder").
    proc = subprocess.run(
        [
            str(_SIL_HOST_EXE), str(_PIPELINE_PATH), str(recording_path),
            "--search-dir", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
            "--dump-outputs",
        ],
        capture_output=True, text=True, check=True,
    )
    cpp_by_tick = _parse_sil_host_dump(proc.stdout)

    assert cpp_by_tick.keys() == py_by_tick.keys(), (proc.stdout, proc.stderr)
    assert len(py_by_tick) == 10
    for t_ns in py_by_tick:
        assert cpp_by_tick[t_ns] == py_by_tick[t_ns], f"tick {t_ns} diverged:\n{proc.stdout}"
