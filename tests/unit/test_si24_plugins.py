# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-29` `SI-24 plugins` -- `UT-PLG-02`/`UT-PLG-03`
(`docs/v2/SIM_Software_Test_Spec_v0.1.md` §5.24). `UT-PLG-01` (`SW-0357`,
`scripts/check_invariants.py`'s framework-source grep) is `WP-01`'s own
test, unchanged here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.io.base import RunManifest
from adas_sim.io.jsonl import JsonlReader
from adas_sim.plugins.conformance import templates
from adas_sim.plugins.conformance.exporter_kit import check_exporter
from adas_sim.plugins.conformance.module_kit import check_module
from adas_sim.plugins.conformance.reader_kit import check_reader
from adas_sim.plugins.registry import (
    EXTENSION_POINTS, exporter_for, extension_point_home, register_exporter, registered_exporters,
)
from adas_sim.resolve.plugins import PluginBundle


# ---------------------------------------------------------------------------
# UT-PLG-02 -- SW-0358: exactly three points (retired from four, `SM-12`,
# 2026-08-29 -- `"visualization"` pointed at `adas_sim.scene.registry`,
# which retired with the rest of the Python scene/render/player tree), each
# exercised by its shipped template plug-in and conformance kit; a fourth
# is refused.
# ---------------------------------------------------------------------------


def test_extension_points_are_exactly_three():
    assert EXTENSION_POINTS == ("reader", "exporter", "module")
    assert len(EXTENSION_POINTS) == 3


def test_reader_extension_point_passes_its_kit_against_a_real_codec(tmp_path):
    sample = tmp_path / "sample.jsonl"
    sample.write_text(json.dumps({"kind": "header", "meta": None, "topics": {}}) + "\n", encoding="utf-8")
    result = check_reader(JsonlReader, sample)
    assert result.ok, result.problems


def test_exporter_extension_point_passes_its_kit_against_a_real_codec(tmp_path):
    result = check_exporter(lambda: exporter_for("csv"), tmp_path / "out.csv", RunManifest())
    assert result.ok, result.problems


def test_module_extension_point_passes_its_kit_against_the_template(tmp_path):
    plugin_root = templates.write_template_plugin_dir(tmp_path / "component_root")
    bundle = PluginBundle.resolve(explicit=plugin_root)
    assert bundle is not None
    result = check_module(bundle)
    assert result.ok, result.problems


def test_a_fourth_extension_point_is_refused():
    with pytest.raises(AuthoringError) as excinfo:
        extension_point_home("recorder")
    assert "three extension points" in str(excinfo.value)
    for point in EXTENSION_POINTS:
        assert point in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-PLG-03 -- SW-0359: a plug-in of any kind is added by registration
# alone -- no edit to a framework file, and no roster to search for.
# ---------------------------------------------------------------------------


def test_reader_added_by_registration_alone(tmp_path):
    from adas_sim.plugins.registry import register, registered_extensions

    calls = []

    class _Marker:
        capabilities = None

        def __init__(self, path):
            calls.append(path)

    register(".marker9", reader=_Marker)
    assert ".marker9" in registered_extensions()


def test_exporter_added_by_registration_alone():
    class _MarkerWriter:
        capabilities = None

        def open(self, path, meta, topics): ...
        def write(self, topic, log_time_ns, payload, *, capture_time_ns=None): ...
        def close(self): ...

    register_exporter("marker9", _MarkerWriter)
    assert "marker9" in registered_exporters()
    assert isinstance(exporter_for("marker9"), _MarkerWriter)


def test_module_added_by_registration_alone(tmp_path):
    plugin_root = templates.write_template_plugin_dir(tmp_path / "component_root9", component="marker9")
    bundle = PluginBundle.resolve(explicit=plugin_root)
    assert bundle is not None and bundle.component == "marker9"


def test_no_plug_in_roster_exists_in_the_registration_modules():
    """A static search, not a claim: none of the three registration modules'
    own source names the plug-ins added by the tests above (`SW-0359`'s
    Accept clause: "a static check finds no plug-in roster") -- if adding a
    plug-in by registration alone required an edit to one of these files,
    the name we just registered above would appear in its source."""
    import adas_sim.plugins.registry as registry_mod
    import adas_sim.resolve.plugins as plugins_mod

    for module in (registry_mod, plugins_mod):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for planted_name in (".marker9", "marker9"):
            assert planted_name not in source
