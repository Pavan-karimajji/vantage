# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0164 / ANL-SW-34 -- the check is tested, not trusted."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_invariants import check_anl_sw34  # noqa: E402


def test_check_anl_sw34_passes_on_an_empty_tree(tmp_path):
    """ANL-SW-34: no `config/`/`graph/`/`ingest/`/`runspec/` present at all."""
    assert check_anl_sw34(src_root=tmp_path) == []


def test_check_anl_sw34_fails_on_a_planted_io_import(tmp_path):
    """ANL-SW-34: the check is tested, not trusted."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "bad.py").write_text("from adas_sim.io.base import RecordingReader\n", encoding="utf-8")
    findings = check_anl_sw34(src_root=tmp_path)
    assert findings
    assert "ANL-SW-34" in findings[0]


def test_check_anl_sw34_fails_on_a_planted_ctypes_import(tmp_path):
    """ANL-SW-34: `ctypes` is refused exactly like `adas_sim.io`."""
    ingest_dir = tmp_path / "ingest"
    ingest_dir.mkdir()
    (ingest_dir / "bad.py").write_text("import ctypes\n", encoding="utf-8")
    findings = check_anl_sw34(src_root=tmp_path)
    assert findings
    assert "ANL-SW-34" in findings[0]


def test_check_anl_sw34_config_module_is_clean():
    """WP-04's own new `config/**` code imports neither `adas_sim.io` nor
    `ctypes` -- `config/bundle.py` takes plain project names/paths rather
    than a `SilComponent` precisely to keep this true (`IMP-0159`/`0160`'s
    own design note)."""
    sim_root = _SCRIPTS_DIR.parent
    config_only = check_anl_sw34(src_root=sim_root / "src" / "adas_sim")
    assert all("\\config\\" not in f and "/config/" not in f for f in config_only)


def test_check_anl_sw34_not_yet_enforced_documents_the_known_graph_violation():
    """`graph/pipeline.py` (formerly `contracts/pipeline.py`) already imports
    `adas_sim.io.base.RecordingReader` for `Pipeline.load`'s `recording:`
    parameter -- predates `WP-04`, and untangling it is `WP-05`'s own seam
    work (`IF-09`), not this `WP`'s. This test documents the known,
    accepted gap rather than silently expecting a clean tree; when the
    seam lands and this starts failing, wiring `check_anl_sw34` into
    `run_all()` is the one-line follow-up (IMP-0164's own design note)."""
    sim_root = _SCRIPTS_DIR.parent
    findings = check_anl_sw34(src_root=sim_root / "src" / "adas_sim")
    assert any("graph" in f and "pipeline.py" in f for f in findings)
