# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""RCT:WP-13 (`IMP-0048`, `IMP-0051`): Vantage's Python code writes recordings through the one Python writer.

`ANL-06` `.c2` -- `check_one_recording_writer.py`, taken from the `adas-interfaces` package the build names, finds
no mcap writer import under this repo's `src/` (a `McapWriter` left in `src/adas_sim/io/mcap.py` would be one).
`IMP-0051` -- `io/recording_writer.py` reads `adas_recording.path` beside the `simengine` and says which build to run
when the file or the folder is missing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.io.recording_writer import PATH_FILE, find_recording_package, recording_writer

SRC = Path(__file__).resolve().parents[2] / "src"


def _built_package() -> Path:
    """The `python/` folder the sil build names, or a skip with the reason when it is not built here."""
    try:
        return find_recording_package()
    except EnvironmentError_ as exc:
        print(f"recording writer not found: {exc}", file=sys.stderr)
        pytest.skip(f"recording writer not found: {exc}")


def test_anl_06_c2_no_mcap_writer_import_under_vantages_src():  # ANL-06.c2
    package = _built_package()
    checker = package.parent / "scripts" / "check_one_recording_writer.py"
    if not checker.is_file():
        pytest.skip(f"check_one_recording_writer.py is not in the package at {checker.parent}")
    result = subprocess.run([sys.executable, str(checker), "--root", str(SRC)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_writer_module_is_the_one_the_build_names():  # IMP-0051
    package = _built_package()
    module = recording_writer()
    assert Path(module.__file__).resolve().is_relative_to(package.resolve())
    assert {"McapRecorder", "TopicSpec", "RecordingError"} <= set(dir(module))


def _fake_engine(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "simengine.exe").write_bytes(b"")
    (directory / "simengine").write_bytes(b"")
    return directory


def test_the_path_file_beside_the_engine_names_the_folder(tmp_path):  # IMP-0051
    engine = _fake_engine(tmp_path / "bin")
    package = tmp_path / "python"
    (package / "adas_recording").mkdir(parents=True)
    (package / "adas_recording" / "writer.py").write_text("", encoding="utf-8")
    (engine / PATH_FILE).write_text(package.as_posix() + "\n", encoding="utf-8")
    assert find_recording_package(search=[engine]) == package


def test_a_missing_path_file_is_an_error_naming_the_build_to_run(tmp_path):  # IMP-0051
    engine = _fake_engine(tmp_path / "bin")
    with pytest.raises(EnvironmentError_) as raised:
        find_recording_package(search=[engine])
    assert PATH_FILE in str(raised.value) and "scripts/build.py" in str(raised.value)


def test_a_folder_without_the_writer_is_an_error_naming_the_build_to_run(tmp_path):  # IMP-0051
    engine = _fake_engine(tmp_path / "bin")
    (engine / PATH_FILE).write_text((tmp_path / "nowhere").as_posix() + "\n", encoding="utf-8")
    with pytest.raises(EnvironmentError_) as raised:
        find_recording_package(search=[engine])
    assert "adas_recording/writer.py" in str(raised.value) and "scripts/build.py" in str(raised.value)
