# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Scene -> Foxglove `SceneUpdate`/`FrameTransforms` (S-D1, `R-SIM-13`):
demonstrating "visualization is identical regardless of origin" in a viewer
we did not write, by translating the SAME `Scene` a Qt/matplotlib renderer
already draws into a foreign tool's own schema, rather than a second,
independent rendering.

**One entity per `Layer`** (this stage's own checklist item), so Foxglove
Studio's own per-entity visibility toggle lines up with our layer toggles
for free. **Entity id IS `Layer.id`, unchanged** (`N-2`/`N-6`) -- no
translation table, so a layer named in an error or the inspector reads
identically in both viewers.

**Must not** (this stage's own words): let a Foxglove type reach `scene/`.
This module is the ONLY place `foxglove.messages` is imported anywhere in
this package -- `UT-D1-4` asserts it mechanically. The mapping is
one-directional: `scene/` has never heard of Foxglove, and never will.

**Frame graph.** Real dynamic pose composition (sensor mounting, ego
kinematics) needs `core/tick.py`'s `Tick` composed with the project's
resolved poses -- out of scope here, same as `sim_visualization_spec.md`
§11.4 already scopes real camera extrinsics to a later phase ("Scoped for
Phase D4"). What THIS stage owns is narrower and load-bearing on its own:
the earlier Foxglove attempt failed because an entity referenced a frame
(`chase_camera`) nothing ever published, and every entity silently rendered
at the origin (`df_carla_viz_plan.md` §2). `frame_transforms_for` closes
exactly that hole -- a static identity transform for every frame a Scene's
prims actually reference, parented to `"ego"` -- never a real pose, but
never a stranded reference either.

**Heatmap/image.** Foxglove's `SceneEntity` has no bulk-data primitive (no
`PointCloud`/`Grid`/`CompressedImage` slot on the entity itself -- those are
separate top-level channels). `R-SIM-2` already keeps a `Prim`'s bulk
payload OUT of the Scene (`Prim.bulk`, a `BulkRef` into the recording), so
there is nothing more to draw here even in principle: this module maps both
kinds to a labelled placeholder `TextPrimitive` naming the referenced topic,
satisfying `UT-D1-1`'s "every kind maps to something" without pretending to
render bytes it was never handed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import foxglove.messages as fg

from adas_sim.io.base import Provenance, RecordingWriter, TopicInfo
from adas_sim.render.theme import Theme, resolve
from adas_sim.scene.types import Layer, Prim, Scene

#: The two topics `write_scene_snapshot` writes into (checklist item 3:
#: "`/scene` topic written into a session recording, so a recording opened
#: cold shows the full spatial scene with no framework present"). Foxglove
#: Studio recognizes these natively by schema NAME (`foxglove.SceneUpdate`/
#: `foxglove.FrameTransforms`) -- no custom panel, no framework code needed
#: to view them, which is the whole point of writing a foreign tool's own
#: schema rather than our own.
SCENE_TOPIC = "/scene"
FRAME_TRANSFORMS_TOPIC = "/tf"

#: Used whenever `Prim.style` is empty -- a prim with no explicit style is
#: still drawable (many providers rely on the layer's own convention), and
#: `theme.resolve` refuses an unregistered/empty token outright (`UT-A3-4`),
#: so SOME registered fallback is required. `object.default` is the
#: framework's own generic-object token (`render/theme.py`), reused rather
#: than a second default color literal living in this module.
_FALLBACK_STYLE = "object.default"

#: A flat prim's z-extent in a 3D viewer (circle/ellipse/heatmap
#: placeholder) -- legibility, not geometry (mirrors `Prim.width_px`'s own
#: "pixels are not physical" exception, just in the one axis a Scene's 2D
#: prims don't otherwise have).
_THIN_HEIGHT_M = 0.05

#: `Prim.z` is stacking ORDER (a small int), not metres. Foxglove has no
#: separate z-order concept for coplanar entities, so this converts order
#: into a deterministic, tiny vertical offset -- enough that two prims at
#: different `z` never occupy exactly one depth plane, never large enough to
#: read as real height.
_Z_ORDER_SCALE_M = 0.001

_IDENTITY_QUATERNION = fg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)


def _hex_to_color(hex_color: str, alpha: float) -> fg.Color:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return fg.Color(r=r, g=g, b=b, a=alpha)


def _color_for(prim: Prim, theme: Theme) -> fg.Color:
    style = resolve(prim.style or _FALLBACK_STYLE, theme)
    return _hex_to_color(style.color, prim.alpha)


def _z_of(prim: Prim) -> float:
    return prim.z * _Z_ORDER_SCALE_M


def _yaw_pose(x: float, y: float, z: float, yaw_rad: float) -> fg.Pose:
    # Pose.position is a Vector3 (NOT Point3, despite the SDK's own
    # docstring saying "Point denoting position") -- Point3 is for raw
    # geometry arrays (LinePrimitive.points etc.), Vector3 for a pose;
    # confirmed against the installed foxglove-sdk directly (TypeError
    # otherwise), not assumed from the docs.
    return fg.Pose(
        position=fg.Vector3(x=x, y=y, z=z),
        orientation=fg.Quaternion(x=0.0, y=0.0, z=math.sin(yaw_rad / 2.0), w=math.cos(yaw_rad / 2.0)),
    )


def _flat_pose(x: float, y: float, z: float) -> fg.Pose:
    return fg.Pose(position=fg.Vector3(x=x, y=y, z=z), orientation=_IDENTITY_QUATERNION)


def _points3(points_m: Iterable[tuple[float, float]], z: float) -> list[fg.Point3]:
    return [fg.Point3(x=x, y=y, z=z) for x, y in points_m]


class _UnmappedPrimKind(ValueError):
    """A `Prim.kind` this module does not know how to draw -- `Prim.__post_
    init__` already refuses anything outside the closed `PrimKind` set, so
    reaching this means the catalogue grew and this module was not updated
    alongside it (exactly the failure `UT-D1-1`'s table-driven test exists
    to catch before a foreign viewer silently drops the new kind)."""


def _append_primitive(prim: Prim, theme: Theme, buckets: dict[str, list[object]]) -> None:
    """Appends this ONE prim's Foxglove primitive(s) into `buckets`' per-kind
    lists (`lines`/`cubes`/`spheres`/`cylinders`/`arrows`/`texts`) -- the
    caller owns one `SceneEntity` per `Layer`, so every prim in that layer
    contributes into the SAME entity's buckets."""
    color = _color_for(prim, theme)
    z = _z_of(prim)

    if prim.kind == "polyline":
        buckets["lines"].append(fg.LinePrimitive(
            type=fg.LinePrimitiveLineType.LineLoop if prim.closed else fg.LinePrimitiveLineType.LineStrip,
            points=_points3(prim.points_m or (), z), color=color, thickness=(prim.width_px or 2.0) * 0.02,
        ))
    elif prim.kind == "polygon":
        # Foxglove's LinePrimitive draws an outline only -- `filled`/`hatch`
        # have no native fill equivalent without triangulating an arbitrary
        # polygon, out of scope here (an honest gap, not a silent one: the
        # outline itself is never wrong, only never filled).
        buckets["lines"].append(fg.LinePrimitive(
            type=fg.LinePrimitiveLineType.LineLoop, points=_points3(prim.points_m or (), z), color=color,
            thickness=(prim.width_px or 2.0) * 0.02,
        ))
    elif prim.kind == "points":
        for x, y in prim.points_m or ():
            buckets["spheres"].append(fg.SpherePrimitive(
                pose=_flat_pose(x, y, z), size=fg.Vector3(x=0.2, y=0.2, z=0.2), color=color,
            ))
    elif prim.kind == "box":
        buckets["cubes"].append(fg.CubePrimitive(
            pose=_yaw_pose(prim.cx_m or 0.0, prim.cy_m or 0.0, z, prim.yaw_rad or 0.0),
            size=fg.Vector3(x=prim.length_m or 0.0, y=prim.width_m or 0.0, z=prim.height_m or _THIN_HEIGHT_M),
            color=color,
        ))
    elif prim.kind == "circle":
        diameter = (prim.r_m or 0.0) * 2.0
        buckets["cylinders"].append(fg.CylinderPrimitive(
            pose=_flat_pose(prim.cx_m or 0.0, prim.cy_m or 0.0, z),
            size=fg.Vector3(x=diameter, y=diameter, z=_THIN_HEIGHT_M),
            bottom_scale=1.0, top_scale=1.0, color=color,
        ))
    elif prim.kind == "ellipse":
        buckets["cylinders"].append(fg.CylinderPrimitive(
            pose=_yaw_pose(prim.cx_m or 0.0, prim.cy_m or 0.0, z, prim.yaw_rad or 0.0),
            size=fg.Vector3(x=(prim.a_m or 0.0) * 2.0, y=(prim.b_m or 0.0) * 2.0, z=_THIN_HEIGHT_M),
            bottom_scale=1.0, top_scale=1.0, color=color,
        ))
    elif prim.kind == "arrow":
        length = math.hypot(prim.dx_m or 0.0, prim.dy_m or 0.0)
        yaw = math.atan2(prim.dy_m or 0.0, prim.dx_m or 0.0)
        buckets["arrows"].append(fg.ArrowPrimitive(
            pose=_yaw_pose(prim.x_m or 0.0, prim.y_m or 0.0, z, yaw),
            shaft_length=length * 0.8, shaft_diameter=0.08, head_length=length * 0.2, head_diameter=0.16,
            color=color,
        ))
    elif prim.kind == "text":
        buckets["texts"].append(fg.TextPrimitive(
            pose=_flat_pose(prim.x_m or 0.0, prim.y_m or 0.0, z), billboard=True, font_size=16.0, color=color,
            text=prim.text or "",
        ))
    elif prim.kind == "grid":
        # The bounding outline only, not every gridline -- a line per
        # `spacing_m` division would make entity size a function of extent /
        # spacing rather than a bounded, deterministic count.
        half = (prim.extent_m or 0.0) / 2.0
        corners = ((-half, -half), (half, -half), (half, half), (-half, half))
        buckets["lines"].append(fg.LinePrimitive(
            type=fg.LinePrimitiveLineType.LineLoop, points=_points3(corners, z), color=color, thickness=0.02,
        ))
    elif prim.kind in ("heatmap", "image"):
        topic = prim.bulk.topic if prim.bulk is not None else "(no bulk reference)"
        buckets["texts"].append(fg.TextPrimitive(
            pose=_flat_pose(prim.x0_m or 0.0, prim.y0_m or 0.0, z), billboard=True, font_size=12.0, color=color,
            text=f"[{prim.kind} -- bulk data, not rendered here (R-SIM-2); recording topic: {topic}]",
        ))
    else:
        raise _UnmappedPrimKind(f"Prim.kind {prim.kind!r} has no Foxglove mapping in render/foxglove.py")


_BUCKET_KEYS = ("lines", "cubes", "spheres", "cylinders", "arrows", "texts")


class _MixedFrameLayer(ValueError):
    """A layer whose prims name more than one `Prim.frame` -- one
    `SceneEntity` has exactly one `frame_id`, so a prim's own coordinates
    are only meaningful under a single, consistent frame per entity. Raised
    rather than silently rendering a `sensor:0`-relative prim as if it were
    `ego`-relative (exactly the class of bug `frame_transforms_for`'s own
    docstring names -- a stranded/misattributed frame, just caught here
    instead of left to render wrong in the foreign viewer). If a real layer
    provider ever legitimately needs this, the fix is splitting it into one
    layer per frame upstream (still `R-SIM-2`-clean geometry), not widening
    this adapter to guess."""


def scene_entity_for_layer(layer: Layer, theme: Theme) -> fg.SceneEntity:
    """One `SceneEntity` per `Layer` -- id unchanged (`N-2`), so toggling
    this entity off in Foxglove Studio is exactly toggling this layer off in
    the GUI viewer. `frame_id` is the layer's OWN prims' frame (`"ego"` for an
    empty layer) -- every prim in the layer must share it; see
    `_MixedFrameLayer`. Prims within the layer are emitted in DECLARATION
    order into each bucket (`UT-D1-3`: never a set/dict-iteration order)."""
    frames = {prim.frame for prim in layer.prims}
    if len(frames) > 1:
        raise _MixedFrameLayer(
            f"layer {layer.id!r} mixes frames {sorted(frames)} -- one SceneEntity needs one frame_id"
        )
    frame_id = next(iter(frames), "ego")

    buckets: dict[str, list[object]] = {key: [] for key in _BUCKET_KEYS}
    for prim in layer.prims:
        _append_primitive(prim, theme, buckets)
    return fg.SceneEntity(
        frame_id=frame_id, id=layer.id,
        lines=buckets["lines"], cubes=buckets["cubes"], spheres=buckets["spheres"],
        cylinders=buckets["cylinders"], arrows=buckets["arrows"], texts=buckets["texts"],
    )


def scene_update(scene: Scene, theme: Theme = "dark") -> fg.SceneUpdate:
    """The whole `Scene`, one entity per `Layer`, layers in `Scene.layers`'
    own declaration order (`UT-D1-3`: sorted/deterministic, never re-derived
    from a set)."""
    return fg.SceneUpdate(entities=[scene_entity_for_layer(layer, theme) for layer in scene.layers])


def referenced_frames(scene: Scene) -> tuple[str, ...]:
    """Every DISTINCT frame name any prim in `scene` actually uses, sorted
    (`UT-D1-3`) -- the set `frame_transforms_for` must cover for `UT-D1-2`
    to hold (no entity may reference a frame the graph never publishes)."""
    frames: set[str] = set()
    for layer in scene.layers:
        for prim in layer.prims:
            frames.add(prim.frame)
    return tuple(sorted(frames))


def frame_transforms_for(scene: Scene) -> fg.FrameTransforms:
    """A static identity transform for every frame `scene`'s prims
    reference, parented to `"ego"` (`"ego"` itself is parented to `"world"`,
    completing the two base frames -- `R-COORD-1`). NEVER a real pose (that
    needs `core/tick.py`'s `Tick` composed with the project's resolved
    mounting poses, out of scope here, see the module docstring) -- this
    closes only the stranding bug (`UT-D1-2`): every `frame_id` an entity
    names resolves to SOMETHING in the graph, even if that something is not
    yet where the sensor really sits.
    """
    frames = referenced_frames(scene)
    transforms = []
    for frame in frames:
        if frame == "ego":
            parent = "world"
        elif frame == "world":
            continue  # world has no parent; nothing to publish for it
        else:
            parent = "ego"
        transforms.append(fg.FrameTransform(
            parent_frame_id=parent, child_frame_id=frame,
            translation=fg.Vector3(x=0.0, y=0.0, z=0.0), rotation=_IDENTITY_QUATERNION,
        ))
    if "ego" not in frames and any(f != "world" for f in frames):
        # A non-base frame was referenced without "ego" itself appearing --
        # still needs ego -> world published so the chain to world resolves.
        transforms.append(fg.FrameTransform(
            parent_frame_id="world", child_frame_id="ego",
            translation=fg.Vector3(x=0.0, y=0.0, z=0.0), rotation=_IDENTITY_QUATERNION,
        ))
    return fg.FrameTransforms(transforms=transforms)


def scene_recording_topics() -> dict[str, TopicInfo]:
    """`{SCENE_TOPIC: ..., FRAME_TRANSFORMS_TOPIC: ...}` -- a caller merges
    this into its own `topics` mapping before `RecordingWriter.open()`
    (channels are registered at `open()` time, not per write, `io/mcap.py`'s
    own discipline). `schema_bytes` is each message class's own real
    `FileDescriptorSet` (`ClassName.get_schema().data`) -- Foxglove Studio
    resolves the channel by schema NAME alone, so no generated binding is
    needed on the reading side either (`R-SIM-11`, same reasoning `interfaces`'
    own manifest embedding already relies on)."""
    return {
        SCENE_TOPIC: TopicInfo(
            schema_name=fg.SceneUpdate.get_schema().name, provenance=Provenance.SIMULATED,
            schema_bytes=fg.SceneUpdate.get_schema().data,
        ),
        FRAME_TRANSFORMS_TOPIC: TopicInfo(
            schema_name=fg.FrameTransforms.get_schema().name, provenance=Provenance.SIMULATED,
            schema_bytes=fg.FrameTransforms.get_schema().data,
        ),
    }


def write_scene_snapshot(writer: RecordingWriter, scene: Scene, log_time_ns: int, theme: Theme = "dark") -> None:
    """Writes one tick's `/scene` + `/tf` messages into an ALREADY-OPEN
    `writer` (its `topics` must already include `scene_recording_topics()`'s
    two entries, or the write raises on an unregistered channel same as any
    other topic would). `capture_time_ns=log_time_ns`: a Scene is a pure
    function of the tick it was built for, so reception and validity are the
    same instant here, unlike a sensor's own two-clock model (`R-SIM-14`).

    **Not yet called from `sources/recorder.py`'s live tick loop** -- that
    needs the recorder to build a `Scene` each tick (`core/runner.py`'s
    `build_scene`, today only called from the Qt viewer's own paint path),
    a separate integration into already-tested live-recording code left for
    a follow-up pass rather than risked alongside this stage's own untested-
    in-production mapping code. This function is the tested, ready-to-call
    primitive that integration would use.
    """
    writer.write(SCENE_TOPIC, log_time_ns, scene_update(scene, theme).encode(), capture_time_ns=log_time_ns)
    writer.write(
        FRAME_TRANSFORMS_TOPIC, log_time_ns, frame_transforms_for(scene).encode(), capture_time_ns=log_time_ns,
    )
