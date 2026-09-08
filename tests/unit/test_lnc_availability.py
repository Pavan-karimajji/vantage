# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-03` (`launcher/availability.py`,
`SW-0344`). `F-LIBDIR`-shaped fixture: a deployed library directory with
one platform's binary present, one absent."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import yaml

from adas_sim.launcher.availability import check_all, check_availability
from adas_sim.launcher.model import Selection
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec


def _manifest(*, component: str) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="out", proto_type="test.A"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _one_stage_pipeline(tmp_path: Path, *, impl: str) -> Pipeline:
    data = {"version": 1, "name": "solo", "stages": [{"name": "solo", "mode": "simulate", "impl": impl, "inputs": {}}]}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    component = InProcessSilComponent("solo", _manifest(component="solo"), lambda dt_ns, inputs: {})
    component.init()
    return Pipeline.load(path, components={"solo": component})


# ---------------------------------------------------------------------------
# UT-LNC-03 -- SW-0344: shown before launch, no dlopen
# ---------------------------------------------------------------------------


def test_a_present_binary_is_reported_available(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libpresent.so").write_bytes(b"\x00")
    (lib_dir / "present.dll").write_bytes(b"\x00")

    result = check_availability("sut", "dll:present", search=(lib_dir,))
    assert result.available is True
    assert result.reason == ""


def test_an_absent_binary_is_reported_unavailable_before_launch(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()

    result = check_availability("sut", "dll:absent", search=(lib_dir,))
    assert result.available is False
    assert "absent" in result.reason or "no binary" in result.reason


def test_no_dlopen_is_ever_attempted(tmp_path):
    """`UT-LNC-03`'s own "count load attempts" -- must be zero for both a
    present and an absent module."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libpresent.so").write_bytes(b"\x00")
    (lib_dir / "present.dll").write_bytes(b"\x00")

    with mock.patch("adas_sim.resolve.component.ctypes.CDLL") as cdll:
        check_availability("sut", "dll:present", search=(lib_dir,))
        check_availability("sut", "dll:absent", search=(lib_dir,))
        cdll.assert_not_called()


def test_a_stage_with_no_impl_is_unavailable(tmp_path):
    result = check_availability("sut", None, search=())
    assert result.available is False
    assert "no impl" in result.reason


def test_version_is_unknown_never_a_guess(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libpresent.so").write_bytes(b"\x00")
    (lib_dir / "present.dll").write_bytes(b"\x00")

    result = check_availability("sut", "dll:present", search=(lib_dir,))
    assert result.version == "unknown"


def test_check_all_reports_every_stage_in_the_selection(tmp_path):
    pipeline = _one_stage_pipeline(tmp_path, impl="stub:solo")
    selection = Selection(base_pipeline=pipeline)

    results = check_all(selection)
    assert [r.stage for r in results] == ["solo"]
    # stub: has no resolvable binary in a file-loaded pipeline (Pipeline.load
    # has no components= at launch time) -- reported unavailable, not a
    # false "available".
    assert results[0].available is False
