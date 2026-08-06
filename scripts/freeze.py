# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`python scripts/freeze.py` -- S-D5's one-folder frozen build (PyInstaller,
`sim_implementation_plan.md`'s own tool choice). Entry point is `scripts/
vantage.py` itself, already the external-plug-in-path-aware dev launcher
(`--plugin-root`/`ADAS_SIM_PLUGIN_PATH`, `R-SIM-20`) -- freezing bundles
CPython, Qt, the framework, the renderers and the codecs into
`dist/vantage/`, with **no component baked in** (this stage's own "must
not"): a component's `sim/` plug-ins are discovered at RUN time via
`--plugin-root`, never at freeze time, so `dist/vantage/` never learns a
component's name (`R-SIM-1`).

Requires the `package` extra (`pip install -e .[package]`, or just
`pyinstaller` -- it is never a runtime dependency of `adas_sim` itself, so
a frozen build never bundles its own freezer). Not itself part of the
`adas_sim` package -- `scripts/` is build machinery, the same placement
`R-BUILD` gives the component-level build scripts, extended here to
Python packaging.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    import PyInstaller.__main__

    extra = list(sys.argv[1:] if argv is None else argv)
    args = [
        str(_SIM_ROOT / "scripts" / "vantage.py"),
        "--name", "vantage",
        "--onedir",
        "--noconfirm",
        "--distpath", str(_SIM_ROOT / "dist"),
        "--workpath", str(_SIM_ROOT / "build" / "pyinstaller"),
        # PySide6/mcap ship data (Qt plugins) and submodules PyInstaller's
        # static import scan does not see on its own -- `--collect-all` is
        # the documented escape hatch for exactly this, not a guess.
        "--collect-all", "PySide6",
        "--collect-all", "mcap",
        "--collect-all", "mcap_protobuf_support",
        # UT-D5-2: `app/version.py` reads `importlib.metadata.version
        # ("adas-sim")` -- absent this, a frozen build's own `--version`
        # falls back to "unknown" (real gap, found running this build for
        # the first time; `version_info` degrades honestly rather than
        # crashing, but the real fix is carrying the metadata).
        "--copy-metadata", "adas-sim",
        *extra,
    ]
    PyInstaller.__main__.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
