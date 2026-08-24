# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ArrayView` -- SW-0014/SW-0015 (`IMP-0014`/`IMP-0015`).

Exposes an engine-owned buffer to Python with **zero copy** --
`__array_interface__` (numpy's own protocol) points straight at the buffer
`simcoreReadPort` returned, so `numpy.asarray(view)` shares memory rather
than allocating (`SW-0014`) -- and a **generation guard** (`SW-0015`): every
access compares the generation captured when the view was taken against the
engine's *current* generation and raises `StaleViewError`, naming the tick,
the moment they disagree.

Without the guard, a view held past the tick its buffer was reused would
silently read the NEXT tick's bytes under the PREVIOUS tick's label --
exactly the "never estimate/re-derive what nothing produced" failure
`R-SIM-7` names, at the scripting-API boundary rather than inside a layer
provider.

`buffer` is anything `ctypes.addressof`-compatible -- what a real engine
binding will hand this once one exists (`SW-0017`, `adas_sim.transport`,
`WP-27`'s Python side -- `engine/bridge.py`'s own note is that no
shared-library artifact exporting `simcore/abi/simcore.h`'s C ABI exists in
this tree yet, so nothing here can bind a *real* engine arena today).
`GenerationSource` is the seam that lets a test stand in for the engine with
no DLL at all: anything with a `current_generation()` method -- the real one
will read a live counter off the transport, a test one just increments in
place to simulate the engine reusing the buffer between ticks.
"""

from __future__ import annotations

import ctypes
from typing import Protocol, runtime_checkable

from adas_sim.diagnostics.errors import AuthoringError


class StaleViewError(AuthoringError):
    """Raised by any access on an `ArrayView` once the engine has reused the
    buffer it points at. `kind`/`exit_code` are inherited from
    `AuthoringError` -- SI-07's closed four-kind taxonomy (`SW-0121`) has no
    fifth kind for this, and the fix genuinely is in the caller's own
    script: hold the view for one tick only, or copy it (`bytes(view)`)."""


@runtime_checkable
class GenerationSource(Protocol):
    """Whatever `ArrayView` checks itself against -- the real engine
    binding, or a test double simulating buffer reuse."""

    def current_generation(self) -> int: ...


class ArrayView:
    """A zero-copy view onto an engine-owned buffer, valid for exactly the
    tick it was taken at.

    `dtype`/`shape` follow numpy's own `__array_interface__` vocabulary
    (`typestr`, e.g. `"<f4"`; a shape tuple). `readonly=True` by default --
    an `ArrayView` never writes back into the engine's memory (`R-SIM-4`'s
    one-directional ABI: the engine takes plain data and returns an `int`,
    never a callback).
    """

    __slots__ = ("_buffer", "_generation", "_source", "_tick", "__array_interface__")

    def __init__(
        self,
        buffer,
        *,
        dtype: str,
        shape: tuple[int, ...],
        generation: int,
        source: GenerationSource,
        tick: int,
        readonly: bool = True,
    ) -> None:
        #: Kept alive for the view's own lifetime -- ctypes does not
        #: refcount the memory a raw address points at, only the array/
        #: struct object itself.
        self._buffer = buffer
        self._generation = generation
        self._source = source
        self._tick = tick
        address = buffer if isinstance(buffer, int) else ctypes.addressof(buffer)
        self.__array_interface__ = {"shape": shape, "typestr": dtype, "data": (address, readonly), "version": 3}

    def _check_fresh(self) -> None:
        current = self._source.current_generation()
        if current != self._generation:
            raise StaleViewError(
                expected=f"generation {self._generation} (the buffer as it stood at tick {self._tick})",
                found=f"generation {current} -- the engine has reused this buffer since",
                where="adas_sim.pyapi.views.ArrayView",
                hint=f"this view was taken at tick {self._tick} and is now stale; re-read the port for the "
                     "current tick instead of holding a view across it",
            )

    def __len__(self) -> int:
        self._check_fresh()
        return self.__array_interface__["shape"][0] if self.__array_interface__["shape"] else 1

    def __getitem__(self, index):
        self._check_fresh()
        return self._buffer[index]

    @property
    def tick(self) -> int:
        """The tick this view was taken at -- what `StaleViewError` names."""
        return self._tick

    @property
    def generation(self) -> int:
        return self._generation
