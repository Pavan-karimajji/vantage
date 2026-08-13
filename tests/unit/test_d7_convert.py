# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `cli/convert.py` tests: `UT-D7-6` (docs/sim_implementation_plan.md).
`tiny.mcap` (`tests/fixtures/`, S-A4's own self-contained fixture) round-
trips through `.mcap` twice -- the only registered `round_trips=True`
codec this session adds no second one of, so "convert to a genuinely
different format and back" stays a named gap, not silently claimed."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.cli.convert import run
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.plugins.registry import reader_for
import adas_sim.io.csv  # noqa: F401 -- registers ".csv" (write-only)
import adas_sim.io.mcap  # noqa: F401 -- registers ".mcap"

_TINY = Path(__file__).resolve().parent.parent / "fixtures" / "tiny.mcap"


def test_convert_round_trips_topics_schemas_provenance_and_message_bytes(tmp_path):
    """UT-D7-6."""
    once = tmp_path / "once.mcap"
    twice = tmp_path / "twice.mcap"
    assert run([str(_TINY), str(once)]) == 0
    assert run([str(once), str(twice)]) == 0

    original = reader_for(_TINY)
    roundtripped = reader_for(twice)
    try:
        assert original.topics() == roundtripped.topics()
        assert original.meta() == roundtripped.meta()
        assert list(original.messages()) == list(roundtripped.messages())
    finally:
        original.close()
        roundtripped.close()


def test_convert_refuses_a_write_only_destination(tmp_path):
    """`round_trips` gates both sides -- an export is never a convert target."""
    with pytest.raises(AuthoringError, match="round_trips"):
        run([str(_TINY), str(tmp_path / "out.csv")])


def test_convert_refuses_a_write_only_source(tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(AuthoringError, match="write-only"):
        run([str(csv_path), str(tmp_path / "out.mcap")])
