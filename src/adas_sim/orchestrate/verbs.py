# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0232`: the command-line verb set is a closed, published, counted set
-- growth requires a requirement, not just a new `cli/*.py` file. `VERBS` is
that single published source: `cli/__init__.py`'s dispatch table is checked
against its keys (`tests/unit/test_si15_orchestrate.py::
test_cli_dispatch_matches_published_verbs`), so the two cannot silently
drift (`ANL-SW-40`'s own "a verb in one and not the other" failure mode).

`SW-0234`: every verb also carries a `dry_run` callable, asserted present at
table-construction time (`assert_dry_run_table_complete`) rather than
discovered missing at invocation. The **generic** dry run every verb gets by
default (`_generic_dry_run`) parses that verb's own `argparse` arguments and
prints the resolved plan -- never calling the verb's real `run()` body, so
it loads no module and decodes no message by construction (`SW-0234`'s own
Accept clause), for any verb, with no per-verb authoring burden.

**Every entry is built lazily** (`_lazy(module_name)`), matching
`cli/__init__.py`'s own deferred-import discipline: `cli.view` pulls in
`PySide6`, `cli.render` pulls in `matplotlib`, `cli.convert`/`cli.export`
pull in `mcap` (`UT-A1-2` -- `sim doctor`/`sim explain` must stay usable
with neither installed). Importing `adas_sim.orchestrate.verbs` itself must
therefore never import a single `cli.*` submodule eagerly; each is imported
only inside the closure the caller actually invokes.

`VERBS`'s own callables reach the CLI module's `run(argv) -> int`, not a
`pyapi` function. **`adas_sim.pyapi` landed at `WP-29`** (`IMP-0230`/
`IMP-0231`), but only wraps verb DISPATCH (`pyapi.Api.verb`/`dry_run` call
straight through to `VERBS[name].run(argv)`) plus its own pre-existing
diagnostics (`SW-0286`) -- no verb's actual business logic (recording
construction, engine invocation, manifest building, batch orchestration,
...) has been migrated INTO `pyapi.Api` itself, so `SW-0229`'s literal
Accept clause ("every `cli/*.py` module imports nothing but `argparse` and
`adas_sim.pyapi`", `ANL-SW-39`, whole-tree) still does not hold -- that is
a dedicated follow-on WP migrating each verb's own logic one method at a
time, not a consequence of `pyapi` merely existing (`IMP-0229`, `WP-23`)."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache

Runner = Callable[[list[str] | None], int]


@dataclass(frozen=True, slots=True)
class VerbEntry:
    run: Runner
    dry_run: Runner
    #: `R-SIM-12`'s own producing/executing distinction (`SW-0233`): `record`
    #: produces and executes nothing; `run` does both; `resim` executes an
    #: existing artifact. `""` for a verb that is neither (inspection,
    #: conversion, diagnostics).
    produces_executes: str = ""


@lru_cache(maxsize=None)
def _module(name: str):  # noqa: ANN202 -- returns a cli submodule, imported on first use only
    return importlib.import_module(f"adas_sim.cli.{name}")


def _lazy_run(name: str) -> Runner:
    return lambda argv=None: _module(name).run(argv)


def _generic_dry_run(name: str, argv: list[str] | None) -> int:
    """`SW-0234`: parses `argv` against the verb's own parser and prints the
    resolved plan. Never calls the verb's real `run()` -- so, for every
    verb uniformly, no module is loaded and no message is decoded."""
    parser = _module(name).build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(f"[dry run] {parser.prog}: would execute with {vars(args)}")
    return 0


def _lazy_dry_run(name: str) -> Runner:
    return lambda argv=None: _generic_dry_run(name, argv)


#: `SW-0232`'s own closed, published set -- 15 verbs today, one row each.
#: A verb added here without an `IMP`/`SW` row backing it is exactly the
#: growth `ANL-SW-40` refuses. Module names match `adas_sim/cli/<name>.py`
#: exactly, except `"list"` -> `list_cmd` (`cli/__init__.py`'s own
#: `list`-shadowing note applies here too) and `"run"` -> `run` (the CLI
#: submodule, unambiguous here since this module never binds a bare `run`
#: name at module scope).
_MODULE_OF = {
    "doctor": "doctor", "explain": "explain", "probe": "probe", "view": "view", "render": "render",
    "convert": "convert", "export": "export", "record": "record", "run": "run", "resim": "resim",
    "check": "check", "determinism": "determinism", "batch": "batch", "list": "list_cmd", "validate": "validate",
}

#: `doctor`/`explain`/`validate` are already dry by construction (report,
#: explain-only, lint-only -- none of the three executes a module or decodes
#: a recording), so their real `run` doubles as `dry_run` rather than paying
#: for a second argparse pass with nothing left to add.
_ALREADY_DRY = frozenset({"doctor", "explain", "validate"})

VERBS: Mapping[str, VerbEntry] = {
    verb: VerbEntry(
        run=_lazy_run(module_name),
        dry_run=_lazy_run(module_name) if verb in _ALREADY_DRY else _lazy_dry_run(module_name),
        produces_executes={"record": "produces", "run": "produces_and_executes", "resim": "executes"}.get(verb, ""),
    )
    for verb, module_name in _MODULE_OF.items()
}


def verb_count() -> int:
    """`SW-0232`'s own "reported per release" number."""
    return len(VERBS)


def assert_dry_run_table_complete() -> None:
    """`IMP-0234`'s own construction-time assertion: every entry MUST carry
    a `dry_run` callable -- `VerbEntry` being frozen with no default already
    makes a missing one a `TypeError` at import time, so this exists to give
    that failure a name a test can call directly rather than relying on
    import-time behaviour alone."""
    missing = [name for name, entry in VERBS.items() if entry.dry_run is None]
    if missing:
        raise ValueError(f"verb(s) with no dry_run callable: {missing}")


assert_dry_run_table_complete()
