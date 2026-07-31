# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 tests for `modules/df/sim/layers/{common,bsd}.py`: UT-B1-2, UT-B1-3,
UT-B1-4, UT-B1-5, UT-B1-6, UT-B1-7, UT-B1-8, UT-B1-11, UT-B1-12, UT-B1-13,
UT-B1-14 (docs/sim_implementation_plan.md). Also UT-C4-1, UT-C4-2 (`S-C4`).

Placement note: these test a component's own layer providers
(`modules/df/sim/layers/`), not the framework. They live here rather than in
a `modules/df`-owned suite because that is where `S-B1`'s own test IDs are
tracked and where the pytest infrastructure already exists; `modules/df` has
no Python test suite yet (only C++ `ctest`). Revisit if one is ever added
for other reasons.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import replace
from pathlib import Path

import pytest

MODULES_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DF_ROOT = MODULES_ROOT / "df"
_GENERATED_PY = MODULES_ROOT / "interfaces" / "build" / "generated_py"

if str(DF_ROOT) not in sys.path:
    sys.path.insert(0, str(DF_ROOT))

from adas_sim.core.history import FrameTree, HistoryView, LayerCtx  # noqa: E402
from adas_sim.core.tick import Pose2D, PortValue, Tick  # noqa: E402
from adas_sim.model.project import ProjectModel  # noqa: E402
from adas_sim.model.sensors import SensorModel  # noqa: E402

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _load_generated_bindings():
    """The interfaces component's own generated protobuf bindings, used here
    only to construct controlled test messages -- never required by the
    framework itself (R-SIM-11), and this build output may not exist on a
    fresh checkout (a partial clone), hence the named skip."""
    required = [
        _GENERATED_PY / "PerceptionCore__Outputs" / "gen_object_list_pb2.py",
        _GENERATED_PY / "VehSigProvider__Outputs" / "veh_dyn_pb2.py",
        _GENERATED_PY / "Bsd__Outputs" / "bsd_outputs_pb2.py",
    ]
    if not all(p.is_file() for p in required):
        return None
    for sub in ("", "PerceptionCore__Outputs", "VehSigProvider__Outputs", "Bsd__Outputs"):
        path = str(_GENERATED_PY / sub) if sub else str(_GENERATED_PY)
        if path not in sys.path:
            sys.path.insert(0, path)
    import bsd_outputs_pb2
    import gen_object_list_pb2
    import veh_dyn_pb2
    return gen_object_list_pb2, veh_dyn_pb2, bsd_outputs_pb2


_bindings = _load_generated_bindings()
pytestmark = pytest.mark.skipif(
    _bindings is None,
    reason="modules/interfaces/build/generated_py is absent -- build interfaces first",
)
if _bindings is not None:
    _gen_object_list_pb2, _veh_dyn_pb2, _bsd_outputs_pb2 = _bindings
    from sim.layers import bsd, common  # noqa: E402  (df's own package, needs DF_ROOT on sys.path)


def _veh_dyn(vx: float = 20.0, yaw_rate: float = 0.0):
    msg = _veh_dyn_pb2.VehDyn()
    msg.longitudinal.velocity = vx
    msg.lateral.yaw_rate.yaw_rate = yaw_rate
    return msg


def _gen_object_list(objects: list[tuple[int, float, float, int]]):
    """`objects`: list of `(ui_id, dist_x, dist_y, classification)`."""
    msg = _gen_object_list_pb2.GenObjectList()
    for _ in range(50):
        msg.objects.add()
    for i, (ui_id, dist_x, dist_y, classification) in enumerate(objects):
        obj = msg.objects[i]
        obj.kinematic.f_dist_x = dist_x
        obj.kinematic.f_dist_y = dist_y
        obj.attributes.e_classification = classification
        obj.general.ui_id = ui_id
    return msg


def _bsd_outputs(left_warning: int = 0, right_warning: int = 0):
    msg = _bsd_outputs_pb2.BsdOutputs()
    msg.left.warning = left_warning
    msg.right.warning = right_warning
    return msg


def _make_tick(index: int, *, veh_dyn=None, gen_object_list=None, bsd_outputs=None,
               veh_dyn_valid: bool = True, veh_dyn_age_s: float = 0.0, dt_ns: int = 50_000_000,
               pose: Pose2D = _POSE, stage: str = "df") -> Tick:
    ports = {}
    if veh_dyn is not None:
        ports["source.veh_dyn"] = PortValue(
            name="source.veh_dyn", message=veh_dyn, origin="measured",
            valid=veh_dyn_valid, updated=veh_dyn_valid, hold_age_s=veh_dyn_age_s,
        )
    if gen_object_list is not None:
        ports["source.gen_object_list"] = PortValue(name="source.gen_object_list", message=gen_object_list, origin="measured")
    if bsd_outputs is not None:
        qualified = f"{stage}.bsd.outputs"
        ports[qualified] = PortValue(name=qualified, message=bsd_outputs, origin="simulated")
    return Tick(index=index, t_ns=index * dt_ns, dt_ns=dt_ns if index else 0, ports=ports, pose=pose)


def _ctx(ticks: tuple[Tick, ...], *, project: str = "base") -> LayerCtx:
    known_ports = frozenset().union(*(t.ports.keys() for t in ticks)) if ticks else frozenset()
    return LayerCtx(
        model=ProjectModel.resolve(project=project), history=HistoryView(_ticks=ticks),
        frames=FrameTree(ticks[-1].pose), known_ports=known_ports,
    )


# ---------------------------------------------------------------------------

def test_provider_purity_same_tick_twice_yields_equal_layers():
    """UT-B1-2."""
    tick = _make_tick(0, gen_object_list=_gen_object_list([(1, 10.0, -3.0, 1)]))
    ctx = _ctx((tick,))
    assert common.objects_layer(ctx) == common.objects_layer(ctx)


def test_no_provider_module_imports_a_renderer():
    """UT-B1-3: AST scan, GT-2 as a test."""
    banned = ("cv2", "matplotlib", "PySide6", "foxglove")
    violations = []
    for path in sorted((DF_ROOT / "sim" / "layers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == b or name.startswith(b + ".") for b in banned):
                    violations.append(f"{path}: imports {name}")
    assert not violations, "\n".join(violations)


def test_ego_box_equals_ego_model_and_changes_with_project():
    """UT-B1-4: asserted by changing the project and seeing the box change,
    not by comparing to a literal."""
    tick = _make_tick(0)
    for project in ("base", "cus1", "2w_base"):
        ctx = _ctx((tick,), project=project)
        prim = common.ego_layer(ctx)[0].prims[0]
        ego = ctx.model.ego()
        assert prim.length_m == pytest.approx(ego.x_front_m - ego.x_rear_m)
        assert prim.width_m == pytest.approx(2.0 * ego.half_width_m)
    base_box = common.ego_layer(_ctx((tick,), project="base"))[0].prims[0]
    cus1_box = common.ego_layer(_ctx((tick,), project="cus1"))[0].prims[0]
    assert base_box.length_m != cus1_box.length_m


def test_two_different_object_classes_draw_different_footprints():
    """UT-B1-5."""
    tick = _make_tick(0, gen_object_list=_gen_object_list([(1, 10.0, -3.0, 1), (2, 20.0, 3.0, 3)]))  # CAR, PEDESTRIAN
    ctx = _ctx((tick,))
    prims = [p for p in common.objects_layer(ctx)[0].prims if p.kind == "box"]
    assert len(prims) == 2
    assert (prims[0].length_m, prims[0].width_m) != (prims[1].length_m, prims[1].width_m)


def test_warning_state_is_read_not_recomputed_even_when_contradictory():
    """UT-B1-6: a deliberately contradictory output (BLINKING with no
    causal object at all) is drawn as BLINKING regardless."""
    tick = _make_tick(0, bsd_outputs=_bsd_outputs(left_warning=2, right_warning=0))  # BLINKING, no objects
    ctx = _ctx((tick,))
    layer = bsd.warning_layer(ctx)[0]
    prims = layer.prims
    left_circle = next(p for p in prims if p.kind == "circle" and p.pick_id == "bsd.warning.left")
    assert left_circle.style == "status.critical"  # BLINKING's token, shown as-is
    # The band's position is calibration-derived even though its state is
    # real (S-B1Δ, OD-6) -- a prim legitimately mixes the two.
    assert layer.derived is True
    assert all(p.derived for p in prims)


def test_calibration_reconstructed_zone_layer_carries_derived_true():
    """UT-B1-7. S-B1Δ: the individual prims carry `derived=True` too, not
    only the `Layer` (OD-6)."""
    tick = _make_tick(0)
    ctx = _ctx((tick,))
    layer = bsd.zone_layer(ctx)[0]
    assert layer.derived is True
    assert all(p.derived for p in layer.prims)


def test_warning_layer_binds_correctly_under_a_renamed_stage():
    """S-B1Δ (`R-SIM-21`, arch `D13`): `bsd.py` no longer spells the
    pipeline stage name -- the same provider binds correctly whichever
    stage name a pipeline gave the `df` component."""
    tick = _make_tick(0, bsd_outputs=_bsd_outputs(left_warning=1, right_warning=0), stage="driving_functions")
    ctx = _ctx((tick,))
    prims = bsd.warning_layer(ctx)[0].prims
    left_circle = next(p for p in prims if p.kind == "circle" and p.pick_id == "bsd.warning.left")
    assert left_circle.style == "status.warning"


def test_warning_layer_yields_nothing_when_the_run_never_produced_bsd_outputs():
    """The port genuinely isn't part of this run -- Block 1 has no live
    manifest to call this an error, so it stays a silent empty result
    (checked with the user, `S-B1Δ`), same as `UT-B1-1`'s own gating."""
    tick = _make_tick(0, veh_dyn=_veh_dyn())  # a real tick, just no bsd stage at all
    ctx = _ctx((tick,))
    assert bsd.warning_layer(ctx) == ()


def test_padding_slots_produce_no_prims():
    """UT-B1-8: the classic "50 objects at the origin" picture."""
    tick = _make_tick(0, gen_object_list=_gen_object_list([(1, 10.0, -3.0, 1)]))
    ctx = _ctx((tick,))
    prims = common.objects_layer(ctx)[0].prims
    # One real object -> exactly one box + one label, not 50.
    assert len([p for p in prims if p.kind == "box"]) == 1


def test_stale_port_changes_what_the_hud_draws():
    """UT-B1-11: age_s/valid metadata survives the tick/port boundary."""
    fresh_tick = _make_tick(0, veh_dyn=_veh_dyn(vx=20.0), veh_dyn_valid=True, veh_dyn_age_s=0.0)
    stale_tick = _make_tick(0, veh_dyn=_veh_dyn(vx=20.0), veh_dyn_valid=False, veh_dyn_age_s=1.5)
    fresh_prim = common.hud_layer(_ctx((fresh_tick,)))[0].prims[0]
    stale_prim = common.hud_layer(_ctx((stale_tick,)))[0].prims[0]
    assert fresh_prim.style != stale_prim.style
    assert "stale" in stale_prim.text


def test_ego_trail_out_of_order_calls_give_identical_output():
    """UT-B1-12: a temporal layer, but the provider holds no state between
    calls. Poses are varied directly and explicitly here (standing in for
    real ego-in-world data, e.g. a world model's ground truth) -- never
    dead-reckoned from `veh_dyn`, which `trail_layer` no longer reads at all
    (R-SIM-7: a layer may transform data a port/world model already
    produced, never estimate new information by integrating one over time)."""
    poses = tuple(Pose2D(x_m=float(i), y_m=0.0, yaw_rad=0.0) for i in range(10))
    ticks = tuple(_make_tick(i, pose=poses[i]) for i in range(10))
    ctx = _ctx(ticks)
    first = common.trail_layer(ctx)
    # Call again "out of order" (a second, later call) -- purity means the
    # provider has nothing that could make this differ.
    third = common.trail_layer(_ctx(ticks))
    second = common.trail_layer(ctx)
    assert first == second == third
    assert len(first[0].prims[0].points_m) == 10


def test_ego_trail_with_no_real_pose_source_draws_nothing():
    """A recording with no ego-position ground truth (every tick's pose is
    the coordinate-origin default -- this component's own legacy recordings
    carry none) transforms to the same point at every tick; drawing that as
    a trail would be a fabricated flat line, so the layer draws nothing."""
    ticks = tuple(_make_tick(i) for i in range(10))  # default pose at every tick
    ctx = _ctx(ticks)
    assert common.trail_layer(ctx) == ()


def test_provider_is_pure_no_attribute_changes_between_calls():
    """UT-B1-13."""
    ticks = tuple(_make_tick(i, veh_dyn=_veh_dyn(vx=15.0)) for i in range(5))
    ctx = _ctx(ticks)
    before = common.hud_layer(ctx)
    after = common.hud_layer(ctx)
    assert before == after


def test_no_two_layer_ids_share_a_prefix():
    """UT-B1-14: solo/mute selects by id; a prefix collision would select
    the wrong set."""
    ids = ["df.common.frame", "df.common.ego", "df.common.objects", "df.common.hud",
           "df.common.trail", "bsd.zone", "bsd.warning", "bsd.sensor_fov"]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert not a.startswith(b) and not b.startswith(a), (a, b)


def test_changing_a_sensor_value_changes_the_drawn_fov(monkeypatch):
    """UT-C4-1: isolates one `BSD_SENSOR_*` field's effect on the drawn
    wedge, through the real layer provider (`sensor_fov_layer`), not the
    geometry helper directly -- "asserted on the Scene"."""
    tick = _make_tick(0)
    ctx = _ctx((tick,))
    narrow = SensorModel(sensor_id="0", fields={
        "POSE_X_M": -0.8, "POSE_Y_M": 0.78, "POSE_YAW_DEG": 140.0,
        "FOV_AZIMUTH_DEG": 60.0, "RANGE_MAX_CAR_M": 80.0,
    })
    wide = replace(narrow, fields={**narrow.fields, "FOV_AZIMUTH_DEG": 75.0})

    monkeypatch.setattr(bsd, "_bsd_sensors", lambda project: (narrow,))
    narrow_prims = bsd.sensor_fov_layer(ctx)[0].prims
    monkeypatch.setattr(bsd, "_bsd_sensors", lambda project: (wide,))
    wide_prims = bsd.sensor_fov_layer(ctx)[0].prims

    assert narrow_prims[0].points_m != wide_prims[0].points_m
    assert bsd.sensor_fov_layer(ctx)[0].derived is True
    assert all(p.derived for p in wide_prims)


def test_sensor_fov_has_no_per_project_branch_and_differs_by_real_project():
    """UT-C4-2: `base` (two sensors, `LEFT`/`RIGHT`) and `2w_base` (one
    sensor, `BOTH`) draw different geometry through the identical call --
    and, structurally, `bsd.py`'s code contains no comparison against a
    project name to have produced that difference (the exact shape S-C4
    removed from `viz.py`'s `_bsd_project_sensor`) -- an AST scan, not a
    text grep, so the prose above describing that removal doesn't trip it."""
    tree = ast.parse((DF_ROOT / "sim" / "layers" / "bsd.py").read_text(encoding="utf-8"))
    violations = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
        and any(isinstance(c, ast.Constant) and isinstance(c.value, str) for c in node.comparators)
        and (
            (isinstance(node.left, ast.Attribute) and node.left.attr == "project")
            or (isinstance(node.left, ast.Name) and node.left.id == "project")
        )
    ]
    assert not violations

    tick = _make_tick(0)
    base_prims = bsd.sensor_fov_layer(_ctx((tick,), project="base"))[0].prims
    two_w_prims = bsd.sensor_fov_layer(_ctx((tick,), project="2w_base"))[0].prims
    assert len(base_prims) == 2
    assert len(two_w_prims) == 1
    assert base_prims[0].points_m != two_w_prims[0].points_m
