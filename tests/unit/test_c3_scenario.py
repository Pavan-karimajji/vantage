# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3 scenario schema v2 + v1-upgrader tests (docs/sim_implementation_plan.md).

Every fixture is a synthetic scenario under `tests/fixtures/scenarios/` --
names no function, asserts nothing about any component's behaviour
(`sim_scenarios_and_expectations.md` SS0, `R-SIM-1`). The real 18 cases stay
in `modules/df/tests/`; verifying the upgrader against them is a df-side test
that imports this module, not a sim-side one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.contracts.scenario import (
    CURRENT_SCENARIO_VERSION, ConstantAnchor, CrossesAnchor, Scenario, load_scenario,
)
from adas_sim.core.errors import AuthoringError

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "scenarios"


# ---------------------------------------------------------------------------
# UT-C3-1-equivalent -- v1 upgrader mechanics
# ---------------------------------------------------------------------------


def test_v1_lead_sugar_upgrades_to_one_actor_dead_ahead():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert scenario.schema == CURRENT_SCENARIO_VERSION
    assert len(scenario.scenario.actors) == 1
    actor = scenario.scenario.actors[0]
    assert actor.name == "lead"
    assert actor.long_offset_m == 30.0  # initial_gap_m -> long_offset_m
    assert actor.lateral_offset_m == 0.0
    assert actor.speed_mps == 0.0
    assert actor.classification == "CAR"
    assert actor.lateral_profile == ()
    assert scenario.world["carla"]["actor_blueprints"] == {"lead": "vehicle.fixture.target"}


def test_v1_actors_list_preserves_every_field():
    scenario = load_scenario(_FIXTURES / "fixture_actors_v1.yaml")
    assert len(scenario.scenario.actors) == 1
    actor = scenario.scenario.actors[0]
    assert actor.name == "target"
    assert actor.long_offset_m == -1.0
    assert actor.lateral_offset_m == -6.0
    assert actor.speed_mps == 20.0
    assert actor.classification == "CAR"
    assert [p.name for p in actor.lateral_profile] == ["converge", "hold"]
    assert actor.lateral_profile[0].rate_mps == 0.25
    assert actor.lateral_profile[0].duration_s == 8.0


def test_v1_ego_and_world_carla_fields_move_correctly():
    scenario = load_scenario(_FIXTURES / "fixture_actors_v1.yaml")
    assert scenario.scenario.ego.speed_mps == 20.0
    assert scenario.world["carla"]["map"] == "FixtureTown"
    assert scenario.world["carla"]["host"] == "127.0.0.1"
    assert scenario.world["carla"]["spawn_point_index"] == 12
    assert scenario.world["carla"]["ego_blueprint"] == "vehicle.fixture.ego"


def test_v1_end_condition_present_is_preserved():
    scenario = load_scenario(_FIXTURES / "fixture_actors_v1.yaml")
    assert scenario.run.end_condition == {"type": "time_elapsed", "max_s": 21.0}


def test_v1_end_condition_absent_stays_none_not_a_guessed_default():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert scenario.run.end_condition is None


def test_v1_roll_fault_is_not_auto_upgraded_and_raises(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_lead_v1.yaml").read_text(encoding="utf-8"))
    raw["roll_fault"] = {"corrupt_after_s": 2.0, "corrupt_offset_deg": 5.0}
    path = tmp_path / "with_roll_fault.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuthoringError, match="roll_fault"):
        load_scenario(path)


def test_v1_no_roll_fault_is_empty_faults_list():
    scenario = load_scenario(_FIXTURES / "fixture_actors_v1.yaml")
    assert scenario.run.faults == ()


def test_v1_sensor_model_fields_move_verbatim():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert scenario.sensor_model.object_range_m == 100.0
    assert scenario.sensor_model.num_object_slots == 50
    assert scenario.sensor_model.preset is None


def test_v1_null_dll_path_is_not_treated_as_set():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert scenario.sut.dll_path is None
    assert scenario.sut.project == "base"
    assert scenario.sut.pipeline is None


def test_v1_non_null_dll_path_is_honoured_with_deprecation_warning(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_lead_v1.yaml").read_text(encoding="utf-8"))
    raw["df"]["dll_path"] = "build/fixture.dll"
    path = tmp_path / "fixture_dll_path.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.warns(DeprecationWarning, match="dll_path is deprecated"):
        scenario = load_scenario(path)
    assert scenario.sut.dll_path == "build/fixture.dll"


def test_v1_doc_captures_the_full_leading_comment_block():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert "Fixture: v1 shape using the `lead:` sugar" in scenario.doc
    assert "UT-C3-1-equivalent" in scenario.doc
    # The block stops at the first non-comment line -- `carla:` never leaks in.
    assert "carla:" not in scenario.doc


def test_v1_id_defaults_to_the_file_stem():
    scenario = load_scenario(_FIXTURES / "fixture_lead_v1.yaml")
    assert scenario.id == "fixture_lead_v1"


# ---------------------------------------------------------------------------
# v2-authored round trip -- markers, expect, world, sut.pipeline
# ---------------------------------------------------------------------------


def test_v2_authored_scenario_round_trips_every_section():
    scenario = load_scenario(_FIXTURES / "fixture_v2.yaml")
    assert isinstance(scenario, Scenario)
    assert scenario.id == "fixture_v2"
    assert "freshly authored v2 fixture" in scenario.doc

    assert scenario.scenario.road.hint == "straight_multilane"
    assert scenario.scenario.road.min_straight_m == 400
    assert scenario.scenario.ego.speed_mps == 20.111
    assert len(scenario.scenario.actors) == 1
    assert scenario.scenario.actors[0].classification == "CAR"

    assert scenario.world["carla"]["spawn_point_index"] == 54
    assert scenario.sensor_model.preset == "fixture_ideal"
    assert scenario.run.end_condition == {"type": "time_elapsed", "max_s": 21.0}
    assert scenario.sut.pipeline == "fixture_only"
    assert scenario.sut.project == "base"

    entry = scenario.markers["entry_s"].at
    assert isinstance(entry, ConstantAnchor)
    assert entry.seconds == 4.80
    assert entry.source == "fixtures/fixture_v2_offline.py"

    crossing = scenario.markers["crossing"].at
    assert isinstance(crossing, CrossesAnchor)
    assert crossing.signal == "widget.outputs.value"
    assert crossing.threshold == 0.5
    assert crossing.direction == "rising"

    assert len(scenario.expect) == 1
    assert scenario.expect[0]["id"] == "EXP-1"


# ---------------------------------------------------------------------------
# Load errors
# ---------------------------------------------------------------------------


def test_unsupported_schema_version_raises_authoring_error(tmp_path):
    path = tmp_path / "future.yaml"
    path.write_text(yaml.safe_dump({"schema": 99, "id": "future"}), encoding="utf-8")
    with pytest.raises(AuthoringError, match="schema"):
        load_scenario(path)


def test_missing_required_actor_field_raises_authoring_error(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_actors_v1.yaml").read_text(encoding="utf-8"))
    del raw["actors"][0]["speed_mps"]
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(AuthoringError, match="speed_mps"):
        load_scenario(path)


def test_missing_lead_and_actors_raises_authoring_error(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_lead_v1.yaml").read_text(encoding="utf-8"))
    del raw["lead"]
    path = tmp_path / "no_actors.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(AuthoringError, match="lead"):
        load_scenario(path)


def test_constant_marker_without_from_raises_authoring_error(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_v2.yaml").read_text(encoding="utf-8"))
    del raw["markers"][0]["from"]
    path = tmp_path / "marker_no_from.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(AuthoringError, match="from"):
        load_scenario(path)


def test_predicate_marker_with_two_signals_raises_authoring_error(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_v2.yaml").read_text(encoding="utf-8"))
    raw["markers"][1]["at"]["second"] = "truth.objects[0].y_m"
    path = tmp_path / "marker_two_signals.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(AuthoringError, match="first"):
        load_scenario(path)


def test_predicate_marker_with_neither_becomes_nor_crosses_raises_authoring_error(tmp_path):
    raw = yaml.safe_load((_FIXTURES / "fixture_v2.yaml").read_text(encoding="utf-8"))
    del raw["markers"][1]["at"]["crosses"]
    del raw["markers"][1]["at"]["dir"]
    path = tmp_path / "marker_bare_first.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(AuthoringError, match="becomes"):
        load_scenario(path)
