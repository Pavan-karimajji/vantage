# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`WP-01` (`IMP-0051`): the run setup writer emits schema
`adas.sim.runspec/2.0` -- `trigger`, `clock_period_ns`, `previous_cycle`,
`bulk`, `buffer_depth`, `outputs.livemeas`, `readiness_limit_steps`,
`fallback_max_gap` -- writes none of `grid`, `order`, `delay_steps`,
`sampling`, `on_missing`, and refuses, naming the key, a `⊘` value nobody
supplied. These are unit tests of the writer; `SYT-RUN-02`, `-03`, `-04`,
`-06`, `-09` and `SYT-ORC-02`, `-03` are system tests built in `WP-09`."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest

from adas_sim.config import load
from adas_sim.config.paths import ConfigPaths
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.resolve.component import ComponentManifest, PortSpec
from adas_sim.runspec.canon import RunSpec, canonical
from adas_sim.runspec.emit import (
    RUN_SPEC_SCHEMA,
    LiveMeasSpec,
    RunSetupValues,
    emit_run_spec,
    validate_run_spec,
)

_RETIRED_TOP_LEVEL = ("grid", "order", "grid_step_ns", "diagnostics", "coherence", "reference_build_sha256")


def _manifest(name: str, *, period_ns: int = 0, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=name, version="1.0", abi_version=1, build_id="x", inputs=inputs, outputs=outputs,
        project="base", config_bundle_sha256="deadbeef", descriptor_set=b"", period_ns=period_ns,
    )


def _emit(tmp_path: Path, values: RunSetupValues, **kwargs) -> RunSpec:
    comp_dir = tmp_path / "composition"
    comp_dir.mkdir()
    (comp_dir / "package.yaml").write_text(
        "version: 1\nunits:\n"
        "  - name: meas\n    impl: dll:meas\n    ports: [outputs]\n"
        "  - name: sut\n    impl: dll:sut\n    ports: [outputs]\n",
        encoding="utf-8",
    )
    conn_dir = tmp_path / "connections"
    conn_dir.mkdir()
    (conn_dir / "package.yaml").write_text(
        "version: 1\nname: demo\nwiring:\n  - stage: sut\n    port: objects\n    from: meas.objects\n",
        encoding="utf-8",
    )
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "meas.dll").touch()
    (lib_dir / "sut.dll").touch()
    manifests = {
        "meas": _manifest("meas", outputs=(PortSpec(name="objects", proto_type="test.Echo"),)),
        "sut": _manifest(
            "sut", period_ns=20_000_000, inputs=(PortSpec(name="objects", proto_type="test.Echo"),),
            outputs=(PortSpec(name="outputs", proto_type="test.Echo"),),
        ),
    }
    return emit_run_spec(
        load(ConfigPaths(project_root=tmp_path)), run_id="r1", manifests=manifests, search=[lib_dir],
        setup_values=values, modes={"meas": "measured"}, **kwargs,
    )


def _values(**overrides) -> RunSetupValues:
    fields = dict(
        readiness_limit_steps=12, fallback_max_gap=3, trigger={"sut": "control"},
        buffer_depth={"*": 16, "sut.outputs": 32},
    )
    fields.update(overrides)
    return RunSetupValues(**fields)


def test_the_setup_carries_schema_2_0_and_validates_against_the_published_schema(tmp_path):
    spec = _emit(tmp_path, _values())
    assert RUN_SPEC_SCHEMA == "adas.sim.runspec/2.0"
    assert spec.data["schema"] == "adas.sim.runspec/2.0"
    validate_run_spec(spec)  # does not raise


def test_the_new_keys_are_written_from_the_setup_values(tmp_path):
    spec = _emit(
        tmp_path,
        _values(
            previous_cycle=frozenset({"sut.objects"}), bulk=frozenset({"meas.objects"}),
            livemeas=LiveMeasSpec("lm", 64, 4096, 4, 65536),
        ),
    )
    assert spec.data["readiness_limit_steps"] == 12
    assert spec.data["fallback_max_gap"] == 3
    assert spec.data["outputs"]["livemeas"] == {
        "name": "lm", "cycle_slot_count": 64, "cycle_slot_size": 4096, "bulk_slot_count": 4, "bulk_slot_size": 65536,
    }
    meas, sut = spec.data["stages"]
    assert meas["trigger"] == "" and sut["trigger"] == "control"  # a measured stage is never run
    assert meas["clock_period_ns"] == 0 and sut["clock_period_ns"] == 20_000_000
    assert sut["inputs"] == [
        {"port": "objects", "producer": "meas", "producer_port": "objects", "previous_cycle": True}
    ]
    ports = {(stage["name"], port["name"]): port for stage in spec.data["stages"] for port in stage["ports"]}
    assert ports[("meas", "objects")]["bulk"] is True and ports[("sut", "outputs")]["bulk"] is False
    assert ports[("meas", "objects")]["buffer_depth"] == 16  # the "*" entry
    assert ports[("sut", "outputs")]["buffer_depth"] == 32  # an exact entry wins


def test_no_live_measurement_means_no_livemeas_key(tmp_path):
    spec = _emit(tmp_path, _values(livemeas=None))
    assert "livemeas" not in spec.data["outputs"]


def test_none_of_the_retired_keys_is_written(tmp_path):
    spec = _emit(tmp_path, _values())
    text = canonical(spec)
    for key in _RETIRED_TOP_LEVEL:
        assert key not in spec.data, key
    for stage in spec.data["stages"]:
        assert "period_ns" not in stage
        for port in stage["ports"]:
            assert "sampling" not in port and "on_missing" not in port
        for edge in stage["inputs"]:
            assert "delay_steps" not in edge
    assert '"sampling"' not in text and '"on_missing"' not in text and '"delay_steps"' not in text


@pytest.mark.parametrize("key", ["readiness_limit_steps", "fallback_max_gap"])
def test_a_missing_integer_value_is_refused_naming_the_key(tmp_path, key):
    with pytest.raises(AuthoringError) as raised:
        _emit(tmp_path, _values(**{key: None}))
    assert key in str(raised.value)


def test_a_port_with_no_buffer_depth_is_refused_naming_the_stage_and_the_port(tmp_path):
    with pytest.raises(AuthoringError) as raised:
        _emit(tmp_path, _values(buffer_depth={"meas.objects": 8}))
    assert "buffer_depth" in str(raised.value)
    assert "sut" in str(raised.value)


def test_a_simulated_stage_with_no_trigger_is_refused_naming_the_stage(tmp_path):
    with pytest.raises(AuthoringError) as raised:
        _emit(tmp_path, _values(trigger={}))
    assert "sut" in str(raised.value) and "trigger" in str(raised.value)


def test_a_live_measurement_geometry_value_that_is_not_an_integer_is_refused_naming_the_key(tmp_path):
    with pytest.raises(AuthoringError) as raised:
        _emit(tmp_path, _values(livemeas=LiveMeasSpec("lm", 64, None, 4, 65536)))  # type: ignore[arg-type]
    assert "cycle_slot_size" in str(raised.value)


def test_the_published_schema_refuses_a_retired_or_unknown_key():
    spec = _emit_for_schema_check()
    for key in ("grid", "order", "diagnostics"):
        bad = RunSpec(data={**spec.data, key: {}})
        with pytest.raises(jsonschema.ValidationError):
            validate_run_spec(bad)
    stage = dict(spec.data["stages"][0], colour="red")
    with pytest.raises(jsonschema.ValidationError):
        validate_run_spec(RunSpec(data={**spec.data, "stages": [stage]}))
    port_with_sampling = dict(spec.data["stages"][0]["ports"][0], sampling="strict")
    stage_with_port = dict(spec.data["stages"][0], ports=[port_with_sampling])
    with pytest.raises(jsonschema.ValidationError):
        validate_run_spec(RunSpec(data={**spec.data, "stages": [stage_with_port]}))


def _emit_for_schema_check() -> RunSpec:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        return _emit(Path(tmp), _values())
