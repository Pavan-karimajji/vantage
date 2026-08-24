# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Api` -- the public scripting surface (`SW-0230`, `DD-07`): **one import,
one construction, one call** reaches every capability.

    from adas_sim.pyapi import Api
    api = Api()
    record = api.evidence("stage_name.port_name", session, tick=120)

`orchestrate.verbs.VERBS` is the single, closed, published verb table
(`SW-0231`/`SW-0232`) -- `Api.verb`/`Api.dry_run` reach it by name so the CLI
and a script can never diverge on what a verb does; `Api` never re-derives
verb semantics of its own (`verbs.py`'s own docstring named this exact move
as its own honestly-scoped interim state, ahead of this package landing).

Every diagnostic (`SW-0286`, `UT-DIA-14`) is already a structurally-typed
function taking plain arguments and returning a dataclass or dict a script
can consume with no text parsing -- `diagnostics/evidence.py`,
`diagnostics/explain.py`, `diagnostics/estimate.py`,
`diagnostics/determinism.py`, `diagnostics/tolerance.py`,
`resolve/probe.py` (already true, per `SW-0286`'s own `Now.`). `Api`
re-exposes them as bound methods -- one place a script reaches every
diagnostic, rather than needing to know which `adas_sim.diagnostics.*`
submodule each lives in.
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.diagnostics.determinism import AxisResult, Divergence, compare_exact, compare_with_tolerance, derive_axis
from adas_sim.diagnostics.estimate import DurationEstimate, Shape, estimate_duration
from adas_sim.diagnostics.evidence import Evidence, evidence, format_evidence
from adas_sim.diagnostics.explain import explain, injection_boundary, known_names
from adas_sim.diagnostics.tolerance import ToleranceSet, load_tolerance
from adas_sim.orchestrate.verbs import VERBS, verb_count
from adas_sim.resolve.component import ComponentManifest
from adas_sim.resolve.probe import probe_manifest
from adas_sim.session.session import Session

__all__ = ["Api"]


class Api:
    """Constructed with no arguments -- the "one construction" of `DD-07`.
    Every method is one call; none takes an `argv` list to parse except
    `verb`/`dry_run`, which forward to the CLI-shaped verb table by design
    (`SW-0231`) rather than re-deriving each verb's own arguments here."""

    # ---- SW-0231/SW-0232: the closed, published verb table -----------------
    def verb(self, name: str, argv: list[str] | None = None) -> int:
        """Runs one of `orchestrate.verbs.VERBS`'s published verbs by name,
        e.g. `api.verb("resim", ["in.mcap", "pipeline.yaml", "--out", "out.mcap"])`.
        `UT-API-04` runs the same verb through the CLI and through this
        method and diffs the artifact directories -- they must not diverge,
        because both paths dispatch through the one `VERBS` table."""
        return VERBS[name].run(argv)

    def dry_run(self, name: str, argv: list[str] | None = None) -> int:
        """`SW-0234`: every verb's dry run, reached the same way as its real
        run -- prints the resolved plan, executes nothing."""
        return VERBS[name].dry_run(argv)

    @staticmethod
    def verbs() -> tuple[str, ...]:
        """The published verb set, for a script that wants to enumerate
        rather than name one verb -- `verb_count()`'s own callers already
        report this per release (`SW-0232`)."""
        return tuple(VERBS)

    # ---- SW-0286: every diagnostic, already pyapi-shaped -------------------
    @staticmethod
    def evidence(address: str, session: Session, tick: int) -> Evidence:
        """`evidence(address, session, tick)` -- the ONE producer (`R-SIM-25`,
        `SW-0273`); `format_evidence` is the text formatter, `Api.evidence`
        itself is the structured one a script consumes directly."""
        return evidence(address, session, tick)

    @staticmethod
    def format_evidence(record: Evidence) -> tuple[tuple[str, str], ...]:
        return format_evidence(record)

    @staticmethod
    def explain_signal(address: str, session: Session, tick: int) -> Evidence:
        """`SW-0403` (`IMP-0403`): the provenance query, reached from a
        script -- literally `evidence()` (`SW-0273`'s ONE producer), never a
        second derivation. `cli/explain.py --at`'s own answer and the GUI
        evidence panel's are proven field-for-field identical against this
        same `evidence()` call (`IMP-0273`'s tests); this method is that
        producer's third caller, not a third implementation."""
        return evidence(address, session, tick)

    @staticmethod
    def explain(name: str, session: Session) -> dict[str, object]:
        """Resolves any name in the system -- port, topic, layer, signal,
        error or id -- to what it is, what produced it, which document
        defines it. Executes nothing (`ANL-SW-34`)."""
        return explain(name, session)

    @staticmethod
    def known_names(session: Session) -> list[str]:
        return known_names(session)

    @staticmethod
    def injection_boundary(stages) -> tuple[tuple[str, str, str, str], ...]:
        return injection_boundary(stages)

    @staticmethod
    def estimate_duration(shape: Shape, *, history_path: Path | None = None) -> DurationEstimate:
        """Returns `(estimate, accuracy_band)` -- the band is measured from
        prior runs of the same shape, never asserted (`SW-0272`)."""
        return estimate_duration(shape, history_path=history_path)

    @staticmethod
    def probe_manifest(path: Path) -> ComponentManifest:
        """A module's ports from its manifest -- `adasAbiVersion`/
        `adasManifest` only, never an execute call (`resolve/probe.py`'s own
        symbol-bounded scope)."""
        return probe_manifest(path)

    @staticmethod
    def compare_exact(reader_a, reader_b) -> Divergence | None:
        return compare_exact(reader_a, reader_b)

    @staticmethod
    def compare_with_tolerance(reader_a, reader_b, tolerance: ToleranceSet):
        return compare_with_tolerance(reader_a, reader_b, tolerance)

    @staticmethod
    def derive_axis(manifest_a, manifest_b) -> AxisResult:
        return derive_axis(manifest_a, manifest_b)

    @staticmethod
    def load_tolerance(path: Path, *, component: str) -> ToleranceSet:
        return load_tolerance(path, component=component)
