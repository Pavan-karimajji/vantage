# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The facts behind `sim explain` (DG-2), kept out of `cli/` (GT-9) so they
are reachable from a plain script. **Seeded at S-B2** over what exists now: a
session, its topics, its registered layer ids, its `run_id`. Grows at
`S-C1c` (ports, schemas, producers) and `S-D6` (expectations, values) --
same reasoning as `core/diagnostics.py`'s `sim doctor` seed at `S-A1`: the
tool that explains names is needed while names are being created, not after.

`S-D6`'s own completion (`UT-D6-7`): a codec name and an error code join
`run_id`/topic/layer here, plus fuzzy "did you mean" (`N-8`) on a miss.
**A style token is deliberately NOT resolved here** -- `render/theme.py`
sits ABOVE `core/` in the package map (`sim_api_reference.md` §1, enforced
by `UT-A1-6`'s import-direction test), so this module cannot import it.
`cli/explain.py`, which IS allowed to import `render/`, checks style
tokens first and extends the "did you mean" list with them -- see its own
comment for why that one branch lives there instead of here.
"""

from __future__ import annotations

import difflib
import sys

from adas_sim.core.session import Session
from adas_sim.io.registry import codec_info, registered_extensions
from adas_sim.scene.registry import registered_providers

#: DG-5's closed error taxonomy (`sim_naming_and_diagnostics.md`), matched
#: by taxonomy name (`"authoring"`), class name with or without the
#: builtin-shadowing trailing underscore (`EnvironmentError`/
#: `EnvironmentError_`, `core/errors.py`), or the bare exit code as a
#: string (`"2"`) -- whichever a developer actually has in hand: a
#: traceback names the class, a script checks the exit code, the docs name
#: the taxonomy.
_ERROR_TAXONOMY: dict[str, dict[str, object]] = {
    "authoring": {
        "exit_code": 2, "error_class": "AuthoringError",
        "means": "the YAML/pipeline/scenario is wrong", "who_fixes_it": "the person who wrote the file",
    },
    "environment": {
        "exit_code": 3, "error_class": "EnvironmentError_",
        "means": "a library, bundle or dependency is missing", "who_fixes_it": "sim doctor says which",
    },
    "contract": {
        "exit_code": 4, "error_class": "ContractError",
        "means": "an ABI/manifest/version mismatch", "who_fixes_it": "the component's build",
    },
    "internal": {
        "exit_code": 70, "error_class": "InternalError",
        "means": "a framework bug", "who_fixes_it": "an issue, with the run_id",
    },
}


def _match_error_kind(name: str) -> str | None:
    if name in _ERROR_TAXONOMY:
        return name
    for key, info in _ERROR_TAXONOMY.items():
        error_class = str(info["error_class"])
        if name in (error_class, error_class.rstrip("_")) or name == str(info["exit_code"]):
            return key
    return None


def known_names(session: Session) -> list[str]:
    """Every core-level name `explain` can resolve, for the fuzzy "did you
    mean" when nothing matches exactly. Public: `cli/explain.py` extends
    this with style-token names and re-runs `difflib` over the COMBINED
    list for its own "did you mean" -- ranking two separately-truncated
    match lists by merging and re-sorting them alphabetically would throw
    away `difflib`'s own similarity order (found the hard way, see that
    module's own comment)."""
    topics = list(session.ticks[0].ports) if session.ticks else []
    layers = list(registered_providers())
    return [session.run_id, *topics, *layers, *registered_extensions(), *_ERROR_TAXONOMY]


def explain(name: str, session: Session) -> dict[str, object]:
    """Everything known about `name` right now: the session's own `run_id`,
    a topic present in its recording, a registered layer id, a registered
    codec extension (with or without the leading dot), or DG-5's closed
    error taxonomy. An unresolved name gets a fuzzy "did you mean" (`N-8`)
    instead of failing bare.
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

    matches = difflib.get_close_matches(name, known_names(session), n=3, cutoff=0.6)
    return {
        "kind": "unknown",
        "name": name,
        "searched": ["run_id", "topics", "registered layers", "codecs", "error codes"],
        "did_you_mean": matches,
    }
