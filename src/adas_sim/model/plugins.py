# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`PluginBundle.resolve()` -- plug-ins are **authored** in the component
(`modules/<name>/sim/`, `R-SIM-1`) and **delivered** beside its built library,
exactly like the config bundle (`R-SIM-3a`; `R-SIM-20`, `FR-SIM-64`). Resolution order
mirrors `ProjectModel.resolve` tier for tier: explicit -> embedded-in-recording
-> library `sim/` -> source checkout.

**A recording never carries a plug-in's bytes** (`NR-SIM-44`) -- only its
identity and `sha256` -- so opening a colleague's recording never runs their
code. The asymmetry with the config bundle is deliberate: configuration is
data, a plug-in is code.

A plug-in outside the player's declared `api:` range is refused **before it is
imported**: `resolve()` imports nothing, and `import_modules()` runs only
after `api` has been checked.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal

import yaml

from adas_sim.core.errors import AuthoringError

PluginBundleOrigin = Literal["explicit", "embedded", "library", "checkout"]

#: The plug-in API generation range THIS player supports (`NR-SIM-9`'s
#: existing terms, applied to plug-ins) -- independent of the Scene major and
#: the ABI version; three separate numbers, on purpose (a Scene bump must not
#: gratuitously invalidate every plug-in).
SUPPORTED_PLUGIN_API_MIN = 1
SUPPORTED_PLUGIN_API_MAX = 1


def _read_plugin_yaml(plugin_dir: Path) -> dict | None:
    path = plugin_dir / "plugin.yaml"
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@dataclass(frozen=True, slots=True)
class PluginBundle:
    component: str
    api: int
    sha256: str
    provides: tuple[str, ...]
    origin: PluginBundleOrigin
    root: Path  #: the resolved `sim/` directory `provides:` is relative to

    def __repr__(self) -> str:
        return f"<PluginBundle {self.component!r} api={self.api} origin={self.origin}>"

    @classmethod
    def resolve(
        cls,
        *,
        explicit: Path | None = None,
        recording: Path | None = None,
        library_dir: Path | None = None,
        checkout: Path | None = None,
    ) -> PluginBundle | None:
        """`None` when no tier carries a `plugin.yaml` at all -- a component
        with no `sim/` plug-ins is a legitimate state (not every component
        under test contributes layers), never an error. Each tier is a
        directory the CALLER already resolved (`checkout` included: same
        reasoning `ProjectModel.resolve`'s `project:` parameter uses -- the
        caller, not this function, decides which component's checkout is in
        play, because there is no bundle yet to read that identity from)."""
        for origin, plugin_dir in (
            ("explicit", explicit), ("embedded", recording), ("library", library_dir), ("checkout", checkout),
        ):
            if plugin_dir is None:
                continue
            data = _read_plugin_yaml(Path(plugin_dir))
            if data is None:
                continue
            return cls._from_yaml(data, origin=origin, root=Path(plugin_dir))
        return None

    @classmethod
    def _from_yaml(cls, data: dict, *, origin: PluginBundleOrigin, root: Path) -> PluginBundle:
        for required in ("api", "component", "provides"):
            if required not in data:
                raise AuthoringError(
                    expected=f"plugin.yaml to declare '{required}'",
                    found=f"keys present: {sorted(data)}", where=str(root / "plugin.yaml"),
                    hint="a packed bundle's plugin.yaml is a build output -- rebuild the component",
                )
        api = int(data["api"])
        if not (SUPPORTED_PLUGIN_API_MIN <= api <= SUPPORTED_PLUGIN_API_MAX):
            raise AuthoringError(
                expected=f"plugin api in [{SUPPORTED_PLUGIN_API_MIN}, {SUPPORTED_PLUGIN_API_MAX}]",
                found=f"api={api}", where=str(root / "plugin.yaml"),
                hint="refused before import (NR-SIM-44) -- rebuild the plug-in against a "
                     "supported player generation, or upgrade the player",
            )
        return cls(
            component=str(data["component"]), api=api, sha256=str(data.get("sha256", "")),
            provides=tuple(data["provides"]), origin=origin, root=root,
        )

    def import_modules(self) -> tuple[ModuleType, ...]:
        """Imports every `provides:` module under a private, collision-free
        name `_adas_plugin.<component>.<dotted>` -- **never** the literal
        `sim.layers.<x>` two components' plug-ins would otherwise collide on
        when both sit on one plug-in path (`UT-C8-3`): a bare `sys.path`
        insert plus `import sim.layers.x` caches the FIRST match in
        `sys.modules` under the name `sim.layers.x` forever, silently
        shadowing every other component's identically-named module. Importing
        is what registers a layer provider (`R-VAR-2`'s "discovery by
        import"); `scene.registry.layer_provider` is what actually raises on
        a duplicate layer id, naming both providers -- this function only
        has to make sure every plug-in's module genuinely gets imported."""
        modules: list[ModuleType] = []
        for dotted in self.provides:
            # `self.root` IS the resolved `sim/` directory (whichever tier
            # won), so a `provides:` entry's leading "sim" segment names
            # that same directory, not a child of it -- strip it before
            # joining, or every path doubles ".../sim/sim/...".
            parts = dotted.split(".")
            if parts and parts[0] == "sim":
                parts = parts[1:]
            file_path = self.root.joinpath(*parts).with_suffix(".py")
            if not file_path.is_file():
                raise AuthoringError(
                    expected=f"'{dotted}' to resolve to {file_path}", found="file not found",
                    where=f"plugin.yaml 'provides' for component '{self.component}'",
                    hint="the bundle is a build output -- rebuild it, or check provides: "
                         "against sim/'s real layout",
                )
            module_name = f"_adas_plugin.{self.component}.{dotted}"
            if module_name in sys.modules:
                modules.append(sys.modules[module_name])
                continue
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            modules.append(module)
        return tuple(modules)
