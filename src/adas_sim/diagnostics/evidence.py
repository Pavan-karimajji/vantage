# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The `Evidence` record and `evidence(address, session, tick)` (`OD-6`,
`R-SIM-25`, arch §5.19) -- "what was this value, and where did it come from".

**`cli/explain.py --at` is this framework's own headless caller.** The
Python-side GUI evidence panel this docstring used to describe as the other
formatter retired with the rest of the Python scene/render/player tree
(`SM-12`); `viz`'s own C++ evidence chain (`BuildEvidence`) is the live
"two formatters, one producer" the retired panel used to be (`GT-9`'s
principle, now spanning languages rather than one Python process).

**It grows; it is not re-designed.** Arch §5.19 sketches the destination
fields -- `port`, `stage`, `overrides`, `faults`, `config_bundle`,
`component`, `plugin` -- to be added as those concepts come to exist. Adding
one is additive to the dataclass. `R-SIM-25`'s "a field it cannot fill reads
`unknown`" applies from the day a field exists, not before.
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
    kind: str  # "run_id" | "port" | "unknown" -- grows at S-C1c (field/layer/signal)
    value: str  # formatted value, at this tick
    tick: int
    t_ns: int
    topic: str | None  # the port name that carried it (N-2: topic and port name are the same path)
    origin: Origin | None
    run_id: str
    #: `ST-D6-3`: the owning stage's config bundle and build id, from
    #: `session.meta.components` -- `None` when the address resolved to no
    #: port (`kind` other than `port`) or that stage carries no
    #: `RunManifest` entry (a manifestless recording, `manifest_version=0`).
    config_bundle_sha256: str | None = None
    component_build_id: str | None = None
    #: `F-8` (2026-08-28): the owning stage's `library_sha256`, under its own
    #: name. **Not a fallback for `component_build_id` and never rendered as
    #: one.** A recording written by this framework populates
    #: `library_sha256` and leaves `build_id` empty — nothing sets a build id
    #: today — so before this field existed, *"which build produced it"*
    #: (`DEMO_AND_SCOPE.md` §1) read `unknown` while the answer sat one
    #: dereference away in the same manifest. Showing that hash under the
    #: `component_build_id` label would have been the plausible-looking
    #: default `R-SIM-25`/`NR-SIM-4` forbid — two different facts, one of
    #: them absent. So both are carried, each says which it is, and
    #: `component_build_id` still reads `unknown` when no build id was
    #: recorded, because it genuinely was not.
    component_library_sha256: str | None = None
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


def _component_provenance(port_address: str, session: Session) -> tuple[str | None, str | None, str | None]:
    """`port_address`'s owning stage's build provenance as
    `(config_bundle_sha256, build_id, library_sha256)`, or `(None, None,
    None)` when that stage has no `RunManifest` entry -- never a guess
    across stages (`R-SIM-25`, `NR-SIM-4`).

    **The three are returned separately and stay separate** (`F-8`). Every
    recording this framework writes fills `library_sha256` and leaves
    `build_id` empty, so collapsing them would make the answer to *"which
    build?"* silently mean *"which library file"* on most recordings and
    genuinely mean *"which build id"* on the rest -- one label, two facts,
    which is the substitution `R-SIM-25` exists to prevent. Each travels
    under its own name and each is `None` when truly absent.
    """
    stage_name = port_address.split(".", 1)[0]
    for component in session.meta.components:
        if component.name == stage_name:
            return (
                component.config_bundle_sha256 or None,
                component.build_id or None,
                component.library_sha256 or None,
            )
    return (None, None, None)


def evidence(address: str, session: Session, tick: int) -> Evidence:
    """`address`'s evidence at `tick` -- a run_id, a port (present in that
    tick's own `ports`), or `kind="unknown"`. Raises the same way
    `Session.at` does for an out-of-range `tick` (`AuthoringError`); an
    unresolvable `address` is not an error here, only `kind="unknown"`,
    mirroring `core/explain.explain`'s own degrade.

    **No `kind="prim"` any more.** Resolving a rendered `Prim.pick_id` back
    to a port retired with the rest of the Python scene/render/player tree
    (`SM-12`, `docs/VIZ_Sync_Plan_v0.1.md`) -- `viz`'s own C++ evidence
    chain (`BuildEvidence`, `cpp/viz/player/evidence.hpp`) is the live
    equivalent for anything rendered as a `Prim` today, since no Python
    layer provider can register one any more.
    """
    current = session.at(tick)

    if address == session.run_id:
        return Evidence(
            address=address, kind="run_id", value=session.run_id,
            tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
        )

    if address in current.ports:
        port_value = current.ports[address]
        config_bundle_sha256, component_build_id, component_library_sha256 = _component_provenance(
            address, session)
        return Evidence(
            address=address, kind="port", value=str(port_value.message),
            tick=tick, t_ns=current.t_ns, topic=address, origin=port_value.origin,
            run_id=session.run_id, config_bundle_sha256=config_bundle_sha256,
            component_build_id=component_build_id,
            component_library_sha256=component_library_sha256,
        )

    return Evidence(
        address=address, kind="unknown", value="",
        tick=tick, t_ns=current.t_ns, topic=None, origin=None, run_id=session.run_id,
    )


#: The one fixed field order `cli/explain.py --at` renders.
EVIDENCE_FIELDS = (
    "address", "kind", "value", "tick", "t_ns", "topic", "origin", "run_id",
    "config_bundle_sha256", "component_build_id", "component_library_sha256",
    "rung", "quality",
)


#: The label column width `cli/explain.py` prints with, **derived from the
#: field names rather than typed** (`F-8`, 2026-08-28). It used to be a
#: literal `20` in the CLI and a matching literal `20` in `UT-D3-8`'s own
#: parser -- two copies of one number, so adding a field whose name exceeded
#: it split the CLI's own output in the wrong place and made the two surfaces
#: appear to disagree when they did not. One definition, so a longer field
#: name can never silently misalign them again.
EVIDENCE_LABEL_WIDTH = max(len(field) for field in EVIDENCE_FIELDS) + 1


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
