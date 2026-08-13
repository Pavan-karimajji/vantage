# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `cli/export.py` tests: `ST-D7-1`, `ST-D7-4` (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from adas_sim.cli.export import run
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import writer_for
import adas_sim.io.csv  # noqa: F401 -- registers ".csv"
import adas_sim.io.mcap  # noqa: F401 -- registers ".mcap"

_PROJECT = "base"
_TICK_COUNT = 5
_DT_NS = 50_000_000


def _write_synthetic_recording(out_path: Path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-d7-export-cli", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d7.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, config_bundle_sha256="c" * 64),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.MEASURED)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def test_export_opens_in_pandas_with_the_preamble_skipped(tmp_path):
    """ST-D7-1."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_csv = tmp_path / "export.csv"

    assert run([str(recording), str(out_csv), "--ports", "test.marker"]) == 0
    df = pd.read_csv(out_csv, comment="#")
    assert len(df) == _TICK_COUNT
    assert list(df["log_time_ns"]) == [i * _DT_NS for i in range(_TICK_COUNT)]
    assert "test.marker" in df.columns


def test_export_header_carries_run_id_bundle_hash_and_origin_tags(tmp_path):
    """ST-D7-4."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_csv = tmp_path / "export.csv"

    assert run([str(recording), str(out_csv), "--ports", "test.marker"]) == 0
    preamble = [line for line in out_csv.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
    assert any("run_id=test-d7-export-cli" in line for line in preamble)
    assert any("bundle_sha256[test]=" + "c" * 64 in line for line in preamble)
    assert any(line.startswith("# origin:") and "test.marker=measured" in line for line in preamble)


def test_export_all_ports_when_none_named(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_csv = tmp_path / "export.csv"

    assert run([str(recording), str(out_csv)]) == 0
    df = pd.read_csv(out_csv, comment="#")
    assert "test.marker" in df.columns


def test_export_via_the_main_dispatcher(tmp_path, monkeypatch):
    import sys
    from adas_sim.cli import main as cli_main

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    out_csv = tmp_path / "export.csv"
    monkeypatch.setattr(sys, "argv", ["sim", "export", str(recording), str(out_csv), "--ports", "test.marker"])
    assert cli_main() == 0
    assert out_csv.is_file()
