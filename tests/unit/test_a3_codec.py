# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 `scene/codec.py` tests: UT-A3-2, UT-A3-8, UT-A3-9, UT-A3-10
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.core.errors import ContractError
from adas_sim.scene.codec import SceneProto, decode_scene, encode_scene
from adas_sim.scene.types import BulkRef, Layer, Prim, Scene

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "adas_sim"


def _sample_scene() -> Scene:
    prim = Prim(kind="box", cx_m=1.0, cy_m=-2.0, length_m=4.5, width_m=1.8, yaw_rad=0.1, style="ego.body")
    layer = Layer(id="sim.test.ego", group="sim", prims=(prim,), label="Ego", level=1, derived=False)
    return Scene(t_s=3.5, layers=(layer,))


def test_scene_round_trips_to_an_equal_object():
    """UT-A3-2."""
    scene = _sample_scene()
    assert decode_scene(encode_scene(scene)) == scene


def test_bulk_ref_and_derived_round_trip():
    """S-A3Δ: `Prim.bulk` (a `BulkRef`) and `Prim.derived` survive encode/decode
    like every other field -- UT-A3-2's contract, extended to the two fields
    this delta adds."""
    ref = BulkRef(topic="df/point_cloud", log_time_ns=42, field="points",
                  count=100_000, encoding="f32[3]")
    prim = Prim(kind="points", bulk=ref, derived=True, style="truth.trace")
    layer = Layer(id="sim.test.cloud", group="sim", prims=(prim,), derived=True)
    scene = Scene(t_s=1.0, layers=(layer,))
    assert decode_scene(encode_scene(scene)) == scene


def test_a_higher_minor_version_still_reads_unknown_fields_skipped():
    """UT-A3-8: a future minor version's extra field is invisible to this
    reader but does not raise, and every field this reader knows survives."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "test_future_scene.proto"
    fdp.package = "adas_sim.scene.v1.test_future"
    fdp.syntax = "proto2"
    msg = fdp.message_type.add()
    msg.name = "FutureScene"
    for name, number, ftype in (("version", 1, _dpb.FieldDescriptorProto.TYPE_STRING),
                                 ("t_s", 2, _dpb.FieldDescriptorProto.TYPE_DOUBLE),
                                 ("note_from_the_future", 99, _dpb.FieldDescriptorProto.TYPE_STRING)):
        f = msg.field.add()
        f.name, f.number, f.type = name, number, ftype
        f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    future_cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.scene.v1.test_future.FutureScene"))
    future_bytes = future_cls(version="1.99", t_s=7.25, note_from_the_future="a S-A4 field, say").SerializeToString()

    scene = decode_scene(future_bytes)
    assert scene.version == "1.99"
    assert scene.t_s == pytest.approx(7.25)
    assert scene.layers == ()


def test_a_higher_major_version_is_refused_naming_both_versions():
    """UT-A3-9: never partially rendered."""
    msg = SceneProto(version="2.0", t_s=1.0)
    with pytest.raises(ContractError) as excinfo:
        decode_scene(msg.SerializeToString())
    err = excinfo.value
    assert "2.0" in err.found
    assert "1" in err.expected


def test_scene_package_imports_nothing_from_render_view_io_or_sources():
    """UT-A3-10: `scene/` imports nothing from `render/`, `view/`, `io/` or
    `sources/` (module scan)."""
    banned = ("render", "view", "io", "sources")
    violations = []
    for path in sorted((SRC_ROOT / "scene").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                parts = name.split(".")
                if parts[0] == "adas_sim" and len(parts) > 1 and parts[1] in banned:
                    violations.append(f"{path}: imports {name}")
    assert not violations, "\n".join(violations)
