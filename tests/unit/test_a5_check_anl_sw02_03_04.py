# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-05: design §3.2's enforcement table -- ANL-SW-02, ANL-SW-03,
ANL-SW-04. The checks are tested, not trusted."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_invariants import check_anl_sw02, check_anl_sw03, check_anl_sw04, run_all  # noqa: E402


def test_check_anl_sw02_passes_on_an_empty_tree(tmp_path):
    assert check_anl_sw02(simcore_root=tmp_path) == []


def test_check_anl_sw02_fails_on_a_planted_gcd_call(tmp_path):
    (tmp_path / "grid.cpp").write_text("auto step = std::gcd(a, b);\n", encoding="utf-8")
    findings = check_anl_sw02(simcore_root=tmp_path)
    assert findings
    assert "ANL-SW-02" in findings[0]


def test_check_anl_sw02_fails_on_a_planted_snap_token(tmp_path):
    (tmp_path / "grid.cpp").write_text("int SnapToGrid(int x);\n", encoding="utf-8")
    findings = check_anl_sw02(simcore_root=tmp_path)
    assert findings


def test_check_anl_sw03_passes_on_an_empty_tree(tmp_path):
    assert check_anl_sw03(simcore_root=tmp_path) == []


def test_check_anl_sw03_fails_on_a_planted_reference_prefix(tmp_path):
    (tmp_path / "wire.cpp").write_text('if (ref.starts_with("self.")) { }\n', encoding="utf-8")
    findings = check_anl_sw03(simcore_root=tmp_path)
    assert findings
    assert "ANL-SW-03" in findings[0]


def test_check_anl_sw04_passes_on_an_empty_tree(tmp_path):
    assert check_anl_sw04(simcore_root=tmp_path) == []


def test_check_anl_sw04_fails_on_a_planted_yaml_path_literal(tmp_path):
    (tmp_path / "config.cpp").write_text('auto f = fopen("ingest_map.yaml", "r");\n', encoding="utf-8")
    findings = check_anl_sw04(simcore_root=tmp_path)
    assert findings
    assert "ANL-SW-04" in findings[0]


def test_check_anl_sw04_does_not_flag_a_documentation_comment(tmp_path):
    """The established comment convention cites `docs/v2/*.yaml` as
    provenance (e.g. `errors.hpp`'s own "Ported from docs/v2/errors.yaml")
    -- a bare comment mention is not code opening a file."""
    (tmp_path / "errors.cpp").write_text(
        "// Ported from docs/v2/events.yaml -- same values as the Python side.\n", encoding="utf-8",
    )
    assert check_anl_sw04(simcore_root=tmp_path) == []


def test_run_all_is_clean_on_the_real_tree():
    """The three checks are wired into `run_all()` -- `simcore`'s own real
    content (`errors/events.cpp`, `runspec/load.cpp`) must stay clean."""
    assert run_all() == []
