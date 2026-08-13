# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `sim probe <lib>` (`docs/sim_implementation_plan.md`, `sim_learn.md`,
`ST-D5-2` -- one of the cross-referenced witnesses that the player discovers a
component's ports from its manifest with no rebuild --
SS5's own worked example: `sim probe ./df_sil.dll` and `sim probe
<recording>.mcap` share ONE verb). No C++/Conan toolchain exists in this
shell to build a real component (`df_sil` etc.), so this proves the REAL
ctypes-load path -- `CtypesSilComponent(path)` genuinely `dlopen`ing a real
compiled `.so` -- against a minimal, dependency-free fixture
(`tests/fixtures/echo_stub/echo_stub.c`, pure C, zero deps, hand-encoded
manifest bytes), compiled here with `gcc`. Same precedent as
`test_c5_relocatability.py`'s own `adas_fixture.cpp`: evidence for the
mechanism, not a substitute for probing a real `df_sil.dll` wherever a real
build exists.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.cli.probe import run
from adas_sim.plugins.registry import is_registered_recording_extension

_FIXTURE_SRC = Path(__file__).resolve().parents[1] / "fixtures" / "echo_stub" / "echo_stub.c"
_INTERFACES_INCLUDE = Path(__file__).resolve().parents[3] / "interfaces" / "include"
_TINY = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"

pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX .so path only -- see test_c5_relocatability.py's own AR-3 note on why this is a "
        "designed boundary, not a gap: the Windows dlopen equivalent is proven wherever a real MSVC build exists",
    ),
    pytest.mark.skipif(shutil.which("gcc") is None, reason="no C toolchain (gcc) available"),
    pytest.mark.skipif(not _INTERFACES_INCLUDE.is_dir(), reason="interfaces submodule not checked out"),
]


def _compile_fixture(out_dir: Path) -> Path:
    lib_path = out_dir / "libecho_stub.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(lib_path), str(_FIXTURE_SRC), f"-I{_INTERFACES_INCLUDE}"],
        check=True, capture_output=True, text=True,
    )
    return lib_path


def test_extension_dispatch_recognizes_recording_codecs_and_nothing_else():
    assert is_registered_recording_extension(".mcap") is True
    assert is_registered_recording_extension(".csv") is True
    assert is_registered_recording_extension(".so") is False
    assert is_registered_recording_extension(".dll") is False


def test_probe_lib_loads_a_real_dynamic_library_and_prints_its_manifest(tmp_path, capsys):
    lib_path = _compile_fixture(tmp_path)
    exit_code = run([str(lib_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "component        echo_stub" in out
    assert "abi_version      1" in out
    assert "inputs (0):" in out
    assert "outputs (0):" in out


def test_probe_recording_path_is_unchanged(capsys):
    exit_code = run([str(_TINY)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "recording        " in out
    assert "run_id           20260729T000000Z-t1ny0000" in out
