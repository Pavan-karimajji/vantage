# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-05: IMP-0001, IMP-0003, IMP-0005, IMP-0006, IMP-0007, IMP-0009,
IMP-0011, IMP-0412 -- UT-SPC-01, 02, 04, 06, 24. Schema `adas.sim.runspec/2.0`
(`WP-01`, `IMP-0051`): the setup carries no `grid`, `order`, `sampling` or
`on_missing`, so the tests of those (UT-SPC-07, UT-SPC-23, the emit-time
wiring cycle) are gone; the writer's new keys are tested in
`test_vnt_wp01_emit.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.config import load
from adas_sim.config.override import Override, OverrideVerb
from adas_sim.config.paths import ConfigPaths
from adas_sim.diagnostics.errors import InternalError
from adas_sim.resolve.component import ComponentManifest, PortSpec
from adas_sim.runspec.canon import RunSpec
from adas_sim.runspec.emit import RUN_SPEC_SCHEMA, RunSetupValues, SourceSpec, emit_run_spec, unresolved


def _manifest(name: str, *, period_ns: int = 20_000_000, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=name, version="1.0", abi_version=1, build_id="x",
        inputs=inputs, outputs=outputs, project="base",
        config_bundle_sha256="deadbeef", descriptor_set=b"", period_ns=period_ns,
    )


def _setup_values() -> RunSetupValues:
    """Provisional test values -- the writer has no default for any of them."""
    return RunSetupValues(
        readiness_limit_steps=4, fallback_max_gap=4, trigger={"aeb": "", "bsd": ""}, buffer_depth={"*": 16},
    )


def _project(tmp_path: Path, *, wiring_yaml: str = "") -> ConfigPaths:
    comp_dir = tmp_path / "composition"
    comp_dir.mkdir()
    (comp_dir / "package.yaml").write_text(
        "version: 1\nunits:\n"
        "  - name: aeb\n    impl: dll:aeb\n    ports: [outputs]\n"
        "  - name: bsd\n    impl: dll:bsd\n    ports: [outputs]\n",
        encoding="utf-8",
    )
    if wiring_yaml:
        conn_dir = tmp_path / "connections"
        conn_dir.mkdir()
        (conn_dir / "package.yaml").write_text(wiring_yaml, encoding="utf-8")
    return ConfigPaths(project_root=tmp_path)


def _manifests():
    return {
        "aeb": _manifest("aeb", outputs=(PortSpec(name="outputs", proto_type="adas.df.AebOutputs"),)),
        "bsd": _manifest(
            "bsd", inputs=(PortSpec(name="aeb_in", proto_type="adas.df.AebOutputs"),),
            outputs=(PortSpec(name="outputs", proto_type="adas.df.BsdOutputs"),),
        ),
    }


def test_emit_produces_a_spec_with_no_unresolved_construct(tmp_path):
    """UT-SPC-01: the emit raises unless unresolved() returns empty --
    verified directly by calling unresolved() on the returned spec too."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path, wiring_yaml=(
        "version: 1\nname: demo\nwiring:\n  - stage: bsd\n    port: aeb_in\n    from: aeb.outputs\n"
    ))
    cfg = load(paths)

    spec = emit_run_spec(
        cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir],
        sources=[SourceSpec(path=(tmp_path / "rec.mcap").resolve(), sha256="abc")],
        outputs={"path": str((tmp_path / "out.mcap").resolve()), "codec": "mcap"},
    )

    assert unresolved(spec) == []
    assert spec.data["schema"] == RUN_SPEC_SCHEMA  # IMP-0005


def test_stages_impl_carries_a_resolved_absolute_path_never_a_stem(tmp_path):
    """UT-SPC-02 (the emit-time slice): IMP-0003 -- no search_path/stem
    survives into the field itself, only a resolved absolute path."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path)
    cfg = load(paths)

    spec = emit_run_spec(cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir])

    aeb_stage = next(s for s in spec.data["stages"] if s["name"] == "aeb")
    assert Path(aeb_stage["impl"]["path"]).is_absolute()
    assert aeb_stage["impl"]["path"].endswith("aeb.dll")


def test_every_port_carries_a_concrete_record_policy(tmp_path):
    """UT-SPC-06: a port with no explicit policy still gets a value
    ('full', the closed default) -- never absent from the spec."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path)
    cfg = load(paths)

    spec = emit_run_spec(cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir])

    for stage in spec.data["stages"]:
        for port in stage["ports"]:
            assert port["record"] in ("full", "excluded")  # a real closed value, never absent


def test_sources_ingest_and_absent_are_empty_and_sha256_is_carried(tmp_path):
    """UT-SPC-24 / IMP-0011 (scoped for WP-05, ingest itself is WP-12):
    ingest/absent emit as empty lists, never guessed; sha256 travels
    through from the probe pass unchanged."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path)
    cfg = load(paths)
    recording = (tmp_path / "rec.mcap").resolve()

    spec = emit_run_spec(
        cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir],
        sources=[SourceSpec(path=recording, sha256="the-real-hash")],
    )

    assert spec.data["sources"] == [
        {"path": str(recording), "sha256": "the-real-hash", "codec": "mcap", "ingest": [], "absent": []}
    ]


def test_a_relative_source_path_is_refused(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path)
    cfg = load(paths)

    with pytest.raises(InternalError):
        emit_run_spec(
            cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir],
            sources=[SourceSpec(path=Path("relative/rec.mcap"), sha256="x")],
        )


def test_mutations_are_built_from_overrides_using_resolve_address(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "aeb.dll").touch()
    (lib_dir / "bsd.dll").touch()
    paths = _project(tmp_path)
    cfg = load(paths)

    spec = emit_run_spec(
        cfg, run_id="r1", setup_values=_setup_values(), manifests=_manifests(), search=[lib_dir],
        overrides={"aeb": {"outputs.ttc_s": Override(verb=OverrideVerb.SCALE, value=1.1)}},
    )

    assert spec.data["mutations"] == [{
        "verb": "scale",
        "address": {"stage": "aeb", "port": "outputs", "path": ["ttc_s"], "index": None},
        "operands": [1.1], "window_ns": [0, None],
    }]


def test_unresolved_flags_a_leftover_reference_and_a_relative_path():
    spec = RunSpec(data={"stages": [{"impl": {"path": "self.something"}}]})
    findings = unresolved(spec)
    assert findings  # both the relative-path AND self.-reference checks should fire
    assert any("self." in f or "relative" in f for f in findings)


def test_unresolved_is_clean_for_a_well_formed_spec():
    spec = RunSpec(data={"stages": [{"impl": {"path": "C:/abs/x.dll"}}]})
    assert unresolved(spec) == []
