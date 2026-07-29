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


def _registered_extensions() -> list[str]:
    return sorted(set(_READERS) | set(_WRITERS))


def reader_for(path: Path) -> RecordingReader:
    factory = _READERS.get(path.suffix)
    if factory is None:
        raise AuthoringError(
            expected=f"a registered extension: {_registered_extensions()}", found=repr(path.suffix),
            where=str(path), hint="register a codec for this extension, or use one already registered",
        )
    return factory(path)


def writer_for(path: Path) -> RecordingWriter:
    factory = _WRITERS.get(path.suffix)
    if factory is None:
        if path.suffix in _READERS:
            raise AuthoringError(
                expected="a codec with a writer", found=f"{path.suffix!r} is read-only (write_only capability absent)",
                where=str(path), hint="this extension has no registered writer",
            )
        raise AuthoringError(
            expected=f"a registered extension: {_registered_extensions()}", found=repr(path.suffix),
            where=str(path), hint="register a codec for this extension, or use one already registered",
        )
    return factory()
