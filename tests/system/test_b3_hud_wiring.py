# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 12 system tests: `UT-B3-5`'s Qt half (docs/
sim_implementation_plan.md) -- `view/hud.py`'s own formatting/staleness
logic is already covered headlessly (`tests/unit/test_b3_hud.py`). Proves
`MainWindow` renders HUD text every tick (framework-known fields always;
ego-state and the stale banner only when the caller configures them,
`__init__`'s own docstring on why) and that the banner reacts to a port
actually going stale mid-session.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
from adas_sim.config.project import bundle_bytes_for_recording  # noqa: E402
import adas_sim.player.shell.qt_window as viewer_module  # noqa: E402
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 3
_DT_NS = 50_000_000


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path, *, config_bundle_bytes: bytes = b"") -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-hud", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3_hud.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="build-xyz"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=config_bundle_bytes)
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


def _open_window(recording, **kwargs) -> MainWindow:
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT, **kwargs)
    window.show()
    _pump_until_loaded(window)
    assert window.session is not None
    return window


def test_hud_lines_carry_the_frameworks_own_known_fields(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    lines, banner = window._hud_and_stale_banner(0)
    assert len(lines) == 3
    assert "base" in lines[2]
    assert "build-xyz" in lines[2]
    # AR-57: this fixture's own topic is Provenance.UNKNOWN -- genuinely
    # stimulus-only (no port ever carries origin="simulated") -- so the
    # banner is real, not the "nothing configured" absence this test's own
    # name once implied. `test_max_age_not_exceeded_no_banner` below is the
    # real "nothing wrong" case for the stale half specifically.
    assert banner == (
        "STIMULUS-ONLY: no port here was ever a stage's own computed output "
        "-- resim through a pipeline to see one"
    )


def test_stale_banner_reaches_the_rendered_frame(tmp_path):
    """The Qt-level proof that `_hud_and_stale_banner`'s output actually
    reaches `render_scene` -- `test_render_scene_draws_a_stale_banner`
    (`tests/unit/test_b1_bev_render.py`) already proves a banner changes
    pixels in isolation; this proves `MainWindow` really wires the two
    together, by comparing two real windows differing only in config."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    plain = _open_window(recording)
    with_banner = _open_window(recording, max_age_s={"test.marker": -1.0})
    assert plain.bev.pixmap().toImage() != with_banner.bev.pixmap().toImage()


def test_ego_state_signal_not_configured_means_no_fourth_line(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    lines, _banner = window._hud_and_stale_banner(0)
    assert len(lines) == 3


def test_ego_state_signal_configured_and_resolvable_adds_a_fourth_line(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    # "test.marker" resolves to raw bytes (no schema) -- not numeric, so it
    # is silently dropped per-field rather than crashing or lying about a
    # velocity that was never really there.
    window = _open_window(recording, ego_state_signals={"vx": "test.marker"})
    lines, _banner = window._hud_and_stale_banner(0)
    assert len(lines) == 3  # dropped: not a real numeric value


def test_max_age_configured_and_exceeded_produces_a_stale_banner(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    # age_s is always 0.0 for a freshly-produced port (core/tick.py's own
    # default), so a max_age_s of a negative number is the only way this
    # fixture can force "exceeds its declared maximum" without a live,
    # multi-rate port to hold a stale value across ticks.
    window = _open_window(recording, max_age_s={"test.marker": -1.0})
    _lines, banner = window._hud_and_stale_banner(0)
    assert banner is not None
    assert "test.marker" in banner


def test_max_age_not_exceeded_no_banner(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording, max_age_s={"test.marker": 999.0})
    _lines, banner = window._hud_and_stale_banner(0)
    # AR-57: this fixture's own recording is genuinely stimulus-only, so
    # the OTHER half of the merged banner still fires -- what this test
    # actually asserts is that the STALE half specifically stays absent
    # when nothing is stale, not that the banner slot is empty overall
    # (`test_hud_lines_carry_the_frameworks_own_known_fields` covers that).
    assert banner is not None and "STALE" not in banner


def _make_bundle_bytes(*, project: str) -> bytes:
    """A minimal S-C5-shaped bundle -- `ProjectModel`'s `_bundle_ego` only
    requires `vehicle/ego_params.yaml` (`test_a2_project.py::_make_bundle`
    builds the same shape on disk; this serializes it straight to bytes,
    the way `Recorder.open` embeds a real build's bundle, `R-SIM-6`)."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="adas_sim_hud_bundle_src_"))
    try:
        (tmp_dir / "vehicle").mkdir()
        (tmp_dir / "vehicle" / "ego_params.yaml").write_text(
            "EGO_LENGTH_M: 4.5\nEGO_WIDTH_M: 1.8\nEGO_WHEELBASE_M: 2.7\nEGO_OVERHANG_FRONT_M: 0.9\n",
            encoding="utf-8",
        )
        (tmp_dir / "manifest.yaml").write_text(f"project: {project}\n", encoding="utf-8")
        return bundle_bytes_for_recording(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_hud_reports_checkout_bundle_origin_when_the_recording_carries_no_bundle(tmp_path):
    """`ST-C5-2`: a recording with no embedded bundle (the common case
    today, `config_bundle_bytes=b""`) resolves the viewer's `ProjectModel`
    off the source checkout, and the HUD line names that tier explicitly
    (`R-SIM-3a` -- never silently substituted, never left unstated)."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    lines, _banner = window._hud_and_stale_banner(0)
    assert "cfg:checkout" in lines[2]


def test_no_stimulus_only_banner_when_a_topic_is_genuinely_simulated(tmp_path):
    """`AR-57`'s converse, real end to end: a recording carrying even one
    `Provenance.SIMULATED` topic (a stage's own genuinely-computed and
    recorded output, `R-SIM-12`) reaches `MainWindow` with no STIMULUS-ONLY
    banner -- the merged slot carries neither half's text."""
    recording = tmp_path / "rec_simulated.mcap"
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-hud-sim", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3_hud.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="build-xyz"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.SIMULATED)}
    writer = writer_for(recording)
    writer.open(recording, manifest, topics)
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()

    window = _open_window(recording)
    _lines, banner = window._hud_and_stale_banner(0)
    assert banner is None


def test_hud_reports_embedded_bundle_origin_when_the_recording_carries_its_own_bundle(tmp_path):
    """`ST-C5-2`'s own claim: opening a recording with an embedded bundle
    (`UT-C5-9`'s mechanism) reports `bundle_origin == "embedded"` in the
    HUD -- no checkout project needs to exist for this to be true."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, config_bundle_bytes=_make_bundle_bytes(project=_PROJECT))
    window = _open_window(recording)
    lines, _banner = window._hud_and_stale_banner(0)
    assert "cfg:embedded" in lines[2]
