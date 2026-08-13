# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The run correlation id (N-9, sim_api_reference.md §2.1)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone

from adas_sim.diagnostics.errors import InternalError

#: The minimum input set a run id must be derived from (N-9). Additional keys
#: in `inputs` are hashed too; these are simply the ones that must be present.
REQUIRED_KEYS = (
    "pipeline_sha",
    "recording_sha",
    "project",
    "component_build_shas",
    "bundle_sha",
    "overrides_repr",
    "seed",
)


def new_run_id(*, inputs: Mapping[str, str], clock: datetime | None = None) -> str:
    """N-9 correlation id: '<UTC compact>-<8 hex>'.

    `inputs` is hashed to the hex suffix and MUST contain, sorted by key:
    pipeline_sha, recording_sha, project, component_build_shas (joined),
    bundle_sha, overrides_repr, seed. Two runs with identical inputs therefore
    share a hex suffix -- and a differing result under one suffix is a
    determinism finding, not a mystery.
    """
    missing = sorted(set(REQUIRED_KEYS) - set(inputs))
    if missing:
        raise InternalError(
            expected=f"run-id inputs containing {list(REQUIRED_KEYS)}",
            found=f"missing {missing}",
            where="adas_sim.runspec.ids.new_run_id",
            hint="supply every required key (N-9); a caller passing a partial "
                 "input set is a framework bug, not a user authoring mistake",
        )
    when = clock if clock is not None else datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    digest_src = "\n".join(f"{key}={inputs[key]}" for key in sorted(inputs))
    digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:8]
    return f"{stamp}-{digest}"
