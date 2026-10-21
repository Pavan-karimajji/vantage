# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0374 / ANL-SW-68 -- `check_headers.py` is tested, not trusted
(Plan WP-01 Exit: every `scripts/check_*.py` ships a planted-violation
test, IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_headers import check_cpp_headers, check_python_headers  # noqa: E402


def test_check_python_headers_passes_on_the_current_skeleton():
    findings, scanned = check_python_headers()
    assert findings == []
    assert scanned > 0


def test_check_python_headers_reports_skipped_on_an_empty_tree(tmp_path):
    findings, scanned = check_python_headers(sim_root=tmp_path)
    assert findings == []
    assert scanned == 0


def test_check_python_headers_fails_on_a_planted_missing_header(tmp_path):
    """The check is tested, not trusted: a file with no header block must
    be caught, not silently passed."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "no_header.py").write_text('"""No header here."""\n', encoding="utf-8")
    findings, scanned = check_python_headers(sim_root=tmp_path)
    assert scanned == 1
    assert findings
    assert "no_header.py" in findings[0]


def test_check_python_headers_fails_on_a_planted_wrong_component(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "wrong.py").write_text(
        "# Copyright (c) <ORG>. All Rights Reserved.\n"
        "# Proprietary and Confidential.\n"
        "# COMPONENT: DF\n"
        "# @author Someone\n",
        encoding="utf-8",
    )
    findings, scanned = check_python_headers(sim_root=tmp_path)
    assert scanned == 1
    assert findings
    assert "wrong.py" in findings[0]


def test_the_copy_distributed_launchers_are_exempt_and_a_neighbouring_script_is_not(tmp_path):
    """build.py, build_gui.py and setup.py are byte-identical in every component (CPY-1), so none can carry
    COMPONENT: SIM; a script beside them with no header is still a finding."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("build.py", "build_gui.py", "setup.py", "other.py"):
        (scripts / name).write_text('"""No header."""\n', encoding="utf-8")
    findings, scanned = check_python_headers(sim_root=tmp_path)
    assert scanned == 1
    assert len(findings) == 1 and "other.py" in findings[0]


def test_check_python_headers_accepts_the_real_template(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "ok.py").write_text(
        "# Copyright (c) <ORG>. All Rights Reserved.\n"
        "# Proprietary and Confidential.\n"
        "# COMPONENT: SIM\n"
        "# @author Pavan Karimajji\n"
        "\n"
        '"""Module docstring."""\n',
        encoding="utf-8",
    )
    findings, scanned = check_python_headers(sim_root=tmp_path)
    assert scanned == 1
    assert findings == []


def test_check_cpp_headers_passes_on_the_current_skeleton():
    """`src/simcore/` gained real content at `WP-03` (`errors.hpp`,
    `events.hpp`, `events.cpp`); `src/simengine/` still has none until
    `WP-14`."""
    findings, scanned = check_cpp_headers()
    assert findings == []
    assert scanned > 0


def test_check_python_headers_exempts_scripts_build_py():
    """`R-BUILD-2`: `scripts/build.py` is byte-identical across every
    component and carries no `COMPONENT:` token by design -- must not be
    flagged."""
    findings, scanned = check_python_headers()
    assert not any("scripts\\build.py" in f or "scripts/build.py" in f for f in findings)
    assert scanned > 0


def test_check_cpp_headers_fails_on_a_planted_missing_header(tmp_path):
    simcore = tmp_path / "src" / "simcore"
    simcore.mkdir(parents=True)
    (simcore / "bus.hpp").write_text("#pragma once\n", encoding="utf-8")
    findings, scanned = check_cpp_headers(sim_root=tmp_path)
    assert scanned == 1
    assert findings
    assert "bus.hpp" in findings[0]
