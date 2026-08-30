# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`pyapi.engine` -- the thin binding onto the engine invocation path
(`DD-03`), and message classes built at run time from a manifest's
`FileDescriptorSet` with zero generated bindings and zero `interfaces`
checkout (`SW-0240`, `R-SIM-11`).

**Today's real shape, stated rather than hidden:** `simcore` is built as a
static library only -- no CMake target in this tree exports
`simcore/abi/simcore.h`'s C ABI as a shared object (`engine/bridge.py`'s own
note), so there is nothing yet for an in-process `ctypes` binding to load.
`run` below is therefore a direct ALIAS for `engine.bridge.run_engine`
-- never a second function whose own body calls it again, which is exactly
what `ANL-SW-41`'s "one invocation shape" check (`test_engine_bridge_
run_engine_has_exactly_one_call_site`) polices -- under a name a script
imports through `pyapi` rather than reaching into `adas_sim.engine`
directly. One process per invocation, exactly what every existing rewired
call site (`cli/resim.py`, `orchestrate/worker.py`, `check/runner.py`, and
-- until the retiring Python GUI's own `player/shell/qt_window.py` was
deleted, `SM-12` -- its Run button) already pays (`WP-15b`, `IMP-0422`).
The day a shared-library target exists, `engine.bridge.
run_engine` itself gains the in-process implementation; `pyapi.engine.run`
stays the same alias and every script already importing it is unaffected.

`resolve_message_classes`/`probe_manifest` are re-exported, not
reimplemented (`R-BUILD`'s no-second-implementation principle): the real
mechanism already lives in `resolve/component.py`/`resolve/probe.py`
(`SW-0240`'s `Now.` field -- "Already true"), landed for the probe path in
earlier work packages this session. `pyapi` is where a script reaches it
without knowing that path exists.
"""

from __future__ import annotations

from collections.abc import Mapping

from adas_sim.engine.bridge import EngineRunResult, resolve_simengine_executable, run_engine
from adas_sim.resolve.component import ADAS_SIL_ABI_VERSION, ComponentManifest, resolve_message_classes
from adas_sim.resolve.probe import probe_manifest

__all__ = [
    "EngineRunResult", "run", "resolve_simengine_executable",
    "ComponentManifest", "ADAS_SIL_ABI_VERSION", "probe_manifest", "resolve_message_classes",
]


#: `ANL-SW-41`/`test_engine_bridge_run_engine_has_exactly_one_call_site`:
#: `engine.bridge.run_engine` is the true bottom of the stack, funnelled
#: through by every higher-level caller -- an ALIAS, deliberately, never a
#: second function whose own body invokes it a second time. `pyapi.engine.
#: run(spec_path, ...)` reaches the exact same one call site
#: `orchestrate/run.py::invoke_engine` and the rewired `WP-15b` callers do.
run = run_engine


def message_classes_for(manifest: ComponentManifest) -> Mapping[str, type]:
    """`SW-0240`: message classes built at run time from `manifest`'s
    `FileDescriptorSet` -- no generated bindings required, ever (`R-SIM-11`).
    A thin re-export of `resolve.component.resolve_message_classes`."""
    return resolve_message_classes(manifest)
