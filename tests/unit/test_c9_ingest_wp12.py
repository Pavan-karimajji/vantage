# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-12` `SI-12` ingest tests: `UT-ING-01` .. `UT-ING-14`
(`docs/v2/SIM_Software_Test_Spec_v0.1.md` §5.12). `test_c9_ingest.py`
covers the pre-`WP-12` `UT-C9-*` surface (parser, absent, double-claim,
feasible-cuts) and is not duplicated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.ingest.description import Description, Tier, resolve_descriptions, TIER_ORDER
from adas_sim.ingest.family import check_no_double_claim, match_family
from adas_sim.ingest.header import HeaderBinding, Rung, rung_for
from adas_sim.ingest.identity import SourceIdentity, resolve_identity
from adas_sim.ingest.map import IngestMap, ProvidedPort, _parse_ingest_map
from adas_sim.ingest.static import resolve_static
from adas_sim.ingest.units import factor_offset, resolve_unit
from adas_sim.io.base import Provenance


def _write_map(tmp_path: Path, body: dict, *, filename: str = "family.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# UT-ING-01 -- onboard a family; one parser (SW-0187)
# ---------------------------------------------------------------------------


def test_onboarding_a_family_needs_only_one_yaml_and_the_one_parser(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["some/topic"]},
        "provides": {"source.x": {"from": ["some/topic"], "proto_type": "test.Schema"}},
    })
    ingest_map = _parse_ingest_map(path)
    assert ingest_map.family == "test.family"
    assert ingest_map.provides[0].port == "source.x"


# ---------------------------------------------------------------------------
# UT-ING-02 -- every SignalBinding field declared and read back
# ---------------------------------------------------------------------------


def test_every_signal_binding_field_is_declared_and_read_back(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["ARS540.Obj"]},
        "provides": {"fusion.objects": {
            "from": ["ARS540.Obj"], "proto_type": "adas.perception.DfObjList", "origin": "measured",
            "unit": "km_h", "shape": [8],
            "header": {"t_source": "fusion.t_source", "counter": "fusion.counter", "status": "fusion.status"},
        }},
    })
    ingest_map = _parse_ingest_map(path)
    provided = ingest_map.provides[0]
    assert provided.proto_type == "adas.perception.DfObjList"
    assert provided.origin is Provenance.MEASURED
    assert provided.shape == (8,)
    assert provided.factor == pytest.approx(1.0 / 3.6)
    assert provided.offset == 0.0
    assert provided.header == HeaderBinding(
        t_source="fusion.t_source", counter="fusion.counter", status="fusion.status",
    )


def test_a_map_declaring_no_unit_keeps_the_identity_conversion(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["t"]},
        "provides": {"source.x": {"from": ["t"], "proto_type": "test.Schema"}},
    })
    provided = _parse_ingest_map(path).provides[0]
    assert (provided.factor, provided.offset) == (1.0, 0.0)
    assert provided.header is None


# ---------------------------------------------------------------------------
# UT-ING-03 -- bind the three header channels; omit them, read the rung
# ---------------------------------------------------------------------------


def test_rung_is_header_counter_when_counter_is_bound():
    assert rung_for(HeaderBinding(counter="c")) is Rung.HEADER_COUNTER


def test_rung_is_source_time_when_only_t_source_is_bound():
    assert rung_for(HeaderBinding(t_source="t")) is Rung.SOURCE_TIME


def test_rung_is_reception_time_when_no_header_binding_is_declared():
    assert rung_for(None) is Rung.RECEPTION_TIME
    assert rung_for(HeaderBinding()) is Rung.RECEPTION_TIME


# ---------------------------------------------------------------------------
# UT-ING-04 -- absent: port with a reason, read at load
# (double-claim / feasible-cut halves already covered by test_c9_ingest.py)
# ---------------------------------------------------------------------------


def test_absent_port_reason_is_read_at_load(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["t"]},
        "absent": {"egoDyn": {"reason": "never recorded by this rig"}},
    })
    ingest_map = _parse_ingest_map(path)
    assert ingest_map.absent[0].port == "egoDyn"
    assert ingest_map.absent[0].reason == "never recorded by this rig"


# ---------------------------------------------------------------------------
# UT-ING-05 -- two files matching different maps by declared rule
# ---------------------------------------------------------------------------


def _map(family: str, *, path_glob: str | None = None) -> IngestMap:
    return IngestMap(
        family=family, match_any_topic=frozenset(), provides=(), absent=(),
        path=Path(f"{family}.yaml"), path_glob=path_glob,
    )


def test_two_files_match_different_maps_by_path_glob():
    map_a = _map("family.a", path_glob="carla_*.mcap")
    map_b = _map("family.b", path_glob="ars540_*.mcap")

    assert match_family(Path("carla_run_001.mcap"), [map_a, map_b]) == (map_a,)
    assert match_family(Path("ars540_bench_003.mcap"), [map_a, map_b]) == (map_b,)


def test_match_family_by_embedded_identity_when_no_glob_fires():
    map_a = _map("family.a")
    identity = SourceIdentity(family="family.a", model="m", name="n", instance=0)
    assert match_family(Path("unrelated_name.mcap"), [map_a], identity=identity) == (map_a,)


# ---------------------------------------------------------------------------
# UT-ING-06 -- two applicable maps claim one port
# ---------------------------------------------------------------------------


def test_check_no_double_claim_raises_naming_both_families_and_the_topic():
    claim_a = ProvidedPort(
        topic="shared/topic", port="source.x", manifest_port="x",
        proto_type="test.Schema", origin=Provenance.MEASURED, family="family.a",
    )
    claim_b = ProvidedPort(
        topic="shared/topic", port="source.y", manifest_port="y",
        proto_type="test.Schema", origin=Provenance.MEASURED, family="family.b",
    )
    with pytest.raises(AuthoringError) as excinfo:
        check_no_double_claim({"shared/topic": [claim_a, claim_b]}, where="test")
    message = str(excinfo.value)
    assert "family.a" in message and "family.b" in message and "shared/topic" in message


def test_check_no_double_claim_is_silent_for_a_single_claimant():
    claim = ProvidedPort(
        topic="t", port="source.x", manifest_port="x",
        proto_type="test.Schema", origin=Provenance.MEASURED, family="family.a",
    )
    check_no_double_claim({"t": [claim]}, where="test")  # must not raise


# ---------------------------------------------------------------------------
# UT-ING-07 -- each unit from the closed table; then a unit outside it
# ---------------------------------------------------------------------------


def test_each_closed_unit_resolves_a_real_factor_and_offset():
    assert factor_offset("m", where="test") == (1.0, 0.0)
    assert factor_offset("km", where="test") == (1000.0, 0.0)
    factor, offset = factor_offset("celsius", where="test")
    assert offset == pytest.approx(273.15)
    assert factor == pytest.approx(1.0)


def test_a_unit_outside_the_closed_table_is_refused():
    with pytest.raises(AuthoringError) as excinfo:
        resolve_unit("furlongs_per_fortnight", where="test")
    assert "furlongs_per_fortnight" in str(excinfo.value)


def test_a_provides_entry_naming_an_unknown_unit_is_refused_at_parse(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["t"]},
        "provides": {"source.x": {"from": ["t"], "unit": "smoots"}},
    })
    with pytest.raises(AuthoringError) as excinfo:
        _parse_ingest_map(path)
    assert "smoots" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-ING-08 -- no callable/lambda/eval anywhere in the module; output is
# data only (also the narrower half of ANL-SW-36, exercised structurally)
# ---------------------------------------------------------------------------


def test_parsed_ingest_map_is_plain_data_with_no_callables(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["t"]},
        "provides": {"source.x": {"from": ["t"]}},
    })
    ingest_map = _parse_ingest_map(path)
    for provided in ingest_map.provides:
        for value in (provided.topic, provided.port, provided.proto_type, provided.family):
            assert isinstance(value, str)
        assert not callable(provided.factor) and not callable(provided.offset)


# ---------------------------------------------------------------------------
# UT-ING-09 -- two sources of one family/model, different instances; then
# an incomplete identity
# ---------------------------------------------------------------------------


def test_two_instances_of_one_family_and_model_are_distinguished_by_instance():
    a = resolve_identity({"family": "df", "model": "ars540", "name": "front", "instance": 0}, where="a")
    b = resolve_identity({"family": "df", "model": "ars540", "name": "front", "instance": 1}, where="b")
    assert a != b
    assert a.instance == 0 and b.instance == 1


def test_an_incomplete_identity_is_reported_not_guessed():
    with pytest.raises(AuthoringError) as excinfo:
        resolve_identity({"family": "df", "model": "ars540", "name": "front"}, where="test")
    assert "instance" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-ING-10 -- resolve descriptions with each tier available in turn
# ---------------------------------------------------------------------------


def test_resolve_descriptions_prefers_embedded_over_configured_over_convention():
    identity = SourceIdentity(family="df", model="ars540", name="front", instance=0)
    embedded = Description(type="ars540_can_dbc", version="1.0", path=Path("e.dbc"), tier=Tier.EMBEDDED)
    configured = Description(type="ars540_can_dbc", version="1.1", path=Path("c.dbc"), tier=Tier.CONFIGURED)
    convention = Description(type="ars540_can_dbc", version="1.0", path=Path("v.dbc"), tier=Tier.CONVENTION)

    assert resolve_descriptions(identity, [convention, configured, embedded])[0].tier is Tier.EMBEDDED
    assert resolve_descriptions(identity, [convention, configured])[0].tier is Tier.CONFIGURED
    assert resolve_descriptions(identity, [convention])[0].tier is Tier.CONVENTION
    assert TIER_ORDER == (Tier.EMBEDDED, Tier.CONFIGURED, Tier.CONVENTION)


# ---------------------------------------------------------------------------
# UT-ING-11 -- a description version inside, then outside, its accepted set
# ---------------------------------------------------------------------------


def test_a_description_version_inside_its_accepted_set_resolves():
    identity = SourceIdentity(family="df", model="ars540", name="front", instance=0)
    good = Description(type="ars540_can_dbc", version="1.1", path=Path("d.dbc"), tier=Tier.EMBEDDED)
    assert resolve_descriptions(identity, [good]) == (good,)


def test_a_description_version_outside_its_accepted_set_is_refused():
    identity = SourceIdentity(family="df", model="ars540", name="front", instance=0)
    bad = Description(type="ars540_can_dbc", version="9.9", path=Path("d.dbc"), tier=Tier.EMBEDDED)
    with pytest.raises(AuthoringError) as excinfo:
        resolve_descriptions(identity, [bad])
    assert "9.9" in str(excinfo.value) and "ars540_can_dbc" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-ING-12 -- static data present in the recording, then absent from it
# ---------------------------------------------------------------------------


def test_static_data_present_in_the_recording_wins_over_a_sidecar(tmp_path):
    sidecar_dir = tmp_path
    (sidecar_dir / "calib.bin").write_bytes(b"sidecar bytes")
    payload, origin = resolve_static(
        "calib", recording_static={"calib": b"recording bytes"}, static_dir=sidecar_dir,
        naming_convention="{port}.bin",
    )
    assert (payload, origin) == (b"recording bytes", "recording")


def test_static_data_absent_from_the_recording_falls_back_to_the_sidecar(tmp_path):
    sidecar_dir = tmp_path
    (sidecar_dir / "calib.bin").write_bytes(b"sidecar bytes")
    payload, origin = resolve_static("calib", recording_static={}, static_dir=sidecar_dir, naming_convention="{port}.bin")
    assert payload == b"sidecar bytes"
    assert origin.startswith("sidecar:")


def test_static_data_absent_from_both_is_an_authoring_error_naming_both(tmp_path):
    with pytest.raises(AuthoringError) as excinfo:
        resolve_static("calib", recording_static={}, static_dir=tmp_path, naming_convention="{port}.bin")
    message = str(excinfo.value)
    assert "calib" in message


# ---------------------------------------------------------------------------
# UT-ING-13 -- record a decision about a recording; the recording's bytes
# and mtime are unchanged before and after (read-only, IMP-0200)
# ---------------------------------------------------------------------------


def test_resolving_static_data_never_writes_the_sidecar_file(tmp_path):
    sidecar_dir = tmp_path
    sidecar = sidecar_dir / "calib.bin"
    sidecar.write_bytes(b"original")
    before = (sidecar.read_bytes(), sidecar.stat().st_mtime_ns)

    resolve_static("calib", recording_static={}, static_dir=sidecar_dir, naming_convention="{port}.bin")

    after = (sidecar.read_bytes(), sidecar.stat().st_mtime_ns)
    assert before == after


def test_parsing_an_ingest_map_never_writes_the_map_file(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["t"]},
        "provides": {"source.x": {"from": ["t"]}},
    })
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    _parse_ingest_map(path)
    after = (path.read_bytes(), path.stat().st_mtime_ns)
    assert before == after


# ---------------------------------------------------------------------------
# UT-ING-14 -- precedence is a module constant; a sidecar at each tier
# still resolves in TIER_ORDER
# ---------------------------------------------------------------------------


def test_tier_order_is_a_printable_module_constant_not_discovered():
    assert isinstance(TIER_ORDER, tuple)
    assert [t.value for t in TIER_ORDER] == ["embedded", "configured", "convention"]


def test_a_sidecar_at_each_tier_still_resolves_in_declared_precedence_order():
    identity = SourceIdentity(family="df", model="ars540", name="front", instance=0)
    candidates = [
        Description(type="carla_object_list", version="0.9", path=Path(f"{tier.value}.json"), tier=tier)
        for tier in (Tier.CONVENTION, Tier.CONFIGURED, Tier.EMBEDDED)  # deliberately out of order
    ]
    resolved = resolve_descriptions(identity, candidates)
    assert resolved[0].tier is Tier.EMBEDDED
