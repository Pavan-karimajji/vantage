# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`UT-D8-7` (`docs/sim_implementation_plan.md`, `sim_player.md` §2's
third ban: "a pipeline with a missing stage still renders the stages that
resolve, with the broken one badged -- degrade visibly, never refuse to
draw"). `Pipeline.load()` is atomic (one broken stage fails the whole
load, `contracts/pipeline.py`'s own design) -- `MainWindow._degraded_
pipeline_summary` is the scoped fix: when the real load fails, it
independently re-walks the declared stages with the same non-raising
tools `sim doctor` already uses (`Pipeline.parse_stages`,
`resolve_library_report`) and names EVERY stage's own resolution, not
just the first exception's."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
import yaml

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
from adas_sim.render.viewer import MainWindow, set_high_dpi_policy  # noqa: E402

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

_TICK_COUNT = 3
_DT_NS = 50_000_000


def _write_synthetic_recording(out_path: Path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-d8-degrade", run_kind="resim",
        created_utc="2026-08-06T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d8_degrade.yaml", project="base", pipeline="none", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def _pump_until_loaded(window: MainWindow, timeout_ms: int = 5000) -> None:
    loop = QtCore.QEventLoop()
    ceiling = QtCore.QTimer()
    ceiling.setSingleShot(True)
    ceiling.timeout.connect(loop.quit)
    ceiling.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: loop.quit() if window.session is not None else None)
    poll.start(10)
    loop.exec()
    poll.stop()
    ceiling.stop()


def _open_window(recording: Path, **kwargs) -> MainWindow:
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, **kwargs)
    window.show()
    _pump_until_loaded(window)
    return window


def test_degraded_summary_names_every_stage_not_just_the_first(tmp_path):
    search_dir = tmp_path / "libs"
    search_dir.mkdir()
    # Every platform's candidate name, because `_candidate_names` is platform-
    # specific (`fake_ok.dll` on Windows, `libfake_ok.so`/`fake_ok.so` on
    # POSIX): writing only the POSIX one made this assert the OPPOSITE on
    # Windows. Never actually loaded here -- only resolved (P-5).
    (search_dir / "libfake_ok.so").write_bytes(b"")
    (search_dir / "fake_ok.dll").write_bytes(b"")

    pipeline_path = tmp_path / "mixed.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "mixed",
        "stages": [
            {"name": "resolvable", "mode": "simulate", "impl": "stubdll:fake_ok"},
            {"name": "missing", "mode": "simulate", "impl": "dll:does_not_exist_anywhere"},
        ],
    }, sort_keys=False), encoding="utf-8")

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording, pipeline_path=pipeline_path, pipeline_search=[search_dir])

    # The real Pipeline.load() still fails atomically (the "resolvable"
    # stage's fake .so is not a real library, and "missing" has none at
    # all) -- the DOCK stays empty, same "degrades the DOCK, never the
    # window" claim test_d3_mainwindow_pipeline_panel.py already proves.
    assert window.session is not None
    assert window.pipeline_panel_state is None

    summary = window._degraded_pipeline_summary()
    assert "resolvable: ok" in summary
    assert "missing: broken" in summary
    assert "does_not_exist_anywhere" in summary


def test_degraded_summary_names_a_stage_with_no_impl_at_all(tmp_path):
    pipeline_path = tmp_path / "no_impl.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "no_impl", "stages": [{"name": "bare", "mode": "simulate"}],
    }, sort_keys=False), encoding="utf-8")

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording, pipeline_path=pipeline_path)

    summary = window._degraded_pipeline_summary()
    assert "bare: broken (no impl:)" in summary


def test_degraded_summary_empty_when_the_pipeline_yaml_itself_is_malformed(tmp_path):
    """The raw exception already names the real problem (a malformed
    file); the per-stage summary adds nothing useful and returns `""`
    rather than a confusing second, unrelated message."""
    pipeline_path = tmp_path / "broken.yaml"
    pipeline_path.write_text("{not: valid: yaml:::", encoding="utf-8")

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording, pipeline_path=pipeline_path)

    assert window._degraded_pipeline_summary() == ""


def test_status_bar_shows_the_full_per_stage_detail_on_a_real_load_failure(tmp_path):
    """`_on_loaded` shows a further "loaded N ticks" message right after
    `_load_pipeline_panel` runs (unrelated to this fix, pre-existing
    sequencing), so the pipeline-load message is transient -- captured via
    `messageChanged` rather than read back after everything settles."""
    pipeline_path = tmp_path / "missing.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "missing", "stages": [{"name": "gone", "mode": "simulate", "impl": "dll:nowhere"}],
    }, sort_keys=False), encoding="utf-8")

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, pipeline_path=pipeline_path)
    messages = []
    window.statusBar().messageChanged.connect(lambda text: messages.append(text) if text else None)
    window.show()
    _pump_until_loaded(window)

    assert any("gone: broken" in m for m in messages), messages
