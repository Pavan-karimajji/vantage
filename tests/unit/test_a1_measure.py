# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0367 -- `measure.py` is tested, not trusted (IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from measure import Provenance, format_measurement, measure_provenance  # noqa: E402


def test_measure_provenance_fills_all_four_fields():
    p = measure_provenance()
    assert p.platform
    assert p.shell
    assert p.cpu
    assert p.build_type  # "unknown" is a valid, honest value -- never empty
    assert p.python


def test_format_measurement_carries_the_number_and_all_provenance_fields():
    p = Provenance(platform="TestOS-1", shell="testshell", cpu="TestCPU", build_type="Release", python="3.12.0")
    line = format_measurement(12.5, "ms", provenance=p)
    assert "12.5" in line
    assert "ms" in line
    assert "TestOS-1" in line
    assert "testshell" in line
    assert "TestCPU" in line
    assert "Release" in line


def test_measure_provenance_reports_unknown_build_type_when_unset(monkeypatch):
    """A measurement with no provenance would be indistinguishable from
    one deliberately taken outside a build -- 'unknown' is the honest
    value the check exists to require, never a blank field."""
    monkeypatch.delenv("CMAKE_BUILD_TYPE", raising=False)
    p = measure_provenance()
    assert p.build_type == "unknown"


def test_measure_provenance_picks_up_declared_build_type(monkeypatch):
    monkeypatch.setenv("CMAKE_BUILD_TYPE", "Debug")
    p = measure_provenance()
    assert p.build_type == "Debug"
