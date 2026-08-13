# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c `UT-C1c-15a` (`docs/sim_implementation_plan.md`, `R-SIM-10`): a
`stubdll:` stage loads through the **same** `CtypesSilComponent` path a
`dll:` stage does, and its port set is indistinguishable from a `dll:`
stage's to everything downstream -- "executed and injected produce the
same port set" proven at the `impl:` axis rather than only at the `mode:`
axis. `contracts/pipeline.py`'s own `_resolve_components` already routes
both `dll:` and `stubdll:` through one branch (`kind in ("dll",
"stubdll")`) -- true by construction, but this session's own lesson is
that reading a code path is not running it, so this test resims the SAME
compiled library twice, once addressed each way, and diffs the results.

`echo_stub_with_output.c` (`S-D6`'s own fixture) is reused rather than a
new one written -- `sim_sil_contract.md` §8's own "a stub DLL built
in-tree that implements the generic ABI over a trivial echo component" is
singular; a second near-identical fixture would just be the same claim
twice. Compiles on **both** platforms now (this stage's own finding: the fixture was missing `ADAS_SIL_ABI_EXPORTS` before
including `adas_sil_abi.h`, so a Windows/MSVC build silently produced a
DLL exporting nothing -- fixed in the fixture itself (a one-line
`#define`, mirrors every real component's own CMake wiring), proven here
by actually building and running it on Windows via `cl.exe`, not merely
by reasoning that the POSIX build (gcc, `test_d6_probe.py`/`test_d6_day_
one_walkthrough.py`) would carry over.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.determinism import compare_exact
from adas_sim.runspec.manifest import build_manifest
from adas_sim.core.resim import resim_pipeline_merged
from adas_sim.plugins.registry import reader_for

_FIXTURE_SRC = Path(__file__).resolve().parents[1] / "fixtures" / "echo_stub" / "echo_stub_with_output.c"
_INTERFACES_INCLUDE = Path(__file__).resolve().parents[3] / "interfaces" / "include"
_TINY = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"

# Ordinary VS install layouts differ only in edition/version, both variable --
# no vswhere.exe in this environment, so a glob is the honest best effort
# rather than one hardcoded path (`P-5`'s own "consult the platform, not a
# guess" extended to "consult it broadly, not narrowly").
_VCVARS_GLOBS = (
    "Program Files/Microsoft Visual Studio/*/*/VC/Auxiliary/Build/vcvars64.bat",
    "Program Files (x86)/Microsoft Visual Studio/*/*/VC/Auxiliary/Build/vcvars64.bat",
)


def _find_vcvars64() -> Path | None:
    for drive in ("C:", "D:"):
        root = Path(f"{drive}/")
        for pattern in _VCVARS_GLOBS:
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def _compile_fixture_posix(out_dir: Path) -> Path:
    lib_path = out_dir / "libecho_stub_with_output.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(lib_path), str(_FIXTURE_SRC), f"-I{_INTERFACES_INCLUDE}"],
        check=True, capture_output=True, text=True,
    )
    return lib_path


def _compile_fixture_windows(out_dir: Path, vcvars64: Path) -> Path:
    lib_path = out_dir / "echo_stub_with_output.dll"
    build_bat = out_dir / "build.bat"
    build_bat.write_text(
        "@echo off\r\n"
        f'call "{vcvars64}"\r\n'
        f"cd /d {out_dir}\r\n"
        f'cl.exe /LD /std:c11 /I "{_INTERFACES_INCLUDE}" "{_FIXTURE_SRC}" /Fe:"{lib_path.name}"\r\n',
        encoding="utf-8",
    )
    proc = subprocess.run(["cmd.exe", "/c", str(build_bat)], capture_output=True, text=True)
    assert proc.returncode == 0 and lib_path.is_file(), (
        f"MSVC build of the stub fixture failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return lib_path


def _compile_fixture(out_dir: Path) -> Path:
    if sys.platform == "win32":
        vcvars64 = _find_vcvars64()
        if vcvars64 is None:
            pytest.skip("no MSVC install found (no vcvars64.bat under Program Files) to compile the stub fixture")
        return _compile_fixture_windows(out_dir, vcvars64)
    if shutil.which("gcc") is None:
        pytest.skip("no C toolchain (gcc) available")
    return _compile_fixture_posix(out_dir)


@pytest.fixture(autouse=True)
def _require_interfaces_checkout():
    if not _INTERFACES_INCLUDE.is_dir():
        pytest.skip("interfaces submodule not checked out")


def _pipeline_yaml(path: Path, *, impl_kind: str) -> None:
    path.write_text(
        "version: 1\n"
        f"name: stubdll_probe_{impl_kind}\n"
        "stages:\n"
        "  - name: echo_stub_with_output\n"
        "    mode: simulate\n"
        f'    impl: "{impl_kind}:echo_stub_with_output"\n'
        "    inputs: {}\n",
        encoding="utf-8",
    )


def _resim_to(lib_dir: Path, pipeline_path: Path, out_path: Path) -> None:
    pipeline = Pipeline.load(pipeline_path, search=[lib_dir])
    pipeline.init_components(None)
    try:
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=pipeline_path, run_kind="resim",
            source_kind="mcap", recording_path=_TINY,
        )
        resim_pipeline_merged(pipeline, _TINY, out_path, meta=meta)
    finally:
        pipeline.shutdown_components()


def test_ut_c1c_15a_stubdll_and_dll_impl_produce_byte_identical_results(tmp_path):
    lib_path = _compile_fixture(tmp_path)
    lib_dir = lib_path.parent

    dll_pipeline_path = tmp_path / "pipeline_dll.yaml"
    _pipeline_yaml(dll_pipeline_path, impl_kind="dll")
    dll_out = tmp_path / "via_dll.mcap"
    _resim_to(lib_dir, dll_pipeline_path, dll_out)

    stubdll_pipeline_path = tmp_path / "pipeline_stubdll.yaml"
    _pipeline_yaml(stubdll_pipeline_path, impl_kind="stubdll")
    stubdll_out = tmp_path / "via_stubdll.mcap"
    _resim_to(lib_dir, stubdll_pipeline_path, stubdll_out)

    reader_dll, reader_stubdll = reader_for(dll_out), reader_for(stubdll_out)
    try:
        # The two runs' own manifests legitimately differ (different pipeline
        # name/hash) -- compare_exact diffs PORT VALUES, never manifest/file
        # bytes (R-SIM-24's own discipline, reused here for a different axis:
        # impl: kind, not process/host/build).
        divergence = compare_exact(reader_dll, reader_stubdll)
    finally:
        reader_dll.close()
        reader_stubdll.close()

    assert divergence is None, divergence
