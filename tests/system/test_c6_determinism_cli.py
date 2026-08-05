# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`S-C6` (`R-SIM-24`) system test: `sim determinism <run-a> <run-b>` end to
end, through real `.mcap` files and the real CLI dispatch (`cli/
determinism.py::run`) -- `ST-C6-3` (axis reported, never flagged) and
`ST-C6-2`'s CLI-level half (a real divergence reddens the real command,
naming where)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.cli.determinism import run as determinism_run
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.io.mcap import McapWriter


def _write_recording(path: Path, *, host: str, nonce: str, library_sha: str, payload: bytes) -> None:
    meta = RunManifest(
        manifest_version=2, host=host, process_nonce=nonce,
        components=(ComponentBuildInfo(name="df", library_sha256=library_sha, config_bundle_sha256="cfg1"),),
    )
    writer = McapWriter()
    writer.open(path, meta, {"a": TopicInfo(schema_name="a", provenance=Provenance.SIMULATED)})
    writer.write("a", 0, payload)
    writer.close()


def test_same_process_pair_with_identical_payloads_passes(tmp_path, capsys):
    a = tmp_path / "a.mcap"
    b = tmp_path / "b.mcap"
    _write_recording(a, host="h1", nonce="shared", library_sha="lib1", payload=b"x")
    _write_recording(b, host="h1", nonce="shared", library_sha="lib1", payload=b"x")

    exit_code = determinism_run([str(a), str(b)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "axis: same process" in out
    assert "PASS" in out


def test_rebuilt_binary_pair_with_a_real_divergence_fails_naming_where(tmp_path, capsys):
    a = tmp_path / "a.mcap"
    b = tmp_path / "b.mcap"
    _write_recording(a, host="h1", nonce="n1", library_sha="libA", payload=b"x")
    _write_recording(b, host="h1", nonce="n2", library_sha="libB", payload=b"DIFFERENT")

    exit_code = determinism_run([str(a), str(b)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "axis: rebuilt binary" in out
    assert "FAIL" in out
    assert "topic 'a'" in out


def test_two_dimensions_differing_reports_neither_axis(tmp_path, capsys):
    a = tmp_path / "a.mcap"
    b = tmp_path / "b.mcap"
    _write_recording(a, host="machine-a", nonce="n1", library_sha="libA", payload=b"x")
    _write_recording(b, host="machine-b", nonce="n2", library_sha="libB", payload=b"x")

    exit_code = determinism_run([str(a), str(b)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "axis: NEITHER" in out
    assert "host" in out and "library_sha256:df" in out


def test_axis_flag_is_refused(tmp_path):
    a = tmp_path / "a.mcap"
    b = tmp_path / "b.mcap"
    _write_recording(a, host="h1", nonce="n1", library_sha="lib1", payload=b"x")
    _write_recording(b, host="h1", nonce="n1", library_sha="lib1", payload=b"x")

    with pytest.raises(SystemExit):
        determinism_run([str(a), str(b), "--axis", "same_process"])
