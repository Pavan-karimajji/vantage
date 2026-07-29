# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The facts behind `sim explain` (DG-2), kept out of `cli/` (GT-9) so they
are reachable from a plain script. **Seeded at S-B2** over what exists now: a
session, its topics, its registered layer ids, its `run_id`. Grows at
`S-C1c` (ports, schemas, producers) and `S-D6` (expectations, values) --
same reasoning as `core/diagnostics.py`'s `sim doctor` seed at `S-A1`: the
tool that explains names is needed while names are being created, not after.
"""

from __future__ import annotations

from adas_sim.core.session import Session
from adas_sim.scene.registry import registered_providers


def explain(name: str, session: Session) -> dict[str, object]:
    """Everything known about `name` right now: a topic (present in the
    session's recording), a registered layer id, or the session's own
    `run_id`. Fuzzy "did you mean" (`N-8`) is `S-D6`'s job, once there are
    enough names for a near-miss to be worth suggesting.
    """
    if name == session.run_id:
        return {
            "kind": "run_id",
            "name": name,
            "tick_count": len(session),
            "deterministic": session.deterministic,
            "manifest_known": session.meta.known,
        }

    topics = session.ticks[0].ports if session.ticks else {}
    if name in topics:
        port_value = topics[name]
        return {
            "kind": "topic",
            "name": name,
            "present_in_recording": True,
            "origin": port_value.origin,
        }

    providers = registered_providers()
    if name in providers:
        entry = providers[name]
        return {
            "kind": "layer",
            "name": name,
            "module": entry.module,
            "qualname": entry.qualname,
        }

    return {
        "kind": "unknown",
        "name": name,
        "searched": ["run_id", "topics", "registered layers"],
    }
