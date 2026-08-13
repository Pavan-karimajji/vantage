# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`GT-13` (`sim_implementation_plan.md` §2, `NR-SIM-40`): a real,
measured, dated determinism number against a real `df_sil.dll` -- what
`ST-C6-3` proved was the TOOL (`sim determinism` correctly reports each
axis, unit/CLI level, synthetic manifests); this is the tool run for real,
same-process and fresh-process axes, over an actual resim. **The numbers
go in this document, whatever they are** -- timed and reported, not
asserted as a bound (`ST-B2-2`/`ST-D7-7`'s own discipline).

**Same-process**: two `sim resim` calls made in-process (this test's own
Python process), so `core.manifest._PROCESS_NONCE` -- generated once at
import time -- is identical between them by construction; `derive_axis`
should report `same_process`.

**Fresh-process**: one in-process call plus one real `sim.exe resim`
subprocess -- a genuinely separate process, a different `process_nonce`,
same library/host/config, so `derive_axis` should report `fresh_process`.

**Rebuilt-binary and different-machine stay unmeasured here, honestly** --
the first needs a second, independently-built `df_sil.dll` from the same
source (a real Conan/MSVC build this pass did not run a second time), the
second needs a second machine. Neither is guessed at or faked; `GT-13`'s own
box states this exactly as a blank finding, not an omission (`R-SIM-25`,
`NR-SIM-4`).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from adas_sim.cli.resim import run as resim_run
from adas_sim.diagnostics.determinism import compare_exact, derive_axis
from adas_sim.plugins.registry import reader_for

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"

_DF_SIL_DIR = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
_PIPELINE_PATH = DF_ROOT / "sim" / "pipelines" / "df_only.yaml"
_RECORDING = DF_ROOT / "tests" / "carla_testruns" / "exports" / "bsd_curve_r172_passby_20260727_213847.mcap"
_SIM_EXE = SIM_ROOT / ".venv" / "Scripts" / "sim.exe"

_SKIP_REASON = (
    "needs a real df_sil.dll build here (scripts/build.py df -t sil -p vs2026 -P base), "
    "the recording set, and the venv's own sim.exe entry point"
)


@pytest.fixture(autouse=True)
def _require_real_environment():
    if sys.platform != "win32":
        pytest.skip("Windows-only build path (df_sil.dll) -- same as test_c7_cross_host_resim.py")
    if not (_DF_SIL_DIR / "df_sil.dll").is_file():
        pytest.skip(f"{_SKIP_REASON}: df_sil.dll not found at {_DF_SIL_DIR}")
    if not _RECORDING.is_file():
        pytest.skip(f"{_SKIP_REASON}: {_RECORDING} not found")
    if not _SIM_EXE.is_file():
        pytest.skip(f"{_SKIP_REASON}: {_SIM_EXE} not found")


def _resim_in_process(out_path: Path) -> None:
    exit_code = resim_run([
        str(_RECORDING), "--pipeline", str(_PIPELINE_PATH), "--save", str(out_path),
        "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
    ])
    assert exit_code == 0


def _resim_subprocess(out_path: Path) -> None:
    proc = subprocess.run(
        [
            str(_SIM_EXE), "resim", str(_RECORDING), "--pipeline", str(_PIPELINE_PATH),
            "--save", str(out_path), "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
        ],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_gt13_determinism_same_process_and_fresh_process_measured(tmp_path, capsys):
    path_a = tmp_path / "run_a.mcap"
    path_b = tmp_path / "run_b.mcap"
    path_c = tmp_path / "run_c.mcap"

    t0 = time.perf_counter()
    _resim_in_process(path_a)
    _resim_in_process(path_b)
    same_process_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    _resim_subprocess(path_c)
    fresh_process_s = time.perf_counter() - t1

    def _compare(path_x: Path, path_y: Path) -> tuple[str | None, bool]:
        reader_x, reader_y = reader_for(path_x), reader_for(path_y)
        try:
            axis = derive_axis(reader_x.meta(), reader_y.meta())
            exact = compare_exact(reader_x, reader_y) is None
        finally:
            reader_x.close()
            reader_y.close()
        return axis.axis, exact

    axis_ab, exact_ab = _compare(path_a, path_b)
    axis_ac, exact_ac = _compare(path_a, path_c)

    with capsys.disabled():
        print(f"\nGT-13/NR-SIM-40: {_RECORDING.name} through df_only.yaml against a real df_sil.dll")
        print(f"  same_process  (2 in-process resims, {same_process_s:.2f}s): "
              f"axis={axis_ab!r} exact={exact_ab}")
        print(f"  fresh_process (in-process vs sim.exe subprocess, {fresh_process_s:.2f}s): "
              f"axis={axis_ac!r} exact={exact_ac}")
        print("  rebuilt_binary, different_machine: not measured this pass (needs a second build / a second machine)")

    assert axis_ab == "same_process"
    assert exact_ab is True
    assert axis_ac == "fresh_process"
    assert exact_ac is True
