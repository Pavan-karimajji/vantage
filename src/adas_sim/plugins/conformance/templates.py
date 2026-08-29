# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Shipped template plug-ins -- one per extension point (`SW-0358`'s own
Accept clause: *"each of the three is exercised by a shipped template
plug-in that passes its own conformance kit"*).

`"reader"`/`"exporter"` need no template of their own: `io.jsonl.
JsonlReader` and `io.csv.CsvWriter` are already real, already registered
codecs (`DD-04`'s one-implementation rule -- a second, parallel
"just for conformance" reader/writer would be exactly the duplication that
rule forbids), so `reader_kit`/`exporter_kit` exercise those directly.

`"module"` has no existing component-free equivalent -- every real plug-in
belongs to a component, and this framework's own `src/` may never name one
(`R-SIM-1`). The function below is that template: minimal, real,
registered by import alone, carrying no component name anywhere in this
file.

**The `"visualization"` extension point retired with the rest of the
Python scene/render/player tree** (`SW-0358`'s 2026-08-29 amendment,
`SM-12`) -- this file's own former template layer provider went with it."""

from __future__ import annotations

from pathlib import Path

import yaml


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
