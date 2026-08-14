# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The closed `event=` vocabulary (SI-07, N-10, sim_api_reference.md §2.5).

Moved out of `diagnostics/logging.py` into its own module (`WP-03`,
`IMP-0127`) so it has a C++ parity twin: `src/simcore/errors/events.cpp`
carries the same twelve values, hand-transcribed from `docs/v2/events.yaml`
alongside this file and kept honest by `scripts/check_error_parity.py`.
"""

from __future__ import annotations

from enum import StrEnum


class Event(StrEnum):
    """The closed `event=` vocabulary (N-10). Adding a value is a review."""

    RUN_START = "run_start"
    RUN_END = "run_end"
    STAGE_INIT = "stage_init"
    STAGE_SHUTDOWN = "stage_shutdown"
    EXEC_OK = "exec_ok"
    EXEC_FAIL = "exec_fail"
    PORT_MISSING = "port_missing"
    PORT_OVERRIDDEN = "port_overridden"
    DEGRADE = "degrade"
    EXPECT_PASS = "expect_pass"
    EXPECT_FAIL = "expect_fail"
    BUNDLE_MISMATCH = "bundle_mismatch"
