# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 6 `core/signals.py` tests: `UT-B3-6`
(docs/sim_implementation_plan.md) plus the resolver mechanics it rests on --
longest-prefix port matching, field-path walking (incl. repeated-field
indexing), and `@signal`/`derived.*` dispatch. No Qt (`core/` stays
Qt-free, `UT-B3-17`)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.core.history import FrameTree, HistoryView, LayerCtx
from adas_sim.core.signals import _SIGNALS, registered_signals, resolve_series, resolve_tick, signal
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.model.project import ProjectModel

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


@pytest.fixture(autouse=True)
def _clean_signal_registry():
    """The registry is module-global (`layer_provider`'s own pattern, `S-A3`
    onward) -- restore it so one test's `@signal` cannot leak into another."""
    before = dict(_SIGNALS)
    yield
    _SIGNALS.clear()
    _SIGNALS.update(before)


def _tick(index: int, ports: dict) -> Tick:
    return Tick(index=index, t_ns=index * 50_000_000, dt_ns=50_000_000, ports=ports, pose=_POSE)


def _port(name: str, message: object) -> PortValue:
    return PortValue(name=name, message=message, origin="measured")


def test_raw_port_field_needs_no_registration_at_all():
    """UT-B3-6."""
    message = SimpleNamespace(longitudinal=SimpleNamespace(velocity=12.5))
    tick = _tick(0, {"source.veh_dyn": _port("source.veh_dyn", message)})
    assert resolve_tick(tick, "source.veh_dyn.longitudinal.velocity") == 12.5


def test_resolve_finds_the_longest_matching_port_not_the_first():
    short = SimpleNamespace(c=SimpleNamespace(d="wrong -- this is the a.b port's own field c.d"))
    long = SimpleNamespace(d="right")
    tick = _tick(0, {
        "a.b": _port("a.b", short),
        "a.b.c": _port("a.b.c", long),
    })
    assert resolve_tick(tick, "a.b.c.d") == "right"


def test_resolve_with_no_field_path_returns_the_whole_port_message():
    message = SimpleNamespace(x=1)
    tick = _tick(0, {"truth.objects": _port("truth.objects", message)})
    assert resolve_tick(tick, "truth.objects") is message


def test_resolve_walks_a_repeated_field_index():
    message = SimpleNamespace(objects=[SimpleNamespace(dist_x=3.2), SimpleNamespace(dist_x=9.1)])
    tick = _tick(0, {"truth.objects": _port("truth.objects", message)})
    assert resolve_tick(tick, "truth.objects.objects[1].dist_x") == 9.1


def test_resolve_raises_for_an_out_of_range_index():
    message = SimpleNamespace(objects=[SimpleNamespace(dist_x=3.2)])
    tick = _tick(0, {"truth.objects": _port("truth.objects", message)})
    with pytest.raises(AuthoringError) as excinfo:
        resolve_tick(tick, "truth.objects.objects[5].dist_x")
    assert "5" in excinfo.value.expected


def test_resolve_raises_for_an_address_matching_no_known_port():
    tick = _tick(0, {"a.b": _port("a.b", SimpleNamespace())})
    with pytest.raises(AuthoringError) as excinfo:
        resolve_tick(tick, "nothing.like.this")
    assert "a.b" in excinfo.value.hint


def test_resolve_raises_naming_the_missing_field():
    message = SimpleNamespace(known=1)
    tick = _tick(0, {"a.b": _port("a.b", message)})
    with pytest.raises(AuthoringError) as excinfo:
        resolve_tick(tick, "a.b.unknown_field")
    assert "unknown_field" in excinfo.value.expected


def test_resolve_raises_when_the_port_message_is_invalid_this_tick():
    tick = _tick(0, {"a.b": _port("a.b", None)})
    with pytest.raises(AuthoringError):
        resolve_tick(tick, "a.b.anything")


def test_signal_decorator_rejects_a_duplicate_name():
    @signal("derived.test_dup")
    def _first(tick, ctx):
        return 0.0

    with pytest.raises(AuthoringError) as excinfo:
        @signal("derived.test_dup")
        def _second(tick, ctx):
            return 0.0

    assert "_first" in excinfo.value.expected
    assert "_second" in excinfo.value.found


def test_signal_is_registered_with_its_unit():
    @signal("derived.test_unit", unit="s")
    def _ttc(tick, ctx):
        return 1.0

    assert registered_signals()["derived.test_unit"] == (_ttc, "s")


def test_derived_signal_resolves_via_resolve_tick_given_a_ctx():
    @signal("derived.test_double")
    def _double(tick, ctx):
        return tick.index * 2

    ctx = LayerCtx(model=ProjectModel.resolve(project="base"), history=HistoryView(_ticks=()), frames=FrameTree(_POSE))
    tick = _tick(5, {})
    assert resolve_tick(tick, "derived.test_double", ctx=ctx) == 10


def test_derived_signal_without_ctx_raises_naming_the_signal():
    @signal("derived.test_needs_ctx")
    def _f(tick, ctx):
        return 0.0

    tick = _tick(0, {})
    with pytest.raises(AuthoringError) as excinfo:
        resolve_tick(tick, "derived.test_needs_ctx")
    assert "derived.test_needs_ctx" in excinfo.value.hint


def test_resolve_series_returns_tick_index_value_pairs_in_order():
    ticks = tuple(_tick(i, {"a.b": _port("a.b", SimpleNamespace(v=i * 10))}) for i in range(4))
    assert resolve_series(ticks, "a.b.v") == ((0, 0), (1, 10), (2, 20), (3, 30))


def test_resolve_series_for_a_raw_field_never_resolves_a_project():
    """A raw field pays no `ProjectModel.resolve` cost -- proven by using a
    project name that does not exist under `shared_config/projects` and
    still succeeding."""
    ticks = tuple(_tick(i, {"a.b": _port("a.b", SimpleNamespace(v=i))}) for i in range(2))
    assert resolve_series(ticks, "a.b.v", project="no-such-project-anywhere") == ((0, 0), (1, 1))


def test_resolve_series_for_a_derived_signal_builds_a_real_ctx_per_tick():
    @signal("derived.test_series_ego")
    def _project_name(tick, ctx):
        return ctx.model.project

    ticks = tuple(_tick(i, {}) for i in range(3))
    result = resolve_series(ticks, "derived.test_series_ego", project="base")
    assert result == ((0, "base"), (1, "base"), (2, "base"))


def _enum_message_cls():
    """A real `{state: Enum}` schema -- a protobuf enum field decodes to a
    bare int by default (`google.protobuf`'s own Python mapping); this is
    what `_walk_field_path`'s enum-name resolution actually converts."""
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.name = "b3_signals_enum.proto"
    fdp.package = "adas_sim.test.b3signals"
    fdp.syntax = "proto3"
    enum = fdp.enum_type.add()
    enum.name = "WarningState"
    for name, number in [("OFF", 0), ("NORMAL", 1), ("BLINKING", 2)]:
        value = enum.value.add()
        value.name, value.number = name, number
    msg = fdp.message_type.add()
    msg.name = "SideState"
    f = msg.field.add()
    f.name, f.number, f.type, f.type_name = (
        "warning", 1, descriptor_pb2.FieldDescriptorProto.TYPE_ENUM, ".adas_sim.test.b3signals.WarningState",
    )

    pool = descriptor_pool.DescriptorPool()
    pool.Add(fdp)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.b3signals.SideState"))


def test_an_enum_field_resolves_to_its_name_not_its_bare_int():
    """UT-B3-6-equivalent: `equals: NORMAL` in an `expect:` block (or a plot
    label) must compare a name against a name, never `1` against
    `'NORMAL'`."""
    side_state_cls = _enum_message_cls()
    message = side_state_cls(warning=1)
    tick = _tick(0, {"df.bsd.outputs": _port("df.bsd.outputs", message)})
    assert resolve_tick(tick, "df.bsd.outputs.warning") == "NORMAL"
