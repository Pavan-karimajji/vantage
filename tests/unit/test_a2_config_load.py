# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0154/IMP-0165/IMP-0166 -- UT-CFG-07, UT-CFG-15, UT-CFG-16."""

from __future__ import annotations

import pytest

from adas_sim.config import load, validate_only
from adas_sim.config.kinds import FileKind
from adas_sim.config.layers import Layer
from adas_sim.config.paths import ConfigPaths
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.diagnostics.explain import explain, known_names
from adas_sim.session.session import Session


def _write_composition(project_root, *, units_yaml: str) -> None:
    comp_dir = project_root / "composition"
    comp_dir.mkdir(parents=True)
    (comp_dir / "package.yaml").write_text(f"version: 1\nunits:\n{units_yaml}", encoding="utf-8")


def test_a_well_formed_project_loads_with_no_recording_and_no_binary(tmp_path):
    """UT-CFG-15: validate with every recording and binary removed --
    load()/validate_only() take a bare directory of YAML, nothing else."""
    _write_composition(tmp_path, units_yaml="  - name: aeb\n    impl: dll:aeb\n    ports: [outputs]\n")
    paths = ConfigPaths(project_root=tmp_path)

    cfg = validate_only(paths)

    assert cfg.resolved[FileKind.COMPOSITION]["units"].value == [
        {"name": "aeb", "impl": "dll:aeb", "ports": ["outputs"]}
    ]


@pytest.mark.parametrize("broken_class", ["unknown_key", "bad_version", "cross_unit_reference"])
def test_break_each_class_of_reference_fails_at_load_before_any_tick(broken_class, tmp_path):
    """UT-CFG-07: break each class of reference; confirm the failure occurs
    at load, before any tick (there is no tick concept here at all --
    config/** never executes anything, ANL-SW-34)."""
    comp_dir = tmp_path / "composition"
    comp_dir.mkdir(parents=True)
    bodies = {
        "unknown_key": "version: 1\nunits: []\ntotally_bogus: 1\n",
        "bad_version": "version: 99\nunits: []\n",
        "cross_unit_reference": (
            "version: 1\nunits:\n"
            "  - name: aeb\n    impl: dll:aeb\n"
            "  - name: bsd\n    impl: dll:bsd\n    ports: [aeb]\n"
        ),
    }
    (comp_dir / "package.yaml").write_text(bodies[broken_class], encoding="utf-8")
    paths = ConfigPaths(project_root=tmp_path)

    with pytest.raises(AuthoringError):
        load(paths)


def test_cli_layer_wins_and_is_merged_last(tmp_path):
    _write_composition(tmp_path, units_yaml="  - name: aeb\n    impl: dll:aeb\n")
    paths = ConfigPaths(project_root=tmp_path)

    cfg = load(paths, cli={FileKind.COMPOSITION: {"version": 1}})

    assert cfg.resolved[FileKind.COMPOSITION]["version"].layer is Layer.CLI


def test_run_the_dry_run_read_the_source_layer_for_every_resolved_value(tmp_path):
    """UT-CFG-16: run the dry run; read the source layer for every resolved
    value -- and (IMP-0166) explain() surfaces it too."""
    _write_composition(tmp_path, units_yaml="  - name: aeb\n    impl: dll:aeb\n")
    paths = ConfigPaths(project_root=tmp_path)
    cfg = load(paths)

    for leaf in cfg.resolved[FileKind.COMPOSITION].values():
        assert leaf.layer is Layer.PACKAGE
        assert leaf.file.name == "package.yaml"

    empty_session = Session(run_id="r1", name="r1", ticks=())
    result = explain("version", empty_session, config=cfg)
    assert result["kind"] == "config_value"
    assert result["layer"] == "package"
    assert result["value"] == 1
    assert "version" in known_names(empty_session, config=cfg)
