# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`write_recording`: a test's way to get a small `.mcap` input, through the one Python recording writer
(`io/recording_writer.py`, `RCT:IMP-0048`). It adds no writer of its own: the file is `adas_recording`'s, with the
provenance a recording must state given as arguments (a test that needs a foreign or legacy shape writes that
file itself, as `test_a4_legacy.py` does). Skips with the reason printed when the build that names the writer is
not here.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.io.base import TopicInfo
from adas_sim.io.recording_writer import recording_writer


def write_recording(
    path: Path, topics: Mapping[str, TopicInfo], messages: Sequence[tuple[str, int, bytes]], *,
    source_kind: str = "synthetic", run_kind: str = "sim", extra_manifest: Mapping[str, object] | None = None,
    config_bundle: Mapping[str, str] | None = None,
) -> Path:
    """`messages` are `(topic, log_time_ns, payload)` in file order; each time is a whole number of microseconds."""
    try:
        module = recording_writer()
    except EnvironmentError_ as exc:
        print(f"recording writer not found: {exc}", file=sys.stderr)
        pytest.skip(f"recording writer not found: {exc}")
    specs = {topic: module.TopicSpec(info.schema_name, info.schema_bytes, info.provenance.value) for topic, info in topics.items()}
    manifest = {
        "source_kind": source_kind, "run_kind": run_kind, "components": [],
        "record_policies": {topic: "full" for topic in topics}, **(extra_manifest or {}),
    }
    with module.McapRecorder(path, specs, manifest, config_bundle=config_bundle) as recorder:
        for topic, log_time_ns, payload in messages:
            assert log_time_ns % 1000 == 0, f"{topic}: {log_time_ns} ns is not a whole number of microseconds"
            recorder.write(topic, log_time_ns // 1000, payload)
    return path
