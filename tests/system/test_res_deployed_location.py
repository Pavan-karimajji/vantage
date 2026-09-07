# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-21` -- `IT-14`/`IT-15`, against a hand-built `F-LIBDIR` (a deployed
library directory carrying `sim/ingest/` and `sim/plugin.yaml`) with the
source checkout it stands in for never referenced -- both resolve purely
from the deployed directory, exactly as `R-SIM-20` requires.
"""

from __future__ import annotations

import sys

import pytest
import yaml

from adas_sim.ingest.map import discover_ingest_maps_from_library_dirs
from adas_sim.resolve.plugins import discover_plugins, register_plugin_root


def test_it14_ingest_map_resolves_from_the_deployed_directory_with_no_checkout(tmp_path):
    """`IT-14`: delete the source checkout; run; the map resolves from the
    deployed directory (`<library_dir>/sim/ingest/`, `SW-0194`)."""
    library_dir = tmp_path / "deployed_only" / "lib"
    ingest_dir = library_dir / "sim" / "ingest"
    ingest_dir.mkdir(parents=True)
    (ingest_dir / "legacy.yaml").write_text(
        yaml.safe_dump({
            "family": "df.legacy",
            "matches": {"any_topic": ["df/gen_object_list"]},
            "provides": {"gen_object_list": {"from": ["df/gen_object_list"]}},
        }),
        encoding="utf-8",
    )
    # No `modules/*/sim/ingest` tree exists anywhere under tmp_path -- there
    # is nothing that could look like a source checkout to fall back to.
    assert not (tmp_path / "modules").exists()

    maps = discover_ingest_maps_from_library_dirs([library_dir])

    assert len(maps) == 1
    assert maps[0].family == "df.legacy"
    assert maps[0].provides[0].port == "gen_object_list"


def test_it15_player_points_at_a_folder_of_libraries_with_no_sibling_checkout(tmp_path, monkeypatch):
    """`IT-15`: point the player at a folder of libraries; layers render
    with no `PYTHONPATH` and no sibling checkout (`SW-0209`) -- proven here
    by discovering and importing a plug-in purely from `library_dir/sim/`,
    with `sys.path` unmodified."""
    library_dir = tmp_path / "deployed_only" / "lib"
    sim_dir = library_dir / "sim"
    sim_dir.mkdir(parents=True)
    (sim_dir / "layers.py").write_text(
        "REGISTERED = True\n", encoding="utf-8",
    )
    (sim_dir / "plugin.yaml").write_text(
        yaml.safe_dump({
            "api": 1, "component": "df", "provides": ["sim.layers"], "sha256": "cafef00d",
            "description": "test plugin", "version": "1.0", "author": "test", "projects": ["base"],
        }),
        encoding="utf-8",
    )
    (library_dir / "config").mkdir()

    path_before = list(sys.path)
    resolution = discover_plugins([library_dir])
    assert len(resolution) == 1
    bundle = resolution[0]
    (module,) = bundle.import_modules()
    assert module.REGISTERED is True
    assert sys.path == path_before  # no PYTHONPATH mutation

    # `register_plugin_root` is the same entry point `scripts/vantage.py`
    # uses -- confirms the config/ sibling is returned too.
    config_dir = register_plugin_root(library_dir)
    assert config_dir == library_dir / "config"
