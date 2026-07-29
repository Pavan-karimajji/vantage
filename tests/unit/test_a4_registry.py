# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 `io/registry.py` test: UT-A4-7 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

import adas_sim.io.mcap  # noqa: F401 -- registers ".mcap"
from adas_sim.core.errors import AuthoringError
from adas_sim.io.registry import reader_for, writer_for


def test_unknown_extension_raises_naming_registered_codecs():
    """UT-A4-7."""
    with pytest.raises(AuthoringError) as excinfo:
        reader_for(Path("recording.notaformat"))
    err = excinfo.value
    assert ".notaformat" in err.found
    assert ".mcap" in err.expected

    with pytest.raises(AuthoringError):
        writer_for(Path("recording.notaformat"))
