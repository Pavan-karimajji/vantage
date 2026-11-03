# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0068` (`D29 (1)`): `McapReader.meta()` takes a component's bundle hash from the `config_bundle` block's
`<stage>/bundle.sha256` when the `manifest` entry states none, where the engine writes it."""

from __future__ import annotations

import yaml
from mcap.writer import Writer

from adas_sim.io.mcap import McapReader

_HASH = "ab" * 32


def _recording(path, *, entry: dict, bundle: dict | None):
    with path.open("wb") as handle:
        writer = Writer(handle)
        writer.start(profile="", library="imp-0068-test")
        manifest = {"manifest_version": 1, "components": [{"name": "sut", "build_id": "b", **entry}]}
        writer.add_metadata("manifest", {"yaml": yaml.safe_dump(manifest)})
        if bundle is not None:
            writer.add_metadata("config_bundle", bundle)
        writer.finish()


def test_imp_0068_a_bundle_hash_is_filled_from_the_config_bundle_block(tmp_path):
    path = tmp_path / "filled.mcap"
    _recording(path, entry={}, bundle={"sut/bundle.sha256": _HASH + "\n", "sut/default.yaml": "X: 1\n"})
    assert McapReader(path).meta().components[0].config_bundle_sha256 == _HASH


def test_imp_0068_a_hash_the_manifest_states_is_kept(tmp_path):
    path = tmp_path / "kept.mcap"
    _recording(path, entry={"config_bundle_sha256": "cd" * 32}, bundle={"sut/bundle.sha256": _HASH})
    assert McapReader(path).meta().components[0].config_bundle_sha256 == "cd" * 32


def test_imp_0068_with_no_block_the_hash_is_left_empty(tmp_path):
    path = tmp_path / "none.mcap"
    _recording(path, entry={}, bundle=None)
    assert McapReader(path).meta().components[0].config_bundle_sha256 == ""
