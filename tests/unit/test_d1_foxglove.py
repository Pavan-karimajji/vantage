# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D1 `render/foxglove.py` tests (`docs/sim_implementation_plan.md`):
`UT-D1-1` (every `PrimKind` maps to a valid entity), `UT-D1-2` (every
entity's `frame_id` exists in the emitted frame graph), `UT-D1-3` (sorted,
deterministic ordering -- two exports of one Scene are byte-identical),
`UT-D1-4` (no module under `scene/` imports or names a Foxglove type).

Foxglove's own SDK message objects are write-only (no readable attributes
beyond `.encode()`/`.get_schema()` -- confirmed against the installed
`foxglove-sdk`, not assumed), so every assertion here decodes `.encode()`'s
bytes back into a real, introspectable protobuf message using the SAME
technique `contracts/component.py`'s `resolve_message_classes` already uses
for a component's own descriptor set: build a `DescriptorPool` from
`ClassName.get_schema().data` (a real `FileDescriptorSet`) and parse into it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

pytest.importorskip("foxglove")  # optional extra (pyproject `[foxglove]`); P-10 -- absent means skip, never a collection error

import foxglove.messages as fg  # noqa: E402
from adas_sim.render.foxglove import (  # noqa: E402
    frame_transforms_for, referenced_frames, scene_entity_for_layer, scene_update,
)
from adas_sim.scene.types import Layer, Prim, PrimKind, Scene  # noqa: E402

_SCENE_DIR = Path(__file__).resolve().parents[2] / "src" / "adas_sim" / "scene"


def _decode(cls: type, encoded: bytes):
    schema = cls.get_schema()
    fds = descriptor_pb2.FileDescriptorSet()
    fds.ParseFromString(schema.data)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in fds.file}
    added: set[str] = set()

    def add(file_proto) -> None:
        if file_proto.name in added:
            return
        added.add(file_proto.name)
        for dependency in file_proto.dependency:
            if dependency in by_name:
                add(by_name[dependency])
        pool.Add(file_proto)

    for file_proto in fds.file:
        add(file_proto)

    msg_cls = message_factory.GetMessageClass(pool.FindMessageTypeByName(schema.name))
    msg = msg_cls()
    msg.ParseFromString(encoded)
    return msg


#: One representative Prim per PrimKind, and which decoded-entity bucket it
#: must land in -- UT-D1-1's own table. `PrimKind.__args__` is the closed
#: catalogue itself (scene/types.py), so a 12th kind added there without a
#: matching row here fails this table's own completeness check below,
#: rather than silently falling through render/foxglove.py's final `else`.
_PRIM_TABLE: dict[PrimKind, tuple[Prim, str]] = {
    "polyline": (Prim(kind="polyline", points_m=((0, 0), (1, 1)), style="truth.trace"), "lines"),
    "polygon": (Prim(kind="polygon", points_m=((0, 0), (1, 0), (1, 1)), style="sensor.fov"), "lines"),
    "box": (Prim(kind="box", cx_m=1, cy_m=1, length_m=1, width_m=1, style="object.default"), "cubes"),
    "circle": (Prim(kind="circle", cx_m=0, cy_m=0, r_m=1, style="sensor.range_ring"), "cylinders"),
    "ellipse": (Prim(kind="ellipse", cx_m=0, cy_m=0, a_m=1, b_m=0.5, style="measure.annotation"), "cylinders"),
    "points": (Prim(kind="points", points_m=((0, 0),), style="object.default"), "spheres"),
    "arrow": (Prim(kind="arrow", x_m=0, y_m=0, dx_m=1, dy_m=1, style="frame.axis"), "arrows"),
    "text": (Prim(kind="text", x_m=0, y_m=0, text="hi", style="object.label"), "texts"),
    "grid": (Prim(kind="grid", extent_m=10, spacing_m=1, style="frame.grid"), "lines"),
    "heatmap": (Prim(kind="heatmap", x0_m=0, y0_m=0, style="object.default"), "texts"),
    "image": (Prim(kind="image", style="object.default"), "texts"),
}


def test_prim_table_covers_the_whole_closed_kind_catalogue():
    """A prerequisite for UT-D1-1 itself: if PrimKind ever grows a 12th
    value, THIS assertion fails first, naming the gap, rather than the new
    kind silently falling through render/foxglove.py's own catch-all."""
    assert set(_PRIM_TABLE) == set(PrimKind.__args__)


@pytest.mark.parametrize("kind", sorted(PrimKind.__args__))
def test_every_prim_kind_maps_to_a_populated_bucket(kind):
    """UT-D1-1."""
    prim, expected_bucket = _PRIM_TABLE[kind]
    entity = scene_entity_for_layer(Layer(id="l", group="g", prims=(prim,)), "dark")
    decoded = _decode(fg.SceneEntity, entity.encode())
    bucket = getattr(decoded, expected_bucket)
    assert len(bucket) == 1, f"{kind!r} did not land in decoded.{expected_bucket}"


def test_every_entity_frame_id_exists_in_the_emitted_frame_graph():
    """UT-D1-2."""
    ego_layer = Layer(id="ego_layer", group="g", prims=(
        Prim(kind="box", cx_m=1, cy_m=1, length_m=1, width_m=1, style="object.default", frame="ego"),
    ))
    sensor_layer = Layer(id="sensor_layer", group="g", prims=(
        Prim(kind="box", cx_m=0, cy_m=0, length_m=1, width_m=1, style="sensor.housing", frame="sensor:0"),
    ))
    scene = Scene(layers=(ego_layer, sensor_layer))

    entity_frame_ids = {
        _decode(fg.SceneEntity, scene_entity_for_layer(layer, "dark").encode()).frame_id for layer in scene.layers
    }
    graph = _decode(fg.FrameTransforms, frame_transforms_for(scene).encode())
    published_children = {t.child_frame_id for t in graph.transforms}

    for frame_id in entity_frame_ids:
        assert frame_id == "world" or frame_id in published_children, (
            f"entity frame_id {frame_id!r} not published by the frame graph"
        )
    # And the chain to world is unbroken for the non-ego frame (the exact
    # stranding bug this stage exists to close): sensor:0 -> ego -> world,
    # every link present.
    assert ("ego", "sensor:0") in {(t.parent_frame_id, t.child_frame_id) for t in graph.transforms}
    assert ("world", "ego") in {(t.parent_frame_id, t.child_frame_id) for t in graph.transforms}


def test_frame_graph_covers_a_scene_referencing_only_ego():
    scene = Scene(layers=(Layer(id="l", group="g", prims=(
        Prim(kind="box", cx_m=0, cy_m=0, length_m=1, width_m=1, style="object.default"),
    )),))
    assert referenced_frames(scene) == ("ego",)
    graph = _decode(fg.FrameTransforms, frame_transforms_for(scene).encode())
    assert {(t.parent_frame_id, t.child_frame_id) for t in graph.transforms} == {("world", "ego")}


def test_entity_and_frame_ordering_is_deterministic_two_exports_identical():
    """UT-D1-3."""
    layers = tuple(
        Layer(id=f"layer_{i}", group="g", prims=(
            Prim(kind="box", cx_m=float(i), cy_m=0.0, length_m=1, width_m=1, style="object.default"),
        ))
        for i in (3, 1, 2)  # declaration order, deliberately not sorted -- must be preserved, not re-sorted
    )
    scene = Scene(layers=layers)
    first = scene_update(scene).encode()
    second = scene_update(scene).encode()
    assert first == second

    first_ft = frame_transforms_for(scene).encode()
    second_ft = frame_transforms_for(scene).encode()
    assert first_ft == second_ft


def test_scene_module_never_imports_or_names_foxglove():
    """UT-D1-4: no module under scene/ imports or names a Foxglove type --
    checked by parsing every scene/*.py file's AST for an "foxglove" import
    or identifier, never by a runtime side effect (so this test needs no
    foxglove-sdk installed to be meaningful)."""
    offenders = []
    for path in sorted(_SCENE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any("foxglove" in alias.name.lower() for alias in node.names):
                    offenders.append(path.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "foxglove" in node.module.lower():
                    offenders.append(path.name)
            elif isinstance(node, ast.Name) and "foxglove" in node.id.lower():
                offenders.append(path.name)
    assert offenders == []


def test_mixed_frame_layer_raises_naming_the_frames_rather_than_misplacing_geometry():
    """A real bug this test suite caught while writing UT-D1-2: an entity
    has exactly one frame_id, so a layer whose prims name more than one
    Prim.frame cannot be flattened into one entity without silently
    misplacing whichever prims are NOT in the entity's declared frame."""
    from adas_sim.render.foxglove import _MixedFrameLayer

    mixed = Layer(id="mixed", group="g", prims=(
        Prim(kind="box", cx_m=0, cy_m=0, length_m=1, width_m=1, style="object.default", frame="ego"),
        Prim(kind="box", cx_m=0, cy_m=0, length_m=1, width_m=1, style="object.default", frame="sensor:0"),
    ))
    with pytest.raises(_MixedFrameLayer):
        scene_entity_for_layer(mixed, "dark")
