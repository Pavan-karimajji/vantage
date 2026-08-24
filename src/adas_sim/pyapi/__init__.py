# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`adas_sim.pyapi` -- SI-23, the whole scripting surface (`R-SIM-16`: every
capability usable in ~3 lines from a script or notebook). `Api` (`api.py`)
is the public surface; `views.py::ArrayView` is the zero-copy buffer view;
`engine.py` is the thin binding onto the engine invocation path.

Nothing outside `adas_sim.pyapi` (and `adas_sim.transport`, `SW-0017`, not
yet built -- `WP-27`'s Python transport binding) may import `ctypes` or open
a shared-memory handle (`ANL-SW-07`); this package is the one place that
rule permits it.
"""

from __future__ import annotations

from adas_sim.pyapi.api import Api
from adas_sim.pyapi.views import ArrayView, StaleViewError

#: The scripting-surface version -- semantic, and deliberately independent
#: of the module ABI (`resolve.component.ADAS_SIL_ABI_VERSION`) and the
#: plug-in API generation (`resolve.plugins.SUPPORTED_PLUGIN_API_*`,
#: `IMP-0360`'s three contracts, `WP-31`). Bump this when `Api`'s own
#: surface changes shape; the other two move on their own schedules and a
#: single combined number would make them look coupled when they are not.
API_VERSION = "1.0.0"

__all__ = ["Api", "ArrayView", "StaleViewError", "API_VERSION"]
