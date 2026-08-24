# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Taps (`SW-0285`, `IMP-0285`): any internal port becomes recorded output by
naming it in a `taps:` table -- no code change, and removing a tap has no
other effect on the run (`R-SIM-6`'s per-port `record:` policy is for a
port already wired into the pipeline; a tap is the same idea one level
deeper, for a port a stage's manifest declares but no `inputs:`/`outputs:`
wiring consumes).

`parse_taps` and `resolve_taps` are the declaration and resolution halves --
pure, no recorder, no file I/O. Wiring `resolve_taps`'s output into
`sources.recorder.Recorder`'s own topic table (`Recorder._topics`,
`sources/recorder.py`) is this row's own named follow-on: that file is
outside `WP-24`'s `adas_sim/diagnostics/**` `Files:` scope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.resolve.component import ComponentManifest, PortSpec


@dataclass(frozen=True, slots=True)
class Tap:
    """One declared internal port, by stage and port name -- the same two
    coordinates every other reference in this package uses (`R-SIM-21`),
    never a spelled topic string."""

    stage: str
    port: str


def parse_taps(raw: Mapping[str, Sequence[str]]) -> tuple[Tap, ...]:
    """`taps: {<stage>: [<port>, ...]}` from the run configuration --
    order-preserving, a duplicate `(stage, port)` pair collapsed to one
    entry rather than recording it twice."""
    seen: set[tuple[str, str]] = set()
    taps: list[Tap] = []
    for stage_name, ports in raw.items():
        for port_name in ports:
            key = (stage_name, port_name)
            if key in seen:
                continue
            seen.add(key)
            taps.append(Tap(stage=stage_name, port=port_name))
    return tuple(taps)


def resolve_taps(
    taps: Sequence[Tap], manifests: Mapping[str, ComponentManifest],
) -> tuple[PortSpec, ...]:
    """Each declared `Tap` resolved against its stage's real manifest --
    naming both the stage and the port, plus the ports actually available,
    when a tap names one that is not there (`R-SIM-25`: never a silent
    no-op). A tap may name either an input or an output port -- an
    "internal" port here means "not already in the pipeline's normal
    wiring," not "output-only"."""
    resolved: list[PortSpec] = []
    for tap in taps:
        manifest = manifests.get(tap.stage)
        if manifest is None:
            raise AuthoringError(
                expected=f"a stage named {tap.stage!r}",
                found=f"known stages: {sorted(manifests)}",
                where="adas_sim.diagnostics.tap.resolve_taps",
                hint="check the stage name against the pipeline",
            )
        all_ports = (*manifest.inputs, *manifest.outputs)
        match = next((p for p in all_ports if p.name == tap.port), None)
        if match is None:
            raise AuthoringError(
                expected=f"a port named {tap.port!r} on stage {tap.stage!r}",
                found=f"available ports: {sorted(p.name for p in all_ports)}",
                where="adas_sim.diagnostics.tap.resolve_taps",
                hint="check the port name against the component's manifest",
            )
        resolved.append(match)
    return tuple(resolved)
