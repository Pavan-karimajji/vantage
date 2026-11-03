# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-15: IMP-0090 / ANL-04 (SYS-0074) -- ``check_single_carrier.py`` is tested, not trusted.

ANL-04 .c1 is the clean run, .c2 a planted ``SetTransportPublisher`` call in ``src/simcore/abi/simcore.cpp`` and
.c3 a planted ``#include "simcore/transport_shm.hpp"`` in ``src/simcore/runner/cycle_loop.cpp``, each reported with
file and line; the script's own ``--selftest`` plants the same two in a copy of the real tree (R-REQ-9).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_single_carrier as script  # noqa: E402

ABI = "src/simcore/abi/simcore.cpp"
CYCLE_LOOP = "src/simcore/runner/cycle_loop.cpp"


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_tree(tmp_path):
    write(
        tmp_path,
        ABI,
        "// the retired TransportPublisher is only named in this comment\n"
        'const char* kNote = "SetTransportPublisher and transport_shm.hpp in a message";\n'
        "int Engine() { return 0; }\n",
    )
    write(tmp_path, CYCLE_LOOP, '#include "simcore/runner.hpp"\nint Loop() { return 0; }\n')
    write(tmp_path, "src/simengine/main.cpp", "int main() { return 0; }\n")
    return tmp_path


def test_anl_04_c1_a_clean_tree_has_no_finding(clean_tree, capsys):
    assert script.check_single_carrier(clean_tree) == []
    assert script.main(["--root", str(clean_tree)]) == 0
    assert "clean" in capsys.readouterr().out


def test_anl_04_c2_a_planted_set_transport_publisher_call_is_reported_with_file_and_line(clean_tree, capsys):
    path = clean_tree / ABI
    path.write_text(path.read_text(encoding="utf-8") + "void Attach(Runner* r) { r->SetTransportPublisher(nullptr); }\n", encoding="utf-8")
    findings = script.check_single_carrier(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{ABI}:4: transport name: ")
    assert script.main(["--root", str(clean_tree)]) == 1
    assert f"{ABI}:4:" in capsys.readouterr().out


def test_anl_04_c3_a_planted_include_of_the_transport_header_is_reported_with_file_and_line(clean_tree):
    path = clean_tree / CYCLE_LOOP
    path.write_text(path.read_text(encoding="utf-8") + '#include "simcore/transport_shm.hpp"\n', encoding="utf-8")
    findings = script.check_single_carrier(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{CYCLE_LOOP}:3: transport include: ")


def test_anl_04_a_transport_word_in_a_comment_or_a_string_is_not_a_finding(clean_tree):
    assert script.check_single_carrier(clean_tree) == []


def test_selftest_plants_c2_and_c3_in_the_real_tree_and_passes(capsys):
    assert script.selftest() == 0
    out = capsys.readouterr().out
    assert "ANL-04 .c2" in out and "ANL-04 .c3" in out
    assert "FAIL" not in out


def test_the_real_tree_is_clean_of_the_retired_transport():
    assert script.check_single_carrier() == []
