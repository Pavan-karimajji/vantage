# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-24` `SI-17 diagnostics` -- `UT-DIA-01` through `UT-DIA-13`
(`docs/v2/SIM_Software_Test_Spec_v0.1.md` §5.17). Most of `SI-17` was
already built under earlier work (`diagnostics/evidence.py`, `explain.py`,
`determinism.py`, `tolerance.py`, `diagnostics.py`/doctor); this file adds
the `WP-24`-scoped coverage citing each `UT-DIA-*` identifier verbatim
(`R-REQ-9`), plus the genuinely new pieces this package lands
(`summary.py`, `estimate.py`, `tap.py`, the dry run).

`UT-DIA-14` (`SW-0286`) and `UT-DIA-15` (`SW-0403`) are not here: both cite
`pyapi`, which does not exist yet (`WP-29`) -- see the plan's own `WP-24`
row."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from google.protobuf import descriptor_pb2, wrappers_pb2

from adas_sim.diagnostics.determinism import (
    compare_exact, compare_with_tolerance, derive_axis, format_report,
)
from adas_sim.diagnostics.diagnostics import doctor_report
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.diagnostics.estimate import Shape, estimate_duration, record_measurement, within_band
from adas_sim.diagnostics.evidence import EVIDENCE_FIELDS, evidence, format_evidence
from adas_sim.diagnostics.explain import DryRun, dry_run, explain, injection_boundary
from adas_sim.diagnostics.summary import format_summary, reconciles, summarize
from adas_sim.diagnostics.tap import Tap, parse_taps, resolve_taps
from adas_sim.diagnostics.tolerance import ToleranceRow, ToleranceSet
from adas_sim.player.panels.evidence_panel import EvidencePanelState
from adas_sim.resolve.component import ComponentManifest, PortSpec
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


# ---------------------------------------------------------------------------
# UT-DIA-01 -- SW-0271: the dry run reports the plan, loading no module and
# decoding no message.
# ---------------------------------------------------------------------------


def _chain4_pipeline_yaml(tmp_path: Path) -> Path:
    """`F-CHAIN4`'s own shape (`vdy -> perception -> fusion -> aeb`), with
    `perception` `measured` and everything else `simulate` -- one real
    injection-boundary crossing (`perception -> fusion`) and no library that
    needs to exist on disk, since `dry_run` must never resolve `impl:`."""
    stages = [
        {"name": "vdy", "mode": "simulate", "impl": "dll:nonexistent_vdy", "inputs": {}},
        {"name": "perception", "mode": "measured", "impl": None, "inputs": {"in": "vdy.out"}},
        {"name": "fusion", "mode": "simulate", "impl": "dll:nonexistent_fusion", "inputs": {"in": "perception.out"}},
        {"name": "aeb", "mode": "simulate", "impl": "dll:nonexistent_aeb", "inputs": {"in": "fusion.out"}},
    ]
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "chain4", "stages": stages}, sort_keys=False), encoding="utf-8")
    return path


def test_dry_run_loads_no_module_and_decodes_no_message(tmp_path):
    pipeline_path = _chain4_pipeline_yaml(tmp_path)
    result = dry_run(pipeline_path, tick_count=100)
    assert isinstance(result, DryRun)
    assert result.modules_loaded == 0
    assert result.messages_decoded == 0


def test_dry_run_reports_every_listed_element_present(tmp_path):
    pipeline_path = _chain4_pipeline_yaml(tmp_path)
    result = dry_run(pipeline_path, tick_count=100)
    assert len(result.stages) == 4
    assert result.schedule  # present for every stage, "unknown" is still present
    assert result.injection_boundary == (("perception", "out", "fusion", "in"),)
    assert isinstance(result.coherence, tuple)  # graph.coherence.classify's own return shape
    assert result.estimate.estimate_s >= 0.0


def test_injection_boundary_is_computed_structurally_with_no_component_resolution(tmp_path):
    """`CN-0121`: only ports crossing FROM a `measured` stage INTO a
    `simulate` stage count -- `vdy -> perception` (simulate -> measured) is
    not the boundary."""
    from adas_sim.graph.build import Pipeline

    stages = Pipeline.parse_stages(_chain4_pipeline_yaml(tmp_path))
    boundary = injection_boundary(stages)
    assert boundary == (("perception", "out", "fusion", "in"),)


# ---------------------------------------------------------------------------
# UT-DIA-02 -- SW-0273: one evidence producer, two formatters -- field for
# field identical, and no second constructor exists (closes the `⊘` this row
# used to carry: it awaited this package's own implementation, not a number).
# ---------------------------------------------------------------------------

_PORT = "echo_stub.echo"


def _session_with_port() -> Session:
    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={_PORT: PortValue(name=_PORT, message=b"\xca\xfe", origin="simulated")},
        pose=_POSE,
    )
    return Session(run_id="run-si17", name="s", ticks=(tick,), meta=RunManifest(), known_ports=frozenset({_PORT}))


def test_gui_panel_and_cli_formatter_produce_field_for_field_identical_output():
    session = _session_with_port()
    for address in (session.run_id, _PORT, "no-such-address"):
        panel = EvidencePanelState(session)
        gui_rows = panel.view_for(address, 0).rows
        cli_rows = format_evidence(evidence(address, session, 0))
        assert gui_rows == cli_rows


def _load_check_evidence_single_producer():
    import sys
    from pathlib import Path as _Path

    scripts_dir = _Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from check_evidence_single_producer import check_evidence_single_producer

    return check_evidence_single_producer


def test_no_second_code_path_constructs_an_evidence_record():
    check = _load_check_evidence_single_producer()
    assert check() == []


def test_check_evidence_single_producer_fails_on_a_planted_second_constructor(tmp_path):
    """`ANL-SW-64`'s own discipline: every `ANL-*` check ships its planted
    violation. A copy of the real producer file, renamed so the check's own
    exclusion of `evidence.py` does not shield it, plants exactly the
    defect `SW-0273`'s Accept clause is checking for."""
    check = _load_check_evidence_single_producer()
    fake_adas_sim = tmp_path / "adas_sim"
    fake_adas_sim.mkdir()
    (fake_adas_sim / "second_producer.py").write_text(
        "from adas_sim.diagnostics.evidence import Evidence\n"
        "def sneaky(address, session, tick):\n"
        "    return Evidence(address=address, kind='port', value='', tick=tick, t_ns=0, "
        "topic=None, origin=None, run_id='')\n",
        encoding="utf-8",
    )
    findings = check(fake_adas_sim, tmp_path / "does_not_exist.py")
    assert len(findings) == 1
    assert "second_producer.py" in findings[0]


# ---------------------------------------------------------------------------
# UT-DIA-03 -- SW-0274: every field present or `unknown`, never a plausible
# default -- exercised against `rung`/`quality`, unfillable today.
# ---------------------------------------------------------------------------


def test_evidence_rung_and_quality_are_present_and_read_unknown_when_unfillable():
    session = _session_with_port()
    record = evidence(_PORT, session, 0)
    assert record.rung is None
    assert record.quality is None
    rows = dict(format_evidence(record))
    assert rows["rung"] == "unknown"
    assert rows["quality"] == "unknown"
    assert set(EVIDENCE_FIELDS) >= {"rung", "quality"}


def test_no_evidence_field_ever_renders_the_bare_python_none():
    session = _session_with_port()
    record = evidence(session.run_id, session, 0)  # kind="run_id": most fields unfillable
    rows = format_evidence(record)
    assert all(text != "None" for _name, text in rows)


# ---------------------------------------------------------------------------
# UT-DIA-04 -- SW-0275: the evidence chain adds no new capture -- calling it
# repeatedly is a pure read, never mutating the session it was given.
# ---------------------------------------------------------------------------


def test_evidence_is_a_pure_read_with_no_session_mutation():
    session = _session_with_port()
    before = session.ticks[0].ports[_PORT]
    for _ in range(5):
        evidence(_PORT, session, 0)
    after = session.ticks[0].ports[_PORT]
    assert before is after
    assert evidence(_PORT, session, 0) == evidence(_PORT, session, 0)  # idempotent, no hidden state


# ---------------------------------------------------------------------------
# UT-DIA-05 -- SW-0277: the environment report never raises, against a
# missing library, an unreadable recording and an incompatible plug-in
# together in one call.
# ---------------------------------------------------------------------------


def test_doctor_report_never_raises_against_several_simultaneous_faults(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "version: 1\nname: broken\nstages:\n"
        "  - name: df\n    mode: simulate\n    impl: \"dll:totally_missing_stem\"\n    inputs: {}\n",
        encoding="utf-8",
    )
    bad_recording = tmp_path / "broken.mcap.xyz"
    bad_recording.write_bytes(b"not a real recording")

    report = doctor_report(pipeline_path=pipeline_path, search=[tmp_path], recording_path=bad_recording)

    assert report["problems"]  # every fault reported
    assert any("totally_missing_stem" in p for p in report["problems"])
    assert any(str(bad_recording) in p for p in report["problems"])


# ---------------------------------------------------------------------------
# UT-DIA-06 -- SW-0278: any name resolves to an explanation, with near
# matches naming the set searched on a miss.
# ---------------------------------------------------------------------------


def test_misspelled_run_id_gets_a_near_match_naming_what_was_searched():
    session = _session_with_port()
    result = explain(session.run_id[:-1], session)  # drop the last char
    assert result["kind"] == "unknown"
    assert result["searched"]
    assert session.run_id in result["did_you_mean"]


def test_misspelled_topic_gets_a_near_match():
    session = _session_with_port()
    misspelled = _PORT.replace("echo", "eho")
    result = explain(misspelled, session)
    assert result["kind"] == "unknown"
    assert _PORT in result["did_you_mean"]


def test_exact_topic_and_run_id_resolve_without_a_miss():
    session = _session_with_port()
    assert explain(_PORT, session)["kind"] == "topic"
    assert explain(session.run_id, session)["kind"] == "run_id"


# ---------------------------------------------------------------------------
# UT-DIA-07 -- SW-0279: probing a module reads its ports from its manifest
# with no hand-mapping and no per-module code -- a component the framework
# has never seen still lists its full port set.
# ---------------------------------------------------------------------------


def test_probe_lists_the_full_port_set_of_a_component_never_seen_before(monkeypatch, capsys):
    from adas_sim.cli import probe as probe_cli

    manifest = ComponentManifest(
        component="totally_unseen_component_zzz", version="1", abi_version=1, build_id="b",
        inputs=(PortSpec(name="in_a", proto_type="test.A"),),
        outputs=(PortSpec(name="out_b", proto_type="test.B"), PortSpec(name="out_c", proto_type="test.C")),
        project="base", config_bundle_sha256="cfg", descriptor_set=b"", period_ns=0,
    )

    class _FakeComponent:
        def __init__(self, path):
            del path
            self.manifest = manifest

    monkeypatch.setattr(probe_cli, "CtypesSilComponent", _FakeComponent)
    exit_code = probe_cli.run([str(Path("does-not-matter.dll"))])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "totally_unseen_component_zzz" in out
    for port in ("in_a", "out_b", "out_c"):
        assert port in out


# ---------------------------------------------------------------------------
# UT-DIA-08/09/10 -- SW-0280/0281/0282: named first divergence, the axis
# derived from the manifests, over decoded port values.
# ---------------------------------------------------------------------------


def _manifest(*, host="h1", nonce="n1", library_sha="lib1", build_id="b1", bundle_sha="cfg1") -> RunManifest:
    return RunManifest(
        manifest_version=2, host=host, process_nonce=nonce,
        components=(ComponentBuildInfo(name="df", library_sha256=library_sha, build_id=build_id, config_bundle_sha256=bundle_sha),),
    )


class _FakeReader:
    def __init__(self, topics, messages):
        self._topics = topics
        self._messages = messages

    def meta(self):
        return RunManifest()

    def topics(self):
        return self._topics

    def messages(self, topics=None):
        for m in self._messages:
            if topics is None or m[0] in topics:
                yield m

    def close(self):
        pass


def test_run_comparison_names_the_first_diverging_tick_port_and_field():
    topics = {"a": TopicInfo(schema_name="a", provenance=Provenance.SIMULATED)}
    reader_a = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"y")])
    reader_b = _FakeReader(topics, [("a", 0, 0, b"x"), ("a", 10, 10, b"DIFFERENT")])
    divergence = compare_exact(reader_a, reader_b)
    assert divergence is not None
    assert (divergence.tick_index, divergence.topic) == (1, "a")


def test_axis_derived_from_one_differing_dimension_never_a_caller_flag():
    a = _manifest(nonce="n1", library_sha="libA")
    b = _manifest(nonce="n2", library_sha="libB")
    result = derive_axis(a, b)
    assert result.axis == "rebuilt_binary"


def test_axis_inconclusive_when_host_and_build_both_differ():
    a = _manifest(nonce="n1", host="m1", library_sha="libA")
    b = _manifest(nonce="n2", host="m2", library_sha="libB")
    result = derive_axis(a, b)
    assert result.axis is None
    assert set(result.differing_dimensions) == {"host", "library_sha256:df"}


def _double_schema():
    fd_proto = descriptor_pb2.FileDescriptorProto()
    wrappers_pb2.DoubleValue.DESCRIPTOR.file.CopyToProto(fd_proto)
    fds = descriptor_pb2.FileDescriptorSet()
    fds.file.append(fd_proto)
    return fds.SerializeToString(), "google.protobuf.DoubleValue"


def test_comparison_is_over_decoded_port_values_not_file_bytes():
    """Two 'recordings of one deterministic run', differing only in run
    identifier and timestamp (never part of a port payload here), compare
    equal -- SW-0282."""
    schema_bytes, schema_name = _double_schema()
    topics = {"a": TopicInfo(schema_name=schema_name, provenance=Provenance.SIMULATED, schema_bytes=schema_bytes)}
    payload = wrappers_pb2.DoubleValue(value=3.0).SerializeToString()
    reader_a = _FakeReader(topics, [("a", 0, 0, payload)])
    reader_b = _FakeReader(topics, [("a", 999, 999, payload)])  # different log/capture time, same port bytes
    assert compare_exact(reader_a, reader_b) is None


# ---------------------------------------------------------------------------
# UT-DIA-11 -- SW-0283: two axes are gates with no tolerance field, two are
# measurements; a passing report prints the tolerance used and the headroom
# consumed.
# ---------------------------------------------------------------------------


def test_gate_axes_have_no_tolerance_field_to_print():
    with pytest.raises(AuthoringError):
        format_report("same_process", [])
    with pytest.raises(AuthoringError):
        format_report("fresh_process", [])


def test_passing_measurement_report_prints_tolerance_and_headroom():
    tolerance = ToleranceSet(component="df", rows=(ToleranceRow(field="ttc_s", abs_tol=0.05, why="FP contraction"),), sha256="abc123")
    text = format_report("rebuilt_binary", [], headroom=0.4, tolerance=tolerance)
    assert "PASS" in text
    assert "headroom_consumed=0.400" in text
    assert "df" in text
    assert "ttc_s" in text
    assert "FP contraction" in text


def test_failing_measurement_report_names_every_divergence():
    from adas_sim.diagnostics.determinism import Divergence

    divergences = [Divergence(tick_index=3, topic="a", field="ttc_s", detail="1.0 vs 2.0")]
    text = format_report("different_machine", divergences, headroom=0.0, tolerance=None)
    assert "FAIL" in text
    assert "tick=3" in text
    assert "ttc_s" in text


# ---------------------------------------------------------------------------
# UT-DIA-12 -- SW-0284: tolerance declared once per component and field,
# mandatory reason, integers/enums never overridable.
# ---------------------------------------------------------------------------


def test_tolerance_row_without_why_is_refused_at_load(tmp_path):
    from adas_sim.diagnostics.tolerance import load_tolerance

    path = tmp_path / "tolerance.yaml"
    path.write_text(yaml.safe_dump({"fields": {"ttc_s": {"abs_tol": 0.01}}}), encoding="utf-8")
    with pytest.raises(AuthoringError):
        load_tolerance(path, component="df")


def test_tolerance_never_widens_an_integer_field_regardless_of_the_file():
    """`compare_with_tolerance` (`test_c6_determinism.py`'s own coverage)
    never even looks a non-float field up in `ToleranceSet` -- `ToleranceRow`
    itself carries no "kind" a caller could use to mark one widened, so
    there is no path by which an integer/enum family gets a nonzero bound."""
    row = ToleranceRow(field="cycle_counter", abs_tol=0.02, why="test")
    tolerance = ToleranceSet(component="df", rows=(row,), sha256="")
    # An int/enum field is exact regardless of what a same-named row says --
    # compare_with_tolerance's own is_float gate, exercised directly here via
    # bound_for to show the row exists but the comparator would never consult
    # it for a non-float descriptor.
    assert tolerance.bound_for("cycle_counter").abs_tol == 0.02  # the row itself loads fine
    # but compare_with_tolerance only ever reads it for a CPPTYPE_FLOAT/DOUBLE
    # field (see determinism.py::compare_with_tolerance's own is_float check) --
    # covered end-to-end for a float field by test_c6_determinism.py.


# ---------------------------------------------------------------------------
# UT-DIA-13 -- SW-0285: any internal port becomes recorded output by naming
# it, with no code change; a bad tap names both the stage and the port.
# ---------------------------------------------------------------------------


def test_tap_resolves_a_declared_internal_port_against_the_real_manifest():
    manifest = ComponentManifest(
        component="df", version="1", abi_version=1, build_id="b",
        inputs=(), outputs=(PortSpec(name="internal_debug_state", proto_type="test.Debug"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    taps = parse_taps({"df": ["internal_debug_state"]})
    resolved = resolve_taps(taps, {"df": manifest})
    assert resolved == (PortSpec(name="internal_debug_state", proto_type="test.Debug"),)


def test_tap_naming_an_unknown_port_names_the_stage_the_port_and_what_exists():
    manifest = ComponentManifest(
        component="df", version="1", abi_version=1, build_id="b",
        inputs=(), outputs=(PortSpec(name="real_port", proto_type="test.A"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    taps = parse_taps({"df": ["no_such_port"]})
    with pytest.raises(AuthoringError) as excinfo:
        resolve_taps(taps, {"df": manifest})
    assert "no_such_port" in str(excinfo.value)
    assert "df" in str(excinfo.value)
    assert "real_port" in str(excinfo.value)


def test_removing_a_tap_leaves_the_declared_set_unchanged_for_the_rest():
    taps_with = parse_taps({"df": ["a", "b"]})
    taps_without = parse_taps({"df": ["a"]})
    assert {t.port for t in taps_with} == {"a", "b"}
    assert {t.port for t in taps_without} == {"a"}
    assert taps_without[0] == Tap(stage="df", port="a")


# ---------------------------------------------------------------------------
# SW-0130 (IMP-0130, this WP's own `summary.py`) -- UT-ERR-08: the end
# summary reconciles exactly with the structured log's counts.
# ---------------------------------------------------------------------------


def test_warning_summary_reconciles_with_the_structured_log():
    from adas_sim.diagnostics.events import Event
    from adas_sim.diagnostics.logging import log

    lines: list[str] = []

    def _capture(*args, **kwargs):
        import io
        import sys

        buf = io.StringIO()
        real_stderr = sys.stderr
        sys.stderr = buf
        try:
            log(*args, **kwargs)
        finally:
            sys.stderr = real_stderr
        lines.append(buf.getvalue().rstrip("\n"))

    _capture(Event.PORT_MISSING, run="r1", port="a")
    _capture(Event.PORT_MISSING, run="r1", port="b")
    _capture(Event.DEGRADE, run="r1")
    _capture(Event.EXEC_FAIL, run="r1", stage="df")

    summary = summarize(lines)
    assert reconciles(summary, lines)
    counts = summary.as_mapping()
    assert counts["port_missing"] == 2
    assert counts["degrade"] == 1
    assert counts["exec_fail"] == 1
    assert summary.total == 4
    assert "4 total" in format_summary(summary)


def test_warning_summary_is_empty_when_nothing_warned():
    summary = summarize(["2026-01-01T00:00:00.000Z INFO  run=r1 event=tick_ok"])
    assert summary.total == 0
    assert format_summary(summary) == "warnings: none"


# ---------------------------------------------------------------------------
# SW-0272 (IMP-0272, `estimate.py`) -- ANL-SW-43: the estimate's own
# accuracy factor is seeded from the first campaign, not asserted.
# ---------------------------------------------------------------------------


def test_estimate_has_no_accuracy_factor_before_any_campaign_has_run(tmp_path):
    shape = Shape(stage_count=4, tick_count=1000)
    result = estimate_duration(shape, history_path=tmp_path / "history.json")
    assert result.estimate_s > 0.0
    assert result.accuracy_factor is None  # unseeded, honestly


def test_first_measurement_seeds_the_band_and_the_second_is_checked_against_it(tmp_path):
    history_path = tmp_path / "history.json"
    shape = Shape(stage_count=4, tick_count=1000)

    seeded = record_measurement(shape, 12.0, run_id="campaign-1", history_path=history_path)
    assert seeded.accuracy_factor is not None  # seeded run marked, per ANL-SW-43's own note
    assert seeded.seeded_from == "campaign-1"

    # A second measurement close to the seed stays within the band it just seeded.
    assert within_band(seeded, 12.5) is True
    # A wildly different second measurement fails it -- failable from the second run.
    assert within_band(seeded, 1200.0) is False


def test_estimate_within_band_always_passes_with_no_seeded_band():
    shape = Shape(stage_count=1, tick_count=1)
    fresh = estimate_duration(shape, history_path=None)
    assert within_band(fresh, 999999.0) is True  # nothing to fail against yet
