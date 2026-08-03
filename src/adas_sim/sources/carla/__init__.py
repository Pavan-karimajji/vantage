# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The CARLA `Source` (`sim_implementation_plan.md` S-C2 slice 5,
`sim_architecture.md`'s own migration table). Ported from
`modules/df/tools/carla/carla_bridge.py` -- the connect/spawn/drive-actors
engine, verbatim in behaviour (`R-STYLE-2`: tidiness is not the point,
behavioural equivalence is). The old script's direct-dispatch calling loop
and its per-function console prints/on-screen indicators do NOT move here --
those are the old positional-ABI harness, out of bounds for `modules/sim`
regardless (`R-SIM-1`).

Every module here defers `import carla` to inside its functions/methods
(never at module scope): `sources.carla` must be importable with no `carla`
package installed (matching `cli/view.py`'s Qt deferral, `UT-A1-2`'s own
discipline) -- only actually driving a live server needs it.
"""

from __future__ import annotations

from adas_sim.sources.carla.source import CarlaSource

__all__ = ["CarlaSource"]
