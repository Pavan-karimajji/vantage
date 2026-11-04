# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`command_line` (`IMP-0151`, `SYS-0110`, `SYS-0123`): the one function that builds the engine's command line. `run_engine`
(the one place that starts `simengine`), the window's *copy command line* and its *start* all call it, so the copied text is the
one that is started (`R-SIM-16`).

Two faces (`ARCH §9`): the developer face is the engine started directly, `<engine> <setup> [--threads N] [--wait-for-attach]`; the
batch face is the same with `--supervise --attempt-timeout-ms D [--restart-on-crash N]`. The deadline has no default
(`SYS-0090`, `SYS-0109`): a batch face without one is refused, naming it, before anything is built.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from adas_sim.diagnostics.errors import AuthoringError

FACES = ("developer", "batch")


def command_line(
    engine: Path | str, setup_path: Path | str, face: str = "developer", *, deadline_ms: int | None = None,
    threads: int = 1, restart_on_crash: int = 0, wait_for_attach: bool = False,
) -> list[str]:
    """The engine's command line for `setup_path` on `face`. The batch face needs `deadline_ms`; the developer face takes none."""
    if face not in FACES:
        raise AuthoringError(expected=f"one of {FACES}", found=repr(face), where="launcher.command.command_line")
    command = [str(engine), str(setup_path)]
    if threads != 1:
        command += ["--threads", str(threads)]
    if wait_for_attach:
        command.append("--wait-for-attach")
    if face == "batch":
        if deadline_ms is None or deadline_ms < 1:
            raise AuthoringError(
                expected="attempt_timeout_ms, the deadline of one attempt (no default exists)", found=repr(deadline_ms),
                where="launcher.command.command_line", hint="a supervised start names its deadline (SYS-0090)",
            )
        command += ["--supervise", "--attempt-timeout-ms", str(deadline_ms)]
        if restart_on_crash:
            command += ["--restart-on-crash", str(restart_on_crash)]
    return command


def command_text(command: Sequence[str]) -> str:
    """The command line as one string a shell runs (Windows quoting rules)."""
    return subprocess.list2cmdline([str(part) for part in command])
