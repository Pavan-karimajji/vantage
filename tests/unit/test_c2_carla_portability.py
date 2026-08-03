# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 5: `UT-C2-11` -- no module under `sources/` launches a
process through a shell or names an absolute path (`sim_portability.md`
P-2, P-6). A grep is the enforcement, same technique `GT-1`
(`scripts/check_invariants.py`) already uses for the `aeb`/`bsd`/...
string ban."""

from __future__ import annotations

import re
from pathlib import Path

_SOURCES_DIR = Path(__file__).resolve().parents[2] / "src" / "adas_sim" / "sources"

#: P-6: no shell, no string-form subprocess/os.system call anywhere.
_SHELL_LAUNCH_PATTERN = re.compile(r"\bos\.system\(|\bshell\s*=\s*True|\bsubprocess\.")

#: P-2: a hard-coded absolute path -- a Windows drive letter or a POSIX
#: root -- anywhere outside a comment/docstring explaining the rule itself.
_ABSOLUTE_PATH_PATTERN = re.compile(r"[\"'][A-Za-z]:[\\/]|[\"']/(?:home|usr|etc|ws)/")


def _source_files() -> list[Path]:
    return sorted(_SOURCES_DIR.rglob("*.py"))


def test_no_module_under_sources_launches_a_process_through_a_shell():
    offenders = [
        str(path) for path in _source_files() if _SHELL_LAUNCH_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_no_module_under_sources_hard_codes_an_absolute_path():
    offenders = [
        str(path) for path in _source_files() if _ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_sources_dir_actually_has_files_to_check():
    """A guard against this test silently checking nothing (e.g. a wrong
    path after a directory move)."""
    assert len(_source_files()) >= 10
