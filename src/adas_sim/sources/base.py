# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Source` Protocol + `Scenario` (`sim_api_reference.md` §8, `S-C2`).

A `Source` is the production-side counterpart to `SilComponent`
(`contracts/component.py`): where a `SilComponent` executes a stage, a
`Source` drives `source.*` stimulus -- live (`sources/carla`) or scripted
(`sources/synthetic.py`). `emits()` is `Source`'s own manifest analogue:
`Pipeline.load`'s `source.*` wiring is validated against it exactly as a
stage-to-stage reference is validated against a producer's `PortSpec.name`s
(`contracts/pipeline.py` `_validate_wiring`), so a pipeline asking a source
for more than it can produce is a load error naming both ends (`R-SIM-10`).

`poll()` returns raw serialized bytes per port, unqualified (no `source.`
prefix) -- exactly the shape `Pipeline.exec`/`step`'s `stimulus:` parameter
already expects, since `source.*` is split into `("source", port)` before
either function ever looks at the map (`contracts/pipeline.py`
`_split_ref`).

`Scenario` (`contracts.scenario.Scenario`, `S-C3`) is the schema-v2 type --
this module's own interim `{name, raw}` wrapper (`S-C2`'s stand-in, before
`S-C3` existed) has been retired in its favour, since `S-C3` is exactly the
"next stage [that] owns that design" this docstring used to point at.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Protocol

from adas_sim.contracts.scenario import Scenario

__all__ = ["Scenario", "Source"]


class Source(Protocol):
    """`sim_api_reference.md` §8. `name` identifies the source in
    diagnostics and the run manifest's `source_kind` field
    (`io.base.RunManifest`, e.g. `"carla"` / `"synthetic"`)."""

    name: ClassVar[str]

    def emits(self) -> frozenset[str]:
        """Port names this source can produce (unqualified -- no `source.`
        prefix), e.g. `{"gen_object_list", "veh_dyn", "veh_sig"}`. A
        pipeline's `source.<name>` reference to a port outside this set is
        a load error naming both the pipeline and this source
        (`R-SIM-10`)."""
        ...

    def start(self, scenario: Scenario) -> None:
        """Connects/spawns/resets for one scenario run. Called once before
        the first `poll()`."""
        ...

    def poll(self) -> Mapping[str, bytes]:
        """Advances one tick and returns this tick's stimulus, keyed by
        unqualified port name -- every name in `emits()` that has a value
        this tick. A name absent from the result is `valid=0` downstream,
        the same "absent port" convention `SilComponent`/`Pipeline` already
        use (`UT-C1c-12`)."""
        ...

    def stop(self) -> None:
        """Releases whatever `start()` acquired (actors, connections,
        processes). Always called, even after a `poll()` raised."""
        ...
