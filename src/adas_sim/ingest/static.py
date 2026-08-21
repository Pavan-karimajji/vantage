# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0199`/`SW-0199`, `IMP-0200`/`SW-0200` -- static parameter data
resolution: a static-kind port (`DD-05`) has no cycle structure, no hold,
no age; its value is resolved once, from one of two sources, and the
choice is reported rather than silently picked. **Unparented in `SYS`**
(`SwReq` §32.3) -- known, not a defect.

Precedence: **the recording first** (`static.py`'s own docstring line in
the design skeleton) -- if the source recording embeds the static port's
payload, that is authoritative for *that run*, because it is what the
component actually saw. Otherwise a **configured sidecar directory**, by a
declared naming convention, is tried. Neither existing is an
`AuthoringError` naming both places this looked.

Both this module and `map.py` **open recordings read-only** (`IMP-0200`)
-- a static payload already resident in an opened `RecordingReader` is
read via its API, and a sidecar file is opened with `Path.read_bytes()`;
neither ever opens a recording path in a write mode. Recording *which*
choice was made belongs to the run manifest the caller assembles
(`runspec/emit.py`'s own artifact) -- this module returns the decision as
plain data (`origin`, third element below) precisely so that write happens
exactly once, at the manifest, never here.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from adas_sim.diagnostics.errors import AuthoringError


def resolve_static(
    port: str,
    *,
    recording_static: Mapping[str, bytes] | None,
    static_dir: Path | None,
    naming_convention: str = "{port}.bin",
) -> tuple[bytes, str]:
    """Returns `(payload, origin)` where `origin` is `"recording"` or
    `f"sidecar:{path}"` -- reported, never discarded, by the caller."""
    if recording_static is not None and port in recording_static:
        return recording_static[port], "recording"

    if static_dir is not None:
        candidate = static_dir / naming_convention.format(port=port)
        if candidate.exists():
            return candidate.read_bytes(), f"sidecar:{candidate}"
        tried_sidecar = str(candidate)
    else:
        tried_sidecar = "(no static_dir configured)"

    raise AuthoringError(
        expected="a static payload embedded in the recording, or a sidecar file at the "
                 "configured directory under the declared naming convention",
        found=f"neither -- recording carries no {port!r} static payload; sidecar tried: {tried_sidecar}",
        where=f"static port {port!r}",
        hint="static data is a port kind (DD-05); declare a source for it, never assume one",
    )
