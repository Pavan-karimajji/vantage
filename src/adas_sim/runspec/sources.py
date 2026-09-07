# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-02`, `sourceset` item (`SW-0008`, `SW-0009`, `SW-0010`, `SW-0054`):
several complete recordings in one run, each port bound to exactly one of
them. Not multi-source merging -- every port still reads from a single
recording, `SourceSet` only decides *which* one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from adas_sim.diagnostics.errors import AuthoringError


@dataclass(frozen=True, slots=True)
class NamedSource:
    """One declared name's recording, plus whether it is this set's
    default (`SW-0008`)."""

    recording: Path
    default: bool = False


class UnknownSource(AuthoringError):
    """`SW-0010`: a port assigned to a name `SourceSet` does not hold --
    raised from `SourceSet.for_port`, naming both, never a caller-composed
    message (`IMP-0010`)."""

    def __init__(self, *, port: str, name: str) -> None:
        super().__init__(
            expected="a source name declared in this set",
            found=f"port {port!r} assigned to undeclared source {name!r}",
            where="runspec/sources.py::SourceSet.for_port",
            hint="declare this source under sources:, or fix the port's assignment",
        )


@dataclass(frozen=True, slots=True)
class SourceSet:
    """Named recordings for one run (`SW-0008`) plus each port's binding
    (`SW-0009`). `sources` maps a declared name to its `NamedSource`;
    exactly one must carry `default=True`, checked once here so a run can
    never assemble with zero or several. `assignments` maps a port to the
    name it is explicitly bound to; a port with no entry there resolves to
    the default (`SW-0054`)."""

    sources: Mapping[str, NamedSource]
    assignments: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        defaults = sorted(name for name, source in self.sources.items() if source.default)
        if len(defaults) != 1:
            raise AuthoringError(
                expected="exactly one source marked default: true",
                found=f"{len(defaults)} ({defaults})",
                where="runspec/sources.py::SourceSet",
                hint="declare exactly one named source as this run's default",
            )

    @property
    def default_name(self) -> str:
        return next(name for name, source in self.sources.items() if source.default)

    def for_port(self, port: str) -> str:
        """`SW-0009`/`SW-0054`: the explicit assignment first, the default
        second -- always exactly one name, never a collection (`IMP-0009`).
        Raises `UnknownSource` here, at resolution, before any recording is
        opened (`IMP-0010`) -- this function never reads a file."""
        assigned = self.assignments.get(port)
        if assigned is None:
            return self.default_name
        if assigned not in self.sources:
            raise UnknownSource(port=port, name=assigned)
        return assigned
