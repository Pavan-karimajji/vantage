# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The facts behind `sim explain` (`DG-2`), kept out of `cli/` (`GT-9`) so they
are reachable from a plain script.

Resolves a `run_id`, topic, layer id, codec name or error code, with fuzzy
"did you mean" on a miss (`N-8`, `UT-D6-7`).

**A style token is deliberately not resolved here.** `render/theme.py` sits
above `core/` in the package map (enforced by `UT-A1-6`'s import-direction
test), so this module cannot import it. `cli/explain.py`, which may import
`render/`, checks style tokens and extends the "did you mean" list with them.
"""

from __future__ import annotations

import sys

from adas_sim.config import ResolvedConfig
from adas_sim.diagnostics.errors import AuthoringError, ContractError, EnvironmentError_, InternalError
from adas_sim.diagnostics.suggest import near_matches
from adas_sim.session.session import Session
from adas_sim.plugins.registry import codec_info, registered_extensions
from adas_sim.scene.registry import registered_providers

#: DG-5's closed error taxonomy (`sim_naming_and_diagnostics.md`), matched
#: by taxonomy name (`"authoring"`), class name with or without the
#: builtin-shadowing trailing underscore (`EnvironmentError`/
#: `EnvironmentError_`, `diagnostics/errors.py`), or the bare exit code as
#: a string (`"2"`) -- whichever a developer actually has in hand: a
#: traceback names the class, a script checks the exit code, the docs name
#: the taxonomy. Built from the real `SimError` subclasses (`WP-03`) rather
#: than a second hand-copied table, so `exit_code` cannot drift from
#: `errors.py`'s own values.
_ERROR_MEANS: dict[str, tuple[str, str]] = {
    "authoring": ("the YAML/pipeline/scenario is wrong", "the person who wrote the file"),
    "environment": ("a library, bundle or dependency is missing", "sim doctor says which"),
    "contract": ("an ABI/manifest/version mismatch", "the component's build"),
    "internal": ("a framework bug", "an issue, with the run_id"),
}
_ERROR_TAXONOMY: dict[str, dict[str, object]] = {
    cls.kind: {
        "exit_code": cls.exit_code, "error_class": cls.__name__,
        "means": _ERROR_MEANS[cls.kind][0], "who_fixes_it": _ERROR_MEANS[cls.kind][1],
    }
    for cls in (AuthoringError, EnvironmentError_, ContractError, InternalError)
}


def _match_error_kind(name: str) -> str | None:
    if name in _ERROR_TAXONOMY:
        return name
    for key, info in _ERROR_TAXONOMY.items():
        error_class = str(info["error_class"])
        if name in (error_class, error_class.rstrip("_")) or name == str(info["exit_code"]):
            return key
    return None


def known_names(session: Session, *, config: ResolvedConfig | None = None) -> list[str]:
    """Every core-level name `explain` can resolve, for the fuzzy "did you
    mean" when nothing matches exactly. Public: `cli/explain.py` extends
    this with style-token names and re-runs `difflib` over the COMBINED
    list for its own "did you mean" -- ranking two separately-truncated
    match lists by merging and re-sorting them alphabetically would throw
    away `difflib`'s own similarity order (found the hard way, see that
    module's own comment)."""
    topics = list(session.ticks[0].ports) if session.ticks else []
    layers = list(registered_providers())
    config_leaves = [leaf for leaves in (config.resolved.values() if config else ()) for leaf in leaves]
    return [session.run_id, *topics, *layers, *registered_extensions(), *_ERROR_TAXONOMY, *config_leaves]


def explain(name: str, session: Session, *, config: ResolvedConfig | None = None) -> dict[str, object]:
    """Everything known about `name` right now: the session's own `run_id`,
    a topic present in its recording, a registered layer id, a registered
    codec extension (with or without the leading dot), a resolved
    configuration leaf (`config`, `IMP-0166` -- `Provenanced`'s payoff:
    which layer/file/line it came from, printed rather than reconstructed),
    or DG-5's closed error taxonomy. An unresolved name gets a fuzzy "did
    you mean" (`N-8`) instead of failing bare.
    """
    if name == session.run_id:
        return {
            "kind": "run_id",
            "name": name,
            "tick_count": len(session),
            "deterministic": session.deterministic,
            "manifest_known": session.meta.known,
        }

    topics = session.ticks[0].ports if session.ticks else {}
    if name in topics:
        port_value = topics[name]
        return {
            "kind": "topic",
            "name": name,
            "present_in_recording": True,
            "origin": port_value.origin,
        }

    providers = registered_providers()
    if name in providers:
        entry = providers[name]
        result: dict[str, object] = {
            "kind": "layer",
            "name": name,
            "module": entry.module,
            "qualname": entry.qualname,
        }
        # S-C8's own remaining item: report the plug-in PATH a layer's
        # module actually loaded from. `PluginBundle.import_modules()`
        # names every plug-in module `_adas_plugin.<component>.<dotted>`
        # (its own docstring on why, R-SIM-1's collision-free-import
        # discipline) -- that module is already in sys.modules by the time
        # it could register a provider at all, and importlib set its real
        # resolved __file__ at import time (spec_from_file_location).
        # A layer registered by the framework's own first-party code
        # (module not under _adas_plugin, e.g. a test fixture) has no
        # plug-in bundle to report -- both fields stay absent rather than
        # guessed (R-SIM-25, NR-SIM-4).
        module_parts = entry.module.split(".")
        if len(module_parts) >= 2 and module_parts[0] == "_adas_plugin":
            result["plugin_component"] = module_parts[1]
            loaded_module = sys.modules.get(entry.module)
            result["plugin_path"] = getattr(loaded_module, "__file__", None) or "unknown"
        return result

    ext = name if name.startswith(".") else f".{name}"
    info = codec_info(ext)
    if info is not None:
        return {"kind": "codec", "name": name, **info}

    error_kind = _match_error_kind(name)
    if error_kind is not None:
        return {"kind": "error_code", "name": name, "taxonomy": error_kind, **_ERROR_TAXONOMY[error_kind]}

    if config is not None:
        for kind, leaves in config.resolved.items():
            if name in leaves:
                prov = leaves[name]
                return {
                    "kind": "config_value", "name": name, "file_kind": kind.value,
                    "value": prov.value, "layer": prov.layer.value,
                    "file": str(prov.file), "line": prov.line,
                }

    matches = near_matches(name, known_names(session, config=config))
    return {
        "kind": "unknown",
        "name": name,
        "searched": ["run_id", "topics", "registered layers", "codecs", "error codes"],
        "did_you_mean": matches,
    }
