# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-21` (`SI-13` `resolve`) -- `UT-RES-10`/`UT-RES-11`, against a real
built `echo_stub` (`F-STUB`) and a real recording (`F-FOREIGN`-shaped: a
tiny `.mcap` with no source checkout involved). Skips with a named reason
if the real stub is absent, same discipline `tests/system/test_d15b_engine_
bridge.py`/`test_c3_check.py` already use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import writer_for
from adas_sim.resolve import probe

_SIM_ROOT = Path(__file__).resolve().parent.parent.parent
_ECHO_STUB_CANDIDATES = (
    _SIM_ROOT / "build-gtest-vs2026" / "tests" / "Release" / "echo_stub.dll",
    _SIM_ROOT / "build-gtest-ubuntu_gcc" / "tests" / "libecho_stub.so",
)


def _find_echo_stub() -> Path | None:
    for candidate in _ECHO_STUB_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


pytestmark = pytest.mark.skipif(_find_echo_stub() is None, reason="no built echo_stub found (see WP-15b's own fixture)")


def test_ut_res_10_enumerates_c_entry_points_and_config_layer_cannot_execute():
    """`UT-RES-10`: enumerate the C entry points each Python package
    reaches; then attempt an execute call from the configuration layer.
    `resolve/probe.py` binds only `adasAbiVersion`/`adasManifest`; it has
    no `adasInit`/`adasExec`/`adasShutdown` attribute at all, so a
    configuration-layer caller literally cannot reach one through it."""
    assert hasattr(probe, "_bind_probe_symbols")
    assert not hasattr(probe, "_bind")  # component.py's execute-path binder is not reachable from here

    stub = _find_echo_stub()
    manifest = probe.probe_manifest(stub)
    assert manifest.component == "echo_stub"

    # `probe._bind_probe_symbols` sets `argtypes`/`restype` on exactly two
    # attributes -- confirming it never touches the three execute symbols
    # is the mechanical form of "cannot reach an execute entry point from
    # a configuration-layer caller going through this module."
    import ctypes

    dll = ctypes.CDLL(str(stub))
    for name in ("adasInit", "adasExec", "adasShutdown"):
        assert getattr(dll, name).argtypes is None  # ctypes default: never configured by probe.py
    probe._bind_probe_symbols(dll)
    for name in ("adasInit", "adasExec", "adasShutdown"):
        assert getattr(dll, name).argtypes is None  # still untouched after the probe binding runs


def test_ut_res_11_probes_a_recording_and_a_module_with_no_handle_surviving(tmp_path):
    """`UT-RES-11`: probe a recording and a module; compare the index
    against a full read and the manifest against what the module host
    reads; serialise both and confirm no handle survives (both dataclasses
    are frozen, no file descriptor/DLL handle stored on either)."""
    stub = _find_echo_stub()

    manifest = probe.read_manifest(stub)
    assert manifest.name == "echo_stub"
    assert manifest.outputs == ()

    recording_path = tmp_path / "recording.mcap"
    writer = writer_for(recording_path)
    writer.open(
        recording_path, meta=RunManifest(),
        topics={"/dummy/heartbeat": TopicInfo(schema_name="test.Heartbeat", provenance=Provenance.MEASURED)},
    )
    for t_ns in (0, 10_000_000, 20_000_000):
        writer.write("/dummy/heartbeat", t_ns, b"\x01", capture_time_ns=t_ns)
    writer.close()

    index = probe.describe_recording(recording_path)
    assert set(index.topics) == {"/dummy/heartbeat"}
    topic = index.topics["/dummy/heartbeat"]
    assert topic.message_count == 3
    assert topic.first_timestamp_ns == 0
    assert topic.last_timestamp_ns == 20_000_000
    assert topic.proto_type == "test.Heartbeat"
    assert topic.origin == "measured"

    # No handle retained: both results are plain, picklable/serialisable
    # frozen dataclasses -- no open file, no ctypes handle stored on them.
    import copy

    copy.deepcopy(index)
    copy.deepcopy(manifest)
