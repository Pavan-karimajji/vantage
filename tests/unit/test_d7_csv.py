# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `io/csv.py` tests: `UT-D7-1`..`UT-D7-5` (docs/sim_implementation_plan.md).
`UT-D7-6` (`sim convert` round-trip) lives in `test_d7_convert.py` -- a
different module under test."""

from __future__ import annotations

import csv as _csv
import io as _io
from pathlib import Path

import pytest
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.io.csv import CsvWriter
from adas_sim.plugins.registry import reader_for
import adas_sim.io.csv  # noqa: F401 -- registers the ".csv" codec (write-only)

_DT_NS = 50_000_000


def _outer_message_cls(unique: str):
    """A tiny dynamic schema: `Outer { x: int32, sub: Inner{y: float},
    tags: repeated string }` -- built the same way `core/runner.decode_message`
    builds a real message at run time (`R-SIM-11`), so these tests exercise
    the real decode path, not a stand-in."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = f"{unique}.proto"
    fdp.package = f"adas_sim.test.{unique}"
    fdp.syntax = "proto3"
    inner = fdp.message_type.add()
    inner.name = "Inner"
    f = inner.field.add()
    f.name, f.number, f.type = "y", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL
    outer = fdp.message_type.add()
    outer.name = "Outer"
    f = outer.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_INT32
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL
    f = outer.field.add()
    f.name, f.number, f.type = "sub", 2, _dpb.FieldDescriptorProto.TYPE_MESSAGE
    f.type_name, f.label = f".adas_sim.test.{unique}.Inner", _dpb.FieldDescriptorProto.LABEL_OPTIONAL
    f = outer.field.add()
    f.name, f.number, f.type = "tags", 3, _dpb.FieldDescriptorProto.TYPE_STRING
    f.label = _dpb.FieldDescriptorProto.LABEL_REPEATED

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName(f"adas_sim.test.{unique}.Outer"))

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)
    return cls, fds.SerializeToString()


def _manifest(**overrides) -> RunManifest:
    defaults = dict(
        manifest_version=1, run_id="20260730T000000Z-c5vc5vc5", scenario="fixtures/test_d7.yaml",
        project="base", components=(ComponentBuildInfo(name="df", config_bundle_sha256="b" * 64),),
    )
    defaults.update(overrides)
    return RunManifest(**defaults)


def test_port_selection_exports_exactly_the_named_leaf_columns_in_order(tmp_path):
    """UT-D7-1."""
    Outer, schema_bytes = _outer_message_cls("d7sel")
    topics = {
        "/df/outer": TopicInfo(schema_name="adas_sim.test.d7sel.Outer", provenance=Provenance.SIMULATED,
                                schema_bytes=schema_bytes),
        "/df/other": TopicInfo(schema_name="", provenance=Provenance.MEASURED),
    }
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["df.outer"])  # "df.other" deliberately not selected
    writer.open(out, _manifest(), topics)
    writer.write("/df/outer", 0, Outer(x=1, sub={"y": 2.5}, tags=["a", "b"]).SerializeToString())
    writer.write("/df/other", 0, b"\x00")
    writer.close()

    rows = list(_csv.reader(_io.StringIO(out.read_text(encoding="utf-8")), delimiter=","))
    header = next(row for row in rows if not row[0].startswith("#") if row)
    assert header == [
        "log_time_ns", "tick_index", "scenario_time_s",
        "df.outer.x", "df.outer.sub.y", "df.outer.tags", "df.outer.age_s",
    ]


def test_log_time_ns_matches_the_recording_tick_for_tick(tmp_path):
    """UT-D7-2."""
    topics = {"/a/p": TopicInfo(schema_name="", provenance=Provenance.MEASURED)}
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["a.p"])
    writer.open(out, _manifest(), topics)
    expected_times = [i * _DT_NS for i in range(4)]
    for t_ns in expected_times:
        writer.write("/a/p", t_ns, b"\x01")
    writer.close()

    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    reader = _csv.DictReader(_io.StringIO("\n".join(lines)))
    assert [int(row["log_time_ns"]) for row in reader] == expected_times


def test_a_held_value_is_distinguishable_from_a_blank_via_age_s(tmp_path):
    """UT-D7-3 (held half): a slower topic's value is repeated with a
    growing `age_s`, not re-emitted as fresh and not blanked."""
    topics = {
        "/a/fast": TopicInfo(schema_name="", provenance=Provenance.MEASURED),
        "/a/slow": TopicInfo(schema_name="", provenance=Provenance.SIMULATED),
    }
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["a.fast", "a.slow"], on_missing="blank")
    writer.open(out, _manifest(), topics)
    for i in range(4):
        writer.write("/a/fast", i * _DT_NS, str(i).encode())
        if i in (1, 3):
            writer.write("/a/slow", i * _DT_NS, str(i).encode())
    writer.close()

    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    rows = list(_csv.DictReader(_io.StringIO("\n".join(lines))))
    assert rows[0]["a.slow"] == "" and rows[0]["a.slow.age_s"] == ""  # leading gap: nothing to hold yet
    assert rows[1]["a.slow.age_s"] == "0.0"  # fresh
    assert rows[2]["a.slow"] == rows[1]["a.slow"]  # held, same value
    assert float(rows[2]["a.slow.age_s"]) == pytest.approx(0.05)  # one tick's worth of age
    assert rows[3]["a.slow.age_s"] == "0.0"  # fresh again


def test_a_missing_port_errors_by_default(tmp_path):
    """UT-D7-3 (missing half): default `on_missing="error"`."""
    topics = {"/a/p": TopicInfo(schema_name="", provenance=Provenance.MEASURED)}
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["a.p"])  # on_missing defaults to "error"
    writer.open(out, _manifest(), topics)
    # no write() calls at all -- "a.p" never appears
    with pytest.raises(AuthoringError):
        writer.close()


def test_a_missing_port_blanks_only_when_asked(tmp_path):
    topics = {"/a/p": TopicInfo(schema_name="", provenance=Provenance.MEASURED)}
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["a.p"], on_missing="blank")
    writer.open(out, _manifest(), topics)
    writer.close()  # still never appears -- must not raise under "blank"

    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    assert lines == ["log_time_ns,tick_index,scenario_time_s,a.p,a.p.age_s"]  # header only, zero ticks


def test_a_missing_port_is_omitted_from_columns_when_asked(tmp_path):
    topics = {
        "/a/p": TopicInfo(schema_name="", provenance=Provenance.MEASURED),
        "/a/never": TopicInfo(schema_name="", provenance=Provenance.MEASURED),
    }
    out = tmp_path / "export.csv"
    writer = CsvWriter(ports=["a.p", "a.never"], on_missing="omit-column")
    writer.open(out, _manifest(), topics)
    writer.write("/a/p", 0, b"\x01")
    writer.close()

    header = next(line for line in out.read_text(encoding="utf-8").splitlines() if line.startswith("log_time_ns"))
    assert "a.never" not in header
    assert "a.p" in header


def test_origin_tags_and_overridden_marks_survive_into_the_header(tmp_path):
    """UT-D7-4."""
    topics = {
        "/a/normal": TopicInfo(schema_name="", provenance=Provenance.MEASURED),
        "/a/tweaked": TopicInfo(schema_name="", provenance=Provenance.OVERRIDDEN),
    }
    out = tmp_path / "export.csv"
    writer = CsvWriter()
    writer.open(out, _manifest(), topics)
    writer.write("/a/normal", 0, b"\x00")
    writer.write("/a/tweaked", 0, b"\x00")
    writer.close()

    preamble = [line for line in out.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
    origin_line = next(line for line in preamble if line.startswith("# origin:"))
    assert "a.normal=measured" in origin_line
    assert "a.tweaked=overridden" in origin_line
    assert any(line.startswith("# run_id=") and _manifest().run_id in line for line in preamble)


def test_a_write_only_codec_is_refused_as_a_resim_input():
    """UT-D7-5 (`io/registry.py`'s loader-facing half)."""
    with pytest.raises(AuthoringError, match="write-only"):
        reader_for(Path("some_export.csv"))
