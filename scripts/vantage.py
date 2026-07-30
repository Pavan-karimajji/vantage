# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Dev convenience launcher for Vantage (`vantage.bat`) -- `sim view`
(`cli/view.py`) plus the one thing it does not do yet: adding a
component's own plug-in root to the import path first
(`sim_architecture.md`'s "the player takes a plug-in root ... adds it to
the import path at start-up, and discovers providers there" -- a real CLI
flag for this is future `S-D8` scope; brought forward here as a thin
script so `--plugin-root` works today).

No component name appears in this file (`R-SIM-1`): `--plugin-root` is any
checkout with its own `sim/layers/` package (df's `modules/df/sim/layers/`
shape, but this script does not know that name)."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parent.parent
_SRC = _SIM_ROOT / "src"


def _register_plugin_root(root: Path) -> None:
    root = root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    layers_dir = root / "sim" / "layers"
    if not layers_dir.is_dir():
        print(f"warning: {root} has no sim/layers/ -- nothing to import from it", file=sys.stderr)
        return
    for py_file in sorted(layers_dir.glob("*.py")):
        if py_file.stem == "__init__":
            continue
        importlib.import_module(f"sim.layers.{py_file.stem}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vantage", description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--plugin-root", type=Path, action="append", default=[],
                         help="a component checkout whose sim/layers/*.py providers get imported first; repeatable")
    parser.add_argument("--project", default="base")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--at", type=float, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))
    for root in args.plugin_root:
        _register_plugin_root(root)

    import adas_sim.io.mcap  # noqa: F401 -- registers the ".mcap" codec
    from adas_sim.app.gui import launch

    return launch(
        args.recording, project=args.project, workspace_path=args.workspace,
        preset=args.preset, at_s=args.at,
    )


if __name__ == "__main__":
    sys.exit(main())
