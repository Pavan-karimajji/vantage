# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The frame graph a `Prim.frame` names: `ego` (default, R-COORD-1), `world`,
`sensor:<id>`, `image:<cam>` (sim_api_reference.md §5, sim_architecture.md
§5.3).

**Scoped to name validation for this stage.** The full graph -- composing a
static part (from `model/`'s resolved poses) with a dynamic part
(`tick.pose`) into an actual transform -- needs `core/tick.py`'s `Tick`,
which does not exist until `S-B2`. What is testable and needed now (`Prim`
construction rejecting an unknown frame, `UT-A3-3`) is just: is this string a
frame name this graph knows about at all.
"""

from __future__ import annotations

#: The two frames with no parameter.
BASE_FRAMES = ("ego", "world")

#: The two parameterised frame families, named for error messages -- not
#: enumerable (a sensor/camera id is data), so `known_frame_kinds()` states
#: the *shape*, never a specific id.
PARAMETERISED_FRAME_PREFIXES = ("sensor:", "image:")


def known_frame_kinds() -> tuple[str, ...]:
    """The frame *kinds* this graph knows, for naming in an error (`N-8`):
    `ego`, `world`, `sensor:<id>`, `image:<cam>`."""
    return (*BASE_FRAMES, "sensor:<id>", "image:<cam>")


def is_known_frame(name: str) -> bool:
    """`ego`/`world` outright, or `sensor:<id>`/`image:<cam>` with a
    non-empty parameter."""
    if name in BASE_FRAMES:
        return True
    for prefix in PARAMETERISED_FRAME_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            return True
    return False


def parse_frame(name: str) -> tuple[str, str | None]:
    """`"ego"` -> `("ego", None)`; `"sensor:0"` -> `("sensor", "0")`. Callers
    that need the actual transform (a later stage) dispatch on the kind."""
    for prefix in PARAMETERISED_FRAME_PREFIXES:
        if name.startswith(prefix):
            return prefix[:-1], name[len(prefix):]
    return name, None
