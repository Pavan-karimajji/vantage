# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0070`: the system tests of the engine-run recording's producer keys, `SYT-RUN-12`, `SYT-ORC-13` and
`SYT-EQO-06` (`VANTAGE_Test_Spec.md`), one test per case `.cN`. Every assertion message names the FAIL side the spec
states for the case.

Where the spec leaves a step open it is chosen so the case can fail:
- "this machine's name" is `socket.gethostname()`, which the engine's `host` is specified to equal (`IMP-0063`);
- the "two runs" of `SYT-RUN-12.c1` and `.c2` are two `simengine` processes, so their `process_nonce` differs;
- `F-RUN-CONFIG` of `.c3` is the echo-stub pipeline of `test_d15b_cli_resim.py` (the one `test_vnt_run_config.py`
  runs); the recording that `--pin-builds` is run against is the one its own `--save` wrote, and the two copies of
  its `manifest` are written through `edit_recording`.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import socket
from pathlib import Path

import pytest
import yaml

from adas_sim.cli.resim import run as resim_run
from adas_sim.diagnostics.determinism import derive_axis
from adas_sim.diagnostics.errors import ContractError, EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable
from adas_sim.io.mcap import McapReader
from tests.support.engine_runs import (
    Recording, event_entries, point_at_recording, ran, simulated_names, stage_of,
)
from tests.support.lab_cases import edit_recording, lab_case
from tests.system.test_d15b_engine_bridge import _echo_stub_path, _write_heartbeat_recording


def _manifest_dict(path: Path) -> dict:
    """The `manifest` block's `yaml` entry as the file holds it."""
    from mcap.reader import make_reader

    with open(path, "rb") as handle:
        for record in make_reader(handle).iter_metadata():
            if record.name == "manifest":
                return yaml.safe_load(record.metadata["yaml"])
    raise AssertionError(f"{path}: no manifest block")


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- SYT-RUN-12 ----------------------------------------------------------------------------------------------------

def test_syt_run_12_c1_the_manifest_names_the_run_the_process_the_setup_and_the_libraries(tmp_path):  # SYT-RUN-12.c1
    case = lab_case("running_example", "cut_c")
    _run, produced = ran(case, tmp_path, "first")
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    manifest = _manifest_dict(produced.path)
    assert manifest.get("run_id") == setup["run_id"], f"SYT-RUN-12.c1: run_id is {manifest.get('run_id')!r}"
    assert manifest.get("run_spec_sha256") == setup["spec_sha256"], "SYT-RUN-12.c1: run_spec_sha256 is another value"
    assert manifest.get("host") == socket.gethostname(), f"SYT-RUN-12.c1: host is {manifest.get('host')!r}"
    assert manifest.get("process_nonce"), "SYT-RUN-12.c1: process_nonce is missing or empty"
    simulated = simulated_names(case)
    by_name = {c["name"]: c for c in manifest["components"]}
    assert sorted(by_name) == sorted(simulated), (
        f"SYT-RUN-12.c1: a missing component entry, or one for a stage that is not simulated (C): {sorted(by_name)}")
    for name in simulated:
        library = Path(stage_of(setup, name)["impl"]["path"])
        assert by_name[name].get("library_sha256") == _sha256_of(library), (
            f"SYT-RUN-12.c1: stage {name}: library_sha256 is missing, empty or not the hash of {library.name}")


def test_syt_run_12_c2_two_runs_differ_only_in_their_process_nonce(tmp_path):  # SYT-RUN-12.c2
    case = lab_case("running_example", "cut_c")
    _run_a, first = ran(case, tmp_path, "first")
    _run_b, second = ran(case, tmp_path, "second")
    a, b = _manifest_dict(first.path), _manifest_dict(second.path)
    assert a["process_nonce"] != b["process_nonce"], "SYT-RUN-12.c2: equal nonces"
    a.pop("process_nonce"), b.pop("process_nonce")
    assert a == b, f"SYT-RUN-12.c2: another difference: {sorted(k for k in a if a.get(k) != b.get(k))}"
    reader_a, reader_b = McapReader(first.path), McapReader(second.path)
    axis = derive_axis(reader_a.meta(), reader_b.meta())
    assert axis.axis == "fresh_process", f"SYT-RUN-12.c2: another axis: {axis.axis} ({axis.differing_dimensions})"


def _echo_resim(tmp_path, monkeypatch, *extra: str, recording: Path | None = None, save: Path | None = None) -> int:
    """`sim resim` of `F-RUN-CONFIG` (the echo-stub pipeline) over `recording`."""
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
    for name, value in (("NAME", "echo_stub"), ("PERIOD_NS", "10000000"), ("OUTPUT_PORT", "outputs"),
                        ("OUTPUT_PROTO_TYPE", "test.Echo"), ("OUTPUT_MAX_BYTES", "64")):
        monkeypatch.setenv(f"ADAS_SIL_TEST_STUB_{name}", value)
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(exist_ok=True)
    if not (lib_dir / ("echo_stub" + stub.suffix)).exists():  # a second call must not rewrite a library already loaded
        (lib_dir / ("echo_stub" + stub.suffix)).write_bytes(stub.read_bytes())
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text(
        "name: producer_keys\nrun_setup:\n  readiness_limit_steps: 8\n  fallback_max_gap: 6\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n"
        "    trigger: ''\n    buffer_depth: {'*': 16}\n", encoding="utf-8")
    if recording is None:
        recording = tmp_path / "in.mcap"
        _write_heartbeat_recording(recording)
    argv = [str(recording), "--pipeline", str(pipeline), "--search", str(lib_dir), *extra]
    if save is not None:
        argv += ["--save", str(save)]
    return resim_run(argv)


def test_syt_run_12_c3_pin_builds_passes_refuses_a_changed_hash_and_an_absent_one(tmp_path, monkeypatch):  # SYT-RUN-12.c3
    saved = tmp_path / "saved.mcap"
    assert _echo_resim(tmp_path, monkeypatch, save=saved) == 0
    assert _manifest_dict(saved)["components"][0].get("library_sha256"), "SYT-RUN-12.c3: --save wrote no library_sha256"
    # `edit_recording` writes through the one recording writer; any lab case supplies the writer's location.
    base = dataclasses.replace(lab_case("running_example", "cut_c"), recording=saved)

    def changed(manifest: dict) -> None:
        manifest["components"][0]["library_sha256"] = "0" * 64

    def stripped(manifest: dict) -> None:
        manifest["components"][0].pop("library_sha256", None)

    mismatch = edit_recording(base, tmp_path / "changed.mcap", lambda ms: ms, manifest_change=changed)
    unpinnable = edit_recording(base, tmp_path / "stripped.mcap", lambda ms: ms, manifest_change=stripped)

    assert _echo_resim(tmp_path, monkeypatch, "--pin-builds", recording=saved) == 0, (
        "SYT-RUN-12.c3: a refusal of the saved recording")
    with pytest.raises(ContractError, match="library_sha256=") as refused:
        _echo_resim(tmp_path, monkeypatch, "--pin-builds", recording=mismatch)
    assert "unpinnable" not in str(refused.value), "SYT-RUN-12.c3: the changed copy was refused as unpinnable"
    with pytest.raises(ContractError, match="unpinnable"):
        _echo_resim(tmp_path, monkeypatch, "--pin-builds", recording=unpinnable)


# ---- SYT-ORC-13 ----------------------------------------------------------------------------------------------------

def test_syt_orc_13_c1_every_runs_overridden_input_is_recorded(tmp_path):  # SYT-ORC-13.c1
    case = lab_case("running_example", "all_simulated")

    def shallow_with_override(setup: dict) -> None:
        for stage in setup["stages"]:
            for port in stage["ports"]:
                port["buffer_depth"] = 1
        setup["mutations"] = [{
            "verb": "scale", "address": {"stage": "source", "port": "Y", "path": ["value"], "index": None},
            "operands": [1.0], "window_ns": [None, None]}]

    # The lab's recording never has two `B` controls at one instant, so no run waits for another; `B`'s controls are
    # paired here (every first one is logged at the instant of the one after it, so both are ready), which is the
    # case the row is for.
    def pair_controls(messages):
        later = [t for topic, t, _p in messages if topic == "B.control"]
        seen = 0
        paired = []
        for index, (topic, time_ns, payload) in enumerate(messages):
            if topic == "B.control":
                if seen % 2 == 0 and seen + 1 < len(later):
                    time_ns = later[seen + 1]
                seen += 1
            paired.append((index, topic, time_ns, payload))
        return [(topic, time_ns, payload) for _i, topic, time_ns, payload in sorted(paired, key=lambda m: (m[2], m[0]))]

    edited = edit_recording(case, tmp_path / "paired.mcap", pair_controls)

    def change(setup: dict) -> None:
        shallow_with_override(setup)
        point_at_recording(setup, edited)

    _run, produced = ran(case, tmp_path, "run", change=change)
    controls = produced.decoded("B.control")
    delivered = produced.decoded("B.in_Y")
    named = [(e.measurement_counter if e is not None else 0)
             for _i, _t, ref_sync in produced.decoded("B.refSync")
             for e in [next((x for x in ref_sync.inputs if x.port == "in_Y"), None)]]
    got = [m.sig_header.measurement_counter for _i, _t, m in delivered]
    assert len(delivered) == len(controls), (
        f"SYT-ORC-13.c1: a count other than the controls': {len(delivered)} in_Y messages for {len(controls)} controls")
    assert got == named, "SYT-ORC-13.c1: a message carrying another run's counter"
    times = [t for _i, t, _m in controls]
    assert len(times) != len(set(times)), "SYT-ORC-13.c1: no step with two B runs, so the case could not fail"


# ---- SYT-EQO-06 ----------------------------------------------------------------------------------------------------

def _divergence_of(path: Path) -> str:
    return _manifest_dict(path).get("divergence", "")


def test_syt_eqo_06_c1_the_manifest_states_the_first_divergence(tmp_path):  # SYT-EQO-06.c1
    diverging = lab_case("running_example", "all_simulated", "no_ref_sync")
    run_a, produced_a = ran(diverging, tmp_path / "a", "run")
    logged = event_entries(run_a.events, "first_divergence")
    assert logged, "SYT-EQO-06.c1: no_ref_sync diverges nowhere, so the case could not fail"
    expected = f"step={logged[0]['step']} stage={logged[0]['stage']} port={logged[0]['port']}"
    assert _divergence_of(produced_a.path) == expected, (
        f"SYT-EQO-06.c1: another value: {_divergence_of(produced_a.path)!r}, the event log says {expected!r}")

    clean = lab_case("running_example", "cut_c")
    _run_b, produced_b = ran(clean, tmp_path / "b", "run")
    assert _divergence_of(produced_b.path) == "none", (
        f"SYT-EQO-06.c1: cut_c compared outputs and none diverged, the manifest says {_divergence_of(produced_b.path)!r}")

    recorded = Recording(clean.recording)
    outputs = [t for t in recorded.topics() if t.split(".")[0] in ("A", "B", "D", "E") and not t.endswith(".control")]
    assert outputs, "SYT-EQO-06.c1: no output topic to remove, so the case could not fail"
    stripped = edit_recording(
        clean, tmp_path / "stripped.mcap", lambda ms: [m for m in ms if m[0] not in set(outputs)], drop_topics=outputs)
    _run_c, produced_c = ran(clean, tmp_path / "c", "run", change=lambda setup: point_at_recording(setup, stripped))
    assert _divergence_of(produced_c.path) == "unknown", (
        f"SYT-EQO-06.c1: no output was compared, the manifest says {_divergence_of(produced_c.path)!r}")
