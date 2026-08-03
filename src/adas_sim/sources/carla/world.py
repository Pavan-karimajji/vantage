# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""CARLA connection/world setup (`S-C2` slice 5). Ported from
`modules/df/tools/carla/carla_bridge.py`'s connection code, verbatim in
behaviour. `carla` is imported inside each function -- this module must be
importable with no `carla` package installed (`R-SIM-11`-style optional
dependency; only actually connecting needs it)."""

from __future__ import annotations

import time


def connect(host: str, port: int, *, timeout_s: float = 60.0):
    """Returns a `carla.Client`, timeout set (`P-6`: never launched through
    a shell, this only ever talks to an already-running server over TCP)."""
    import carla

    client = carla.Client(host, port)
    client.set_timeout(timeout_s)
    return client


def wait_for_world(client, attempts: int = 6, delay_s: float = 10.0):
    """CARLA's world isn't necessarily ready the instant the server process
    is up -- retry."""
    for attempt in range(attempts):
        try:
            return client.get_world()
        except RuntimeError as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Could not get world after {attempts} attempts: {exc}") from exc
            time.sleep(delay_s)


def ensure_map(client, world, map_name: str):
    """Loads `map_name` if `world` isn't already running it -- returns the
    (possibly new) `carla.World`."""
    if map_name not in world.get_map().name:
        world = client.load_world(map_name)
    return world


def set_asynchronous(world) -> None:
    """Asynchronous mode only, deliberately: `synchronous_mode = True` is
    confirmed to stall real CARLA Windows builds after a few ticks (a known
    issue, not specific to this source). `world.wait_for_tick()` (called by
    the driving loop, not here) is the async-mode equivalent -- it blocks
    until the server's next tick, giving per-tick pacing without the hang."""
    settings = world.get_settings()
    settings.synchronous_mode = False
    settings.fixed_delta_seconds = None
    world.apply_settings(settings)
