# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `sim list ports|topics|layers|signals` (`DG-1`,
`docs/sim_implementation_plan.md`). `ports` shares `test_d6_probe.py`'s own
compiled fixture and skip conditions (real ctypes load, no Conan/C++
toolchain needed); `topics`/`layers`/`signals` run against `tiny.mcap`, no
compiler needed at all.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.cli.list_cmd import run

_FIXTURE_SRC = Path(__file__).resolve().parents[1] / "fixtures" / "echo_stub" / "echo_stub.c"
_INTERFACES_INCLUDE = Path(__file__).resolve().parents[3] / "interfaces" / "include"
_TINY = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"

def _compile_fixture(out_dir: Path) -> Path:
    lib_path = out_dir / "libecho_stub.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(lib_path), str(_FIXTURE_SRC), f"-I{_INTERFACES_INCLUDE}"],
        check=True, capture_output=True, text=True,
    )
    return lib_path


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX .so path only, see test_d6_probe.py's own note")
@pytest.mark.skipif(shutil.which("gcc") is None, reason="no C toolchain (gcc) available")
@pytest.mark.skipif(not _INTERFACES_INCLUDE.is_dir(), reason="interfaces submodule not checked out")
def test_list_ports_reads_a_real_library_manifest(tmp_path, capsys):
    lib_path = _compile_fixture(tmp_path)
    exit_code = run(["ports", str(lib_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "inputs (0):" in out
    assert "outputs (0):" in out


def test_list_topics_reads_the_recordings_own_topic_index(capsys):
    exit_code = run(["topics", str(_TINY)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "topics (3):" in out
    assert "/df/aeb.outputs" in out
    assert "/source/veh_dyn" in out
    assert "/source/gen_object_list" in out


def test_list_layers_builds_a_real_scene():
    """A fresh interpreter, deliberately -- same reasoning as
    test_c8_relocatability_installed.py's own: `scene.registry`'s provider
    table is process-global, so whether `df`'s real layer providers are
    already registered (and therefore run against `tiny.mcap`'s synthetic,
    non-protobuf payload, which they cannot decode) depends on whatever else
    THIS pytest session happened to import first -- order-dependent in a way
    that has nothing to do with `cli/list.py`'s own correctness."""
    script = (
        "from adas_sim.cli.list_cmd import run\n"
        f"run(['layers', {str(_TINY)!r}])\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "layers (" in result.stdout


def test_list_signals_is_the_port_level_address_space(capsys):
    exit_code = run(["signals", str(_TINY)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "df.aeb.outputs" in out
    assert "source.veh_dyn" in out
    assert "source.gen_object_list" in out


def test_list_rejects_an_unknown_what():
    with pytest.raises(SystemExit):
        run(["frobnicate", str(_TINY)])
