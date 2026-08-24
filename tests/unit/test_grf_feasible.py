# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-23`, `UT-GRF-27` (`graph/feasible.py`).
`UT-GRF-27` (`F-INDEX`) drives `RecordingIndex`/`ModuleManifest` built by
hand, no file on disk and no library present -- exactly the shape these two
types exist for (`IMP-0411`'s own consumer-side-only scope, see this
module's own top note)."""

from __future__ import annotations

from adas_sim.graph.feasible import ModuleManifest, RecordingIndex, RecordingTopic, feasible_cuts
from adas_sim.resolve.component import PortSpec


# ---------------------------------------------------------------------------
# UT-GRF-23 -- SW-0185: compute feasible cuts from the topic index with
# nothing executed
# ---------------------------------------------------------------------------


def test_feasible_stage_reports_no_missing_ports():
    index = RecordingIndex(topics={"objects": RecordingTopic(proto_type="test.Objects")})
    manifests = {"perception": ModuleManifest(name="perception", outputs=(PortSpec(name="objects", proto_type="test.Objects"),))}

    results = feasible_cuts(index, manifests)

    assert len(results) == 1
    assert results[0].stage == "perception"
    assert results[0].feasible is True
    assert results[0].missing == ()


def test_a_proto_type_mismatch_is_reported_naming_both_types():
    index = RecordingIndex(topics={"objects": RecordingTopic(proto_type="test.Objects.v1")})
    manifests = {"perception": ModuleManifest(name="perception", outputs=(PortSpec(name="objects", proto_type="test.Objects.v2"),))}

    result = feasible_cuts(index, manifests)[0]

    assert result.feasible is False
    assert "test.Objects.v1" in result.missing[0]
    assert "test.Objects.v2" in result.missing[0]


def test_a_missing_topic_with_no_declared_reason_gets_a_generic_one():
    index = RecordingIndex()
    manifests = {"perception": ModuleManifest(name="perception", outputs=(PortSpec(name="objects", proto_type="test.Objects"),))}

    result = feasible_cuts(index, manifests)[0]

    assert result.feasible is False
    assert "not provided by this recording" in result.missing[0]


def test_a_missing_topic_with_a_declared_absent_reason_names_it():
    index = RecordingIndex(absent={"egoDyn": "never recorded by this family"})
    manifests = {"vdy": ModuleManifest(name="vdy", outputs=(PortSpec(name="egoDyn", proto_type="test.VehDyn"),))}

    result = feasible_cuts(index, manifests)[0]

    assert "egoDyn" in result.missing[0]
    assert "never recorded by this family" in result.missing[0]


def test_nothing_is_opened_or_executed_computing_feasibility():
    """`SW-0177`-style purity check, applied to `feasible_cuts`: it takes
    only plain data and returns plain data -- calling it twice with the
    same inputs must be side-effect-free and produce identical output."""
    index = RecordingIndex(topics={"objects": RecordingTopic(proto_type="test.Objects")})
    manifests = {"perception": ModuleManifest(name="perception", outputs=(PortSpec(name="objects", proto_type="test.Objects"),))}

    assert feasible_cuts(index, manifests) == feasible_cuts(index, manifests)


# ---------------------------------------------------------------------------
# UT-GRF-27 -- SW-0411: coherence/feasibility/measured-validation/family-
# matching against a HAND-WRITTEN index and manifest set, no file, no
# library. (This test file covers the feasible_cuts slice only -- coherence
# itself is already proven index-free in test_grf_coherence.py, since
# Pipeline/coherence.classify() never open a file either.)
# ---------------------------------------------------------------------------


def test_feasible_cuts_over_a_multi_stage_hand_written_index_and_manifest_set():
    index = RecordingIndex(
        topics={
            "objects": RecordingTopic(proto_type="test.Objects", origin="measured"),
            "egoDyn": RecordingTopic(proto_type="test.VehDyn", origin="measured"),
        },
        absent={"radar_raw": "never recorded by this family"},
    )
    manifests = {
        "vdy": ModuleManifest(name="vdy", outputs=(PortSpec(name="egoDyn", proto_type="test.VehDyn"),)),
        "perception": ModuleManifest(name="perception", outputs=(PortSpec(name="objects", proto_type="test.Objects"),)),
        "radar_fusion": ModuleManifest(name="radar_fusion", outputs=(PortSpec(name="radar_raw", proto_type="test.Radar"),)),
    }

    results = {r.stage: r for r in feasible_cuts(index, manifests)}

    assert results["vdy"].feasible is True
    assert results["perception"].feasible is True
    assert results["radar_fusion"].feasible is False
    assert "never recorded by this family" in results["radar_fusion"].missing[0]
