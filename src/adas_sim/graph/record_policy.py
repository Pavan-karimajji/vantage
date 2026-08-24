# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- `check_consumed_ports_recorded` (`IMP-0115`, `WP-20`),
relocated verbatim from `graph/build.py::validate_recordable`
(`R-SIM-6`'s per-port `record:` policy, `NR-SIM-42`). `build.py` keeps
`validate_recordable` as a thin wrapper -- both the public name and the two
types it takes (`Stage`, `SilComponent`) stay defined in `build.py`, so this
module imports them rather than re-declaring a second copy (`R-REQ-1`'s
"never a second copy" applied to types, not just requirements text).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from adas_sim.diagnostics.errors import AuthoringError

if TYPE_CHECKING:
    from adas_sim.graph.build import RecordVerb, SilComponent, Stage


def check_consumed_ports_recorded(stages: Sequence["Stage"], components: Mapping[str, "SilComponent"]) -> None:
    """Recording-time-only check (`NR-SIM-42`'s "two different times, two
    different answers"): the recorder calls this before starting, never
    `Pipeline.load` itself -- the very same pipeline loads fine for resim,
    where an excluded/decimated port is merely a cut `sim probe` reports as
    infeasible, not an error. A `mode: simulate` stage consuming a
    producing stage's output that is `excluded`/`decimate`d is a load error
    naming both ends: you would be recording a run whose own inputs you are
    not keeping, which can never be resimmed. `source.*`-fed inputs are
    exempt -- stimulus has no `record:` policy of its own in this model,
    the recorder always keeps it in full."""
    from adas_sim.graph.build import RecordVerb, _split_ref, record_policy_for

    by_name = {stage.name: stage for stage in stages}
    for stage in stages:
        if stage.mode != "simulate":
            continue
        for port_name, ref in stage.inputs.items():
            producer_name, ref_port = _split_ref(ref)
            if producer_name == "source":
                continue
            producer_stage = by_name.get(producer_name)
            if producer_stage is None:
                continue  # an undeclared producer is already _validate_wiring's error
            policy = record_policy_for(producer_stage, ref_port)
            if policy.verb is RecordVerb.FULL:
                continue
            detail = f"decimate={policy.decimate_n}" if policy.verb is RecordVerb.DECIMATE else policy.verb.value
            raise AuthoringError(
                expected=f"'{producer_name}.{ref_port}' to be recorded 'full' while "
                         f"stage '{stage.name}' (mode: simulate) consumes it as '{port_name}'",
                found=f"record: {detail}", where=f"stage '{producer_name}' record '{ref_port}'",
                hint="set record: full for this port, or set the consuming stage to mode: measured/off",
            )
