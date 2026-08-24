# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Conformance kit for the `"module"` extension point (`SW-0358`).

A component onboards by resolving a `PluginBundle` from its own `sim/`
directory (`resolve.plugins.PluginBundle.resolve`, `R-SIM-20`) -- there is
no core roster of components to edit (`R-VAR-2`). This kit checks that an
already-resolved bundle carries the shape every consumer needs: a non-empty
`component` name, an `api` generation within the player's own supported
range, and at least one `provides:` entry that actually imports.

The shipped template plug-in for this point is a `plugin.yaml` + one layer
module built by `plugins.conformance.templates.write_template_plugin_dir`
-- the same minimal shape `resolve/plugins.py`'s own docstring describes,
authored fresh for this kit rather than pointing at a real component's
`modules/<name>/sim/` (this framework's own `src/` may never name one,
`R-SIM-1`)."""

from __future__ import annotations

from adas_sim.plugins.conformance.result import ConformanceResult
from adas_sim.resolve.plugins import SUPPORTED_PLUGIN_API_MAX, SUPPORTED_PLUGIN_API_MIN, PluginBundle


def check_module(bundle: PluginBundle) -> ConformanceResult:
    problems: list[str] = []
    if not bundle.component:
        problems.append("`component` is empty")
    if not (SUPPORTED_PLUGIN_API_MIN <= bundle.api <= SUPPORTED_PLUGIN_API_MAX):
        problems.append(f"api={bundle.api} outside [{SUPPORTED_PLUGIN_API_MIN}, {SUPPORTED_PLUGIN_API_MAX}]")
    if not bundle.provides:
        problems.append("`provides` is empty -- nothing for this module to contribute")
    if not problems:
        try:
            bundle.import_modules()
        except Exception as exc:  # noqa: BLE001 -- reported as a conformance finding, not raised
            problems.append(f"import_modules() raised: {exc!r}")
    return ConformanceResult(ok=not problems, problems=tuple(problems))
