# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 severed-chain developer-surface tests (`docs/sim_implementation_plan.md`):
`UT-D6-5` (auto-close flips only the intervening stages, undo restores the
exact prior modes) and `UT-D6-6` (forcing the gap open yields exactly one
orphan-stage warning naming the stage). Detection itself (`severed_chains`)
and `with_mode`'s basic impl:/inputs: preservation are already covered by
`test_c1c_pipeline.py` -- this stage's own instruction is "verify, do not
rebuild" (`sim_implementation_plan.md`'s S-D6 scope-correction note), and
`UT-D6-6` surfaced a REAL gap while verifying: `with_mode(close_gaps=False)`
silently left an orphan stage with no warning at all. Fixed in
`contracts/pipeline.py` alongside these tests, not before them.

**Fixture topology, and why.** `R-SIM-10`'s own words: "setting a stage to
`simulate` closes the gap by default (intervening stages flip to `simulate`
too, undoably)." The non-trivial case needs the stage being TOGGLED to be
different from the stage auto-close FLIPS -- so this fixture starts
`upstream(simulate) -> measured(measured) -> downstream(measured)` (both
`measured` and `downstream` already off the live chain) and toggles
`downstream` back to `simulate`. That strands `measured` in the middle
(still injecting from a recording while both its neighbours are live) --
exactly `R-SIM-10`'s "intervening stage," and NOT the stage `with_mode` was
called on.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.errors import ProvenanceWarning


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


def _write_pipeline(tmp_path: Path, stages: list[dict]) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "test", "stages": stages}, sort_keys=False), encoding="utf-8")
    return path


def _pre_severed_chain(tmp_path: Path) -> Pipeline:
    """upstream(simulate) -> measured(measured) -> downstream(measured) --
    `downstream` starts already off the live chain, so toggling IT back to
    `simulate` is what creates the severed chain the tests below exercise."""
    upstream = _manifest(component="upstream", outputs=[PortSpec(name="out", proto_type="test.A")])
    measured = _manifest(
        component="measured", inputs=[PortSpec(name="in", proto_type="test.A")],
        outputs=[PortSpec(name="out", proto_type="test.B")],
    )
    downstream = _manifest(component="downstream", inputs=[PortSpec(name="in", proto_type="test.B")])
    stages = [
        {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}},
        {"name": "measured", "mode": "measured", "impl": "stub:measured", "inputs": {"in": "upstream.out"}},
        {"name": "downstream", "mode": "measured", "impl": "stub:downstream", "inputs": {"in": "measured.out"}},
    ]
    path = _write_pipeline(tmp_path, stages)
    return Pipeline.load(path, components={
        "upstream": _stub("upstream", upstream), "measured": _stub("measured", measured),
        "downstream": _stub("downstream", downstream),
    })


def test_auto_close_flips_only_the_intervening_stage_and_undo_restores_exact_prior_modes(tmp_path):
    """UT-D6-5."""
    pipeline = _pre_severed_chain(tmp_path)
    assert pipeline.severed_chains() == ()  # baseline: measured->downstream both off-chain, nothing severed

    reconnected = pipeline.with_mode("downstream", "simulate")  # severs upstream -> measured -> downstream
    by_name = {s.name: s for s in reconnected.stages}
    assert by_name["upstream"].mode == "simulate"      # untouched -- never involved
    assert by_name["measured"].mode == "simulate"       # auto-closed: the INTERVENING stage, not the one toggled
    assert by_name["downstream"].mode == "simulate"      # exactly what we asked with_mode for
    assert reconnected.severed_chains() == ()

    # undo: the ORIGINAL pipeline object is untouched throughout
    # (R-SIM-17-style undoability) -- re-reading it restores the exact prior
    # modes with no separate "undo" call needed.
    assert pipeline.stages[0].mode == "simulate"
    assert pipeline.stages[1].mode == "measured"
    assert pipeline.stages[2].mode == "measured"


def test_forcing_the_gap_open_yields_exactly_one_orphan_warning_naming_the_stage(tmp_path):
    """UT-D6-6. This is the real gap `with_mode` had before this stage:
    close_gaps=False silently left "measured" computed-but-not-consumed,
    with no warning at all."""
    pipeline = _pre_severed_chain(tmp_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        forced_open = pipeline.with_mode("downstream", "simulate", close_gaps=False)

    assert forced_open.severed_chains() != ()  # the gap really is still open
    by_name = {s.name: s for s in forced_open.stages}
    assert by_name["measured"].mode == "measured"  # NOT auto-flipped -- close_gaps=False means it, deliberately
    assert by_name["downstream"].mode == "simulate"  # what we asked for still happens

    provenance_warnings = [w for w in caught if issubclass(w.category, ProvenanceWarning)]
    assert len(provenance_warnings) == 1
    assert "measured" in str(provenance_warnings[0].message)


def test_close_gaps_false_with_nothing_severed_warns_nothing(tmp_path):
    """The warning fires only when there is something to warn about --
    close_gaps=False on a change that severs nothing stays silent, not a
    warning about an empty set."""
    pipeline = _pre_severed_chain(tmp_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Flipping "upstream" (the very start of the chain, no producer of
        # its own) to "measured" cannot strand anything.
        result = pipeline.with_mode("upstream", "measured", close_gaps=False)

    assert result.severed_chains() == ()
    assert [w for w in caught if issubclass(w.category, ProvenanceWarning)] == []
