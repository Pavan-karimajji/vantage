# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The `Evidence` record and `evidence(address, session, tick)` (`OD-6`,
`R-SIM-25`, `sim_architecture.md` §5.19). **Seeded here at `S-B2Δ`** over
what a `Session` alone can answer: `run_id`, a tick's own ports and their
origins, the run manifest. Exactly the same seeding discipline
`core/explain.py` used at this same stage (`S-B2`) for `sim explain`'s
static half -- this is its dynamic half, "what was this value, at this
tick", the two together making `cli/explain.py --at` real.

**Grows, does not get re-designed.** `sim_architecture.md` §5.19 sketches
the destination shape -- `port`, `stage`, `overrides`, `faults`,
`config_bundle`, `component`, `plugin` -- once those concepts exist to
report: ports/stages at `S-C1c`, plug-ins at `S-C8`, the GUI panel at
`S-D3`. Adding a field there is additive to this dataclass, never a
redesign of it (`R-SIM-25`'s own "a field it cannot fill reads unknown"
applies from the day a field is added, not before it exists to omit).

**One producer, two formatters (`OD-6`).** `cli/explain.py --at` and the
future GUI evidence panel (`S-D3`) both call `evidence()` and format its
result -- neither re-derives it, which is what makes "GUI and headless
answer identically" structural rather than a discipline (`GT-9`).
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.core.session import Session
from adas_sim.core.tick import Origin


@dataclass(frozen=True, slots=True)
class Evidence:
    """One producer's answer for one address, at one tick. A field this
    stage cannot fill is `None`, never a plausible-looking default
    (`R-SIM-25`, `NR-SIM-4`)."""

    address: str  # what was asked about, as typed
    kind: str  # "run_id" | "port" | "unknown" -- grows at S-C1c (field/prim/layer/signal)
    value: str  # formatted value, at this tick
    tick: int
    t_ns: int
    topic: str | None  # the port name that carried it (N-2: topic and port name are the same path)
    origin: Origin | None
    run_id: str

    def __repr__(self) -> str:
        return f"<Evidence {self.address!r} kind={self.kind} tick={self.tick}>"


def evidence(address: str, session: Session, tick: int) -> Evidence:
    """`address`'s evidence at `tick` -- a run_id, a port (present in that
    tick's own `ports`), or `kind="unknown"`. Raises the same way
    `Session.at` does for an out-of-range `tick` (`AuthoringError`); an
    unresolvable `address` is not an error here, only `kind="unknown"`,
    mirroring `core/explain.explain`'s own degrade.
    """
    current = session.at(tick)

    if address == session.run_id:
        return Evidence(
            address=address, kind="run_id", value=session.run_id,
            tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
        )

    if address in current.ports:
        port_value = current.ports[address]
        return Evidence(
            address=address, kind="port", value=str(port_value.message),
            tick=tick, t_ns=current.t_ns, topic=address, origin=port_value.origin,
            run_id=session.run_id,
        )

    return Evidence(
        address=address, kind="unknown", value="",
        tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
    )


#: The one fixed field order both `cli/explain.py --at` and the GUI
#: evidence panel (`UT-D3-8`, `view/evidence_panel.py`) render.
EVIDENCE_FIELDS = ("address", "kind", "value", "tick", "t_ns", "topic", "origin", "run_id")


def format_evidence(record: Evidence) -> tuple[tuple[str, str], ...]:
    """`record`'s fields as `(name, text)` pairs, in `EVIDENCE_FIELDS`
    order -- the one formatter both surfaces call (`OD-6`'s "one producer,
    two formatters"), so they cannot render an `Evidence` differently by
    accident. A field this stage could not fill (`None`) prints
    `"unknown"` -- never Python's bare `"None"`, and never blank on one
    surface while the other shows a value (`R-SIM-25`, `NR-SIM-4`)."""
    return tuple((field, _format_field(getattr(record, field))) for field in EVIDENCE_FIELDS)


def _format_field(value: object) -> str:
    return "unknown" if value is None else str(value)
