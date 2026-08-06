# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`register(ext, reader=, writer=)`, lookup by extension (sim_api_reference.md
§4). A new format is one class plus one registration -- nothing above `io/`
changes, and no layer provider, renderer or expectation ever learns a format
exists (R-SIM-14).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable

from adas_sim.core.errors import AuthoringError
from adas_sim.io.base import RecordingReader, RecordingWriter

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
_BUILTIN_CODEC_MODULES = {".mcap": "adas_sim.io.mcap", ".csv": "adas_sim.io.csv"}


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
