# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0151/IMP-0152/IMP-0153 -- UT-CFG-04, UT-CFG-05, UT-CFG-06."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.config import schema
from adas_sim.config.kinds import FileKind
from adas_sim.diagnostics.errors import AuthoringError


def _valid_composition() -> dict:
    return {"version": 1, "units": [{"name": "aeb", "impl": "dll:aeb", "ports": ["outputs"]}]}


def test_valid_composition_passes():
    schema.check_version(FileKind.COMPOSITION, _valid_composition(), where="<test>")
    schema.validate(FileKind.COMPOSITION, _valid_composition(), path=Path("<test>"))


@pytest.mark.parametrize("kind", list(FileKind))
def test_break_each_kinds_schema_reports_file_line_value_and_allowed(kind, tmp_path):
    """UT-CFG-04: break each file kind's schema; read file, line, wrong
    value and allowed values."""
    path = tmp_path / f"{kind.value}.yaml"
    path.write_text("version: 1\nunits: \"not a list\"\n" if kind is FileKind.COMPOSITION else "version: 1\n", encoding="utf-8")
    raw = {"version": 1, "units": "not a list"} if kind is FileKind.COMPOSITION else {"version": 1, "name": 5} if kind is FileKind.CONNECTIONS else {"version": "not an int"}

    with pytest.raises(AuthoringError) as excinfo:
        schema.validate(kind, raw, path=path)
    assert str(path) in str(excinfo.value)


def test_unknown_key_then_near_miss_key(tmp_path):
    """UT-CFG-05: add an unknown key; then one differing by one character
    from a real key."""
    path = tmp_path / "composition.yaml"
    path.write_text("version: 1\nunits: []\ntotally_unknown: 1\n", encoding="utf-8")
    with pytest.raises(AuthoringError) as excinfo:
        schema.validate(FileKind.COMPOSITION, {"version": 1, "units": [], "totally_unknown": 1}, path=path)
    assert "totally_unknown" in str(excinfo.value)

    path2 = tmp_path / "composition2.yaml"
    path2.write_text("version: 1\nunit: []\n", encoding="utf-8")  # "unit" vs real "units"
    with pytest.raises(AuthoringError) as excinfo2:
        schema.validate(FileKind.COMPOSITION, {"version": 1, "unit": []}, path=path2)
    assert "units" in str(excinfo2.value)  # the suggestion


@pytest.mark.parametrize("kind", list(FileKind))
def test_omit_version_then_exceed_supported_range(kind, tmp_path):
    """UT-CFG-06: omit the version in each file kind; then set one beyond
    the supported range."""
    path = tmp_path / f"{kind.value}.yaml"
    path.write_text("units: []\n", encoding="utf-8")
    with pytest.raises(AuthoringError):
        schema.check_version(kind, {}, where=str(path))

    with pytest.raises(AuthoringError):
        schema.check_version(kind, {"version": schema.CURRENT_VERSIONS[kind] + 1}, where=str(path))
