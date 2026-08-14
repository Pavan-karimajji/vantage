# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0158 -- IT-12 (the unit-test-level half; the full checkout /
read-only-install integration run is IT-12 proper, outside pytest's own
sandbox)."""

from __future__ import annotations

from pathlib import Path

from adas_sim.config.kinds import FileKind
from adas_sim.config.paths import ConfigPaths, sim_root


def test_project_root_is_never_derived_from_the_package_install_location(tmp_path):
    """The whole point of IMP-0158: `project_root` is a parameter, so a
    project living far outside `modules/sim` resolves correctly -- nothing
    here falls back to `sim_root()`."""
    paths = ConfigPaths(project_root=tmp_path)
    assert sim_root() not in tmp_path.parents
    assert paths.dir_for(FileKind.COMPOSITION) == tmp_path / "composition"


def test_dir_for_is_one_subdirectory_per_kind(tmp_path):
    paths = ConfigPaths(project_root=tmp_path)
    dirs = {paths.dir_for(kind) for kind in FileKind}
    assert dirs == {tmp_path / kind.value for kind in FileKind}
    assert len(dirs) == len(FileKind)  # no two kinds collide on a directory


def test_config_paths_is_a_plain_dataclass_no_singleton_state():
    a = ConfigPaths(project_root=Path("/one"))
    b = ConfigPaths(project_root=Path("/two"))
    assert a.dir_for(FileKind.LAYOUT) != b.dir_for(FileKind.LAYOUT)
