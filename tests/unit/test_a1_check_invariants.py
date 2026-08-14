# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 invariant-checker test: UT-A1-3 (docs/sim_implementation_plan.md) --
the check is tested, not trusted. `check_gt11` is `S-B1Δ`'s own addition
(R-SIM-21, arch `D13`)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_invariants import (  # noqa: E402
    check_codec_scope_no_function_name,
    check_gt1,
    check_gt3,
    check_gt11,
    check_no_manifest_names_codec,
    check_no_world_model_client,
    check_ut_d8_9,
    run_all,
)


def test_check_gt1_passes_on_an_empty_tree(tmp_path):
    """UT-A1-3."""
    assert check_gt1(src_root=tmp_path) == []


def test_check_gt1_passes_on_the_current_skeleton():
    """UT-A1-3."""
    assert check_gt1() == []


def test_check_gt1_fails_on_a_deliberately_planted_function_identifier(tmp_path):
    """UT-A1-3: the check is tested, not trusted."""
    (tmp_path / "layers.py").write_text("BSD_ZONE_WIDTH_M = 2.0\n", encoding="utf-8")
    findings = check_gt1(src_root=tmp_path)
    assert findings
    assert "GT-1" in findings[0]


def test_check_gt1_fails_on_a_planted_function_identifier_in_a_cpp_file(tmp_path):
    """WP-03: GT-1's scope now includes simcore/simengine's C++ sources,
    not only adas_sim's Python -- the check is tested against a .hpp too."""
    (tmp_path / "zone.hpp").write_text("constexpr double BSD_ZONE_WIDTH_M = 2.0;\n", encoding="utf-8")
    findings = check_gt1(src_root=tmp_path)
    assert findings
    assert "GT-1" in findings[0]
    assert "zone.hpp" in findings[0]


def test_run_all_is_clean_on_the_current_skeleton():
    """All seven checks (GT-1, GT-2, GT-3, GT-6, GT-11, UT-D8-9, WP-02(b)) hold on the tree as it stands."""
    assert run_all() == []


def test_check_gt11_passes_on_an_empty_tree(tmp_path):
    assert check_gt11(superproject_root=tmp_path) == []


def test_check_gt11_passes_on_the_current_skeleton():
    assert check_gt11() == []


def test_check_gt11_allows_self_and_source_prefixed_references(tmp_path):
    layers_dir = tmp_path / "modules" / "test" / "sim" / "layers"
    layers_dir.mkdir(parents=True)
    (layers_dir / "example.py").write_text(
        'requires=("self.bsd.outputs",)\n'
        'ctx.port("self.bsd.outputs")\n'
        'requires=("source.gen_object_list",)\n',
        encoding="utf-8",
    )
    assert check_gt11(superproject_root=tmp_path) == []


def test_check_gt11_fails_on_a_spelled_stage_name(tmp_path):
    """The exact defect `S-B1Δ` closed: `requires=("df.bsd.outputs",)`."""
    layers_dir = tmp_path / "modules" / "test" / "sim" / "layers"
    layers_dir.mkdir(parents=True)
    (layers_dir / "example.py").write_text('requires=("df.bsd.outputs",)\n', encoding="utf-8")
    findings = check_gt11(superproject_root=tmp_path)
    assert findings
    assert "GT-11" in findings[0]


def test_st_c4_1_no_sensor_pose_or_class_footprint_literal_in_bsd_layers():
    """ST-C4-1: `modules/df/sim/layers/bsd.py`'s new `sensor_fov_layer`
    (`S-C4`) reads every pose/FOV/range field off `SensorModel`, never a
    literal -- `check_gt3` (already exercised generically by
    `test_run_all_is_clean_on_the_current_skeleton`) is the mechanised grep
    this stage's own gate names."""
    assert check_gt3() == []


def test_check_ut_d8_9_passes_on_an_empty_tree(tmp_path):
    assert check_ut_d8_9(src_root=tmp_path) == []


def test_check_ut_d8_9_passes_on_the_current_skeleton():
    """`S-D8`: no `Vantage`/`Bench`/`Campaign` token in `adas_sim/` outside `player/shell/`."""
    assert check_ut_d8_9() == []


def test_check_ut_d8_9_fails_on_a_workspace_token_outside_app(tmp_path):
    (tmp_path / "player" / "shell").mkdir(parents=True)
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "session.py").write_text('# only in the Bench workspace\n', encoding="utf-8")
    findings = check_ut_d8_9(src_root=tmp_path)
    assert findings
    assert "UT-D8-9" in findings[0]


def test_check_ut_d8_9_allows_the_token_inside_app(tmp_path):
    app_dir = tmp_path / "player" / "shell"
    app_dir.mkdir(parents=True)
    (app_dir / "window.py").write_text('WORKSPACE_NAME = "Bench"\n', encoding="utf-8")
    assert check_ut_d8_9(src_root=tmp_path) == []


def test_check_codec_scope_reports_clean_when_simcore_io_codecs_does_not_exist_yet():
    """IMP-0383: `src/simcore/io/codecs/` lands WP-06 -- today it does not
    exist, and the check must not silently pass a nonexistent tree the
    way a false PASS would."""
    assert check_codec_scope_no_function_name() == []


def test_check_codec_scope_fails_on_a_planted_function_identifier(tmp_path):
    codecs_dir = tmp_path / "src" / "simcore" / "io" / "codecs"
    codecs_dir.mkdir(parents=True)
    (codecs_dir / "mcap.cpp").write_text("// BSD_ZONE_WIDTH_M reused here\n", encoding="utf-8")
    findings = check_codec_scope_no_function_name(sim_root=tmp_path)
    assert findings
    assert "IMP-0383" in findings[0]


def test_check_no_world_model_client_passes_on_the_current_skeleton():
    """WP-02(b) / DD-12: the deleted `sources/carla` client stays deleted."""
    assert check_no_world_model_client() == []


def test_check_no_world_model_client_fails_on_a_reappeared_directory(tmp_path):
    carla_dir = tmp_path / "src" / "adas_sim" / "sources" / "carla"
    carla_dir.mkdir(parents=True)
    findings = check_no_world_model_client(sim_root=tmp_path)
    assert findings
    assert "WP-02(b)" in findings[0]


def test_check_no_world_model_client_fails_on_a_planted_class_reference(tmp_path):
    src_dir = tmp_path / "src" / "adas_sim" / "cli"
    src_dir.mkdir(parents=True)
    (src_dir / "record.py").write_text("from adas_sim.sources.carla import CarlaSource\n", encoding="utf-8")
    findings = check_no_world_model_client(sim_root=tmp_path)
    assert findings
    assert "WP-02(b)" in findings[0]


def test_check_no_world_model_client_allows_df_s_own_recording_naming_convention(tmp_path):
    """`carla_scenarios`/`carla_testruns` (`check/runner.py`'s real directory
    convention for data df actually captured from CARLA) is provenance
    naming, not the deleted client -- must not be flagged."""
    src_dir = tmp_path / "src" / "adas_sim" / "check"
    src_dir.mkdir(parents=True)
    (src_dir / "runner.py").write_text(
        '_SCENARIOS_DIR_NAME = "carla_scenarios"\n_RECORDINGS_DIR_NAME = "carla_testruns"\n', encoding="utf-8",
    )
    assert check_no_world_model_client(sim_root=tmp_path) == []


def test_check_no_manifest_names_codec_reports_clean_when_no_manifest_exists_yet():
    """`conf/ports.yaml` (IMP-0392) lands WP-10 -- no manifest exists
    anywhere in the superproject yet."""
    assert check_no_manifest_names_codec() == []


def test_check_no_manifest_names_codec_fails_on_a_planted_codec_literal(tmp_path):
    manifest_dir = tmp_path / "modules" / "df" / "conf"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "ports.yaml").write_text("port: objects\ncodec_hint: mcap\n", encoding="utf-8")
    findings = check_no_manifest_names_codec(superproject_root=tmp_path)
    assert findings
    assert "IMP-0383" in findings[0]


def test_check_ut_d8_9_is_case_sensitive_so_ordinary_english_survives(tmp_path):
    """"bench"/"campaign" (lowercase) are ordinary English words ("a test
    bench", "workbench") -- only the capitalized product/workspace token
    is a real finding, matching how the names actually appear at their
    real point of use (`sim_player.md`)."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "example.py").write_text(
        "# run this scenario on the test bench before the campaign starts\n", encoding="utf-8",
    )
    assert check_ut_d8_9(src_root=tmp_path) == []
