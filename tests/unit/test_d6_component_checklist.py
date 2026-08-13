# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `ST-D6-4` unit tests (`docs/sim_implementation_plan.md`,
`sim_sil_contract.md` section 10, `NR-SIM-48`): `component_checklist()`
against synthetic fixture trees -- the pure logic, no real component build
needed. `tests/system/test_d6_component_checklist.py` runs it against the
real `df`/`vdy`/`perception-core` trees and asserts the "same shape"
claim (`ST-D6-4`'s own wording)."""

from __future__ import annotations

from pathlib import Path

from adas_sim.diagnostics.diagnostics import component_checklist


def _minimal_required_tree(root: Path, *, component: str = "widget") -> None:
    """Everything section 10 marks `required`, nothing else -- every
    conditional/optional row should report `present=False, gap=False`."""
    (root / "conf").mkdir(parents=True)
    (root / "conf" / "build.yml").write_text("variants: {}\n", encoding="utf-8")
    (root / "conf" / "ports.yaml").write_text(f"component: {component}\nperiod_ns: 0\n", encoding="utf-8")
    (root / "src" / "component").mkdir(parents=True)
    (root / "src" / "component" / f"{component}_ports.hpp").write_text("// ports\n", encoding="utf-8")
    (root / "src" / "platform" / f"{component}_sil").mkdir(parents=True)
    (root / "src" / "platform" / f"{component}_sil" / "CMakeLists.txt").write_text(
        "adas_pack_config_bundle(target)\n", encoding="utf-8",
    )
    (root / "src" / "project" / "base").mkdir(parents=True)
    (root / "src" / "project" / "base" / "default.yaml").write_text(
        f"{component.upper()}_FN_PERIOD_US: 50000\n", encoding="utf-8",
    )


def test_every_required_row_present_reports_no_gaps(tmp_path):
    _minimal_required_tree(tmp_path)
    rows = component_checklist(tmp_path)

    required = [r for r in rows if r["kind"] == "required"]
    assert len(required) == 7
    assert all(r["present"] for r in required), required
    assert all(not r["gap"] for r in required)


def test_a_missing_required_row_is_a_gap(tmp_path):
    _minimal_required_tree(tmp_path)
    (tmp_path / "conf" / "ports.yaml").unlink()

    rows = component_checklist(tmp_path)
    ports_row = next(r for r in rows if r["artifact"] == "conf/ports.yaml")
    assert ports_row["present"] is False
    assert ports_row["gap"] is True


def test_conditional_and_optional_absence_is_reported_never_judged(tmp_path):
    """`vdy` has nothing to draw and that is legitimate; a missing
    `sim/tolerance.yaml` is a real gap R-SIM-24 cares about -- but this
    tool has no data to tell the two apart, so BOTH report `gap=False`
    when absent. The distinction is left to whoever reads the report
    (section 10's own "three readings"), not invented here."""
    _minimal_required_tree(tmp_path)

    rows = component_checklist(tmp_path)
    non_required = [r for r in rows if r["kind"] != "required"]
    assert len(non_required) == 6
    assert all(not r["present"] for r in non_required)
    assert all(not r["gap"] for r in non_required), "a conditional/optional absence must never be reported as a gap"


def test_conditional_row_present_when_the_files_exist(tmp_path):
    _minimal_required_tree(tmp_path)
    (tmp_path / "sim").mkdir()
    (tmp_path / "sim" / "tolerance.yaml").write_text("fields: {}\n", encoding="utf-8")
    (tmp_path / "sim" / "plugin.yaml").write_text("api: 1\ncomponent: widget\nprovides: []\n", encoding="utf-8")
    (tmp_path / "sim" / "layers").mkdir()
    (tmp_path / "sim" / "layers" / "__init__.py").write_text("", encoding="utf-8")

    rows = component_checklist(tmp_path)
    tolerance_row = next(r for r in rows if r["artifact"] == "sim/tolerance.yaml")
    plugin_row = next(r for r in rows if r["artifact"] == "sim/plugin.yaml + sim/layers/**")
    assert tolerance_row["present"] is True
    assert plugin_row["present"] is True


def test_scenarios_row_detects_a_real_expect_block(tmp_path):
    _minimal_required_tree(tmp_path)
    scenarios = tmp_path / "tests" / "carla_scenarios"
    scenarios.mkdir(parents=True)
    (scenarios / "case.yaml").write_text("version: 2\nexpect:\n  - id: E1\n", encoding="utf-8")

    rows = component_checklist(tmp_path)
    scenario_row = next(r for r in rows if r["artifact"] == "scenarios with expect: blocks")
    assert scenario_row["present"] is True


def test_component_name_falls_back_to_the_directory_name_with_no_ports_yaml(tmp_path):
    named = tmp_path / "some_component"
    named.mkdir()
    rows = component_checklist(named)
    # No conf/ports.yaml at all -- row 4/6 must not raise trying to name a
    # directory; they simply report absent, same as every other row here.
    sil_row = next(r for r in rows if r["artifact"] == "src/platform/<name>_sil/")
    assert sil_row["present"] is False


def test_all_thirteen_rows_are_always_reported_in_order(tmp_path):
    rows = component_checklist(tmp_path)
    assert [r["row"] for r in rows] == list(range(1, 14))
