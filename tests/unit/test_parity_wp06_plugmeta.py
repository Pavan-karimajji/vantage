# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-06` tests: `UT-plugmeta-01`..`UT-plugmeta-04`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.10).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.resolve.plugins import (
    MissingIdentityField, PluginBundle, format_inspection, format_listing_row, format_refusal,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "interfaces" / "scripts"))
import pack_plugin_bundle  # noqa: E402

_COMPLETE = {
    "api": 1, "component": "df", "provides": [],
    "description": "the driving-functions plug-in", "version": "1.0", "author": "test",
    "projects": ["base"],
}


def _write_plugin_yaml(tmp_path: Path, data: dict, *, name: str = "plugin_dir") -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "plugin.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return root


def test_four_fields_all_required_ut_plugmeta_01(tmp_path):
    """UT-plugmeta-01."""
    complete = _write_plugin_yaml(tmp_path, _COMPLETE, name="complete")
    bundle = PluginBundle.resolve(library_dir=complete)
    assert bundle is not None  # .c1: the complete declaration parses

    for missing_field in ("description", "version", "author", "projects"):
        incomplete_data = {k: v for k, v in _COMPLETE.items() if k != missing_field}
        incomplete = _write_plugin_yaml(tmp_path, incomplete_data, name=f"missing_{missing_field}")
        with pytest.raises(AuthoringError):  # .c2: each incomplete one is rejected
            PluginBundle.resolve(library_dir=incomplete)


def test_the_refusal_names_the_field_ut_plugmeta_02(tmp_path):
    """UT-plugmeta-02."""
    for missing_field in ("description", "version", "author", "projects"):
        incomplete_data = {k: v for k, v in _COMPLETE.items() if k != missing_field}
        incomplete = _write_plugin_yaml(tmp_path, incomplete_data, name=f"missing_{missing_field}")
        with pytest.raises(MissingIdentityField) as excinfo:
            PluginBundle.resolve(library_dir=incomplete)
        # .c1: `expected`/`found` -- the refusal's own identification of
        # WHICH field is at fault -- name the removed field and no other.
        # (`hint` legitimately lists the whole vocabulary for context; that
        # is not the same claim as "which field caused this refusal".)
        assert missing_field in excinfo.value.expected
        assert missing_field in excinfo.value.found
        for other in ("description", "version", "author", "projects"):
            if other != missing_field:
                assert other not in excinfo.value.expected
                assert other not in excinfo.value.found


def test_the_copy_is_unchanged_ut_plugmeta_03(tmp_path):
    """UT-plugmeta-03."""
    authored = _write_plugin_yaml(tmp_path, _COMPLETE, name="authored")
    (authored / "layers.py").write_text("VALUE = 1\n", encoding="utf-8")
    deployed_dir = tmp_path / "deployed"

    pack_plugin_bundle.pack(out=deployed_dir, plugin_dir=authored)

    deployed_yaml = yaml.safe_load((deployed_dir / "plugin.yaml").read_text(encoding="utf-8"))
    for field in ("description", "version", "author", "projects"):
        assert deployed_yaml[field] == _COMPLETE[field]  # .c1: identical, not altered or dropped


def test_one_accessor_feeds_every_surface_ut_plugmeta_04(tmp_path):
    """UT-plugmeta-04."""
    root = _write_plugin_yaml(tmp_path, _COMPLETE, name="bundle")
    bundle = PluginBundle.resolve(library_dir=root)
    assert bundle is not None

    listing = format_listing_row(bundle)
    inspection = format_inspection(bundle)
    refusal = format_refusal(bundle, reason="a test reason")

    assert bundle.identity() in listing
    assert bundle.identity() in inspection
    assert bundle.identity() in refusal

    # Change the accessor's output (a different author) and confirm all
    # three surfaces move together -- never one showing a stale value,
    # which would mean a second read path (SW-0053's own FAIL condition).
    changed = PluginBundle(
        component=bundle.component, api=bundle.api, sha256=bundle.sha256, provides=bundle.provides,
        origin=bundle.origin, root=bundle.root, description=bundle.description, version=bundle.version,
        author="someone else", projects=bundle.projects,
    )
    assert format_listing_row(changed) != listing
    assert format_inspection(changed) != inspection
    assert format_refusal(changed, reason="a test reason") != refusal
    assert "someone else" in format_listing_row(changed)
    assert "someone else" in format_inspection(changed)
    assert "someone else" in format_refusal(changed, reason="a test reason")
