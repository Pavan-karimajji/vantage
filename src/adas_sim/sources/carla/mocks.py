# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""CARLA actor state -> `GenObjectList`/`VehDyn`/`VehSig` bytes (`S-C2`
slice 5) -- ground truth standing in for perception, a MOCK (`R-SIM-12`):
tagged `mocked`/`truth` by whatever records it (`sources/recorder.py`),
never presented as a measurement. Ported from
`modules/df/tools/carla/carla_bridge.py`'s `build_gen_object_list`/ego
`VehDyn` construction/`compute_ego_roll`, verbatim in behaviour.

**No generated protobuf binding is imported here** (`R-SIM-11`, `GT-6`):
message classes are supplied by the caller (`CarlaSource`), resolved from a
real component's own manifest via `contracts.component.resolve_message_classes`
-- the same dynamic-from-`descriptor_set` construction every other framework
module already uses, never a generated-code import. `_CLASSIFICATION_VALUES`
mirrors `PerceptionCore__Outputs/gen_object.proto`'s `GenObject.Classification`
enum verbatim (field numbers, not names, are the wire contract -- the same
reasoning `contracts/component.py`'s own hand-built manifest schema states
for its field numbers)."""

from __future__ import annotations

import math

from adas_sim.sources.carla import frame_convert
from adas_sim.sources.carla.actor_behaviour import velocity_world

GEN_OBJECT_LIST_PROTO_TYPE = "adas.perception.GenObjectList"
VEH_DYN_PROTO_TYPE = "adas.common.VehDyn"
VEH_SIG_PROTO_TYPE = "adas.common.VehSig"

#: Verbatim against `PerceptionCore__Outputs/gen_object.proto`'s
#: `GenObject.Classification` enum -- kept as plain ints here (not resolved
#: through a `GenObject` message class) so this module needs no message
#: class beyond `GenObjectList` itself.
_CLASSIFICATION_VALUES = {
    "POINT": 0, "CAR": 1, "TRUCK": 2, "PEDESTRIAN": 3, "MOTORCYCLE": 4,
    "BICYCLE": 5, "WIDE": 6, "UNCLASSIFIED": 7, "OTHER_VEHICLE": 8, "TL": 9, "MULTIPLE": 10,
}


def _project_onto_ego_heading(ego_yaw_deg: float, vx: float, vy: float) -> tuple:
    """Projects a world-frame velocity onto ego's own heading axes
    (forward, OUR +y-left) -- the same convention `frame_convert.to_ego_frame`
    uses for its relative velocity, but absolute rather than ego-relative
    (`GenObject.kinematic`'s `f_vabs_x`/`f_vabs_y`: a real radar/track-filter
    output is ego-frame-*aligned*, not ego-frame-*relative*)."""
    yaw_rad = math.radians(ego_yaw_deg)
    forward = (math.cos(yaw_rad), math.sin(yaw_rad))
    right = (-math.sin(yaw_rad), math.cos(yaw_rad))
    return (vx * forward[0] + vy * forward[1], -(vx * right[0] + vy * right[1]))


def build_gen_object_list_bytes(
    ego_actor, ego_speed_mps: float, targets: list, object_range_m: float, num_object_slots: int,
    message_classes: dict,
) -> bytes:
    """`targets`: a list of `(actor, speed_mps, lateral_rate_mps,
    classification_token)` -- the token already resolved by the caller
    (`CarlaSource`: a scenario's own explicit `classification:` wins,
    `sources/carla/catalogue.py`'s blueprint lookup is the fallback). This
    function only ever consumes an already-resolved token; it does not
    know a catalogue exists.

    `message_classes[GEN_OBJECT_LIST_PROTO_TYPE]` is the `GenObjectList`
    message class, resolved by the caller (never imported here, `R-SIM-11`).

    Always returns exactly `num_object_slots` `GenObject`s, matching a
    fixed-array shape rather than a variable-length list that happens to be
    small in one scenario. Real, in-range targets fill the nearest slots
    first (sorted by distance); any remaining slots are padded with
    default-constructed (all-zero) objects -- a zero-valued `GenObject` has
    `f_dist_x=0`, already outside any eligibility gate requiring `dx > 0`,
    so padding slots are inert without special-casing downstream.
    """
    gen_object_list_cls = message_classes[GEN_OBJECT_LIST_PROTO_TYPE]
    ego_t = ego_actor.get_transform()
    ego_vx, ego_vy = velocity_world(ego_t.rotation.yaw, ego_speed_mps)

    in_range = []
    for actor, speed_mps, lateral_rate_mps, classification_token in targets:
        t = actor.get_transform()
        distance = ego_t.location.distance(t.location)
        if distance > object_range_m:
            continue
        vx, vy = velocity_world(t.rotation.yaw, speed_mps, lateral_rate_mps)
        rel = frame_convert.to_ego_frame(
            ego_t.location.x, ego_t.location.y, ego_t.rotation.yaw, ego_vx, ego_vy,
            t.location.x, t.location.y, vx, vy,
        )
        vabs_x, vabs_y = _project_onto_ego_heading(ego_t.rotation.yaw, vx, vy)
        classification = _CLASSIFICATION_VALUES[classification_token]
        in_range.append((distance, actor.id, rel, vabs_x, vabs_y, classification))
    in_range.sort(key=lambda item: item[0])  # nearest first

    objects_msg = gen_object_list_cls()
    for _distance, actor_id, rel, vabs_x, vabs_y, classification in in_range[:num_object_slots]:
        obj = objects_msg.objects.add()
        obj.kinematic.f_dist_x = rel.dist_x
        obj.kinematic.f_dist_y = rel.dist_y
        obj.kinematic.f_vrel_x = rel.vrel_x
        obj.kinematic.f_vrel_y = rel.vrel_y
        obj.kinematic.f_vabs_x = vabs_x
        obj.kinematic.f_vabs_y = vabs_y
        obj.general.ui_id = actor_id
        obj.general.contributingSensors = 0x2  # radar bit -- CARLA ground truth stands in for that path
        obj.general.f_life_time = 5.0  # ground truth, always mature
        obj.attributes.e_classification = classification
        obj.attributes.existence_probability = 0.95  # ground truth
    while len(objects_msg.objects) < num_object_slots:
        objects_msg.objects.add()  # default-constructed: all-zero, inert padding

    return objects_msg.SerializeToString()


def compute_ego_roll(ego_actor, elapsed_s: float, roll_fault_cfg: dict | None) -> tuple:
    """Ground-truth ego roll from the CARLA actor's own transform. This is
    frame roll, uncorrected -- not a contact-patch-corrected effective
    roll; do not "fix" that discrepancy here. Returns `(roll_angle_rad,
    roll_rate_rad_s, quality)`; `roll_rate` is always `0.0` -- none of
    today's kinematic actors roll, so there is nothing yet to differentiate.

    `roll_fault_cfg` (an optional scenario `roll_fault:` key, `R-SIM-9`'s
    own per-scenario fault injection) is otherwise noise-free and always
    valid, so without it a component's degrade path on a faulted roll
    signal is untested no matter how many scenarios run:
      `corrupt_after_s`/`corrupt_offset_deg`: biases the reported angle
        while quality stays valid -- a plausible-looking but wrong reading.
      `invalid_after_s`: quality -> 0 and roll_angle -> 0 (not a stale
        value) -- a genuinely faulted sensor.
    """
    # CARLA roll is left-handed; negated for the same reason yaw_rate is
    # (actor_behaviour.LaneAdvancer.yaw_rate_rad_s) -- UNVERIFIED against a
    # reference sign convention.
    roll_deg = -ego_actor.get_transform().rotation.roll
    quality = 100
    roll_fault_cfg = roll_fault_cfg or {}
    corrupt_after_s = roll_fault_cfg.get("corrupt_after_s")
    if corrupt_after_s is not None and elapsed_s >= corrupt_after_s:
        roll_deg += roll_fault_cfg.get("corrupt_offset_deg", 0.0)
    invalid_after_s = roll_fault_cfg.get("invalid_after_s")
    if invalid_after_s is not None and elapsed_s >= invalid_after_s:
        quality = 0
        roll_deg = 0.0
    return math.radians(roll_deg), 0.0, quality


def build_veh_dyn_bytes(
    ego_speed_mps: float, accel_mps2: float, yaw_rate_rad_s: float,
    roll_angle_rad: float, roll_rate_rad_s: float, roll_quality: int,
    message_classes: dict,
) -> bytes:
    """`accel_mps2` is a true passthrough, not a placeholder: a kinematic
    ego at constant velocity has zero longitudinal accel. `lateral.accel`
    is `ego_speed_mps * yaw_rate_rad_s` -- a kinematic stand-in ground
    truth, not a measured accelerometer signal (no bank angle/slip/noise
    exists to make it diverge from `v * yaw_rate` the way a real measured
    lateral accel would). **The consumer must still treat `lateral.accel`
    as a real passthrough, never re-derive it as `v * yaw_rate` at the algo
    boundary** (`R-COORD-2`) -- this synthesized value cannot distinguish
    the two, so a component that "fixed" the passthrough rule using this
    source alone would never notice."""
    veh_dyn_cls = message_classes[VEH_DYN_PROTO_TYPE]
    msg = veh_dyn_cls()
    msg.longitudinal.velocity = ego_speed_mps
    msg.longitudinal.accel = accel_mps2
    msg.lateral.yaw_rate.yaw_rate = yaw_rate_rad_s
    msg.lateral.accel.lat_accel = ego_speed_mps * yaw_rate_rad_s
    msg.lateral.roll.roll_angle = roll_angle_rad
    msg.lateral.roll.roll_rate = roll_rate_rad_s
    msg.lateral.roll.quality = roll_quality
    return msg.SerializeToString()


def build_veh_sig_bytes(message_classes: dict) -> bytes:
    """`turn_indicator` stays OFF -- no scenario built so far engages a
    turn signal."""
    veh_sig_cls = message_classes[VEH_SIG_PROTO_TYPE]
    return veh_sig_cls().SerializeToString()
