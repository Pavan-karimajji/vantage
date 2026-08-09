# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`CarlaSource` -- the `Source` (`sim_api_reference.md` §8) that drives a
live CARLA server (`S-C2` slice 5). Ties together `world.py` (connect/map),
`spawn.py` (actor spawn), `actor_behaviour.py` (lane-advance, lateral
profiles), `mocks.py` (ground-truth -> port bytes) and `chase.py`
(spectator follow) -- the engine `modules/df/tools/carla/carla_bridge.py`'s
`run()` loop already implements, decomposed by copy (`R-STYLE-2`).

Camera capture is deliberately **not** ported this slice: the old bridge's
chase-view JPEG recording would need `S-A3Δ`'s `BulkRef` budget mechanism to
carry correctly, which is a real design question outside `S-C2`'s mandatory
checklist -- `emits()` is `gen_object_list`/`veh_dyn`/`veh_sig` only.

`dt_s` is this source's OWN wall-clock pacing (`TARGET_HZ`), not something a
caller passes in: `Source.poll()` takes no argument (`sim_api_reference.md`
§8's frozen signature) because a LIVE world determines its own tick rate --
a caller's `Pipeline`/recorder clock is a separate, nominal `dt_ns` for its
own scheduling (`R-SIM-18`), which for a live CARLA run is expected to
track this source's real pacing but is never used to drive it.

`message_classes` (constructor-required) supplies the `DetectedObjectList`/
`VehDyn`/`VehSig` message classes `mocks.py` builds bytes with -- resolved
by the CALLER from a real component's own manifest
(`contracts.component.resolve_message_classes`, `R-SIM-11`'s own dynamic-
from-`descriptor_set` construction), never imported here (`GT-6`). A live
CARLA recording needs a real library loaded for its manifest alone (no
`exec()` required) purely to harvest these three descriptors -- CLI wiring
for that is left for whoever runs `MC-2` against a real build.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

import yaml

from adas_sim.contracts.scenario import Scenario
from adas_sim.core.errors import AuthoringError, InternalError
from adas_sim.sources.carla import actor_behaviour, chase, mocks, spawn, world
from adas_sim.sources.carla.catalogue import classification_for_blueprint, load_catalogue

#: Matches the pacing already proven against a real CARLA build: paced
#: against wall clock (`time.perf_counter()`), NOT the server's own
#: `snapshot.timestamp` -- the latter was found not to reliably track real
#: elapsed time when polled via `world.wait_for_tick()` this fast in async
#: mode.
TARGET_HZ = 20.0
TARGET_DT_S = 1.0 / TARGET_HZ


def _profile_cfgs(phases: tuple) -> list[dict] | None:
    """A typed `Actor`/`EgoScenario.lateral_profile` back into the plain
    dict shape `actor_behaviour.LateralProfile` already expects (it indexes
    with `in`/`[]`/`.get`, not attributes) -- that module stays untouched;
    only the boundary where a `Scenario` enters this source changes."""
    if not phases:
        return None
    return [{"name": p.name, "rate_mps": p.rate_mps, "duration_s": p.duration_s, "shape": p.shape} for p in phases]


def _ego_cfg_from_scenario(scenario: Scenario, carla_cfg: Mapping[str, object]) -> dict:
    """Adapts `scenario.scenario.ego` + `scenario.world["carla"]` into the
    plain dict `spawn.spawn_kinematic_ego` already expects (`blueprint`,
    `spawn_point_index`, `speed_mps`, `lateral_profile`)."""
    return {
        "blueprint": carla_cfg.get("ego_blueprint"),
        "spawn_point_index": carla_cfg.get("spawn_point_index", 0),
        "speed_mps": scenario.scenario.ego.speed_mps,
        "lateral_profile": _profile_cfgs(scenario.scenario.ego.lateral_profile),
    }


def _actor_cfgs_from_scenario(scenario: Scenario, carla_cfg: Mapping[str, object]) -> list[dict]:
    """Returns a list of actor cfgs (name, blueprint, long_offset_m,
    lateral_offset_m, speed_mps, classification, lateral_profile) --
    `spawn.spawn_kinematic_at`/`actor_behaviour`'s own general shape,
    unchanged since `S-C2`. Blueprints live in `world.carla.
    actor_blueprints` (`contracts/scenario.py`'s v1 upgrader moves them
    there; a hand-authored v2 scenario declares them there directly)."""
    blueprints = carla_cfg.get("actor_blueprints", {})
    return [
        {
            "name": actor.name,
            "blueprint": blueprints.get(actor.name),
            "long_offset_m": actor.long_offset_m,
            "lateral_offset_m": actor.lateral_offset_m,
            "speed_mps": actor.speed_mps,
            "classification": actor.classification,
            "lateral_profile": _profile_cfgs(actor.lateral_profile),
        }
        for actor in scenario.scenario.actors
    ]


def _resolve_sensor_model_preset(scenario_path: Path | None, preset_id: str) -> Mapping[str, object]:
    """`SensorModelRef`'s own docstring: resolving a `preset:` is the
    consumer's job, never the scenario loader's (`R-SIM-1`). Walking up from
    the scenario file to find its nearest `sim/sensor_models/<preset_id>.yaml`
    sibling resolves it with no component name hardcoded here -- this stays
    framework code regardless of which component owns the scenario."""
    if scenario_path is not None:
        for ancestor in scenario_path.resolve().parents:
            candidate = ancestor / "sim" / "sensor_models" / f"{preset_id}.yaml"
            if candidate.is_file():
                return yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    raise AuthoringError(
        expected=f"a sim/sensor_models/{preset_id}.yaml reachable from an ancestor of the scenario file",
        found="no such file in any ancestor directory", where="CarlaSource.start",
        hint="sensor_model.preset names a document under the owning component's sim/sensor_models/",
    )


class CarlaSource:
    name: ClassVar[str] = "carla"

    def __init__(self, *, message_classes: Mapping[str, type], catalogue: dict | None = None) -> None:
        self._message_classes = message_classes
        self._catalogue = catalogue if catalogue is not None else load_catalogue()
        self._world = None
        self._ego_actor = None
        self._actors_by_name: dict = {}
        self._actor_cfgs: list[dict] = []
        self._ego_cfg: dict = {}
        self._object_range_m = 0.0
        self._num_object_slots = 0
        self._roll_fault_cfg: dict | None = None
        self._lateral_profiles: dict = {}
        self._ego_profile = None
        self._lane_advancer = None
        self._elapsed_s = 0.0
        self._last_real_t: float | None = None
        self._started = False

    def __repr__(self) -> str:
        return f"<CarlaSource started={self._started} elapsed_s={self._elapsed_s:.2f}>"

    def emits(self) -> frozenset[str]:
        return frozenset({"gen_object_list", "veh_dyn", "veh_sig"})

    def start(self, scenario: Scenario) -> None:
        carla_cfg = scenario.world.get("carla", {})
        # CARLA's own default RPC host/port -- every real scenario states
        # them explicitly (preserved verbatim by the v1 upgrader), but a
        # hand-authored v2 scenario's `world.carla` (`sim_scenarios_and_
        # expectations.md` SS3) may omit connection details entirely, since
        # "how do I reach a server" is arguably not scenario content.
        client = world.connect(carla_cfg.get("host", "127.0.0.1"), carla_cfg.get("port", 2000))
        live_world = world.wait_for_world(client)
        live_world = world.ensure_map(client, live_world, carla_cfg["map"])
        world.set_asynchronous(live_world)

        ego_cfg = _ego_cfg_from_scenario(scenario, carla_cfg)
        actor_cfgs = _actor_cfgs_from_scenario(scenario, carla_cfg)
        ego_actor = None
        actors_by_name: dict = {}
        # Spawning is inside its own try: a target whose spawn point is
        # blocked would otherwise leave the ego actor behind on the
        # server, and the NEXT run's own ego spawn would then fail on the
        # orphan -- a confusing second failure that hides the first.
        try:
            ego_actor = spawn.spawn_kinematic_ego(live_world, ego_cfg)
            for cfg in actor_cfgs:
                actors_by_name[cfg["name"]] = spawn.spawn_kinematic_at(
                    live_world, ego_actor, cfg["blueprint"], cfg["long_offset_m"],
                    cfg["lateral_offset_m"], cfg["speed_mps"],
                )
        except Exception:
            for actor in actors_by_name.values():
                actor.destroy()
            if ego_actor is not None:
                ego_actor.destroy()
            raise

        focus_actor = next(iter(actors_by_name.values()), None)
        chase.follow_with_spectator(live_world, ego_actor, focus_actor)

        self._world = live_world
        self._ego_actor = ego_actor
        self._actors_by_name = actors_by_name
        self._actor_cfgs = actor_cfgs
        self._ego_cfg = ego_cfg
        self._object_range_m = scenario.sensor_model.object_range_m
        self._num_object_slots = scenario.sensor_model.num_object_slots
        if self._object_range_m is None or self._num_object_slots is None:
            if scenario.sensor_model.preset is None:
                raise AuthoringError(
                    expected="sensor_model.preset or explicit object_range_m/num_object_slots",
                    found="sensor_model declares neither", where="CarlaSource.start",
                    hint="name a sim/sensor_models/*.yaml preset, or set both fields explicitly",
                )
            preset = _resolve_sensor_model_preset(scenario.path, scenario.sensor_model.preset)
            if self._object_range_m is None:
                self._object_range_m = preset.get("object_range_m")
            if self._num_object_slots is None:
                self._num_object_slots = preset.get("num_object_slots")
        # `run.faults` (SS3.2's `roll_fault:` -> `run.faults` upgrade) is a
        # list; this source has only ever driven the single-fault case
        # `roll_fault:` expressed, so the first (only) entry is equivalent.
        self._roll_fault_cfg = scenario.run.faults[0] if scenario.run.faults else None
        self._lateral_profiles = actor_behaviour.build_lateral_profiles(actor_cfgs)
        # The ego may declare a lateral profile too -- the only actor whose
        # lateral motion is also yawed (`yaw_with_lateral=True` below),
        # because only the ego's yaw_rate reaches a consuming component.
        self._ego_profile = actor_behaviour.build_lateral_profiles(
            [{"name": "ego", "lateral_profile": ego_cfg.get("lateral_profile")}]).get("ego")
        self._lane_advancer = actor_behaviour.LaneAdvancer()
        self._elapsed_s = 0.0
        self._last_real_t = None
        self._started = True

    def poll(self) -> Mapping[str, bytes]:
        if not self._started:
            raise InternalError(
                expected="start() called before poll()", found="not started",
                where="CarlaSource.poll", hint="call start() once before the first poll()",
            )
        self._world.wait_for_tick()  # stays synchronized with the server / avoids busy-spinning

        now = time.perf_counter()
        if self._last_real_t is None:
            dt_s = TARGET_DT_S
        else:
            dt_s = now - self._last_real_t
            if dt_s < TARGET_DT_S:
                time.sleep(TARGET_DT_S - dt_s)
                now = time.perf_counter()
                dt_s = now - self._last_real_t
        self._last_real_t = now
        self._elapsed_s += dt_s

        rates = actor_behaviour.lateral_rates(self._lateral_profiles, self._actor_cfgs, self._elapsed_s)
        ego_lateral_rate = self._ego_profile.rate_mps(self._elapsed_s) if self._ego_profile else 0.0
        self._lane_advancer.advance(
            self._world, self._ego_actor, self._ego_cfg["speed_mps"], dt_s, ego_lateral_rate, yaw_with_lateral=True,
        )
        for cfg in self._actor_cfgs:
            self._lane_advancer.advance(
                self._world, self._actors_by_name[cfg["name"]], cfg["speed_mps"], dt_s, rates[cfg["name"]],
            )
        focus_actor = next(iter(self._actors_by_name.values()), None)
        chase.follow_with_spectator(self._world, self._ego_actor, focus_actor)

        targets = [
            (
                self._actors_by_name[cfg["name"]], cfg["speed_mps"], rates[cfg["name"]],
                cfg["classification"] or classification_for_blueprint(cfg["blueprint"], self._catalogue),
            )
            for cfg in self._actor_cfgs
        ]
        gen_object_list_bytes = mocks.build_gen_object_list_bytes(
            self._ego_actor, self._ego_cfg["speed_mps"], targets, self._object_range_m, self._num_object_slots,
            self._message_classes,
        )

        ego_yaw_rate_rad_s = self._lane_advancer.yaw_rate_rad_s(self._ego_actor.id)
        roll_angle_rad, roll_rate_rad_s, roll_quality = mocks.compute_ego_roll(
            self._ego_actor, self._elapsed_s, self._roll_fault_cfg,
        )
        veh_dyn_bytes = mocks.build_veh_dyn_bytes(
            self._ego_cfg["speed_mps"], 0.0, ego_yaw_rate_rad_s, roll_angle_rad, roll_rate_rad_s, roll_quality,
            self._message_classes,
        )
        veh_sig_bytes = mocks.build_veh_sig_bytes(self._message_classes)

        return {"gen_object_list": gen_object_list_bytes, "veh_dyn": veh_dyn_bytes, "veh_sig": veh_sig_bytes}

    def stop(self) -> None:
        if self._ego_actor is not None:
            self._ego_actor.destroy()
        for actor in self._actors_by_name.values():
            actor.destroy()
        self._actors_by_name = {}
        self._ego_actor = None
        self._started = False
