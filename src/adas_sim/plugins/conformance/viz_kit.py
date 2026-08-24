# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Conformance kit for the `"visualization"` extension point (`SW-0358`).

A layer provider registers itself by import (`scene.registry.
layer_provider`, `R-VAR-2` extended from components to layers) -- there is
no core roster to add an entry to. This kit checks that a given
`layer_id` is actually reachable through `scene.registry.
registered_providers()` and that its entry carries the shape every
consumer (`runspec`/`graph`/the layer resolver) depends on: a callable
`func`, and the `module`/`qualname` a `sim explain` answer names.

The shipped template plug-in for this point is `plugins.conformance.
templates.register_template_layer_provider` -- a minimal, component-free
layer (`R-SIM-1`: this framework's own `src/` never names a real
component) any new component's plug-in author can read start to finish."""

from __future__ import annotations

from adas_sim.plugins.conformance.result import ConformanceResult
from adas_sim.scene.registry import registered_providers


def check_visualization(layer_id: str) -> ConformanceResult:
    problems: list[str] = []
    entry = registered_providers().get(layer_id)
    if entry is None:
        return ConformanceResult(ok=False, problems=(f"{layer_id!r} is not registered (registration by import only)",))
    if not callable(entry.func):
        problems.append("registered entry's `func` is not callable")
    if not entry.module or not entry.qualname:
        problems.append("registered entry is missing `module`/`qualname` (what `sim explain` names)")
    return ConformanceResult(ok=not problems, problems=tuple(problems))
