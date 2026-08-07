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

**`ST-D6-3` (S-D6): the `Prim.pick_id` -> port join.** A rendered prim's
`pick_id` did not resolve to the port/topic that produced it -- `kind="prim"`
below closes that, the "still-open half of R-SIM-25's join" `view/
evidence_panel.py`'s own docstring named. The join reuses two pieces that
already existed for a different reason: `scene.registry.LayerProviderEntry.
requires` (the provider's own declared `self.<port>` refs, `R-SIM-21`,
today used only for tick-gating) and `contracts.binding.
try_resolve_component_ref` (the same tolerant resolver `LayerCtx.port`
already calls). No new registry, no live-provider-call interception --
`Layer.id` -> `registered_providers()[id].requires` -> resolved address is a
static lookup. **Honest limit, stated rather than hidden**: `requires` is a
provider's OWN declaration, used today for gating, not a compiler-verified
list of every port its body reads -- a provider that calls `ctx.port(...)`
on a port it never listed in `requires=` resolves to `topic=None` here
(never a guess), same as an address matching nothing does elsewhere in this
module. **Also unblocked this pass**: `config_bundle_sha256`/
`component_build_id`, resolved from `session.meta.components` by the
port's own stage prefix (`core.manifest.build_manifest`'s
`ComponentBuildInfo.name = stage.name`, so `<stage>.<port>`'s stage half is
already the lookup key) -- populated for `kind="port"` too, not only
`kind="prim"`, since asking about a port directly should answer the same
question a prim resolving to that port would.

**One producer, two formatters (`OD-6`).** `cli/explain.py --at` and the
GUI evidence panel (`S-D3`, `view/evidence_panel.py`) both call `evidence()`
and format its result -- neither re-derives it, which is what makes "GUI and
headless answer identically" structural rather than a discipline (`GT-9`).
`MainWindow` already passes a raw `pick_id` as `address` (`render/viewer.py`
`_on_evidence_sync`, predating this change) -- `kind="prim"` landing here
needed no GUI-side edit to reach it, exactly what "one producer" buys.
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
    kind: str  # "run_id" | "port" | "prim" | "unknown" -- grows at S-C1c (field/layer/signal)
    value: str  # formatted value, at this tick
    tick: int
    t_ns: int
    topic: str | None  # the port name that carried it (N-2: topic and port name are the same path)
    origin: Origin | None
    run_id: str
    #: `ST-D6-3`: the owning stage's config bundle and build id, from
    #: `session.meta.components` -- `None` when the address resolved to no
    #: port (`kind` other than `port`/`prim`) or that stage carries no
    #: `RunManifest` entry (a manifestless recording, `manifest_version=0`).
    config_bundle_sha256: str | None = None
    component_build_id: str | None = None
    #: `ST-D6-3`, `kind="prim"` only: the `Layer.id` the selected prim came
    #: from, and `Prim.derived` (`R-SIM-7`'s published-vs-reconstructed
    #: marker) -- both `None` for every other `kind`.
    layer_id: str | None = None
    derived: bool | None = None

    def __repr__(self) -> str:
        return f"<Evidence {self.address!r} kind={self.kind} tick={self.tick}>"


def _component_provenance(port_address: str, session: Session) -> tuple[str | None, str | None]:
    """`port_address`'s owning stage's build provenance, or `(None, None)`
    when that stage has no `RunManifest` entry -- never a guess across
    stages (`R-SIM-25`, `NR-SIM-4`)."""
    stage_name = port_address.split(".", 1)[0]
    for component in session.meta.components:
        if component.name == stage_name:
            return (component.config_bundle_sha256 or None, component.build_id or None)
    return (None, None)


def _resolve_prim(address: str, session: Session, tick: int) -> Evidence | None:
    """`address` as a rendered `Prim.pick_id` at `tick` -- `None` when no
    currently-registered layer provider's scene contains it (unresolvable,
    not an error: mirrors `evidence()`'s own `kind="unknown"` degrade).

    **Guarded by `registered_providers()`, checked before anything else.**
    No layer plug-in imported into this process (the plain CLI and every
    unit test that does not import one, `S-C8`'s plug-in loading being a
    separate, larger gap this row does not close) means no `Prim` could
    possibly exist -- returning early here skips `build_scene`'s real
    `ProjectModel.resolve` disk I/O for the ordinary "not a prim" case,
    the same one every non-prim address already took before this function
    existed.

    **Every OTHER registered provider runs too, and its failure is not
    this address's failure.** `registered_providers()` is one process-global
    registry (`R-VAR-2`) shared by every component's real layers and every
    test fixture ever imported this process -- `build_scene` calls all of
    them, not just whichever one might own `address`. A provider crashing
    on a session/tick it was never designed for (found for real: a
    component's provider dereferencing a port's decoded message on a
    session whose recording carries that port undecoded) must not be
    reported as *this* address failing to resolve -- caught and treated the
    same as "no matching prim", which is what it honestly is from this
    call's point of view.
    """
    from adas_sim.scene.registry import registered_providers
    if not registered_providers():
        return None

    from adas_sim.contracts.binding import try_resolve_component_ref
    from adas_sim.core.runner import build_scene

    current = session.at(tick)
    try:
        scene = build_scene(session, tick, project=session.meta.project or "base")
    except Exception:
        return None
    for layer in scene.layers:
        for prim in layer.prims:
            if prim.pick_id != address:
                continue
            entry = registered_providers().get(layer.id)
            resolved_ports: list[str] = []
            if entry is not None:
                for ref in entry.requires:
                    resolved = try_resolve_component_ref(
                        ref, known_ports=session.known_ports,
                        where="adas_sim.core.evidence.evidence",
                    )
                    if resolved is not None:
                        resolved_ports.append(resolved)
            topic = resolved_ports[0] if resolved_ports else None
            value = str(current.ports[topic].message) if topic in current.ports else prim.kind
            origin = current.ports[topic].origin if topic in current.ports else None
            config_bundle_sha256 = component_build_id = None
            if topic is not None:
                config_bundle_sha256, component_build_id = _component_provenance(topic, session)
            return Evidence(
                address=address, kind="prim", value=value,
                tick=tick, t_ns=current.t_ns, topic=topic, origin=origin, run_id=session.run_id,
                config_bundle_sha256=config_bundle_sha256, component_build_id=component_build_id,
                layer_id=layer.id, derived=prim.derived,
            )
    return None


def evidence(address: str, session: Session, tick: int) -> Evidence:
    """`address`'s evidence at `tick` -- a run_id, a port (present in that
    tick's own `ports`), a rendered prim's `pick_id` (`kind="prim"`,
    `ST-D6-3`), or `kind="unknown"`. Raises the same way `Session.at` does
    for an out-of-range `tick` (`AuthoringError`); an unresolvable `address`
    is not an error here, only `kind="unknown"`, mirroring
    `core/explain.explain`'s own degrade.
    """
    current = session.at(tick)

    if address == session.run_id:
        return Evidence(
            address=address, kind="run_id", value=session.run_id,
            tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
        )

    if address in current.ports:
        port_value = current.ports[address]
        config_bundle_sha256, component_build_id = _component_provenance(address, session)
        return Evidence(
            address=address, kind="port", value=str(port_value.message),
            tick=tick, t_ns=current.t_ns, topic=address, origin=port_value.origin,
            run_id=session.run_id, config_bundle_sha256=config_bundle_sha256,
            component_build_id=component_build_id,
        )

    prim_record = _resolve_prim(address, session, tick)
    if prim_record is not None:
        return prim_record

    return Evidence(
        address=address, kind="unknown", value="",
        tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
    )


#: The one fixed field order both `cli/explain.py --at` and the GUI
#: evidence panel (`UT-D3-8`, `view/evidence_panel.py`) render.
EVIDENCE_FIELDS = (
    "address", "kind", "value", "tick", "t_ns", "topic", "origin", "run_id",
    "config_bundle_sha256", "component_build_id", "layer_id", "derived",
)


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
