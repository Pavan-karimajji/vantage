# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 invariant-checker test: UT-A1-3 (docs/sim_implementation_plan.md) --
the check is tested, not trusted."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_invariants import check_gt1, run_all  # noqa: E402


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


def test_run_all_is_clean_on_the_current_skeleton():
    """All four gates (GT-1, GT-2, GT-3, GT-6) hold on the tree as it stands."""
    assert run_all() == []
