# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Vantage's `--version` compatibility statement (S-D5, `UT-D5-2`,
`sim_player.md` §5.15): the player version plus every compatibility number
something opened in Vantage is actually checked against at load time.
Every number here is **read**, never restated -- the same constant each
real refusal already names (`ADAS_SIL_ABI_VERSION` -- `UT-C1c-1`;
`scene.codec.SUPPORTED_MAJOR` -- `test_a3_codec.py`; `CURRENT_PIPELINE_
VERSION` -- `test_c1c_pipeline.py`'s own version tests;
`SUPPORTED_PLUGIN_API_MIN/MAX` -- `test_c8_plugins.py`'s `test_out_of_
range_api_is_refused_naming_both_numbers`), so this can never drift into
reporting a number a refusal does not actually enforce.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

from adas_sim.contracts.component import ADAS_SIL_ABI_VERSION
from adas_sim.contracts.pipeline import CURRENT_PIPELINE_VERSION
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION
from adas_sim.model.plugins import SUPPORTED_PLUGIN_API_MAX, SUPPORTED_PLUGIN_API_MIN
from adas_sim.scene.codec import SUPPORTED_MAJOR as SCENE_MAJOR_VERSION


def _player_version() -> str:
    """`--version` must never crash a shipped binary just to report its
    own name (`R-SIM-25`/`NR-SIM-4`'s "reads unknown, never crashes" -- a
    frozen build's dist-info is a packaging detail, not something a user
    facing an unreadable error should have to debug). Found for real
    freezing `scripts/freeze.py`'s own output: PyInstaller does not carry
    `adas-sim`'s dist-info unless told to (`--copy-metadata`), which
    `version_info` must survive even if that flag is ever forgotten."""
    try:
        return _package_version("adas-sim")
    except PackageNotFoundError:
        return "unknown"


def version_info() -> dict[str, str]:
    """`UT-D5-2`: every one of the four compatibility fields the checklist
    names (ABI generation, Scene major, recording-model/manifest version,
    pipeline-file schema version), plus the plug-in API range (`NR-SIM-44`)
    -- the fifth number Vantage itself enforces at load, not asked for by
    name in the checklist but the same kind of fact and worth the same
    honesty."""
    return {
        "vantage": _player_version(),
        "abi_version": str(ADAS_SIL_ABI_VERSION),
        "scene_major": str(SCENE_MAJOR_VERSION),
        "recording_manifest_version": str(CAPTURE_TIME_MANIFEST_VERSION),
        "pipeline_version": str(CURRENT_PIPELINE_VERSION),
        "plugin_api_range": f"{SUPPORTED_PLUGIN_API_MIN}-{SUPPORTED_PLUGIN_API_MAX}",
    }


def format_version_text() -> str:
    info = version_info()
    lines = [f"vantage {info['vantage']}", "compatibility:"]
    lines += [f"  {key:<26} {value}" for key, value in info.items() if key != "vantage"]
    return "\n".join(lines)
