# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""A15 (`misc/CONSOLIDATED_REQUIREMENTS.md` #16/#24, `SYS-0177`/`SYS-0123`,
`R-SIM-3a`/`R-SIM-6`): the config-bundle hash was landing empty in every
recording a real `dll:`/`stubdll:` pipeline produced, so *"which
calibration?"* read `unknown` even though *"which build?"* (`component_
build_shas`) already worked.

Root cause: `graph.pipeline._resolve_components` has always computed each
stage's bundle directory (`bundle_dirs`, `<library_dir>/config`) -- it is
`_validate_cross_component_agreement`'s own input -- but `Pipeline.load`
discarded it after that one call instead of keeping it on the instance, so
no method existed to turn it into a hash the way `component_build_shas`
already turns `library_paths` into one. `cli/run.py`/`cli/resim.py` therefore
had nothing to pass `core.manifest.build_manifest`'s `component_bundle_
shas`/`component_bundle_paths` kwargs, which defaulted to `{}` (see that
function's own docstring: an empty value there is meant to be a real answer,
never a forgotten one -- this was the forgotten case).

Mirrors `test_d7_pin_builds.py`'s own shape for `component_build_shas`: a
`components=`-supplied stage never sees a bundle directory either, same
"nothing to hash, not an empty string" reasoning (`R-SIM-25`/`NR-SIM-4`).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.config.project import _bundle_sha256
from adas_sim.diagnostics.evidence import evidence, format_evidence
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent
from adas_sim.graph.pipeline import Pipeline, Stage
from adas_sim.runspec.manifest import build_manifest
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _manifest() -> ComponentManifest:
    return ComponentManifest(
        component="echo", version="test", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _bundle_dir(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "config"
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        yaml.safe_dump({"EGO_WHEELBASE_M": 2.7}), encoding="utf-8",
    )
    return bundle_dir


def _pipeline_with_bundle(tmp_path: Path) -> tuple[Pipeline, Path]:
    bundle_dir = _bundle_dir(tmp_path)
    component = InProcessSilComponent(name="echo", manifest=_manifest(), fn=lambda dt_ns, inputs: {})
    stage = Stage(name="echo", mode="simulate", impl="dll:fake", inputs={})
    pipeline = Pipeline(
        name="test", stages=(stage,), version=1, components={"echo": component},
        bundle_dirs={"echo": bundle_dir},
    )
    return pipeline, bundle_dir


# ---------------------------------------------------------------------------
# Pipeline.component_bundle_shas / component_bundle_paths
# ---------------------------------------------------------------------------


def test_component_bundle_shas_matches_a_direct_hash_of_the_resolved_bundle_dir(tmp_path):
    pipeline, bundle_dir = _pipeline_with_bundle(tmp_path)
    expected = _bundle_sha256(bundle_dir)
    assert expected  # the fixture bundle is non-empty
    assert pipeline.component_bundle_shas() == {"echo": expected}


def test_component_bundle_paths_reports_the_directory_as_a_display_string(tmp_path):
    pipeline, bundle_dir = _pipeline_with_bundle(tmp_path)
    assert pipeline.component_bundle_paths() == {"echo": str(bundle_dir)}


def test_component_bundle_shas_omits_a_components_supplied_stage_with_no_bundle_dir():
    """Same convention as `component_build_shas`: a `components=`-supplied
    stage has no bundle directory and is absent from the result, never an
    empty-string placeholder."""
    component = InProcessSilComponent(name="echo", manifest=_manifest(), fn=lambda dt_ns, inputs: {})
    stage = Stage(name="echo", mode="simulate", impl=None, inputs={})
    pipeline = Pipeline(name="test", stages=(stage,), version=1, components={"echo": component})
    assert pipeline.component_bundle_shas() == {}
    assert pipeline.component_bundle_paths() == {}


def test_component_bundle_shas_omits_a_bundle_dir_that_does_not_exist_on_disk(tmp_path):
    """`_resolve_components` always predicts a `dll:`/`stubdll:` stage's
    bundle directory as `<library_dir>/config`, whether or not the build
    actually packed one there yet -- hashing a directory that is not there
    would raise, not degrade honestly, so it is skipped rather than hashed."""
    component = InProcessSilComponent(name="echo", manifest=_manifest(), fn=lambda dt_ns, inputs: {})
    stage = Stage(name="echo", mode="simulate", impl="dll:fake", inputs={})
    pipeline = Pipeline(
        name="test", stages=(stage,), version=1, components={"echo": component},
        bundle_dirs={"echo": tmp_path / "never_built" / "config"},
    )
    assert pipeline.component_bundle_shas() == {}
    # the path is still reported -- it is what a reader would go check
    assert pipeline.component_bundle_paths() == {"echo": str(tmp_path / "never_built" / "config")}


# ---------------------------------------------------------------------------
# End to end: build_manifest -> RunManifest -> evidence() no longer says
# "unknown" for a real dll:/stubdll: pipeline's config-bundle hash.
# ---------------------------------------------------------------------------


def test_build_manifest_carries_the_real_bundle_hash_not_empty(tmp_path):
    pipeline, bundle_dir = _pipeline_with_bundle(tmp_path)
    expected = _bundle_sha256(bundle_dir)

    meta = build_manifest(
        pipeline=pipeline, run_kind="resim", source_kind="mcap", project="base",
        component_build_shas=pipeline.component_build_shas(),
        component_bundle_paths=pipeline.component_bundle_paths(),
        component_bundle_shas=pipeline.component_bundle_shas(),
    )

    assert len(meta.components) == 1
    assert meta.components[0].name == "echo"
    assert meta.components[0].config_bundle_sha256 == expected
    assert meta.components[0].config_bundle_sha256 != ""


def test_evidence_reports_the_real_hash_instead_of_unknown(tmp_path):
    """This is what `sim explain <port> --at <tick>` and the player's
    evidence panel actually render -- `RUN_THE_DEMO.md`'s own documented
    rough edge ("`config_bundle_sha256` reads `unknown`") is what this test
    proves fixed."""
    pipeline, bundle_dir = _pipeline_with_bundle(tmp_path)
    expected = _bundle_sha256(bundle_dir)

    meta = build_manifest(
        pipeline=pipeline, run_kind="resim", source_kind="mcap", project="base",
        component_build_shas=pipeline.component_build_shas(),
        component_bundle_paths=pipeline.component_bundle_paths(),
        component_bundle_shas=pipeline.component_bundle_shas(),
    )

    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={"echo.outputs": PortValue(name="echo.outputs", message=b"\x01", origin="simulated")},
        pose=_POSE,
    )
    session = Session(run_id=meta.run_id, name="s", ticks=(tick,), meta=meta)

    record = evidence("echo.outputs", session, 0)
    assert record.config_bundle_sha256 == expected

    rendered = dict(format_evidence(record))
    assert rendered["config_bundle_sha256"] == expected
    assert rendered["config_bundle_sha256"] != "unknown"
