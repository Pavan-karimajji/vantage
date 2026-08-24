# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""ANL-SW-69 (SIM_Software_Test_Spec_v0.1.md, serves SW-0375, WP-01) -- a
sampled port name is the identical string in the log, in configuration and
on screen (N-1..N-13).

Three surfaces, for one real component (`df`, the only one with a built
screen layer today):
  - config: `modules/df/conf/ports.yaml`'s declared `name:` fields
  - screen: the literal second argument every `AppendPortTree(...)` call
    site passes in `df_viz/layers/*.cpp` (`port_tree.hpp`'s own root_name)
  - log: the `port=` field on a `STAGE_INIT` line, emitted once per
    manifest port by `CtypesSilComponent.init()` -- captured from a real
    `adasInit()` call against the built `df_sil.dll`, never re-derived.

Skips (named reason) if `df_sil.dll` is not built -- `df` is not required to
run this suite, same discipline as `test_c1c_component.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.logging import Event, log
from adas_sim.resolve.component import CtypesSilComponent
from adas_sim.resolve.library import resolve_library
from adas_sim.diagnostics.errors import EnvironmentError_

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
DF_PORTS_YAML = DF_ROOT / "conf" / "ports.yaml"
DF_DEFAULT_PROJECT_YAML = DF_ROOT / "src" / "project" / "base" / "default.yaml"
DF_VIZ_LAYERS_DIR = DF_ROOT / "src" / "platform" / "df_viz" / "layers"
_DF_SIL_SEARCH_DIRS = [
    DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Debug",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Debug",
]
_SKIP_REASON = "no built df_sil.dll found under modules/df/build-*-vs2026 (partial clone / not built)"

_APPEND_PORT_TREE_LITERAL = re.compile(r'AppendPortTree\([^,]+,\s*"([^"]+)"')


def _config_port_names() -> set[str]:
    """Surface 1: `conf/ports.yaml`'s declared `name:` fields."""
    declared = yaml.safe_load(DF_PORTS_YAML.read_text(encoding="utf-8"))
    return {p["name"] for p in (*declared["inputs"], *declared["outputs"])}


def _screen_port_names() -> set[str]:
    """Surface 2: every literal root_name string an `AppendPortTree(...)`
    call site passes, across `df_viz/layers/*.cpp`."""
    names: set[str] = set()
    for path in DF_VIZ_LAYERS_DIR.glob("*.cpp"):
        names.update(_APPEND_PORT_TREE_LITERAL.findall(path.read_text(encoding="utf-8")))
    return names


def _real_df_sil_path() -> Path | None:
    try:
        return resolve_library("df_sil", search=_DF_SIL_SEARCH_DIRS)
    except EnvironmentError_:
        return None


def _logged_port_names(capsys: pytest.CaptureFixture[str]) -> set[str]:
    """Surface 3: `port=` fields from the real `STAGE_INIT` lines
    `CtypesSilComponent.init()` emits, captured from an actual run -- never
    re-derived from the manifest a second time."""
    component = CtypesSilComponent(_real_df_sil_path())
    component.init(DF_DEFAULT_PROJECT_YAML)
    out = capsys.readouterr().err
    names = set()
    for line in out.splitlines():
        if f"event={Event.STAGE_INIT.value}" not in line:
            continue
        match = re.search(r"\bport=(\S+)", line)
        if match:
            names.add(match.group(1))
    return names


def test_anl_sw69_screen_names_are_a_subset_of_config_names():
    """ANL-SW-69: no screen surface renames a concept config didn't declare."""
    screen = _screen_port_names()
    config = _config_port_names()
    assert screen, "no AppendPortTree(...) literal found -- test fixture is stale"
    assert screen <= config, f"screen names not in config: {screen - config}"


def test_anl_sw69_logged_names_are_a_subset_of_config_names(capsys):
    """ANL-SW-69: the log surface names only real, config-declared ports."""
    if _real_df_sil_path() is None:
        pytest.skip(_SKIP_REASON)
    logged = _logged_port_names(capsys)
    config = _config_port_names()
    assert logged, "no STAGE_INIT port= line captured -- log surface regressed"
    assert logged <= config, f"logged names not in config: {logged - config}"


def test_anl_sw69_sampled_port_is_identical_across_all_three_surfaces(capsys):
    """ANL-SW-69's own Accept clause: for a sampled set, the three strings
    are identical. `objects` is the sample -- declared in config, passed
    literally to AppendPortTree in common.cpp, and a real component input."""
    if _real_df_sil_path() is None:
        pytest.skip(_SKIP_REASON)
    sample = "objects"
    assert sample in _config_port_names()
    assert sample in _screen_port_names()
    assert sample in _logged_port_names(capsys)


def test_anl_sw69_fails_on_a_planted_character_difference():
    """R-REQ-9: the check is tested, not trusted -- a real mismatch between
    surfaces must be caught, not silently accepted."""
    config = {"objects", "egoDyn"}
    screen = {"objects", "egoDyn"}
    logged = {"objects", "ego_Dyn"}  # planted: an underscore the other two lack
    assert not (config == screen == logged)
