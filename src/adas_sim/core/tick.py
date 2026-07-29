# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`PortValue`, `Tick` (sim_api_reference.md §2.2). Frozen at S-B2, moved
ahead of `S-B1` in the actual build order (`sim_implementation_plan.md`'s own
finding: `S-B1`'s tests need `Tick`/`LayerCtx`, which are S-B2 deliverables,
and S-B2 has no dependency back on S-B1 -- confirmed with the user before
writing code).

**Note on precedence.** `sim_architecture.md` §5.3's own `Tick` sketch splits
ports into three separate mappings (`stimulus`/`observation`/`truth`); this
stage's own checklist line says "api reference §2.2" explicitly, so the
unified `ports: Mapping[str, PortValue]` + `.port(name)` shape below is what
is implemented -- and it does not lose information, because `PortValue.origin`
already carries the measured/truth/mocked/simulated/overridden tag the
three-way split existed to express (R-SIM-12).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from adas_sim.core.errors import AuthoringError

#: Extended with "unknown" beyond api reference §2.2's literal five values,
#: mirroring `io.base.Provenance` (R-SIM-6): a Tick built from a no-meta
#: recording has ports whose origin is honestly unknown, not fabricated.
Origin = Literal["measured", "truth", "mocked", "simulated", "overridden", "unknown"]


@dataclass(frozen=True, slots=True)
class Pose2D:
    """Ego pose in the world frame (R-COORD-1)."""

    x_m: float
    y_m: float
    yaw_rad: float

    def __repr__(self) -> str:
        return f"<Pose2D x_m={self.x_m:.2f} y_m={self.y_m:.2f} yaw_rad={self.yaw_rad:.3f}>"


@dataclass(frozen=True, slots=True)
class PortValue:
    name: str  # fully qualified, N-2: "<component>.<port>"
    message: Any  # a decoded protobuf message, raw bytes if no schema, or None when invalid
    origin: Origin
    valid: bool = True
    updated: bool = True  # False when held from an earlier tick (multi-rate)
    age_s: float = 0.0  # 0.0 when updated; else time since production

    def __repr__(self) -> str:
        return f"<PortValue {self.name!r} origin={self.origin} valid={self.valid} age_s={self.age_s:.3f}>"


@dataclass(frozen=True, slots=True)
class Tick:
    index: int
    t_ns: int  # integer, accumulated from dt_ns -- never a float sum
    dt_ns: int
    ports: Mapping[str, PortValue]  # keyed by fully qualified name
    pose: Pose2D  # ego pose in the world frame

    def __post_init__(self) -> None:
        # A MappingProxyType, not a plain dict: freezing the Tick dataclass
        # only blocks `tick.ports = ...`, not `tick.ports["x"] = y` -- the
        # in-place mutation UT-B2-11 requires to raise (Session immutability).
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))

    @property
    def t_s(self) -> float:
        return self.t_ns / 1e9  # derived, never fed back

    def port(self, name: str) -> PortValue:
        try:
            return self.ports[name]
        except KeyError:
            raise AuthoringError(
                expected=f"a port named {name!r}",
                found=f"available ports: {sorted(self.ports)}",
                where="adas_sim.core.tick.Tick.port",
                hint="check the port name against the component's manifest",
            ) from None

    def __repr__(self) -> str:
        return f"<Tick index={self.index} t_ns={self.t_ns} ports={len(self.ports)}>"
