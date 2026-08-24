# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`register(ext, reader=, writer=)`, lookup by extension (sim_api_reference.md
§4). A new format is one class plus one registration -- nothing above `io/`
changes, and no layer provider, renderer or expectation ever learns a format
exists (R-SIM-14).

**`EXTENSION_POINTS`** (`SW-0358`/`SW-0359`, `IMP-0358`/`IMP-0359`): this
module's codec registry is one of exactly four public extension points --
`reader`, `exporter`, `visualization`, `module` -- each discovered by
registration, never by editing a core list (`SW-0359`). A fifth requires a
requirement change (`SW-0358`'s own Accept clause), so the tuple's length is
what a conformance kit and `ANL-SW-*` both assert against, not a comment.
`extension_point_home()` names where each point's own registration function
lives, so a script does not need to know four import paths to find out.

The **codec** registry above is `"reader"`'s home (a codec is a reader
*and* a writer registered together, but "reader" is the extension point's
published name -- a recording that can only be written, e.g. today's CSV,
registers a writer here and is still exercised by `"exporter"`'s own kit,
never `"reader"`'s, since `SW-0358`'s four points are about *what a plug-in
does*, not which of `register()`'s two keyword arguments it used).

The **exporter** registry below is new (`IMP-0358`'s own `EXTEND`): unlike a
codec, an export is lossy and terminal (`R-SIM-14`) and is never accepted
back as a resim input, so it is looked up by a bare format name (`"csv"`),
never a file extension a reader could also claim.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Final, Mapping

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.io.base import RecordingReader, RecordingWriter

#: `SW-0358`'s four public extension points, asserted by length. Adding a
#: fifth here with no requirement change is exactly the growth `UT-PLG-02`'s
#: own "attempt to add a fifth" case refuses.
EXTENSION_POINTS: Final[tuple[str, ...]] = ("reader", "exporter", "visualization", "module")

#: Where each extension point's own registration function lives -- one
#: place a script or a new component's author finds all four without
#: knowing four import paths in advance.
_EXTENSION_POINT_HOMES: Final[Mapping[str, str]] = {
    "reader": "adas_sim.plugins.registry.register(ext, reader=...)",
    "exporter": "adas_sim.plugins.registry.register_exporter(name, factory)",
    "visualization": "adas_sim.scene.registry.layer_provider(layer_id)",
    "module": "adas_sim.resolve.plugins.PluginBundle.resolve(...)",
}

#: A reader factory takes the path -- a reader is fully loaded and ready to
#: use as soon as `reader_for()` returns it (`RecordingReader`'s Protocol has
#: no separate open/load step). A writer factory takes nothing -- a writer's
#: `open(path, meta, topics)` is an explicit Protocol method instead.
_READERS: dict[str, Callable[[Path], RecordingReader]] = {}
_WRITERS: dict[str, Callable[[], RecordingWriter]] = {}

#: extension -> the built-in module that registers it, imported lazily on
#: first lookup. `import adas_sim.io` (or anything under it) must not import
#: `mcap` (`UT-A1-2`: no subpackage pulls in a heavy dependency at import
#: time) -- found by `cli explain` genuinely failing to resolve `.mcap` until
#: something had imported `adas_sim.io.mcap` by hand, which every earlier
#: manual smoke test happened to do itself, masking the gap. `reader_for`/
#: `writer_for` are the one place this framework actually needs a codec, so
#: they are the one place it is loaded.
_BUILTIN_CODEC_MODULES = {".mcap": "adas_sim.io.mcap", ".csv": "adas_sim.io.csv", ".jsonl": "adas_sim.io.jsonl"}


def _load_builtin(ext: str) -> None:
    module_name = _BUILTIN_CODEC_MODULES.get(ext)
    if module_name is not None and ext not in _READERS and ext not in _WRITERS:
        importlib.import_module(module_name)


def register(
    ext: str,
    *,
    reader: Callable[[Path], RecordingReader] | None = None,
    writer: Callable[[], RecordingWriter] | None = None,
) -> None:
    """`ext` includes the leading dot (`".mcap"`), matching `Path.suffix`."""
    if reader is not None:
        _READERS[ext] = reader
    if writer is not None:
        _WRITERS[ext] = writer


def registered_extensions() -> list[str]:
    return sorted(set(_READERS) | set(_WRITERS) | set(_BUILTIN_CODEC_MODULES))


def codec_info(ext: str) -> dict[str, object] | None:
    """Best-effort, no-file-needed answer to "what does this codec do" --
    `sim explain <codec name>`'s own need (`DG-2`, `UT-D6-7`). `None` when
    `ext` names no registered codec at all. A reader factory IS the reader
    class (`capabilities` is a class attribute, no instantiation, no I/O);
    a writer factory is called with no arguments to reach the same
    attribute off the instance -- every registered writer's own `__init__`
    opens nothing until `.open()` is called (`io/mcap.py`/`io/csv.py`'s own
    `_new_writer`)."""
    if not is_registered_recording_extension(ext):
        return None
    _load_builtin(ext)
    has_reader = ext in _READERS
    has_writer = ext in _WRITERS
    capabilities = getattr(_READERS[ext], "capabilities", None) if has_reader else None
    if capabilities is None and has_writer:
        capabilities = _WRITERS[ext]().capabilities
    return {"extension": ext, "has_reader": has_reader, "has_writer": has_writer, "capabilities": capabilities}


def is_registered_recording_extension(suffix: str) -> bool:
    """`True` for a suffix (`Path.suffix`, leading dot) this registry knows
    as a recording codec -- read, write or both. The one public check `sim
    probe` (`S-D6`) uses to tell "this path is a recording" from "this path
    is a component library" WITHOUT paying `_load_builtin`'s import cost or
    `reader_for`'s own capability-mismatch error for the library case, which
    is not an error here, just the other branch."""
    return suffix in registered_extensions()


def reader_for(path: Path) -> RecordingReader:
    _load_builtin(path.suffix)
    factory = _READERS.get(path.suffix)
    if factory is None:
        if path.suffix in _WRITERS:
            # R-SIM-14: an export is refused as a resim input **by
            # capability**, never by a naming convention someone could work
            # around -- the writer registered for this extension exists
            # (`write_only`), there is simply no reader for it.
            raise AuthoringError(
                expected="a codec with a reader (round_trips capability)",
                found=f"{path.suffix!r} is write-only -- refused as a resim input",
                where=str(path), hint="an export (e.g. CSV) is lossy and terminal; use the recording it was exported from",
            )
        raise AuthoringError(
            expected=f"a registered extension: {registered_extensions()}", found=repr(path.suffix),
            where=str(path), hint="register a codec for this extension, or use one already registered",
        )
    return factory(path)


def writer_for(path: Path) -> RecordingWriter:
    _load_builtin(path.suffix)
    factory = _WRITERS.get(path.suffix)
    if factory is None:
        if path.suffix in _READERS:
            raise AuthoringError(
                expected="a codec with a writer", found=f"{path.suffix!r} is read-only (write_only capability absent)",
                where=str(path), hint="this extension has no registered writer",
            )
        raise AuthoringError(
            expected=f"a registered extension: {registered_extensions()}", found=repr(path.suffix),
            where=str(path), hint="register a codec for this extension, or use one already registered",
        )
    return factory()


def extension_point_home(point: str) -> str:
    """`SW-0358`: where `point`'s own registration function lives. Raises
    naming the closed set for anything outside it -- a fifth extension
    point is a requirement change, never a new entry here."""
    if point not in _EXTENSION_POINT_HOMES:
        raise AuthoringError(
            expected=f"one of the four extension points: {EXTENSION_POINTS}", found=repr(point),
            where="adas_sim.plugins.registry.extension_point_home",
            hint="SW-0358: a fifth extension point needs a requirement change, not a new registry entry",
        )
    return _EXTENSION_POINT_HOMES[point]


# ---- "exporter" -- new registration surface (IMP-0358) --------------------
#
# An export is lossy and terminal (R-SIM-14): it is never accepted back as a
# resim input, so it is looked up by a bare format name, never a file
# extension a round-trippable codec could also claim. `cli/export.py`
# constructs `CsvWriter` directly today (it needs per-call `ports=`/
# `on_missing=` a zero-argument factory cannot carry) -- this registry is
# the extension point CSV already satisfies, available to any caller that
# does not need that per-call configuration (a conformance kit, a future
# `--format` option), without becoming a second, competing construction
# path for `cli/export.py`'s own use.

_EXPORTERS: dict[str, Callable[[], RecordingWriter]] = {}

#: `"csv"` -> the built-in module that registers it, imported lazily on
#: first lookup -- same reasoning as `_BUILTIN_CODEC_MODULES` above (no
#: subpackage pulls in a dependency at import time, `UT-A1-2`).
_BUILTIN_EXPORTER_MODULES: Final[Mapping[str, tuple[str, str]]] = {"csv": ("adas_sim.io.csv", "CsvWriter")}


def _load_builtin_exporter(name: str) -> None:
    if name in _EXPORTERS:
        return
    entry = _BUILTIN_EXPORTER_MODULES.get(name)
    if entry is not None:
        module_name, attr = entry
        module = importlib.import_module(module_name)
        _EXPORTERS[name] = getattr(module, attr)


def register_exporter(name: str, factory: Callable[[], RecordingWriter]) -> None:
    """Registers an export format by name (`"csv"`, ...) -- discovery by
    registration alone (`SW-0359`), never an edit to `cli/export.py` or this
    module's own source."""
    _EXPORTERS[name] = factory


def registered_exporters() -> list[str]:
    return sorted(set(_EXPORTERS) | set(_BUILTIN_EXPORTER_MODULES))


def exporter_for(name: str) -> RecordingWriter:
    _load_builtin_exporter(name)
    factory = _EXPORTERS.get(name)
    if factory is None:
        raise AuthoringError(
            expected=f"a registered exporter: {registered_exporters()}", found=repr(name),
            where="adas_sim.plugins.registry.exporter_for",
            hint="register_exporter(name, factory) before requesting it",
        )
    return factory()
