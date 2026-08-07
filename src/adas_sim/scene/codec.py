# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Scene` to bytes and back, **protobuf** (sim_implementation_plan.md
S-A3): field numbering gives minor-version tolerance for free, and a
Foxglove renderer wants the schema anyway (`S-D3`). `Scene.version` is
`major.minor`; additive is minor.

**No `.proto` file, no `protoc`.** The schema below is built once, at import
time, straight from `google.protobuf.descriptor_pb2` into a private
`DescriptorPool` -- the same "no generated bindings required" principle
`R-SIM-11` states for a component's messages, applied to the framework's own
IR. `neither `protoc` nor `grpcio-tools` is available on every platform this
runs on without a new build-time dependency (`P-10`); this way there is
nothing to regenerate and nothing else to install.

Proto2 syntax, deliberately: proto3 singular optional fields need a
synthetic one-field oneof per field for presence-tracking (`HasField`),
which is exactly what a hand-built descriptor should not have to reconstruct
by hand for ~40 fields. Proto2's `optional` gives real presence natively.
This schema is internal to `modules/sim` and is never a cross-component
`interfaces` contract, so `R-NAME-4`'s field-naming rule (not its syntax
choice) is what applies -- fields are snake_case, messages PascalCase.
"""

from __future__ import annotations

from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.core.errors import ContractError
from adas_sim.scene.types import BulkRef, Layer, Prim, Scene

_PACKAGE = "adas_sim.scene.v1"
_FT = _dpb.FieldDescriptorProto
# Every real-valued field below is TYPE_DOUBLE, never TYPE_FLOAT: protobuf's
# "float" is 32-bit single precision, but a Python float is a 64-bit double --
# round-tripping a plain value like 0.1 through TYPE_FLOAT silently rounds it
# to ~0.10000000149011612, which breaks UT-A3-2's round-trip-equality
# contract. Found by that test actually failing, not reasoned in advance.


def _field(msg, name: str, number: int, ftype: int, *, repeated: bool = False, type_name: str | None = None) -> None:
    f = msg.field.add()
    f.name = name
    f.number = number
    f.type = ftype
    f.label = _FT.LABEL_REPEATED if repeated else _FT.LABEL_OPTIONAL
    if type_name is not None:
        f.type_name = type_name


def _build_file_descriptor() -> _dpb.FileDescriptorProto:
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "adas_sim_scene.proto"
    fdp.package = _PACKAGE
    fdp.syntax = "proto2"

    point2d = fdp.message_type.add()
    point2d.name = "Point2D"
    _field(point2d, "x", 1, _FT.TYPE_DOUBLE)
    _field(point2d, "y", 2, _FT.TYPE_DOUBLE)

    float_row = fdp.message_type.add()
    float_row.name = "FloatRow"
    _field(float_row, "v", 1, _FT.TYPE_DOUBLE, repeated=True)

    bulk_ref = fdp.message_type.add()
    bulk_ref.name = "BulkRef"
    _field(bulk_ref, "topic", 1, _FT.TYPE_STRING)
    _field(bulk_ref, "log_time_ns", 2, _FT.TYPE_INT64)
    _field(bulk_ref, "field", 3, _FT.TYPE_STRING)
    _field(bulk_ref, "count", 4, _FT.TYPE_INT32)
    _field(bulk_ref, "encoding", 5, _FT.TYPE_STRING)

    prim = fdp.message_type.add()
    prim.name = "Prim"
    # Field numbers are permanent once shipped (append-only): this is what
    # "minor-version tolerance for free" means in practice -- a future field
    # gets the next unused number, never a renumber, never a reuse.
    _field(prim, "kind", 1, _FT.TYPE_STRING)
    _field(prim, "frame", 2, _FT.TYPE_STRING)
    _field(prim, "style", 3, _FT.TYPE_STRING)
    _field(prim, "pick_id", 4, _FT.TYPE_STRING)
    _field(prim, "z", 5, _FT.TYPE_INT32)
    _field(prim, "alpha", 6, _FT.TYPE_DOUBLE)
    _field(prim, "width_px", 7, _FT.TYPE_DOUBLE)
    _field(prim, "offset_px", 8, _FT.TYPE_MESSAGE, type_name=f".{_PACKAGE}.Point2D")
    _field(prim, "points_m", 9, _FT.TYPE_MESSAGE, repeated=True, type_name=f".{_PACKAGE}.Point2D")
    _field(prim, "closed", 10, _FT.TYPE_BOOL)
    _field(prim, "filled", 11, _FT.TYPE_BOOL)
    _field(prim, "hatch", 12, _FT.TYPE_STRING)
    _field(prim, "marker", 13, _FT.TYPE_STRING)
    _field(prim, "cx_m", 14, _FT.TYPE_DOUBLE)
    _field(prim, "cy_m", 15, _FT.TYPE_DOUBLE)
    _field(prim, "length_m", 16, _FT.TYPE_DOUBLE)
    _field(prim, "width_m", 17, _FT.TYPE_DOUBLE)
    _field(prim, "yaw_rad", 18, _FT.TYPE_DOUBLE)
    _field(prim, "height_m", 19, _FT.TYPE_DOUBLE)
    _field(prim, "r_m", 20, _FT.TYPE_DOUBLE)
    _field(prim, "a_m", 21, _FT.TYPE_DOUBLE)
    _field(prim, "b_m", 22, _FT.TYPE_DOUBLE)
    _field(prim, "x_m", 23, _FT.TYPE_DOUBLE)
    _field(prim, "y_m", 24, _FT.TYPE_DOUBLE)
    _field(prim, "dx_m", 25, _FT.TYPE_DOUBLE)
    _field(prim, "dy_m", 26, _FT.TYPE_DOUBLE)
    _field(prim, "text", 27, _FT.TYPE_STRING)
    _field(prim, "anchor", 28, _FT.TYPE_STRING)
    _field(prim, "spacing_m", 29, _FT.TYPE_DOUBLE)
    _field(prim, "extent_m", 30, _FT.TYPE_DOUBLE)
    _field(prim, "x0_m", 31, _FT.TYPE_DOUBLE)
    _field(prim, "y0_m", 32, _FT.TYPE_DOUBLE)
    _field(prim, "cell_dx_m", 33, _FT.TYPE_DOUBLE)
    _field(prim, "cell_dy_m", 34, _FT.TYPE_DOUBLE)
    _field(prim, "values", 35, _FT.TYPE_MESSAGE, repeated=True, type_name=f".{_PACKAGE}.FloatRow")
    _field(prim, "data", 36, _FT.TYPE_BYTES)
    _field(prim, "format", 37, _FT.TYPE_STRING)
    # Field numbers 38+ added by S-A3Δ (`OD-6`, `OD-7`) -- appended, never
    # renumbered, per this file's own "permanent once shipped" rule above.
    _field(prim, "bulk", 38, _FT.TYPE_MESSAGE, type_name=f".{_PACKAGE}.BulkRef")
    _field(prim, "derived", 39, _FT.TYPE_BOOL)
    # Field 40+ added by `AR-56` (2026-08-07) -- same append-only rule.
    _field(prim, "spacing_lateral_m", 40, _FT.TYPE_DOUBLE)

    layer = fdp.message_type.add()
    layer.name = "Layer"
    _field(layer, "id", 1, _FT.TYPE_STRING)
    _field(layer, "group", 2, _FT.TYPE_STRING)
    _field(layer, "prims", 3, _FT.TYPE_MESSAGE, repeated=True, type_name=f".{_PACKAGE}.Prim")
    _field(layer, "label", 4, _FT.TYPE_STRING)
    _field(layer, "z", 5, _FT.TYPE_INT32)
    _field(layer, "level", 6, _FT.TYPE_INT32)
    _field(layer, "default_on", 7, _FT.TYPE_BOOL)
    _field(layer, "derived", 8, _FT.TYPE_BOOL)
    # Field 9 added by `AR-60` (2026-08-07) -- `Layer.unavailable` (`AR-53`,
    # 2026-08-07) was never wired into this codec at all; caught by a golden
    # round-trip carrying an unavailable layer for the first time.
    _field(layer, "unavailable", 9, _FT.TYPE_STRING)

    scene = fdp.message_type.add()
    scene.name = "Scene"
    _field(scene, "version", 1, _FT.TYPE_STRING)
    _field(scene, "t_s", 2, _FT.TYPE_DOUBLE)
    _field(scene, "layers", 3, _FT.TYPE_MESSAGE, repeated=True, type_name=f".{_PACKAGE}.Layer")

    return fdp


_POOL = _dpool.DescriptorPool()
_POOL.Add(_build_file_descriptor())
Point2DProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.Point2D"))
FloatRowProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.FloatRow"))
BulkRefProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.BulkRef"))
PrimProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.Prim"))
LayerProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.Layer"))
SceneProto = _mfactory.GetMessageClass(_POOL.FindMessageTypeByName(f"{_PACKAGE}.Scene"))

#: This build's major version. A recording carrying a different major is
#: refused outright (`UT-A3-9`); a different minor still reads (`UT-A3-8`).
SUPPORTED_MAJOR = 1

#: Every optional `Prim` field name (i.e. everything but `kind`), used to
#: copy only the fields a caller actually set (`HasField`) in both directions.
_PRIM_SCALAR_FIELDS = (
    "frame", "style", "pick_id", "z", "alpha", "width_px",
    "closed", "filled", "hatch", "marker",
    "cx_m", "cy_m", "length_m", "width_m", "yaw_rad", "height_m", "r_m", "a_m", "b_m",
    "x_m", "y_m", "dx_m", "dy_m", "text", "anchor",
    "spacing_m", "extent_m", "x0_m", "y0_m", "cell_dx_m", "cell_dy_m",
    "data", "format", "derived", "spacing_lateral_m",
)


def _prim_to_proto(prim: Prim) -> PrimProto:
    msg = PrimProto(kind=prim.kind)
    for name in _PRIM_SCALAR_FIELDS:
        value = getattr(prim, name)
        if value is not None:
            setattr(msg, name, value)
    if prim.offset_px is not None:
        msg.offset_px.x, msg.offset_px.y = prim.offset_px
    if prim.points_m is not None:
        for x, y in prim.points_m:
            msg.points_m.add(x=x, y=y)
    if prim.values is not None:
        for row in prim.values:
            msg.values.add(v=list(row))
    if prim.bulk is not None:
        msg.bulk.topic = prim.bulk.topic
        msg.bulk.log_time_ns = prim.bulk.log_time_ns
        msg.bulk.field = prim.bulk.field
        msg.bulk.count = prim.bulk.count
        msg.bulk.encoding = prim.bulk.encoding
    return msg


def _prim_from_proto(msg: PrimProto) -> Prim:
    kwargs: dict[str, object] = {"kind": msg.kind}
    for name in _PRIM_SCALAR_FIELDS:
        if msg.HasField(name):
            kwargs[name] = getattr(msg, name)
    if msg.HasField("offset_px"):
        kwargs["offset_px"] = (msg.offset_px.x, msg.offset_px.y)
    if len(msg.points_m):
        kwargs["points_m"] = tuple((p.x, p.y) for p in msg.points_m)
    if len(msg.values):
        kwargs["values"] = tuple(tuple(row.v) for row in msg.values)
    if msg.HasField("bulk"):
        kwargs["bulk"] = BulkRef(
            topic=msg.bulk.topic, log_time_ns=msg.bulk.log_time_ns,
            field=msg.bulk.field, count=msg.bulk.count, encoding=msg.bulk.encoding,
        )
    return Prim(**kwargs)


def _layer_to_proto(layer: Layer) -> LayerProto:
    msg = LayerProto(
        id=layer.id, group=layer.group, label=layer.label, z=layer.z,
        level=layer.level, default_on=layer.default_on, derived=layer.derived,
    )
    if layer.unavailable is not None:
        msg.unavailable = layer.unavailable
    for prim in layer.prims:
        msg.prims.append(_prim_to_proto(prim))
    return msg


def _layer_from_proto(msg: LayerProto) -> Layer:
    return Layer(
        id=msg.id, group=msg.group, prims=tuple(_prim_from_proto(p) for p in msg.prims),
        label=msg.label, z=msg.z, level=msg.level, default_on=msg.default_on, derived=msg.derived,
        unavailable=msg.unavailable if msg.HasField("unavailable") else None,
    )


def encode_scene(scene: Scene) -> bytes:
    msg = SceneProto(version=scene.version, t_s=scene.t_s)
    for layer in scene.layers:
        msg.layers.append(_layer_to_proto(layer))
    return msg.SerializeToString()


def decode_scene(data: bytes) -> Scene:
    msg = SceneProto()
    msg.ParseFromString(data)
    version = msg.version
    major_str = version.split(".", 1)[0] if version else ""
    try:
        major = int(major_str)
    except ValueError:
        major = None
    if major != SUPPORTED_MAJOR:
        raise ContractError(
            expected=f"Scene major version {SUPPORTED_MAJOR}", found=f"version {version!r}",
            where="adas_sim.scene.codec.decode_scene",
            hint="a major version bump is a breaking Scene schema change -- never partially rendered",
        )
    return Scene(
        version=version, t_s=msg.t_s,
        layers=tuple(_layer_from_proto(layer) for layer in msg.layers),
    )
