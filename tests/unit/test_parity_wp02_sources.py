# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-02` tests: `UT-sourceset-01`..`UT-sourceset-04`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.sources import NamedSource, SourceSet, UnknownSource


def test_exactly_one_default_ut_sourceset_01():
    """UT-sourceset-01."""
    one_default = SourceSet(sources={
        "primary": NamedSource(recording=Path("a.mcap"), default=True),
        "secondary": NamedSource(recording=Path("b.mcap")),
    })
    assert one_default.default_name == "primary"  # .c1: accepted

    with pytest.raises(AuthoringError):  # .c2: zero defaults rejected
        SourceSet(sources={
            "primary": NamedSource(recording=Path("a.mcap")),
            "secondary": NamedSource(recording=Path("b.mcap")),
        })

    with pytest.raises(AuthoringError):  # .c2: two defaults rejected
        SourceSet(sources={
            "primary": NamedSource(recording=Path("a.mcap"), default=True),
            "secondary": NamedSource(recording=Path("b.mcap"), default=True),
        })


def test_one_source_per_port_ut_sourceset_02():
    """UT-sourceset-02."""
    sources = SourceSet(sources={
        "primary": NamedSource(recording=Path("a.mcap"), default=True),
        "secondary": NamedSource(recording=Path("b.mcap")),
    }, assignments={"port.b": "secondary"})

    resolved = {port: sources.for_port(port) for port in ("port.a", "port.b", "port.c")}

    assert all(isinstance(name, str) for name in resolved.values())  # .c1: exactly one, never none/two
    assert resolved == {"port.a": "primary", "port.b": "secondary", "port.c": "primary"}


def test_an_unknown_name_raises_before_reading_ut_sourceset_03():
    """UT-sourceset-03."""
    sources = SourceSet(
        sources={"primary": NamedSource(recording=Path("a.mcap"), default=True)},
        assignments={"port.x": "does_not_exist"},
    )

    with pytest.raises(UnknownSource) as excinfo:
        sources.for_port("port.x")  # .c2: for_port never opens a recording -- raises from pure lookup
    message = str(excinfo.value)
    assert "port.x" in message and "does_not_exist" in message  # .c1


def test_assignment_beats_default_ut_sourceset_04():
    """UT-sourceset-04."""
    sources = SourceSet(sources={
        "default_src": NamedSource(recording=Path("a.mcap"), default=True),
        "other": NamedSource(recording=Path("b.mcap")),
    }, assignments={"port.assigned": "other"})

    assert sources.for_port("port.assigned") == "other"  # .c1: assignment wins
    assert sources.for_port("port.neighbour") == "default_src"  # .c1: default for the rest
