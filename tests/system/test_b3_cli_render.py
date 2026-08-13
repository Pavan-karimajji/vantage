# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 13 `cli/render.py` tests: `ST-B3-1` (docs/
sim_implementation_plan.md) -- `sim render <recording> --at <t> --preset
<name> --out fig.png` produces a non-blank PNG **headlessly**. No Qt
import anywhere in this file or in `cli/render.py` itself -- this is the
"needs no display and no PySide6 at all" half of headless, not merely an
offscreen Qt platform."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from adas_sim.cli import main as cli_main
from adas_sim.cli.render import build_parser, run
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import writer_for
import adas_sim.io.mcap  # noqa: F401 -- registers the ".mcap" codec
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim

_PROJECT = "base"
_TICK_COUNT = 5
_DT_NS = 50_000_000


@layer_provider("test.b3l.box", group="test-b3l")
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b3l.box", group="test-b3l", prims=(
        Prim(kind="box", cx_m=5.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="object.label"),
    )),)


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-cli-render", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3l"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def test_render_produces_a_non_blank_png(tmp_path):
    """ST-B3-1."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "fig.png"

    exit_code = run([str(recording), "--at", "0.1", "--out", str(out_png)])
    assert exit_code == 0
    assert out_png.is_file()

    import matplotlib.image
    array = matplotlib.image.imread(out_png)
    assert array.shape[0] > 0 and array.shape[1] > 0
    assert not np.all(array == array[0, 0])  # non-blank: more than one colour


def test_render_with_a_preset_still_produces_a_png(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "fig.png"

    exit_code = run([str(recording), "--at", "0.0", "--preset", "close", "--out", str(out_png)])
    assert exit_code == 0
    assert out_png.is_file()


def test_render_creates_missing_output_directories(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "nested" / "dir" / "fig.png"

    assert run([str(recording), "--at", "0.0", "--out", str(out_png)]) == 0
    assert out_png.is_file()


def test_render_requires_at_and_out():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["some_recording.mcap"])


def test_render_via_the_main_dispatcher(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "fig.png"

    monkeypatch.setattr(sys, "argv", ["sim", "render", str(recording), "--at", "0.0", "--out", str(out_png)])
    assert cli_main() == 0
    assert out_png.is_file()


def test_cli_render_source_names_no_qt_module():
    """Static, not runtime-order-dependent (a shared pytest process may
    already have PySide6 loaded from another test file by the time any
    single test runs) -- `cli/render.py`'s own docstring claims "no Qt
    import anywhere in its dependency chain"; checked directly against the
    source rather than `sys.modules`."""
    import inspect

    from adas_sim.cli import render as render_module
    source = inspect.getsource(render_module)
    assert "import PySide6" not in source and "from PySide6" not in source
    assert "render.viewer" not in source and "app.gui" not in source
