# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Environment facts behind `sim doctor` (DG-3).

Kept out of `cli/` (GT-9: the CLI is argument parsing and dispatch only) so
every fact here is reachable from a plain script with no argparse involved.
Seeded at S-A1 with the environment questions that matter before anything
else exists; grows one field per later stage that adds something worth
checking (pipeline/recording resolution, codec capabilities, bundle hashes).
"""

from __future__ import annotations

import os
import sys
from importlib import metadata


def _install_mode() -> str:
    try:
        dist = metadata.distribution("adas-sim")
    except metadata.PackageNotFoundError:
        return "not installed"
    try:
        direct_url = dist.read_text("direct_url.json") or ""
    except OSError:
        direct_url = ""
    if '"editable": true' in direct_url:
        return "editable"
    return "standard"


def doctor_report() -> dict[str, object]:
    """Gather the S-A1 slice of `sim doctor`'s facts (DG-3): interpreter,
    install mode, platform, console encoding, line endings."""
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "adas_sim_install_mode": _install_mode(),
        "platform": sys.platform,
        "stdout_encoding": getattr(sys.stdout, "encoding", None),
        "stderr_encoding": getattr(sys.stderr, "encoding", None),
        "os_line_separator": repr(os.linesep),
    }
