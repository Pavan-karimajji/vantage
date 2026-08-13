# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `ST-D6-4` system test (`docs/sim_implementation_plan.md`,
`sim_sil_contract.md` section 10, `NR-SIM-48`): `sim doctor --component
<root>` run against the three real component trees this repository
actually has -- `df`, `vdy`, `perception-core` -- produces the **same
shape** of report for all three (`ST-D6-4`'s own wording), and names each
absence. No build needed: every row is a real filesystem/text check
against the checked-in source tree, not a compiled artifact."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.cli import doctor
from adas_sim.diagnostics.diagnostics import component_checklist

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
VDY_ROOT = MODULES_ROOT / "vdy"
PERCEPTION_CORE_ROOT = MODULES_ROOT / "perception-core"

_ROOTS = pytest.mark.parametrize("root", [DF_ROOT, VDY_ROOT, PERCEPTION_CORE_ROOT], ids=["df", "vdy", "perception-core"])


@_ROOTS
def test_real_component_tree_produces_all_thirteen_rows_in_order(root):
    if not root.is_dir():
        pytest.skip(f"{root} not checked out (partial clone)")
    rows = component_checklist(root)
    assert [r["row"] for r in rows] == list(range(1, 14))
    assert [r["kind"] for r in rows] == [
        "required", "required", "required", "required", "required", "required", "required",
        "conditional", "conditional", "optional", "optional", "conditional", "conditional",
    ]


@_ROOTS
def test_real_component_tree_reports_rows_one_through_four_present(root):
    """conf/build.yml, conf/ports.yaml, port structs and a *_sil/ shim are
    the four required rows all three real components actually have --
    section 10's own measured table (`AR-43`, corrected `ST-D6-4`) agrees.
    Rows 5-7 are NOT asserted here: `vdy` genuinely has no `src/project/`
    (its calibration is `adas-shared-config`'s), which this same tool found
    while this test was being written -- see `test_vdy_...` below and
    section 10's own corrected table, not a blanket "no gaps" claim that
    would have been false about the real tree."""
    if not root.is_dir():
        pytest.skip(f"{root} not checked out (partial clone)")
    rows = component_checklist(root)
    first_four = [r for r in rows if r["row"] <= 4]
    gaps = [r["artifact"] for r in first_four if r["gap"]]
    assert gaps == [], f"{root.name}: unexpected gap in rows 1-4: {gaps}"


def test_vdy_has_no_src_project_directory_and_it_is_a_real_gap():
    """Found by this tool while `ST-D6-4` was being built, corrected in
    `sim_sil_contract.md` section 10's own table rather than silently left:
    `vdy`'s calibration lives entirely in `adas-shared-config`, not its own
    `src/project/`, so rows 5-7 (which follow from row 5) are real,
    measured gaps for `vdy` -- the table used to claim otherwise."""
    if not VDY_ROOT.is_dir():
        pytest.skip(f"{VDY_ROOT} not checked out (partial clone)")
    rows = component_checklist(VDY_ROOT)
    default_yaml_row = next(r for r in rows if r["artifact"] == "src/project/<p>/default.yaml")
    assert default_yaml_row["present"] is False
    assert default_yaml_row["gap"] is True


def test_df_and_perception_core_have_rows_five_through_seven():
    for root in (DF_ROOT, PERCEPTION_CORE_ROOT):
        if not root.is_dir():
            pytest.skip(f"{root} not checked out (partial clone)")
        rows = component_checklist(root)
        default_yaml_row = next(r for r in rows if r["artifact"] == "src/project/<p>/default.yaml")
        period_row = next(r for r in rows if r["artifact"] == "<COMPONENT>_<FN>_PERIOD_US in calibration")
        assert default_yaml_row["present"] is True, root.name
        assert period_row["present"] is True, root.name


def test_vdy_has_no_layer_provider_and_it_is_reported_absent_not_judged():
    """`vdy` produces `VehDyn`, not geometry -- section 10's own row 8
    `PLUGIN`/layers is legitimately absent for it. This tool does not know
    that (R-SIM-1: the framework may not know a component's own reason);
    it reports `present=False, gap=False` and leaves the "legitimate"
    reading to section 10's own table, exactly as `test_d6_component_
    checklist.py`'s unit test already proves for a synthetic tree."""
    if not VDY_ROOT.is_dir():
        pytest.skip(f"{VDY_ROOT} not checked out (partial clone)")
    rows = component_checklist(VDY_ROOT)
    layers_row = next(r for r in rows if r["artifact"] == "sim/plugin.yaml + sim/layers/**")
    assert layers_row["present"] is False
    assert layers_row["gap"] is False


def test_df_has_a_layer_provider_and_a_tolerance_file():
    """The two rows `df` actually ships, cross-referenced against `S-C8`
    (plug-in bundle) and the sim build queue's own row 2 (`modules/df/sim/
    tolerance.yaml`)."""
    if not DF_ROOT.is_dir():
        pytest.skip(f"{DF_ROOT} not checked out (partial clone)")
    rows = component_checklist(DF_ROOT)
    layers_row = next(r for r in rows if r["artifact"] == "sim/plugin.yaml + sim/layers/**")
    tolerance_row = next(r for r in rows if r["artifact"] == "sim/tolerance.yaml")
    assert layers_row["present"] is True
    assert tolerance_row["present"] is True


@_ROOTS
def test_doctor_cli_component_flag_prints_the_checklist_and_never_fails_the_run(root, capsys):
    if not root.is_dir():
        pytest.skip(f"{root} not checked out (partial clone)")
    exit_code = doctor.run(["--component", str(root)])
    out = capsys.readouterr().out
    assert "component_checklist" in out
    # ST-D6-4/sim_sil_contract.md section 10: "deliberately not a gate" --
    # a checklist row, however absent, must never be why this exits non-zero
    # on its own (a real problem from another flag still would be, but none
    # is given here).
    assert exit_code == 0
