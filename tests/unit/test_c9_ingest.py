# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C9 recording-ingest tests: UT-C9-1, UT-C9-3, UT-C9-4, UT-C9-5, UT-C9-6
(docs/sim_implementation_plan.md). UT-C9-2 lives in `test_a4_legacy.py`
(`test_legacy_topic_names_map_correctly_and_manifest_is_unknown`) -- the
"named at load" half; this file does not duplicate it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.session.session import Session
from adas_sim.io.base import Provenance, TopicInfo
from adas_sim.ingest.map import AbsentPort, IngestMap, IngestRecordingReader, ProvidedPort, _parse_ingest_map

MODULES_ROOT = Path(__file__).resolve().parents[3]
DF_INGEST_MAP = MODULES_ROOT / "df" / "sim" / "ingest" / "carla_legacy.yaml"
DF_SIL_PORTS_YAML = MODULES_ROOT / "df" / "src" / "platform" / "df_sil" / "df_sil.ports.yaml"


# ---------------------------------------------------------------------------
# UT-C9-1 -- a legacy topic resolves to the manifest's own port name,
# asserted against df_sil.ports.yaml's real declared outputs (not a fixture)
# ---------------------------------------------------------------------------


def test_df_carla_legacy_map_resolves_to_df_sil_ports_yamls_real_output_names():
    if not DF_INGEST_MAP.exists() or not DF_SIL_PORTS_YAML.exists():
        pytest.skip("modules/df is absent (partial clone)")

    ingest_map = _parse_ingest_map(DF_INGEST_MAP)
    real_outputs = {p["name"] for p in yaml.safe_load(DF_SIL_PORTS_YAML.read_text(encoding="utf-8"))["outputs"]}

    by_topic = {p.topic: p for p in ingest_map.provides}
    assert by_topic["df/aeb_outputs"].manifest_port == "aeb.outputs"
    assert by_topic["df/bsd_outputs"].manifest_port == "bsd.outputs"
    assert by_topic["df/aeb_outputs"].manifest_port in real_outputs
    assert by_topic["df/bsd_outputs"].manifest_port in real_outputs


# ---------------------------------------------------------------------------
# UT-C9-3 -- a proto_type mismatch is reported naming both types, never
# coerced
# ---------------------------------------------------------------------------


def _manifest(*, component: str, outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs), project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub_pipeline(tmp_path: Path, *, stage_name: str, manifest: ComponentManifest) -> Pipeline:
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


def _session_with(*, provides: dict[str, ProvidedPort] = {}, absent: dict[str, AbsentPort] = {}) -> Session:
    return Session(run_id="test", name="test", ticks=(), provides=provides, absent=absent)


def test_feasible_cuts_reports_a_proto_type_mismatch_naming_both_types(tmp_path):
    manifest = _manifest(component="under_test", outputs=[PortSpec(name="objects", proto_type="adas.perception.DfObjList")])
    pipeline = _stub_pipeline(tmp_path, stage_name="under_test", manifest=manifest)
    session = _session_with(provides={
        "objects": ProvidedPort(
            topic="some/topic", port="source.objects", manifest_port="objects",
            proto_type="adas.perception.ObjectList", origin=Provenance.MEASURED, family="test.family",
        ),
    })

    results = session.feasible_cuts(pipeline)

    assert len(results) == 1
    assert results[0].feasible is False
    assert "adas.perception.ObjectList" in results[0].missing[0]
    assert "adas.perception.DfObjList" in results[0].missing[0]


# ---------------------------------------------------------------------------
# UT-C9-4 -- an ingest map containing anything beyond the closed vocabulary
# (port/proto_type/origin, reason) is an AuthoringError, not silently
# accepted
# ---------------------------------------------------------------------------


def _write_map(tmp_path: Path, body: dict, *, filename: str = "family.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def test_a_provides_entry_with_an_expression_key_is_refused(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family",
        "matches": {"any_topic": ["some/topic"]},
        "provides": {"source.x": {"from": ["some/topic"], "expr": "x * 2"}},
    })

    with pytest.raises(AuthoringError) as excinfo:
        _parse_ingest_map(path)
    assert "expr" in str(excinfo.value)


def test_an_absent_entry_with_an_extra_key_is_refused(tmp_path):
    path = _write_map(tmp_path, {
        "family": "test.family",
        "matches": {"any_topic": ["some/topic"]},
        "absent": {"source.veh_sig": {"reason": "never recorded", "unit_conversion": "m_to_ft"}},
    })

    with pytest.raises(AuthoringError) as excinfo:
        _parse_ingest_map(path)
    assert "unit_conversion" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-C9-5 -- a topic claimed by two loaded ingest maps raises, naming both
# families
# ---------------------------------------------------------------------------


class _FakeReader:
    """Just enough of `io.base.RecordingReader` for `IngestRecordingReader`."""

    def __init__(self, topics: dict[str, TopicInfo]) -> None:
        self.capabilities = None
        self._topics = topics

    def topics(self):
        return self._topics

    def messages(self, topics=None):
        return iter(())

    def meta(self):
        return None

    def close(self):
        pass


def test_a_topic_claimed_by_two_ingest_maps_raises_naming_both_families():
    topic_info = {"shared/topic": TopicInfo(schema_name="test.Schema", provenance=Provenance.MEASURED)}
    claim = ProvidedPort(
        topic="shared/topic", port="source.x", manifest_port="x",
        proto_type="test.Schema", origin=Provenance.MEASURED, family="family.a",
    )
    map_a = IngestMap(family="family.a", match_any_topic=frozenset({"shared/topic"}), provides=(claim,), absent=(), path=Path("a.yaml"))
    map_b = IngestMap(
        family="family.b", match_any_topic=frozenset({"shared/topic"}),
        provides=(ProvidedPort(
            topic="shared/topic", port="source.y", manifest_port="y",
            proto_type="test.Schema", origin=Provenance.MEASURED, family="family.b",
        ),),
        absent=(), path=Path("b.yaml"),
    )

    with pytest.raises(AuthoringError) as excinfo:
        IngestRecordingReader(_FakeReader(topic_info), [map_a, map_b])
    message = str(excinfo.value)
    assert "family.a" in message
    assert "family.b" in message


# ---------------------------------------------------------------------------
# UT-C9-6 -- feasible_cuts on a recording carrying only "objects" reports
# the one supported cut and, for each unsupported one, which port is missing
# ---------------------------------------------------------------------------


def test_feasible_cuts_reports_the_supported_stage_and_names_missing_ports_for_the_rest(tmp_path):
    objects_only = _manifest(component="objects_stage", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    needs_two = _manifest(
        component="needs_two",
        outputs=[
            PortSpec(name="objects", proto_type="test.Objects"),
            PortSpec(name="egoDyn", proto_type="test.VehDyn"),
        ],
    )
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({"name": "test", "stages": [
            {"name": "objects_stage", "mode": "simulate", "impl": "stub:objects_stage", "inputs": {}},
            {"name": "needs_two", "mode": "simulate", "impl": "stub:needs_two", "inputs": {}},
        ]}, sort_keys=False),
        encoding="utf-8",
    )
    components = {}
    for name, manifest in (("objects_stage", objects_only), ("needs_two", needs_two)):
        component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
        component.init()
        components[name] = component
    pipeline = Pipeline.load(path, components=components)

    session = _session_with(
        provides={"objects": ProvidedPort(
            topic="df/gen_object_list", port="source.gen_object_list", manifest_port="objects",
            proto_type="test.Objects", origin=Provenance.MEASURED, family="test.family",
        )},
        absent={"egoDyn": AbsentPort(port="egoDyn", reason="never recorded by this family", family="test.family")},
    )

    results = {r.stage: r for r in session.feasible_cuts(pipeline)}

    assert results["objects_stage"].feasible is True
    assert results["objects_stage"].missing == ()
    assert results["needs_two"].feasible is False
    assert any("egoDyn" in m and "never recorded by this family" in m for m in results["needs_two"].missing)
