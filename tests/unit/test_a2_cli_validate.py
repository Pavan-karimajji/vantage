# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: `IMP-0165`'s own remaining gap, closed 2026-08-23 -- `sim validate`
as a real CLI verb over the already-tested `config.validate_only`. Wiring
only (`GT-9`): the library-level claims (schema/kinds/version/merge,
`ANL-SW-34`) are `test_a2_config_load.py`'s job, not re-tested here."""

from __future__ import annotations

import pytest

from adas_sim.cli.validate import run
from adas_sim.diagnostics.errors import AuthoringError


def _write_composition(project_root, *, units_yaml: str) -> None:
    comp_dir = project_root / "composition"
    comp_dir.mkdir(parents=True)
    (comp_dir / "package.yaml").write_text(f"version: 1\nunits:\n{units_yaml}", encoding="utf-8")


def test_validate_reports_ok_on_a_well_formed_project(tmp_path, capsys):
    _write_composition(tmp_path, units_yaml="  - name: aeb\n    impl: dll:aeb\n    ports: [outputs]\n")

    exit_code = run([str(tmp_path)])

    assert exit_code == 0
    assert "config valid" in capsys.readouterr().out


def test_validate_raises_an_authoring_error_naming_the_file_on_a_broken_project(tmp_path):
    comp_dir = tmp_path / "composition"
    comp_dir.mkdir()
    (comp_dir / "package.yaml").write_text("version: 1\nunits:\n  - name: aeb\n    bogus_key: 1\n", encoding="utf-8")

    with pytest.raises(AuthoringError) as excinfo:
        run([str(tmp_path)])
    assert "package.yaml" in str(excinfo.value)


def test_validate_needs_no_recording_and_no_binary_present(tmp_path, capsys):
    """`IMP-0165`'s own claim, restated at the CLI: nothing under
    `tmp_path` besides the config tree itself -- no `.mcap`, no `.dll`."""
    _write_composition(tmp_path, units_yaml="  - name: aeb\n    impl: dll:aeb\n    ports: [outputs]\n")

    assert run([str(tmp_path)]) == 0
    present = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert present == {"package.yaml"}
