# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-12` tests: `UT-manifest-03`, `UT-refrun-01`..
`UT-refrun-03` (`docs/v2/parity/PARITY_Test_Spec.md` §5.4/5.12).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from adas_sim.engine.refrun import RefRun, first_divergence, topic_for
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent
from adas_sim.runspec.manifest import build_manifest


# ---------------------------------------------------------------------------
# 5.4 manifest
# ---------------------------------------------------------------------------


def _one_stage_pipeline(tmp_path: Path, *, stage_name: str = "df") -> Pipeline:
    manifest = ComponentManifest(
        component=stage_name, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
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


def test_the_reference_hash_is_written_only_when_there_is_one_ut_manifest_03(tmp_path):
    """UT-manifest-03."""
    pipeline = _one_stage_pipeline(tmp_path)

    side_by_side = build_manifest(
        pipeline=pipeline, run_kind="resim", source_kind="mcap", reference_build_sha256="b" * 64,
    )
    assert side_by_side.reference_build_sha256 == "b" * 64  # .c1

    ordinary = build_manifest(pipeline=pipeline, run_kind="resim", source_kind="mcap")
    assert ordinary.reference_build_sha256 is None  # .c2: omitted, never an empty string


# ---------------------------------------------------------------------------
# 5.12 refrun
# ---------------------------------------------------------------------------


class _Stub:
    """`F-EXEC-STUB`: counts calls and records exactly what it received."""

    def __init__(self, transform=None) -> None:
        self.calls = 0
        self.received: list[Mapping] = []
        self._transform = transform or (lambda inputs: dict(inputs))

    def exec(self, inputs):
        self.calls += 1
        self.received.append(inputs)
        return self._transform(inputs)


def test_one_input_set_two_builds_ut_refrun_01():
    """UT-refrun-01."""
    candidate = _Stub()
    reference = _Stub()
    run = RefRun(candidate=candidate, reference=reference)

    for tick in range(3):
        run.tick({"objects": {"count": tick}})

    assert candidate.calls == 3 and reference.calls == 3
    for candidate_received, reference_received in zip(candidate.received, reference.received):
        assert candidate_received == reference_received  # .c1
        assert candidate_received is reference_received  # structural, not just equal (SW-0048/IMP-0050)


def test_the_first_difference_is_kept_ut_refrun_02():
    """UT-refrun-02."""
    port_order = ["objects", "egoDyn"]
    candidate_ticks = [
        {"objects": {"count": 1}, "egoDyn": {"vx": 10.0}},
        {"objects": {"count": 2}, "egoDyn": {"vx": 11.0}},
    ]
    reference_ticks = [
        {"objects": {"count": 1}, "egoDyn": {"vx": 10.0}},
        {"objects": {"count": 2}, "egoDyn": {"vx": 999.0}},  # injected difference
    ]

    divergence = first_divergence(port_order, candidate_ticks, reference_ticks)

    assert divergence is not None
    assert (divergence.tick, divergence.port, divergence.field) == (1, "egoDyn", "vx")  # .c1
    assert divergence.candidate_value == 11.0 and divergence.reference_value == 999.0


def test_both_builds_outputs_are_separable_ut_refrun_03():
    """UT-refrun-03."""
    port_order = ["objects"]
    candidate_ticks = [{"objects": {"count": 1}}]
    reference_ticks = [{"objects": {"count": 1}}]

    # Record both under role-prefixed topics into one flat store.
    store: dict[str, list] = {}
    store.setdefault(topic_for("candidate", "objects"), []).append(candidate_ticks[0]["objects"])
    store.setdefault(topic_for("reference", "objects"), []).append(reference_ticks[0]["objects"])

    assert set(store) == {"candidate.objects", "reference.objects"}  # separable, not merged

    # Recompute the comparison from the store alone.
    recomputed_candidate = [{"objects": store["candidate.objects"][0]}]
    recomputed_reference = [{"objects": store["reference.objects"][0]}]
    assert first_divergence(port_order, recomputed_candidate, recomputed_reference) is None  # .c1
