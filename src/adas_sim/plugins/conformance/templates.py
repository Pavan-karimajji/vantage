# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Shipped template plug-ins -- one per extension point (`SW-0358`'s own
Accept clause: *"each of the four is exercised by a shipped template
plug-in that passes its own conformance kit"*).

`"reader"`/`"exporter"` need no template of their own: `io.jsonl.
JsonlReader` and `io.csv.CsvWriter` are already real, already registered
codecs (`DD-04`'s one-implementation rule -- a second, parallel
"just for conformance" reader/writer would be exactly the duplication that
rule forbids), so `reader_kit`/`exporter_kit` exercise those directly.

`"visualization"`/`"module"` have no existing component-free equivalent --
every real layer/plug-in belongs to a component, and this framework's own
`src/` may never name one (`R-SIM-1`). The two functions below are that
template: minimal, real, registered by import alone, carrying no component
name anywhere in this file."""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.scene.registry import layer_provider, registered_providers
from adas_sim.scene.types import Layer
from adas_sim.session.history import LayerCtx

#: `SW-0359`: registered by import alone, the moment this module is first
#: imported -- no roster anywhere lists it. Guarded so importing this
#: module twice in one process (every test that needs the template) does
#: not hit `layer_provider`'s own duplicate-id refusal.
TEMPLATE_LAYER_ID = "conformance.template.marker"

if TEMPLATE_LAYER_ID not in registered_providers():

    @layer_provider(TEMPLATE_LAYER_ID, group="conformance")
    def _template_layer(ctx: LayerCtx) -> tuple[Layer, ...]:
        """The shipped template for the `"visualization"` extension point --
        needs no port (`requires=` empty), draws nothing (`Layer` with zero
        prims is legitimate: `"the algorithm did not fire"` vs `"nothing to
        draw"` is `Prim`-count's own distinction, not this template's job to
        demonstrate). A real component's own layer follows this same shape:
        one `@layer_provider`-decorated function, imported once."""
        return (Layer(id=TEMPLATE_LAYER_ID, group="conformance", prims=()),)


def write_template_plugin_dir(root: Path, *, component: str = "conformance_template") -> Path:
    """Writes the shipped template for the `"module"` extension point: a
    `plugin.yaml` + one `provides:` module, the same minimal shape
    `resolve/plugins.py`'s own docstring describes -- `resolve.plugins.
    PluginBundle.resolve(explicit=root)` reads it back like any real
    component's `sim/` directory. `component` is a parameter, never a
    literal naming a real component (`R-SIM-1`)."""
    plugin_dir = root / "sim"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"api": 1, "component": component, "provides": ["sim.layers.template"]}), encoding="utf-8",
    )
    layers_dir = plugin_dir / "layers"
    layers_dir.mkdir(exist_ok=True)
    (layers_dir / "__init__.py").write_text("", encoding="utf-8")
    (layers_dir / "template.py").write_text("MARKER = True\n", encoding="utf-8")
    return plugin_dir
