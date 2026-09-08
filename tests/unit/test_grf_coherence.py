# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-12` through `UT-GRF-17` (`graph/
coherence.py`, the "one correctness defect" fix: a transitive closure in
place of `severed_chains()`'s one-hop scan). Four-stage chain fixture
(`vdy -> perception -> fusion -> aeb`) matches `F-CHAIN4`'s own shape
(`SIM_Software_Test_Spec_v0.1.md`), with every mode combination reachable
including the concept's own broken case: `simulate -> measured -> measured
-> simulate`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.graph import coherence
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


#: `vdy -> perception -> fusion -> aeb`, a linear chain -- each stage
#: consumes the previous one's single `out` port. `modes` is a 4-tuple in
#: that order.
_CHAIN_NAMES = ("vdy", "perception", "fusion", "aeb")


def _chain_pipeline(tmp_path: Path, modes: tuple[str, str, str, str]) -> Pipeline:
    stages = []
    components = {}
    for i, (name, mode) in enumerate(zip(_CHAIN_NAMES, modes)):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": mode, "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    # `_validate_wiring`'s `measured` check reads bare output PORT names
    # (`manifest.outputs[].name`, here always "out") against the recording's
    # topic set -- not stage-qualified -- so one topic covers every measured
    # stage in this fixture.
    any_measured = "measured" in modes

    class _FakeRecording:
        def topics(self):
            return {"out": None} if any_measured else {}

    return Pipeline.load(path, components=components, recording=_FakeRecording() if any_measured else None)


# ---------------------------------------------------------------------------
# UT-GRF-12/13 -- SW-0174/SW-0175: transitive ancestors/descendants
# ---------------------------------------------------------------------------


def test_ancestors_is_the_full_transitive_closure(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    assert coherence.ancestors(pipeline, "aeb") == frozenset({"vdy", "perception", "fusion"})
    assert coherence.ancestors(pipeline, "vdy") == frozenset()


def test_descendants_is_the_full_transitive_closure(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    assert coherence.descendants(pipeline, "vdy") == frozenset({"perception", "fusion", "aeb"})
    assert coherence.descendants(pipeline, "aeb") == frozenset()


# ---------------------------------------------------------------------------
# UT-GRF-14 -- SW-0176: exactly three outcomes, constructed one graph each
# ---------------------------------------------------------------------------


def test_classify_is_empty_normal_when_every_hop_is_live(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    assert coherence.classify(pipeline) == ()


def test_classify_finds_an_orphan_when_nothing_downstream_is_simulate(tmp_path):
    # vdy computes live; perception/fusion/aeb are all measured -- vdy's
    # output feeds a measured stage with no simulate stage anywhere
    # downstream of it.
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "measured"))
    findings = coherence.classify(pipeline)
    assert len(findings) == 1
    assert findings[0].verdict is coherence.Verdict.ORPHAN
    assert findings[0].stale == ("perception",)
    assert findings[0].landing is None


def test_classify_finds_the_transitive_broken_chain_the_one_hop_scan_misses(tmp_path):
    """The package's own named defect: `simulate -> measured -> measured ->
    simulate`. `severed_chains()` (one-hop) finds nothing here -- neither
    `measured` stage's immediate neighbour is the right mode for a one-hop
    match. `classify()` must find it."""
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))

    # Prove the one-hop scan really does miss this -- the defect this
    # module exists to fix, not a hypothetical.
    assert pipeline.severed_chains() == ()

    findings = coherence.classify(pipeline)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.verdict is coherence.Verdict.BROKEN
    assert finding.stale == ("perception", "fusion")
    assert finding.path == ("vdy", "perception", "fusion", "aeb")
    assert finding.landing == "aeb"


def test_classify_still_finds_the_one_hop_broken_chain(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "simulate", "simulate"))
    findings = coherence.classify(pipeline)
    assert len(findings) == 1
    assert findings[0].verdict is coherence.Verdict.BROKEN
    assert findings[0].landing == "fusion"


# ---------------------------------------------------------------------------
# UT-GRF-15 -- SW-0177: classify takes a Pipeline and nothing else
# ---------------------------------------------------------------------------


def test_classify_is_callable_with_only_a_pipeline(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    coherence.classify(pipeline)  # no reader, no loader, no path -- must not raise


# ---------------------------------------------------------------------------
# UT-GRF-16 -- SW-0178: broken chain names the path and the landing point
# ---------------------------------------------------------------------------


def test_render_finding_names_every_stale_stage_and_the_landing(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    finding = coherence.classify(pipeline)[0]

    text = coherence.render_finding(finding)

    assert "perception" in text
    assert "fusion" in text
    assert "aeb" in text  # the landing point


def test_render_finding_orphan_names_the_stale_stage(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "measured"))
    finding = coherence.classify(pipeline)[0]

    text = coherence.render_finding(finding)

    assert "perception" in text


# ---------------------------------------------------------------------------
# UT-GRF-17 -- SW-0179: remedies, smallest change first, applying it clears
# the finding
# ---------------------------------------------------------------------------


def test_remedy_promotes_every_stale_stage_and_is_marked_suggested(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    finding = coherence.classify(pipeline)[0]

    remedy_set = coherence.remedies(finding)

    assert len(remedy_set) == 1
    assert remedy_set[0].suggested
    assert remedy_set[0].promote == ("perception", "fusion")


def test_applying_the_suggested_remedy_produces_a_passing_classification(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "simulate"))
    finding = coherence.classify(pipeline)[0]
    remedy = coherence.remedies(finding)[0]

    fixed = pipeline
    for name in remedy.promote:
        fixed = fixed.with_mode(name, "simulate")

    assert coherence.classify(fixed) == ()


def test_orphan_has_no_remedy(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "measured", "measured", "measured"))
    finding = coherence.classify(pipeline)[0]
    assert coherence.remedies(finding) == ()


def test_normal_has_no_finding_to_remedy(tmp_path):
    pipeline = _chain_pipeline(tmp_path, ("simulate", "simulate", "simulate", "simulate"))
    assert coherence.classify(pipeline) == ()
