# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-02` (`launcher/classify.py`,
`SW-0342`). Same four-stage chain fixture as `test_grf_coherence.py`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.graph import coherence, waiver
from adas_sim.graph.pipeline import Pipeline
from adas_sim.launcher.classify import LaunchBlocked, classify, remedies_for
from adas_sim.launcher.model import Selection
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec

_CHAIN_NAMES = ("vdy", "perception", "fusion", "aeb")


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


def _chain_pipeline(tmp_path: Path, modes_: tuple[str, str, str, str]) -> Pipeline:
    stages = []
    components = {}
    for i, (name, mode) in enumerate(zip(_CHAIN_NAMES, modes_)):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": mode, "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    any_measured = "measured" in modes_

    class _FakeRecording:
        def topics(self):
            return {"out": None} if any_measured else {}

    return Pipeline.load(path, components=components, recording=_FakeRecording() if any_measured else None)


def _selection(tmp_path: Path, modes_: tuple[str, str, str, str]) -> Selection:
    return Selection(base_pipeline=_chain_pipeline(tmp_path, modes_))


# ---------------------------------------------------------------------------
# UT-LNC-02 -- SW-0342: one verdict per selection, and what Launch does
# ---------------------------------------------------------------------------


def test_normal_selection_can_launch(tmp_path):
    result = classify(_selection(tmp_path, ("simulate",) * 4).working_pipeline)
    assert result.findings == ()
    assert result.blocking == ()
    assert result.can_launch is True


def test_orphan_selection_can_still_launch(tmp_path):
    # perception/fusion/aeb all measured -- the walk from perception never
    # reaches a simulate stage, so vdy's live output feeds nothing: ORPHAN,
    # never blocking (SW-0182).
    result = classify(_selection(tmp_path, ("simulate", "measured", "measured", "measured")).working_pipeline)
    assert any(f.verdict is coherence.Verdict.ORPHAN for f in result.findings)
    assert result.blocking == ()
    assert result.can_launch is True


def test_broken_selection_blocks_launch(tmp_path):
    selection = _selection(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    selection = selection.set_mode("perception", "measured")  # vdy->measured->measured->aeb(simulate)

    result = classify(selection.working_pipeline)
    assert any(f.verdict is coherence.Verdict.BROKEN for f in result.findings)
    assert result.blocking != ()
    assert result.can_launch is False


def test_remedies_for_a_broken_finding_matches_the_graph_packages_own(tmp_path):
    selection = _selection(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    selection = selection.set_mode("perception", "measured")

    result = classify(selection.working_pipeline)
    broken = result.blocking[0]
    remedies = remedies_for(broken)
    assert remedies == coherence.remedies(broken)
    assert remedies[0].suggested is True


def test_a_granted_waiver_unblocks_launch(tmp_path):
    selection = _selection(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    selection = selection.set_mode("perception", "measured")

    findings = coherence.classify(selection.working_pipeline)
    broken = next(f for f in findings if f.verdict is coherence.Verdict.BROKEN)
    granted = waiver.waive(broken, "known-good bench recording, reviewed offline")

    result = classify(selection.working_pipeline, (granted,))
    assert result.blocking == ()
    assert result.can_launch is True


def test_launch_blocked_names_the_same_finding_render_finding_would(tmp_path):
    selection = _selection(tmp_path, ("simulate", "simulate", "measured", "simulate"))
    selection = selection.set_mode("perception", "measured")

    result = classify(selection.working_pipeline)
    exc = LaunchBlocked(result.blocking)
    assert coherence.render_finding(result.blocking[0]) in str(exc)
    assert exc.exit_code == 3
