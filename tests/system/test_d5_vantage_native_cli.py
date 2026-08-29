# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`scripts/vantage_native.py`'s real refusal discipline (`SW-0428`,
`WP-34a`) -- every argument or mode `vantage_app.exe` cannot serve refuses
by name, never silently dropped or half-implemented (no `--legacy` fallback
exists any more -- `scripts/vantage.py`, the retiring Python scene/render/
player launcher, is deleted, `SM-12`). Subprocess, the real entry point:
`sys.path` mutation at import time makes an in-process import leak across
tests in one file.

These are the pure-argv-mapping paths -- no `vantage_app.exe` build, no
window, no `sim resim` subprocess -- so they run in this WSL sandbox with
no native-Windows dependency, the fast, portable half of `WP-34a`'s own
verification. The live windowed launch itself (`vantage.bat` driving a
real `vantage_app.exe` against a real deployed plugin root) was verified
live, native `vs2026`, this same pass -- not repeated here as an
automated test (would need a real GLFW window and a real deployed df
build, out of what a fast CI-shaped unit/system test should carry)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_VANTAGE_NATIVE_PY = _SCRIPTS / "vantage_native.py"

_FIXTURE_MCAP = Path(__file__).resolve().parents[1] / "fixtures" / "tiny.mcap"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VANTAGE_NATIVE_PY), *args],
        capture_output=True, text=True, timeout=30,
    )


def test_workspace_flag_refuses_by_name():
    result = _run(str(_FIXTURE_MCAP), "--workspace", "bench")
    assert result.returncode == 1
    assert "--workspace" in result.stderr


def test_preset_and_at_flags_both_named_in_one_refusal():
    result = _run(str(_FIXTURE_MCAP), "--preset", "chase", "--at", "5.0")
    assert result.returncode == 1
    assert "--preset" in result.stderr
    assert "--at" in result.stderr


def test_version_flag_refuses_by_name():
    result = _run("--version")
    assert result.returncode == 1
    assert "--version" in result.stderr


def test_no_recording_refuses_naming_the_start_page_concept():
    result = _run()
    assert result.returncode == 1
    assert "no recording" in result.stderr.lower()


def test_nonexistent_recording_refuses_with_the_real_path():
    result = _run("does/not/exist.mcap")
    assert result.returncode == 1
    assert "does/not/exist.mcap" in result.stderr or "does\\not\\exist.mcap" in result.stderr


def test_bare_recording_with_no_pipeline_and_no_sidecar_refuses_naming_r_sim_5(tmp_path):
    recording = tmp_path / "bare.mcap"
    recording.write_bytes(b"")  # existence is all build_native_argv checks before the sidecar lookup
    result = _run(str(recording))
    assert result.returncode == 1
    assert "--pipeline" in result.stderr


def test_find_vantage_app_exe_prefers_sil_over_gtest_build(tmp_path, monkeypatch):
    """`find_vantage_app_exe`'s own resolution order (`sil` first, `gtest`
    fallback) -- a pure function, no subprocess needed. Real regression
    for the exact ordering `WP-34a`'s own top note documents: TARGET_TYPE
    defaults to `sil` for either Conan target, but a `sil` build (the
    canonical, non-test shape) should win over an incidental `gtest`
    build's own copy when both exist."""
    sys.path.insert(0, str(_SCRIPTS))
    import vantage_native  # noqa: E402

    fake_sim_root = tmp_path
    monkeypatch.setattr(vantage_native, "_SIM_ROOT", fake_sim_root)

    gtest_exe = fake_sim_root / "vantage" / "build-gtest-vs2026" / "build" / "cpp" / "vantage_app" / "Release" / "vantage_app.exe"
    gtest_exe.parent.mkdir(parents=True)
    gtest_exe.write_bytes(b"")
    assert vantage_native.find_vantage_app_exe() == gtest_exe

    sil_exe = fake_sim_root / "vantage" / "build-sil-vs2026" / "build" / "cpp" / "vantage_app" / "Release" / "vantage_app.exe"
    sil_exe.parent.mkdir(parents=True)
    sil_exe.write_bytes(b"")
    assert vantage_native.find_vantage_app_exe() == sil_exe


def test_find_vantage_app_exe_names_the_build_command_when_missing(tmp_path, monkeypatch):
    sys.path.insert(0, str(_SCRIPTS))
    import vantage_native  # noqa: E402

    monkeypatch.setattr(vantage_native, "_SIM_ROOT", tmp_path)
    try:
        vantage_native.find_vantage_app_exe()
        assert False, "expected NativeUnsupported"
    except vantage_native.NativeUnsupported as exc:
        assert "build.bat -t sil -p vs2026" in str(exc)
