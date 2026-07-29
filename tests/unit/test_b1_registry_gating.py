# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 `scene/registry.py` `requires=` gating test: UT-B1-1
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

from adas_sim.core.history import FrameTree, HistoryView, LayerCtx
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.model.project import ProjectModel
from adas_sim.scene.registry import layer_provider

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _ctx_with_ports(ports: dict) -> LayerCtx:
    tick = Tick(index=0, t_ns=0, dt_ns=0, ports=ports, pose=_POSE)
    return LayerCtx(
        model=ProjectModel.resolve(project="base"),
        history=HistoryView(_ticks=(tick,)),
        frames=FrameTree(_POSE),
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
