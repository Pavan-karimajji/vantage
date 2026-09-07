# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-01` tests: `UT-mapschema-01`..`UT-mapschema-03`,
`UT-resolver-01`..`UT-resolver-04`, `UT-manifest-01`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.1/5.2/5.4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.ingest.map import _parse_ingest_map
from adas_sim.ingest.resolve import Absent, Resolution, Unresolved, resolve_port
from adas_sim.io.base import Provenance, TopicInfo
from adas_sim.runspec.manifest import _port_records


def _write_map(tmp_path: Path, body: dict, *, filename: str = "family.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 5.1 mapschema
# ---------------------------------------------------------------------------


def test_port_key_with_an_ordered_list_parses_ut_mapschema_01(tmp_path):
    """UT-mapschema-01."""
    port_keyed = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["topic.a", "topic.b"]},
        "provides": {"source.x": {"from": ["topic.a", "topic.b"]}},
    }, filename="port_keyed.yaml")

    ingest_map = _parse_ingest_map(port_keyed)
    assert ingest_map.provides[0].port == "source.x"
    assert ingest_map.provides[0].candidates == ("topic.a", "topic.b")  # .c1: order preserved

    topic_keyed = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["topic.a"]},
        "provides": {"topic.a": {"port": "source.x"}},
    }, filename="topic_keyed.yaml")
    with pytest.raises(AuthoringError):  # .c2: the old shape is rejected
        _parse_ingest_map(topic_keyed)


def test_a_bad_field_is_named_ut_mapschema_02(tmp_path):
    """UT-mapschema-02."""
    path = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["topic.a"]},
        "provides": {"source.x": {"from": ["topic.a"], "expr": "x * 2"}},
    })

    with pytest.raises(AuthoringError) as excinfo:
        _parse_ingest_map(path)
    message = str(excinfo.value)
    assert "source.x" in message and "expr" in message  # .c1


def test_declared_holes_coexist_with_provided_ports_ut_mapschema_03(tmp_path):
    """UT-mapschema-03."""
    mixed = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["topic.a"]},
        "provides": {"source.x": {"from": ["topic.a"]}},
        "absent": {"source.y": {"reason": "never recorded by this family"}},
    }, filename="mixed.yaml")
    ingest_map = _parse_ingest_map(mixed)  # .c1: mixed document parses
    assert ingest_map.provides[0].port == "source.x"
    assert ingest_map.absent[0].port == "source.y"

    bad_absent = _write_map(tmp_path, {
        "family": "test.family", "matches": {"any_topic": ["topic.a"]},
        "absent": {"source.y": {"reason": "never recorded", "from": ["topic.a"]}},
    }, filename="bad_absent.yaml")
    with pytest.raises(AuthoringError):  # .c2: an absent entry carrying an address is rejected
        _parse_ingest_map(bad_absent)


# ---------------------------------------------------------------------------
# 5.2 resolver
# ---------------------------------------------------------------------------


def _index(*topics: str) -> dict[str, TopicInfo]:
    return {t: TopicInfo(schema_name="test.Schema", provenance=Provenance.MEASURED) for t in topics}


def test_first_present_candidate_wins_ut_resolver_01():
    """UT-resolver-01."""
    both_present = _index("topic.first", "topic.second")
    result = resolve_port("source.x", ("topic.first", "topic.second"), both_present)
    assert result.chosen == "topic.first"  # .c1

    only_second = _index("topic.second")
    result = resolve_port("source.x", ("topic.first", "topic.second"), only_second)
    assert result.chosen == "topic.second"  # .c2


def test_the_choice_is_retained_per_port_ut_resolver_02():
    """UT-resolver-02."""
    index = _index("topic.a")
    resolved = resolve_port("port.resolved", ("topic.a",), index)
    unresolved = resolve_port("port.unresolved", ("topic.missing",), index)

    assert resolved.chosen == "topic.a"  # .c1: one chosen address
    assert unresolved.chosen is None  # .c2: none


def test_a_type_mismatch_is_skipped_not_coerced_ut_resolver_03():
    """UT-resolver-03."""
    index = {
        "topic.wrong": TopicInfo(schema_name="test.Wrong", provenance=Provenance.MEASURED),
        "topic.right": TopicInfo(schema_name="test.Right", provenance=Provenance.MEASURED),
    }
    result = resolve_port("source.x", ("topic.wrong", "topic.right"), index, proto_type="test.Right")
    assert result.chosen == "topic.right"  # .c1
    # .c2: no conversion path exists -- the chosen value is exactly the candidate name
    assert result.chosen == "topic.right"


def test_unresolved_and_absent_are_different_results_ut_resolver_04():
    """UT-resolver-04."""
    resolution = resolve_port("source.unresolved", ("topic.missing",), {})
    unresolved = Unresolved(port=resolution.port)
    absent = Absent(port="source.absent", reason="never recorded by this family")

    assert type(unresolved) is not type(absent)  # .c1
    assert resolution.chosen is None and unresolved.port == "source.unresolved"  # .c2: neither an empty success
    assert absent.reason  # carries a real reason, not an empty value


# ---------------------------------------------------------------------------
# 5.4 manifest
# ---------------------------------------------------------------------------


def test_chosen_addresses_are_written_ut_manifest_01():
    """UT-manifest-01."""
    resolutions = (
        Resolution(port="source.resolved.a", chosen="topic.a"),
        Resolution(port="source.resolved.b", chosen="topic.b"),
        Resolution(port="source.unresolved", chosen=None),
    )

    records = _port_records(resolutions)

    by_port = {r.port: r.matched_address for r in records}
    assert by_port["source.resolved.a"] == "topic.a"  # .c1: every resolved port, once, with its address
    assert by_port["source.resolved.b"] == "topic.b"
    assert len(records) == 3
    assert by_port["source.unresolved"] is None  # .c2: unresolved ports appear with none
