# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Dev convenience launcher for Vantage (`vantage.bat`) -- `sim view`
(`cli/view.py`) plus the one thing it does not do yet: discovering plug-ins
from a **library directory** and importing them first (`S-C8`, `R-SIM-20`,
`FR-SIM-64` -- "point the player at a folder of DLLs and it draws them").

`--plugin-root`/`ADAS_SIM_PLUGIN_PATH` name a component's BUILT LIBRARY
DIRECTORY (e.g. `modules/df/build-sil-vs2026/src/platform/df_sil/Release`,
the same directory that carries `config/`) -- never a raw source checkout
and never a `sim/layers/*.py` glob. Each is resolved through
`PluginBundle.resolve(library_dir=<root>/sim)`, which reads the DEPLOYED
`plugin.yaml` the build already packed there (`interfaces/scripts/
pack_plugin_bundle.py`), checks its `api:` **before importing anything**, and
only then imports the modules it declares under a private, collision-free
name -- so two components' plug-ins on one path never shadow each other
(`UT-C8-3`). No component name appears in this file (`R-SIM-1`): a
library directory is a library directory, whichever component built it."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parent.parent
_SRC = _SIM_ROOT / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adas_sim.model.plugins import PluginBundle  # noqa: E402


def _register_plugin_root(library_dir: Path) -> None:
    library_dir = library_dir.resolve()
    bundle = PluginBundle.resolve(library_dir=library_dir / "sim")
    if bundle is None:
        print(f"warning: {library_dir} has no sim/plugin.yaml -- nothing to import from it", file=sys.stderr)
        return
    bundle.import_modules()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vantage", description=__doc__)
    parser.add_argument(
        "--version", action="store_true",
        help="print the player version and its compatibility statement (S-D5, UT-D5-2), then exit",
    )
    parser.add_argument("recording", type=Path, nargs="?")
    parser.add_argument(
        "--plugin-root", type=Path, action="append", default=[],
        help="a component's built library directory (carries sim/plugin.yaml, packed by the build); repeatable",
    )
    parser.add_argument("--project", default="base")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--at", type=float, default=None)
    parser.add_argument(
        "--pipeline", type=Path, default=None,
        help="S-D3: shows the pipeline panel and its Run button (sim_implementation_plan.md ST-D3-1)",
    )
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for --pipeline's dll:/stubdll: stages (repeatable)",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="config path forwarded to --pipeline's adasInit for a real Run -- same 'adasInit(NULL) bundle "
             "auto-resolution is not built yet' caveat as sim resim --config",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from adas_sim.app.version import format_version_text
        print(format_version_text())
        return 0
    # `recording` is genuinely optional (S-D8): with none given, Vantage
    # opens onto its own start page (recent files, Open Recording…, Probe
    # a Library…) instead of refusing to launch -- "no empty-state
    # configuration... it opens onto either a recording or a start page",
    # sim_player.md §2's own ban on requiring a file before anything shows.

    plugin_roots = list(args.plugin_root)
    env_path = os.environ.get("ADAS_SIM_PLUGIN_PATH", "")
    plugin_roots.extend(Path(p) for p in env_path.split(os.pathsep) if p)
    for root in plugin_roots:
        _register_plugin_root(root)

    import adas_sim.io.mcap  # noqa: F401 -- registers the ".mcap" codec
    from adas_sim.app.gui import launch

    return launch(
        args.recording, project=args.project, workspace_path=args.workspace,
        preset=args.preset, at_s=args.at,
        pipeline_path=args.pipeline, pipeline_search=args.search, pipeline_config=args.config,
    )


if __name__ == "__main__":
    sys.exit(main())
