# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0225` (`SW-0225`, `R-SIM-6`'s own "estimate the size before starting,
labelled an upper bound and revised from the measured rate"): the pre-run
recording-volume estimate, moved out of `sources/recorder.py::Recorder`
(`MOVE` -- same two functions, now over plain numbers instead of a live
`Recorder`/`Pipeline`, so a caller that has not opened anything yet -- a
campaign sizing pass over several scenarios, `sim batch`'s own pre-flight --
can call this with no `Recorder` instance at all).

`Recorder.estimate_upper_bound_bytes`/`revised_estimate_bytes` are now thin
wrappers over `estimate_upper_bound_bytes`/`revised_estimate_bytes` below --
one implementation, not two copies of the same arithmetic.
"""

from __future__ import annotations

#: `ST-C2-3`'s "revised after the first hundred ticks" threshold -- unchanged
#: from `sources/recorder.py::REVISE_AFTER_TICKS`.
REVISE_AFTER_TICKS = 100


def estimate_upper_bound_bytes(port_max_bytes: list[int], ticks: int) -> int:
    """An upper bound from each recorded port's own declared byte cap
    (`max_bytes`, already resolved by the caller -- this function does not
    know about `PortSpec`/`_DEFAULT_PORT_BYTES`, only plain numbers) times
    `ticks`. The caller labels this an upper bound, never a measurement
    (`R-SIM-6`)."""
    return sum(port_max_bytes) * ticks


def revised_estimate_bytes(
    bytes_written: int, ticks_written: int, total_ticks: int,
    *, min_ticks_before_revision: int = REVISE_AFTER_TICKS,
) -> int | None:
    """`None` until `min_ticks_before_revision` real ticks are written --
    before that, only `estimate_upper_bound_bytes` is honest to report."""
    if ticks_written < min_ticks_before_revision:
        return None
    return int(bytes_written / ticks_written * total_ticks)
