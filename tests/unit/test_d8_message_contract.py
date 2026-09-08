# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`UT-D8-8` (`docs/sim_implementation_plan.md`, `sim_player.md` §2's
"no naked identifiers" ban, §5.14's message contract): no failure message
consists only of an identifier -- every one names expected, found and
where it looked. `SimError.__init__` already requires all three as
keyword arguments (`core/errors.py`), so this is a table over REAL,
diverse call sites -- proof the contract holds in practice, not only in
the base class's own signature."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.resolve.component import CtypesSilComponent
from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import SimError
from adas_sim.resolve.plugins import PluginBundle
from adas_sim.config.project import materialize_derived_bundle


def _induce_pipeline_missing_impl(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("version: 1\nname: t\nstages:\n  - name: a\n    mode: simulate\n", encoding="utf-8")
    Pipeline.load(path)


def _induce_ctypes_component_bad_path(tmp_path: Path) -> None:
    CtypesSilComponent(tmp_path / "no_such_library.dll")


def _induce_bundle_override_unknown_key(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (base / "vehicle").mkdir(parents=True)
    (base / "vehicle" / "ego_params.yaml").write_text("EGO_LENGTH_M: 4.5\n", encoding="utf-8")
    materialize_derived_bundle(base, {"NO_SUCH_KEY": 1.0}, tmp_path / "derived")


def _induce_plugin_yaml_missing_required_key(tmp_path: Path) -> None:
    PluginBundle._from_yaml({"component": "x"}, origin="library", root=tmp_path)


#: (name, callable) -- each MUST raise a `SimError` (or, for the one
#: app/-level exception, something with an equally informative message,
#: `WorkspacePermissionError`'s own docstring on why it is not a
#: `SimError`).
_INDUCED_FAILURES = (
    ("pipeline stage missing impl:", _induce_pipeline_missing_impl),
    ("CtypesSilComponent bad path", _induce_ctypes_component_bad_path),
    ("bundle override unknown key", _induce_bundle_override_unknown_key),
    ("plugin.yaml missing required key", _induce_plugin_yaml_missing_required_key),
)


@pytest.mark.parametrize("name,induce", _INDUCED_FAILURES, ids=[n for n, _ in _INDUCED_FAILURES])
def test_every_induced_failure_names_expected_found_and_where(name, induce, tmp_path):
    with pytest.raises(SimError) as exc_info:
        induce(tmp_path)
    error = exc_info.value
    assert error.expected.strip(), f"{name}: expected was empty"
    assert error.found.strip(), f"{name}: found was empty"
    assert error.where.strip(), f"{name}: where was empty"
    # Never a bare identifier: the formatted message names all three, not
    # just a class name or a single token.
    message = str(error)
    assert "expected" in message and "found" in message and "where" in message
    assert len(message.split()) > 5, f"{name}: message reads as a naked identifier: {message!r}"
