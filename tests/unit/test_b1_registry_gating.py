# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 `scene/registry.py` `requires=` gating test: UT-B1-1
(docs/sim_implementation_plan.md). UT-B1-15 (`S-B1Δ`, `R-SIM-21`, arch
`D13`): a `self.<port>` `requires=` entry ambiguous across this run's known
ports raises at first use, naming the plug-in; one that simply matches
nothing yet (or matches but hasn't arrived this tick) stays a silent empty
result -- renumbered off `UT-B1-14`, already used by
`test_b1_df_layers.py`'s layer-id-prefix test (a numbering collision
introduced when the delta was added, caught while implementing)."""

from __future__ import annotations

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.core.history import FrameTree, HistoryView, LayerCtx
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.model.project import ProjectModel
from adas_sim.scene.registry import layer_provider

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _ctx_with_ports(ports: dict, *, known_ports: frozenset[str] = frozenset()) -> LayerCtx:
    tick = Tick(index=0, t_ns=0, dt_ns=0, ports=ports, pose=_POSE)
    return LayerCtx(
        model=ProjectModel.resolve(project="base"),
        history=HistoryView(_ticks=(tick,)),
        frames=FrameTree(_POSE),
        known_ports=known_ports,
    )


def test_a_tick_lacking_a_required_port_yields_no_layers_and_raises_nothing():
    """UT-B1-1."""
    calls = []

    @layer_provider("sim.test.gating.requires_port", requires=("sim.test.needed",))
    def _provider(ctx):
        calls.append(1)
        # If gating did not intercept, this would raise (the port is absent).
        ctx.history.last(1)[-1].port("sim.test.needed")
        return ()

    ctx_missing = _ctx_with_ports({})
    result = _provider(ctx_missing)
    assert result == ()
    assert calls == []  # the wrapped function itself was never called

    ctx_present = _ctx_with_ports({"sim.test.needed": PortValue(name="sim.test.needed", message=b"x", origin="measured")})
    _provider(ctx_present)
    assert calls == [1]


def test_an_ambiguous_self_ref_raises_naming_the_plugin():
    """UT-B1-15: more than one known port matching a `self.<port>` reference
    is an unambiguous same-run collision (never depends on a live component
    manifest to be real), so it raises at first use rather than silently
    drawing nothing or picking one arbitrarily."""

    @layer_provider("sim.test.gating.ambiguous_self_ref", requires=("self.needed",))
    def _provider(ctx):
        return ()

    known_ports = frozenset({"a.needed", "b.needed"})
    ctx = _ctx_with_ports({"a.needed": PortValue(name="a.needed", message=b"x", origin="measured")}, known_ports=known_ports)
    with pytest.raises(AuthoringError, match="_provider"):
        _provider(ctx)


def test_a_self_ref_matching_nothing_yields_a_named_unavailable_placeholder():
    """`AR-53`, supersedes `UT-B1-15`'s own original reading:
    zero matches -- this run's known ports contain nothing this `self.<port>`
    reference could ever resolve to -- used to stay a silent empty result on
    the reasoning that "does not exist" and "hasn't arrived this tick" were
    indistinguishable without a live manifest (`S-B1Δ`). That reasoning
    expired at `S-C1d`: manifests are live, so a zero-match placeholder
    layer is now returned instead, named and carrying no prims, so the
    layer list can say "unavailable" rather than looking identical to
    "never fired". The wrapped function itself is still never called --
    there is nothing for it to read."""
    calls = []

    @layer_provider("sim.test.gating.unmatched_self_ref", requires=("self.needed",))
    def _provider(ctx):
        calls.append(1)
        return ()

    ctx = _ctx_with_ports({}, known_ports=frozenset({"a.other"}))
    result = _provider(ctx)
    assert len(result) == 1
    assert result[0].id == "sim.test.gating.unmatched_self_ref"
    assert result[0].prims == ()
    assert result[0].unavailable is not None and "self.needed" in result[0].unavailable
    assert calls == []


def test_a_resolved_self_ref_absent_this_tick_yields_no_layers_and_raises_nothing():
    """The port genuinely exists this run (resolves unambiguously) but has
    not arrived on this particular tick -- a legitimate empty result, never
    conflated with "does not exist" (arch `D13`)."""
    calls = []

    @layer_provider("sim.test.gating.late_self_ref", requires=("self.needed",))
    def _provider(ctx):
        calls.append(1)
        return ()

    ctx = _ctx_with_ports({}, known_ports=frozenset({"a.needed"}))
    result = _provider(ctx)
    assert result == ()
    assert calls == []
