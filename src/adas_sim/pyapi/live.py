# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-13`, `livectl` item (`SW-0051`/`SW-0052`): a running session's
operations, reachable from a script over a local socket -- no display, no
GUI process to attach to. `LiveSession` opens the socket and serves every
operation `pyapi.Api` already exports (`_operation_table`); `LiveClient` is
the far end a script imports. Neither side invents an operation of its
own: an operation not already on `Api` cannot be registered here, because
the table is BUILT from `Api`'s own public surface, never hand-listed.
"""

from __future__ import annotations

import threading
from multiprocessing.connection import Client, Listener
from typing import Callable

from adas_sim.pyapi.api import Api

#: `WP-13` (`SW-0052`): every public, callable attribute of `Api` -- no
#: hand-picked subset, so an operation with no headless twin cannot exist
#: here. Bound methods only (`api`'s own instance), never a wrapper
#: function with logic of its own.
def _operation_table(api: Api) -> dict[str, Callable[..., object]]:
    return {
        name: getattr(api, name)
        for name in dir(Api)
        if not name.startswith("_") and callable(getattr(api, name))
    }


class LiveSession:
    """`WP-13` (`SW-0051`): serves `api`'s own operations over a local
    socket (`multiprocessing.connection`, stdlib -- a named pipe on
    Windows, a Unix socket elsewhere), so a script with no display can
    attach while the session is running. One connection at a time, one
    request per connection -- a script calls, gets its answer, closes."""

    _AUTHKEY = b"adas-sim-livectl"

    def __init__(self, api: Api | None = None, *, address: tuple[str, int] = ("localhost", 0)) -> None:
        self._operations = _operation_table(api if api is not None else Api())
        self._listener = Listener(address, authkey=self._AUTHKEY)
        self.address = self._listener.address
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()

    def _serve_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                conn = self._listener.accept()
            except OSError:
                return  # the listener was closed from stop()
            try:
                self._serve_one(conn)
            finally:
                conn.close()

    def _serve_one(self, conn) -> None:
        try:
            name, args, kwargs = conn.recv()
        except EOFError:
            return
        if name not in self._operations:
            conn.send(("error", f"no such operation: {name!r}"))
            return
        try:
            result = self._operations[name](*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- reported to the caller, never crashes the session
            conn.send(("error", str(exc)))
            return
        conn.send(("ok", result))

    def close(self) -> None:
        self._stopped.set()
        self._listener.close()
        self._thread.join(timeout=5)


class LiveClient:
    """The far end of `LiveSession`, for a script with no display. `call`
    is the one entry point -- there is no operation-specific method here
    either, for the same reason `LiveSession` has none: the set is
    whatever `Api` exports, discovered on the session's own side."""

    def __init__(self, address: tuple[str, int]) -> None:
        self._address = address

    def call(self, name: str, *args: object, **kwargs: object) -> object:
        conn = Client(self._address, authkey=LiveSession._AUTHKEY)
        try:
            conn.send((name, args, kwargs))
            status, payload = conn.recv()
        finally:
            conn.close()
        if status == "error":
            raise LookupError(payload)
        return payload
