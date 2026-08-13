# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C5 `UT-C5-6`/`UT-C5-7` (`NR-SIM-6`, arch §5.6 "Overrides and
sweeps"): the calibration-sweep mechanism a `run.overrides:` declaration
drives.

`UT-C5-6` proves `model.project.materialize_derived_bundle` itself: a
real per-function `default.yaml` nests one level by function
(`aeb: {AEB_..: ..}`, `df`'s own real shape), so a `run.overrides:`
address like `"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S"` is a YAML PATH, not
a label -- resolved generically (no function name known to the
framework, `R-SIM-1`) by searching every bundle YAML file for the one
where that path already resolves to a value.

`UT-C5-7` proves `core.manifest.resolve_swept_config`'s wiring: given a
declared sweep, it derives a bundle from a real `config:` directory and
returns the path a caller (`cli/resim.py`) must forward to
`Pipeline.init_components` -- proved reaching a component's own `init()`
with a `components=`-supplied double (no real DLL needed, same precedent
`test_c3_fault_hud_widget.py` sets for observing a component call with
no library present)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.resolve.component import ComponentManifest
from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import resolve_swept_config
from adas_sim.config.project import ProjectModel, materialize_derived_bundle


def _make_nested_bundle(bundle_dir: Path) -> None:
    """`df`'s own real bundle shape: `default.yaml` nested one level by
    function, `vehicle/ego_params.yaml` flat (no directory-name nesting,
    same as `test_a2_project.py::_make_real_bundle`)."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "vehicle").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "default.yaml").write_text(
        "aeb:\n"
        "  AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.0\n"
        "  AEB_MIN_SPEED_MPS: 1.0\n"
        "bsd:\n"
        "  BSD_ZONE_LATERAL_OUTER_M: 3.0\n",
        encoding="utf-8",
    )
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        "EGO_LENGTH_M: 4.5\nEGO_WIDTH_M: 1.8\nEGO_WHEELBASE_M: 2.7\nEGO_OVERHANG_FRONT_M: 0.9\n",
        encoding="utf-8",
    )


def test_materialize_derived_bundle_patches_a_nested_calibration_key(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    dest = tmp_path / "derived"

    materialize_derived_bundle(base, {"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S": 1.2}, dest)

    derived = yaml.safe_load((dest / "default.yaml").read_text(encoding="utf-8"))
    assert derived["aeb"]["AEB_TTC_PRE_WARNING_THRESHOLD_S"] == 1.2
    assert derived["aeb"]["AEB_MIN_SPEED_MPS"] == 1.0  # untouched sibling key
    assert derived["bsd"]["BSD_ZONE_LATERAL_OUTER_M"] == 3.0  # untouched sibling section


def test_materialize_derived_bundle_resolves_a_flat_single_segment_address(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    dest = tmp_path / "derived"

    materialize_derived_bundle(base, {"EGO_WHEELBASE_M": 2.9}, dest)

    resolved = ProjectModel.resolve(explicit=dest, project="base")
    assert resolved.ego().wheelbase_m == 2.9
    assert resolved.ego().length_m == 4.5  # untouched


def test_materialize_derived_bundle_changes_the_hash_and_never_touches_the_base(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    dest = tmp_path / "derived"
    base_sha = ProjectModel.resolve(explicit=base, project="base").bundle_sha256

    derived_sha = materialize_derived_bundle(base, {"EGO_WHEELBASE_M": 2.9}, dest)

    assert derived_sha != base_sha
    # the base directory's own file is byte-for-byte untouched (never edited, R-VAR-4)
    still_base_sha = ProjectModel.resolve(explicit=base, project="base").bundle_sha256
    assert still_base_sha == base_sha


def test_materialize_derived_bundle_raises_naming_the_address_when_the_key_is_unknown(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    dest = tmp_path / "derived"

    with pytest.raises(AuthoringError, match="AEB_NO_SUCH_KEY"):
        materialize_derived_bundle(base, {"aeb.AEB_NO_SUCH_KEY": 1.0}, dest)


def test_materialize_derived_bundle_raises_naming_every_candidate_on_an_ambiguous_key(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    # a second file declaring the exact same nested path -- an override
    # naming it can never guess which one the author meant.
    (base / "second.yaml").write_text("aeb:\n  AEB_TTC_PRE_WARNING_THRESHOLD_S: 9.0\n", encoding="utf-8")
    dest = tmp_path / "derived"

    with pytest.raises(AuthoringError, match="2 match"):
        materialize_derived_bundle(base, {"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S": 1.2}, dest)


def test_resolve_swept_config_with_no_overrides_is_a_passthrough(tmp_path):
    config = tmp_path / "some_config"
    resolved = resolve_swept_config(config, {}, project="base")
    assert resolved.effective_config is config
    assert resolved.scratch_dir is None
    assert resolved.base_bundle_sha == ""


def test_resolve_swept_config_requires_a_base_config_to_sweep(tmp_path):
    with pytest.raises(AuthoringError, match="run.overrides"):
        resolve_swept_config(None, {"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S": 1.2}, project="base")


def test_resolve_swept_config_derives_a_real_directory_the_caller_must_forward(tmp_path):
    base = tmp_path / "base"
    _make_nested_bundle(base)
    base_sha = ProjectModel.resolve(explicit=base, project="base").bundle_sha256

    resolved = resolve_swept_config(base, {"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S": 1.2}, project="base")

    assert resolved.effective_config != base
    assert resolved.scratch_dir == resolved.effective_config
    assert resolved.base_bundle_sha == base_sha
    derived = yaml.safe_load((resolved.effective_config / "default.yaml").read_text(encoding="utf-8"))
    assert derived["aeb"]["AEB_TTC_PRE_WARNING_THRESHOLD_S"] == 1.2


class _CapturingComponent:
    """A `SilComponent` double that records what `init()` actually
    received -- the same structural-typing precedent
    `test_c3_fault_hud_widget.py::_stub` sets, minus the `InProcessSilComponent`
    wrapper (this test cares about the config PATH forwarded, not
    `exec()` behaviour)."""

    def __init__(self, name: str, manifest: ComponentManifest) -> None:
        self.name = name
        self.manifest = manifest
        self.received_config_path: object = "never called"

    def init(self, config_path: Path | None = None) -> None:
        self.received_config_path = config_path

    def exec(self, dt_ns, inputs, input_meta=None):
        return {}

    def shutdown(self) -> None:
        pass

    def abi_version(self) -> int:
        return 1


def test_a_swept_config_reaches_the_components_own_init(tmp_path):
    """`UT-C5-7`: end to end, the same sequence `cli/resim.py`'s `run()`
    performs -- `resolve_swept_config` then `Pipeline.init_components` --
    proves the DERIVED directory (not the original `config:`), reflecting
    the override, is what a real component's `init()` actually sees."""
    base = tmp_path / "base"
    _make_nested_bundle(base)

    manifest = ComponentManifest(
        component="df", version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    stub = _CapturingComponent("df", manifest)

    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        yaml.safe_dump({
            "version": 1, "name": "test",
            "stages": [{"name": "df", "mode": "simulate", "impl": "stub:df", "inputs": {}}],
        }, sort_keys=False),
        encoding="utf-8",
    )
    pipeline = Pipeline.load(pipeline_path, components={"df": stub})

    resolved = resolve_swept_config(base, {"EGO_WHEELBASE_M": 2.9}, project="base")
    pipeline.init_components(resolved.effective_config)

    assert stub.received_config_path == resolved.effective_config
    assert stub.received_config_path != base
    derived_ego = yaml.safe_load((stub.received_config_path / "vehicle" / "ego_params.yaml").read_text(encoding="utf-8"))
    assert derived_ego["EGO_WHEELBASE_M"] == 2.9
