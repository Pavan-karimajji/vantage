# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` lean-limit tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §2): `UT-D8-5` (`L-1`, transport row `≤ 12` controls --
the region `sim_player.md`'s own window mockup annotates `(L-1: 12)`
directly) and `UT-D8-6` (`L-3`, a fully normal run shows no provenance/
bundle-mismatch/capability noise anywhere)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.app.shell.window import VantageWindow  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
from adas_sim.render.viewer import TransportBar, set_high_dpi_policy  # noqa: E402

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _count_controls(toolbar: QtWidgets.QToolBar) -> int:
    """Every interactive affordance a developer could act on: a `QAction`
    (button/toggle), or a plain widget added via `addWidget` that is
    itself interactive (slider, combo box) -- a `QLabel` is informational,
    never a control, and is not counted (`tick_label` in `TransportBar`)."""
    count = 0
    for action in toolbar.actions():
        if action.isSeparator():
            continue
        widget = toolbar.widgetForAction(action)
        if isinstance(widget, QtWidgets.QLabel):
            continue
        count += 1
    return count


def test_ut_d8_5_transport_bar_has_at_most_twelve_controls():
    _app()
    bar = TransportBar()
    assert _count_controls(bar) <= 12


def test_ut_d8_5_transport_bar_control_count_is_a_real_number_not_zero():
    """The bound is meaningful only if the count is not trivially empty --
    guards against `_count_controls` silently matching nothing."""
    _app()
    bar = TransportBar()
    assert _count_controls(bar) >= 5


# ---------------------------------------------------------------------------
# UT-D8-6 (L-3): a fully normal run shows no abnormal-only noise.
# ---------------------------------------------------------------------------

_PROJECT = "base"
_NOISE_WORDS = ("stale", "mismatch", "missing", "unresolvable", "unknown", "degraded", "severed")


def _write_normal_recording(path: Path) -> None:
    manifest = RunManifest(
        manifest_version=2, run_id="test-d8-lean", run_kind="resim",
        created_utc="2026-08-06T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d8_lean.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="build-xyz"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.SIMULATED)}
    writer = writer_for(path)
    writer.open(path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(3):
        writer.write("/test/marker", tick * 50_000_000, bytes([tick % 256]))
    writer.close()


def _pump_until_loaded(window: VantageWindow, timeout_ms: int = 5000) -> None:
    loop = QtCore.QEventLoop()
    ceiling = QtCore.QTimer()
    ceiling.setSingleShot(True)
    ceiling.timeout.connect(loop.quit)
    ceiling.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: loop.quit() if window.bench.session is not None else None)
    poll.start(10)
    loop.exec()
    poll.stop()
    ceiling.stop()


def test_ut_d8_6_a_normal_run_has_no_stale_banner(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_normal_recording(recording)
    set_high_dpi_policy()
    _app()
    window = VantageWindow(recording, project=_PROJECT)
    window.show()
    _pump_until_loaded(window)

    _lines, banner = window.bench._hud_and_stale_banner(0)
    assert banner is None


def test_ut_d8_6_a_normal_run_shows_no_noise_words_in_the_hud(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_normal_recording(recording)
    set_high_dpi_policy()
    _app()
    window = VantageWindow(recording, project=_PROJECT)
    window.show()
    _pump_until_loaded(window)

    lines, _banner = window.bench._hud_and_stale_banner(0)
    joined = " ".join(lines).lower()
    for word in _NOISE_WORDS:
        assert word not in joined, f"unexpected {word!r} in a normal run's HUD: {lines}"


def test_ut_d8_6_no_pipeline_given_means_no_faults_or_override_widgets_visible(tmp_path):
    """With no `--pipeline` at all (the common `sim view <recording>`
    case, `sim_player.md` §6 Screen 2's own "the user has configured
    nothing"), the pipeline dock's fault/override affordances -- which
    only ever appear when a pipeline is loaded -- are simply absent."""
    recording = tmp_path / "rec.mcap"
    _write_normal_recording(recording)
    set_high_dpi_policy()
    _app()
    window = VantageWindow(recording, project=_PROJECT)
    window.show()
    _pump_until_loaded(window)

    assert window.bench.pipeline_panel_state is None
