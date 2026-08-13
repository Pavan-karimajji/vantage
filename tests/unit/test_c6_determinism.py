# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-C6 (`R-SIM-24`) unit tests: axis derivation (`ST-C6-3`, `ST-C6-6`) and
the two comparison halves (`ST-C6-2`, `ST-C6-4`)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from google.protobuf import descriptor_pb2, wrappers_pb2

from adas_sim.diagnostics.determinism import compare_exact, compare_with_tolerance, derive_axis
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.diagnostics.tolerance import ToleranceRow, ToleranceSet, load_tolerance
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo


def _manifest(*, host="h1", nonce="n1", library_sha="lib1", build_id="b1", bundle_sha="cfg1") -> RunManifest:
    return RunManifest(
        manifest_version=2, host=host, process_nonce=nonce,
        components=(ComponentBuildInfo(name="df", library_sha256=library_sha, build_id=build_id, config_bundle_sha256=bundle_sha),),
    )


# ---------------------------------------------------------------------------
# ST-C6-3 -- axis derivation, all four.
# ---------------------------------------------------------------------------


def test_same_process_when_nonce_matches_and_nothing_else_differs():
    a = _manifest(nonce="shared")
    b = _manifest(nonce="shared")
    result = derive_axis(a, b)
    assert result.axis == "same_process"
    assert result.differing_dimensions == ()


def test_fresh_process_when_nonce_differs_but_everything_else_agrees():
    a = _manifest(nonce="n1")
    b = _manifest(nonce="n2")
    result = derive_axis(a, b)
    assert result.axis == "fresh_process"


def test_rebuilt_binary_when_only_library_sha_differs():
    a = _manifest(nonce="n1", library_sha="libA")
    b = _manifest(nonce="n2", library_sha="libB")
    result = derive_axis(a, b)
    assert result.axis == "rebuilt_binary"
    assert result.differing_dimensions == ("library_sha256:df",)


def test_different_machine_when_only_host_differs():
    a = _manifest(nonce="n1", host="machine-a")
    b = _manifest(nonce="n2", host="machine-b")
    result = derive_axis(a, b)
    assert result.axis == "different_machine"


# ---------------------------------------------------------------------------
# ST-C6-6 -- two dimensions differing is evidence for neither, both named.
# ---------------------------------------------------------------------------


def test_two_differing_dimensions_is_evidence_for_neither_axis_naming_both():
    a = _manifest(nonce="n1", host="machine-a", library_sha="libA")
    b = _manifest(nonce="n2", host="machine-b", library_sha="libB")
    result = derive_axis(a, b)
    assert result.axis is None
    assert set(result.differing_dimensions) == {"host", "library_sha256:df"}


def test_same_process_nonce_but_something_else_differs_is_also_neither():
    """A same-process claim (matching nonce) with a real difference anyway
    is itself a finding, not a confirmation."""
    a = _manifest(nonce="shared", library_sha="libA")
    b = _manifest(nonce="shared", library_sha="libB")
    result = derive_axis(a, b)
    assert result.axis is None
    assert result.differing_dimensions == ("library_sha256:df",)


# ---------------------------------------------------------------------------
# ST-C6-2/ST-C6-4 -- the two comparisons.
# ---------------------------------------------------------------------------


class _FakeReader:
    def __init__(self, topics: dict[str, TopicInfo], messages: list[tuple[str, int, int | None, bytes]]) -> None:
        self._topics = topics
        self._messages = messages

    def meta(self) -> RunManifest:
        return RunManifest()

    def topics(self) -> dict[str, TopicInfo]:
        return self._topics

    def messages(self, topics=None):
        for m in self._messages:
            if topics is None or m[0] in topics:
                yield m

    def close(self) -> None:
        pass


def test_compare_exact_passes_on_identical_payloads():
    topics = {"a": TopicInfo(schema_name="a", provenance=Provenance.SIMULATED)}
    reader_a = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"y")])
    reader_b = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"y")])
    assert compare_exact(reader_a, reader_b) is None


def test_compare_exact_fails_naming_the_first_diverging_tick_and_topic():
    topics = {"a": TopicInfo(schema_name="a", provenance=Provenance.SIMULATED)}
    reader_a = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"y")])
    reader_b = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"DIFFERENT")])

    divergence = compare_exact(reader_a, reader_b)
    assert divergence is not None
    assert divergence.tick_index == 1
    assert divergence.topic == "a"


def _double_value_schema() -> tuple[bytes, str]:
    fd_proto = descriptor_pb2.FileDescriptorProto()
    wrappers_pb2.DoubleValue.DESCRIPTOR.file.CopyToProto(fd_proto)
    fds = descriptor_pb2.FileDescriptorSet()
    fds.file.append(fd_proto)
    return fds.SerializeToString(), "google.protobuf.DoubleValue"


def test_compare_with_tolerance_passes_within_bound_and_reports_headroom():
    schema_bytes, schema_name = _double_value_schema()
    topics = {"a": TopicInfo(schema_name=schema_name, provenance=Provenance.SIMULATED, schema_bytes=schema_bytes)}
    a_payload = wrappers_pb2.DoubleValue(value=1.0).SerializeToString()
    b_payload = wrappers_pb2.DoubleValue(value=1.02).SerializeToString()
    reader_a = _FakeReader(topics, [("a", 0, 0, a_payload)])
    reader_b = _FakeReader(topics, [("a", 0, 0, b_payload)])

    tolerance = ToleranceSet(component="fixture", rows=(ToleranceRow(field="value", abs_tol=0.05, why="test"),), sha256="")
    divergences, headroom = compare_with_tolerance(reader_a, reader_b, tolerance)
    assert divergences == []
    assert 0.3 < headroom < 0.5  # 0.02 / 0.05 = 0.4


def test_compare_with_tolerance_fails_outside_bound_naming_the_field():
    schema_bytes, schema_name = _double_value_schema()
    topics = {"a": TopicInfo(schema_name=schema_name, provenance=Provenance.SIMULATED, schema_bytes=schema_bytes)}
    a_payload = wrappers_pb2.DoubleValue(value=1.0).SerializeToString()
    b_payload = wrappers_pb2.DoubleValue(value=2.0).SerializeToString()
    reader_a = _FakeReader(topics, [("a", 0, 0, a_payload)])
    reader_b = _FakeReader(topics, [("a", 0, 0, b_payload)])

    divergences, _headroom = compare_with_tolerance(reader_a, reader_b, ToleranceSet(component="fixture", rows=(), sha256=""))
    assert len(divergences) == 1
    assert divergences[0].field == "value"


# ---------------------------------------------------------------------------
# Tolerance loading: default: exact, mandatory why:, no negative bounds.
# ---------------------------------------------------------------------------


def test_missing_tolerance_file_is_default_exact(tmp_path):
    tolerance = load_tolerance(tmp_path / "does_not_exist.yaml", component="df")
    assert tolerance.rows == ()
    assert tolerance.sha256 == ""


def test_row_without_why_is_an_authoring_error(tmp_path):
    path = tmp_path / "tolerance.yaml"
    path.write_text(yaml.safe_dump({"fields": {"ttc_s": {"abs_tol": 0.01}}}), encoding="utf-8")
    with pytest.raises(AuthoringError) as excinfo:
        load_tolerance(path, component="df")
    assert "why" in str(excinfo.value)


def test_row_with_negative_bound_is_an_authoring_error(tmp_path):
    path = tmp_path / "tolerance.yaml"
    path.write_text(yaml.safe_dump({"fields": {"ttc_s": {"abs_tol": -1.0, "why": "test"}}}), encoding="utf-8")
    with pytest.raises(AuthoringError):
        load_tolerance(path, component="df")


def test_valid_tolerance_file_loads_and_hashes(tmp_path):
    path = tmp_path / "tolerance.yaml"
    path.write_text(yaml.safe_dump({"fields": {"ttc_s": {"abs_tol": 0.01, "why": "float FP contraction"}}}), encoding="utf-8")
    tolerance = load_tolerance(path, component="df")
    assert tolerance.bound_for("ttc_s").abs_tol == 0.01
    assert len(tolerance.sha256) == 64
    assert tolerance.bound_for("unrelated_field") is None
