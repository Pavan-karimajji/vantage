# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Console UTF-8 reconfiguration, called once at every entry point (P-4).

A Windows console defaults to cp1252 and raises ``UnicodeEncodeError`` on the
em-dashes, arrows and check marks the design documents and log lines use; a
Linux terminal defaults to UTF-8 and does not. Already hit once writing the
``docs/py`` design-evidence harness (``docs/py/_common.py``); fixed there the
same way.
"""

from __future__ import annotations

import sys


def reconfigure_console_utf8() -> None:
    """Reconfigure stdout/stderr to UTF-8 with ``errors="replace"``.

    Safe to call more than once, and safe when a stream has already been
    wrapped or is not a real console (e.g. captured by a test runner).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
