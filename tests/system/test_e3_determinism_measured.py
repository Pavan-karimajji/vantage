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

**Found live by `WP-15b` (2026-08-23), corrected here rather than left
silently red:** this test's own `same_process` claim assumed `cli.resim.
run()` executed `df_sil.dll` in THIS Python process, so two calls shared
one `process_nonce` by construction. `WP-15b` (`IMP-0422`) moved execution
to a `simengine` subprocess per call (`engine.bridge` -- `simcore` is a
STATIC library with no in-process ABI artifact to bind, see that module's
own docstring on why subprocess is the only shape every call site could
take). `cli.resim.run()` therefore now launches a genuinely separate OS
process on every call, same as `sim.exe resim` always did -- there is no
longer a Python-level "in-process" resim anywhere in the product to
measure `same_process` against. `_resim_in_process`'s name is kept (only
its own docstring below corrected) since it is still what a Python caller
in this same process invokes; it is simply no longer same-process
UNDERNEATH. The genuine same-process claim (two `simEngineRun` calls on
one already-constructed engine, one OS process) now lives at the C++
level -- `IT-11`/`UT-ABI-*` (`tests/integration/test_it11_embed_host.cpp`,
`test_ut_abi_writer_and_resolver.cpp`) -- not here.

**What this test still proves, and does:** every one of the three resims
below is fresh-process by construction now; `exact_ab`/`exact_ac` staying
`True` is the determinism claim that actually matters (`R-SIM-24`) --
`simengine` reproduces byte-identical output across independent process
launches, over a real `df_sil.dll`.

**Fresh-process**: any two of the three resims below -- each its own
`simengine`/`sim.exe` OS process, a different `process_nonce`, same
library/host/config -- so `derive_axis` reports `fresh_process` for every
pair.

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

_DF_SIL_DIR = DF_ROOT / "conan_workarea" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
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
    """Called in THIS Python process, but (since `WP-15b`) executes
    `df_sil.dll` in a fresh `simengine` child process every time -- see
    this module's own top-of-file note. Name kept: this is still the
    "call it from Python code, not a shelled-out CLI" case."""
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
        print(f"  fresh_process (2 Python-invoked resims, {same_process_s:.2f}s): "
              f"axis={axis_ab!r} exact={exact_ab}")
        print(f"  fresh_process (Python-invoked vs sim.exe subprocess, {fresh_process_s:.2f}s): "
              f"axis={axis_ac!r} exact={exact_ac}")
        print("  same_process: no longer reachable from a Python call site since WP-15b -- see IT-11/UT-ABI-* instead")
        print("  rebuilt_binary, different_machine: not measured this pass (needs a second build / a second machine)")

    # WP-15b: both pairs are fresh_process now (see this file's own
    # top-of-file note) -- the claim that survives is determinism itself,
    # not which axis it was filed under.
    assert axis_ab == "fresh_process"
    assert exact_ab is True
    assert axis_ac == "fresh_process"
    assert exact_ac is True
