# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-07` tests: `UT-manifest-02`, `UT-bundle-01`..`UT-bundle-03`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.4/5.11). `F-STORE`: an in-memory
store that can be written, closed and reopened.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.config.bundle import BUNDLE_ABSENT, BundleAbsent, BundleMismatch, embed, read
from adas_sim.graph.build import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent
from adas_sim.runspec.manifest import build_manifest


class _Store:
    """`F-STORE`: written, closed, and reopened -- a fresh `_Store` built
    from a closed one's own bytes stands in for "reopened", since nothing
    here needs real file I/O to prove `embed`/`read`'s own logic."""

    def __init__(self, payload: bytes = b"") -> None:
        self._payload = payload
        self._closed = False

    def write_config_bundle(self, payload: bytes) -> None:
        self._payload = payload

    def close(self) -> None:
        self._closed = True

    def reopen(self) -> "_Store":
        assert self._closed, "reopen() is only meaningful after close()"
        return _Store(self._payload)

    def config_bundle_bytes(self) -> bytes:
        return self._payload


def _bundle_dir(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "vehicle").mkdir(parents=True)
    (root / "vehicle" / "ego_params.yaml").write_text("EGO_WHEELBASE_M: 2.7\n", encoding="utf-8")
    (root / "default.yaml").write_text("AEB_TTC_BRAKE_THRESHOLD_S: 1.5\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# 5.4 manifest
# ---------------------------------------------------------------------------


def _one_stage_pipeline(tmp_path: Path, *, stage_name: str = "df") -> Pipeline:
    manifest = ComponentManifest(
        component=stage_name, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({"name": "test", "stages": [
            {"name": stage_name, "mode": "simulate", "impl": f"stub:{stage_name}", "inputs": {}},
        ]}, sort_keys=False),
        encoding="utf-8",
    )
    component = InProcessSilComponent(stage_name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return Pipeline.load(path, components={stage_name: component})


def test_both_bundle_hashes_are_written_ut_manifest_02(tmp_path):
    """UT-manifest-02."""
    store = _Store()
    digest = embed(store, _bundle_dir(tmp_path))
    pipeline = _one_stage_pipeline(tmp_path)

    manifest = build_manifest(
        pipeline=pipeline, run_kind="sim", source_kind="mcap",
        component_bundle_shas={"df": digest}, component_bundle_embedded_shas={"df": digest},
        config_bundle_embedded=True,
    )

    component = manifest.components[0]
    assert component.config_bundle_sha256 and component.config_bundle_embedded_sha256  # .c1: both present
    assert component.config_bundle_sha256 == component.config_bundle_embedded_sha256  # .c1: and equal


# ---------------------------------------------------------------------------
# 5.11 bundle
# ---------------------------------------------------------------------------


def test_the_bytes_go_in_unchanged_ut_bundle_01(tmp_path):
    """UT-bundle-01."""
    bundle_dir = _bundle_dir(tmp_path)
    store = _Store()

    embed(store, bundle_dir)
    store.close()
    reopened = store.reopen()

    from adas_sim.config.project import bundle_bytes_for_recording
    assert reopened.config_bundle_bytes() == bundle_bytes_for_recording(bundle_dir)  # .c1


def test_the_hash_catches_an_alteration_ut_bundle_02(tmp_path):
    """UT-bundle-02."""
    store = _Store()
    digest = embed(store, _bundle_dir(tmp_path))

    unmodified = read(store, expected_sha256=digest)
    assert isinstance(unmodified, bytes)  # .c1: unmodified bytes read back matching

    store.write_config_bundle(store.config_bundle_bytes() + b"tampered")
    altered = read(store, expected_sha256=digest)
    assert isinstance(altered, BundleMismatch)  # .c2: the alteration is reported
    assert altered.stored == digest
    assert altered.recomputed != digest


def test_absence_consults_nothing_ut_bundle_03(tmp_path):
    """UT-bundle-03."""
    # A valid bundle exists on disk right beside the store, but read() takes
    # no path at all -- there is nothing it *could* consult.
    _bundle_dir(tmp_path)
    empty_store = _Store()

    result = read(empty_store)

    assert result is BUNDLE_ABSENT  # .c1
    assert isinstance(result, BundleAbsent)
