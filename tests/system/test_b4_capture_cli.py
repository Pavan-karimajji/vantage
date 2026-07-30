# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4 tests: `ST-B4-1`, `ST-B4-2` (docs/sim_implementation_plan.md).
No Qt import anywhere in this file or in its dependency chain -- same
"needs no display and no PySide6 at all" discipline `test_b3_cli_render.py`
already established for `cli/render.py`, extended to `render/capture.py`
(`S-B4`)."""

from __future__ import annotations

import json

from adas_sim.cli.render import run
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.io.registry import writer_for
import adas_sim.io.mcap  # noqa: F401 -- registers the ".mcap" codec
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim

_PROJECT = "base"
_TICK_COUNT = 5
_DT_NS = 50_000_000


@layer_provider("test.b4cli.box", group="test-b4cli")
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b4cli.box", group="test-b4cli", prims=(
        Prim(kind="box", cx_m=5.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="object.label"),
    )),)


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b4-cli-render", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b4.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b4cli"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def test_render_twice_at_the_same_tick_is_byte_identical(tmp_path):
    """ST-B4-1: a snapshot is reproducible evidence."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_a = tmp_path / "a.png"
    out_b = tmp_path / "b.png"

    assert run([str(recording), "--at", "0.1", "--out", str(out_a)]) == 0
    assert run([str(recording), "--at", "0.1", "--out", str(out_b)]) == 0
    assert out_a.read_bytes() == out_b.read_bytes()


def test_render_works_with_no_display(tmp_path):
    """ST-B4-2's buildable half: matplotlib's `Agg` backend (`render/bev.py`)
    needs no display at all -- unlike `S-B3`'s Qt panels, there is no
    offscreen-platform flag to set here, which is the point (`UT-B3-17`: no
    Qt anywhere in this dependency chain). "On both platforms" stays open,
    same basis as `ST-B3-2`: no Ubuntu environment this session can verify
    against."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "fig.png"

    assert run([str(recording), "--at", "0.0", "--out", str(out_png)]) == 0
    assert out_png.is_file()


def test_render_writes_a_provenance_sidecar(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_png = tmp_path / "fig.png"

    assert run([str(recording), "--at", "0.1", "--project", _PROJECT, "--out", str(out_png)]) == 0
    sidecar = json.loads(out_png.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["run_id"] == "test-b4-cli-render"
    assert sidecar["project"] == _PROJECT
    assert sidecar["components"][0]["name"] == "test"


def test_render_svg_output_is_vector(tmp_path):
    """`D5`: same Scene, vector output chosen from `--out`'s own suffix."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_svg = tmp_path / "fig.svg"

    assert run([str(recording), "--at", "0.1", "--theme", "print", "--out", str(out_svg)]) == 0
    assert out_svg.is_file()
    assert out_svg.read_bytes().lstrip().startswith(b"<?xml")
    assert out_svg.with_suffix(".json").is_file()
