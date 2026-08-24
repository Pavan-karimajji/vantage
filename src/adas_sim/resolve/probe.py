# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0409`/`IMP-0410` (`SW-0409`/`SW-0410`) -- the probe pass. The ONLY
Python module bounded **by symbol** rather than by folder (`SW-0409`'s own
Shall): it may call `adasAbiVersion`/`adasManifest` (a module's version and
port manifest) and a recording reader's `topics()`/`messages()` describe
path -- never `adasInit`/`adasExec`/`adasShutdown` or any engine step call,
and never anything from the configuration layer (`config/`, `graph/`,
`ingest/`, `runspec/`) reaching one of those through it.

Binds its own two symbols independently of `resolve/component.py::_bind` --
that helper also binds `adasInit`/`adasExec`/`adasShutdown` (the execute
path `CtypesSilComponent` needs), and this module must never carry those
bindings at all, not merely leave them uncalled (`ANL-SW-07`'s symbol scan
below greps for the literal tokens). `ComponentManifest`/`parse_manifest`/
`ADAS_SIL_ABI_VERSION` are pure data/decode -- reused from `component.py`,
never re-implemented, so the manifest's wire shape has exactly one decoder.

`describe_recording`/`read_manifest` are what `WP-05` used today's Python
equivalents for (`io/base.py`'s topic scan, `component.py`'s probe) until
this landed -- see `IMP-0410`'s own design row.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Sequence

from adas_sim.diagnostics.errors import ContractError, EnvironmentError_
from adas_sim.graph.feasible import ModuleManifest, RecordingIndex, RecordingTopic
from adas_sim.ingest.header import RUNG_ORDER, Rung
from adas_sim.plugins.registry import reader_for
from adas_sim.resolve.component import ADAS_SIL_ABI_VERSION, ComponentManifest, parse_manifest
from adas_sim.resolve.library import resolve_library

if sys.platform == "win32":
    # Same reasoning as `resolve/component.py`'s own top-of-module call --
    # a malformed/wrong-architecture PE image must not pop a blocking WER
    # dialog during a probe-only load. Idempotent (SetErrorMode is a
    # process-wide flag, not per-call), harmless if `component.py` already
    # set it in this process.
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)


def _bind_probe_symbols(dll: ctypes.CDLL) -> None:
    """Binds exactly `adasAbiVersion`/`adasManifest` -- `SW-0409`'s
    permitted pair. `adasInit`/`adasExec`/`adasShutdown` are never bound
    here, on purpose: they must not be reachable from this module even as
    an unused, uncalled binding."""
    dll.adasAbiVersion.argtypes = []
    dll.adasAbiVersion.restype = ctypes.c_int32
    dll.adasManifest.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
    dll.adasManifest.restype = ctypes.c_size_t


def probe_manifest(path: Path) -> ComponentManifest:
    """Loads `path`, reads its `adasAbiVersion()`/`adasManifest()` and
    returns the decoded `ComponentManifest` -- no `adasInit` call, so no
    component handle is ever opened, and nothing here needs releasing
    (`SW-0410`'s "no handle retained" Accept clause, satisfied by never
    acquiring one)."""
    try:
        dll = ctypes.CDLL(str(path))
    except OSError as exc:
        raise EnvironmentError_(
            expected="a loadable library implementing the generic SIL ABI",
            found=str(exc), where=str(path),
            hint="check the library was built for this platform and its dependencies are resolvable",
        ) from exc
    _bind_probe_symbols(dll)
    found = dll.adasAbiVersion()
    if found != ADAS_SIL_ABI_VERSION:
        raise ContractError(
            expected=f"ABI version {ADAS_SIL_ABI_VERSION}", found=f"ABI version {found}",
            where=f"adasAbiVersion() in {path}",
            hint="rebuild the component or the framework, whichever is behind",
        )
    needed = dll.adasManifest(None, 0)
    buf = (ctypes.c_uint8 * needed)()
    written = dll.adasManifest(ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)), needed)
    return parse_manifest(bytes(buf[:written]))


def read_manifest(path_or_stem: str | Path, *, search: Sequence[Path] = ()) -> ModuleManifest:
    """`IMP-0410`: `path_or_stem` is either a real path to a module binary,
    or a bare stem resolved through `resolve_library` against `search`
    (`P-5` -- the same one place a stem becomes a path, `resolve/
    library.py`). Narrows the full `ComponentManifest` to `ModuleManifest`
    (`name`, `outputs`) -- `graph/feasible.py`'s own deliberately-narrower
    consumer shape (no version/build_id/descriptor_set/period_ns; those
    come from a loaded library, and a `ModuleManifest` never implies one is
    still loaded)."""
    path = Path(path_or_stem)
    if not path.is_file():
        path = resolve_library(str(path_or_stem), search=search)
    manifest = probe_manifest(path)
    return ModuleManifest(name=manifest.component, outputs=manifest.outputs)


def _highest_rung(reader) -> int:
    """The best rung a codec's own declared capability can support,
    without opening an ingest map (`SI-12`'s job, not this pass's) --
    `SOURCE_CYCLE_ID` is discovered from message bytes by `Cycle
    Reconstructor`, never claimed here; `capture_time` capability is the
    one fact `describe_recording` can honestly report before an ingest map
    exists. Returns an index into `header.RUNG_ORDER`, best (lowest) first,
    matching `RecordingTopic.highest_rung`'s own int shape."""
    capabilities = getattr(type(reader), "capabilities", None)
    if capabilities is not None and getattr(capabilities, "capture_time", False):
        return RUNG_ORDER.index(Rung.SOURCE_TIME)
    return RUNG_ORDER.index(Rung.RECEPTION_TIME)


def describe_recording(path: Path) -> RecordingIndex:
    """`IMP-0410`: reads `path` through the same reader interface a real
    run uses (`io.base.RecordingReader`) -- `topics()` for schema/
    provenance, `messages()` to compute `message_count` and the first/last
    `log_time_ns` per topic -- and returns a plain `RecordingIndex`, the
    file closed before returning (no handle retained). `absent` stays
    empty here: which ports a recording family never carries is `SI-12`'s
    ingest-map fact (`R-SIM-23`), not something a raw probe pass can know
    on its own."""
    reader = reader_for(path)
    try:
        topic_infos = reader.topics()
        rung = _highest_rung(reader)
        counts: dict[str, int] = {name: 0 for name in topic_infos}
        first_ns: dict[str, int] = {}
        last_ns: dict[str, int] = {}
        for topic, log_time_ns, _capture_time_ns, _payload in reader.messages():
            counts[topic] = counts.get(topic, 0) + 1
            if topic not in first_ns:
                first_ns[topic] = log_time_ns
            last_ns[topic] = log_time_ns
    finally:
        reader.close()

    topics = {
        name: RecordingTopic(
            proto_type=info.schema_name,
            message_count=counts.get(name, 0),
            first_timestamp_ns=first_ns.get(name),
            last_timestamp_ns=last_ns.get(name),
            highest_rung=rung,
            origin=info.provenance.value,
        )
        for name, info in topic_infos.items()
    }
    return RecordingIndex(topics=topics)
