# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The `Evidence` record and `evidence(address, session, tick)` (`OD-6`,
`R-SIM-25`, arch §5.19) -- "what was this value, and where did it come from".

**One producer, two formatters.** `cli/explain.py --at` and the GUI evidence
panel both call `evidence()` and format its result; neither re-derives it.
That is what makes "GUI and headless answer identically" structural rather
than a discipline (`GT-9`).

**It grows; it is not re-designed.** Arch §5.19 sketches the destination
fields -- `port`, `stage`, `overrides`, `faults`, `config_bundle`,
`component`, `plugin` -- to be added as those concepts come to exist. Adding
one is additive to the dataclass. `R-SIM-25`'s "a field it cannot fill reads
`unknown`" applies from the day a field exists, not before.

**The `Prim.pick_id` -> port join** reuses two things that already existed:
a provider's declared `requires` (`R-SIM-21`) and
`contracts.binding.try_resolve_component_ref`. `Layer.id` -> the registered
provider's `requires` -> resolved address is a static lookup -- no new
registry, no interception of a live provider call.

**Honest limit:** `requires` is the provider's *own declaration*, not a
compiler-verified list of every port its body reads. A provider calling
`ctx.port(...)` on a port it never declared resolves to `topic=None` here --
never a guess, same as any address matching nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.session.session import Session
from adas_sim.session.tick import Origin


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
    #: `IMP-0274`, from `IMP-0050`/`IMP-0052` (`simcore/bus`'s `Rung`/
    #: `Quality`, `WP-08`): how the timing this value carries was recovered.
    #: `None` today for every `kind` -- `WP-08`'s own explicit scope
    #: boundary leaves wire-level decode and run-manifest reporting of
    #: `rung`/`quality` as named follow-ons, so no Python-side `PortValue`
    #: (`session/tick.py`) carries either field yet to read from. The
    #: fields exist now so `render_panel`/`render_text` never need a second
    #: schema change once that data starts arriving; until then they
    #: honestly format `"unknown"` (`R-SIM-25`, `NR-SIM-4`) rather than
    #: guessing from `origin`.
    rung: str | None = None
    quality: str | None = None

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
    """Resolve `address` as a rendered `Prim.pick_id` at `tick`; `None` when no
        registered provider's scene contains it -- unresolvable, not an error.

        **Guarded by `registered_providers()` before anything else.** With no layer
        plug-in imported into this process, no `Prim` can exist, so returning early
        skips `build_scene`'s real disk I/O for the ordinary "not a prim" case.

        **Every other registered provider runs too, and its failure is not this
        address's failure.** The registry is process-global (`R-VAR-2`), shared by
        every component's layers and every fixture imported this process, and
        `build_scene` calls all of them. A provider crashing on a session it was
        never designed for -- seen for real, dereferencing a port's decoded message
        on a recording that carries it undecoded -- must not be reported as *this*
        address failing. Caught and treated as "no matching prim", which is what it
        honestly is from here.

    """
    from adas_sim.scene.registry import registered_providers
    if not registered_providers():
        return None

    from adas_sim.runspec.address import try_resolve_component_ref
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
                        where="adas_sim.diagnostics.evidence.evidence",
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
    "rung", "quality",
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
