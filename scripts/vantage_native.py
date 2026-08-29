# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Native Vantage launcher -- what `vantage.bat` drives. Drives the real,
proven-live `vantage_app.exe` (`WP-34`,
`docs/v2/SIM_Implementation_Plan_v0.1.md`) -- a genuine GLFW/ImGui window
over the real `viz`/`df_viz` C++ scene/render stack, not a second
implementation of it.

`build_parser()` below is this module's own, since `scripts/vantage.py` --
the retiring Python scene/render/player implementation's launcher, which
used to own the one CLI-grammar definition this module reused -- is deleted
(`SM-12`, `modules/viz/docs/VIZ_Sync_Plan_v0.1.md`). This is the one
grammar definition now; there is no second to drift from it.

**The real, load-bearing gap this file encodes, never silently drops:**
`vantage_app.exe`'s own positional argument is a *Resolved Run Spec* JSON
path (`simEngineCreate`'s own `run_spec_json_path` -- confirmed by reading
`vantage/cpp/vantage_app/vantage_app.cpp`'s own argv-parsing loop in full),
never a raw `.mcap`, and that same loop explicitly REFUSES `--pipeline`/
`--search` itself with a named error. The only way to produce that JSON
today is `sim resim <recording> --pipeline <p.yaml> [--search ...]
[--config ...] --save <out.mcap>` (an OFFLINE subprocess-shaped step,
`adas_sim.cli.resim`), whose `<out.mcap>.spec.json` sidecar is exactly what
`vantage_app.exe` expects. So:

  - `--pipeline ...` (a real RESIM) is served here: this module runs that
    `sim resim` step for you (reusing `adas_sim.cli.resim.run`, not a
    second implementation of it), then hands `vantage_app.exe` the
    resulting spec.json.
  - A *bare replay* (a recording opened with **no** `--pipeline` -- read
    only what the file already contains, `R-SIM-5`'s own `replay`) has **no
    native equivalent at all** today, now that the Python viewer that used
    to serve it is deleted: `vantage_app.exe` cannot open a raw recording,
    full stop. This is a real, structural finding beyond `WP-34`'s own
    named `--pipeline`/`--search` gap (which is the exe's own argv refusal
    above, a different thing) -- a bare recording with no matching
    `.spec.json` sidecar next to it gets a clear, named, permanent refusal
    here.

`--preset`/`--at`/`--workspace`/`--version` were Python-viewer-only
concepts, now gone with it: `vantage_app.exe`'s own argv has no flag for
any of them (same full read of its parsing loop) -- each refuses by name
here rather than being silently dropped or half-implemented.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
_SRC = _SIM_ROOT / "src"

for _p in (_SCRIPTS, _SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def build_parser() -> argparse.ArgumentParser:
    """The Vantage CLI grammar -- formerly `scripts/vantage.py`'s own,
    moved here whole (unchanged) when that file was deleted (`SM-12`).
    `--preset`/`--at`/`--workspace`/`--version` are still accepted here,
    not dropped from the grammar, so `build_native_argv` below can name
    them in a real refusal rather than argparse rejecting them opaquely as
    unknown flags."""
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


class NativeUnsupported(RuntimeError):
    """A real argument or mode `vantage_app.exe` cannot serve. Always
    carries a named fix (`--pipeline`) or a plain statement that none
    exists -- never a bare refusal."""


def find_vantage_app_exe() -> Path:
    """Known build-output locations, `sil` (the canonical production shape,
    `python vantage/scripts/build.py -t sil -p vs2026`) first, `gtest` (the
    shape `WP-33`/`WP-34`'s own verification passes used, and the one that
    also runs `vantage_tests.exe`) second -- the same "check a known build
    output path first" resolution `gui.py` already uses for a
    COMPONENT's plug-ins (`_register_plugin_root`), applied here to
    vantage's own binary. TARGET_TYPE defaults to `sil` regardless of which
    of these two Conan targets is built (`vantage/CMakeLists.txt`'s own top
    comment), so either produces a real `vantage_app.exe`."""
    vantage_dir = _SIM_ROOT / "vantage"
    candidates = [
        vantage_dir / "build-sil-vs2026" / "build" / "cpp" / "vantage_app" / "Release" / "vantage_app.exe",
        vantage_dir / "build-gtest-vs2026" / "build" / "cpp" / "vantage_app" / "Release" / "vantage_app.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise NativeUnsupported(
        "vantage_app.exe not found. Build it first (native vs2026 only -- WSL2 interop's own "
        "cmd.exe/powershell.exe, never a GL window through WSL itself):\n"
        f"  cd {vantage_dir}\n"
        "  build.bat -t sil -p vs2026"
    )


def _resim_to_spec_json(args, tmp_dir: Path) -> Path:
    """Runs `sim resim` (`adas_sim.cli.resim.run`, the same function `sim
    resim`'s own console-script entry point calls -- not a second
    implementation of it) to produce the run-spec `vantage_app.exe` needs;
    see this module's own top note. Returns the `<out>.mcap.spec.json`
    sidecar `resim.run`'s own `--save` path always writes next to its
    output recording."""
    from adas_sim.cli import resim as resim_cli

    # `pipeline_to_run_spec` (`adas_sim.engine.bridge`) hard-refuses a
    # relative path in the emitted spec (`unresolved(spec)`, `IMP-0001`) --
    # a real, immediate finding hit live running this exact wrapper: a user
    # typing the same relative paths `vantage.py`'s own retiring Session
    # path tolerates (it never builds a run_spec at all) gets an opaque
    # `InternalError` from `sim resim` here instead. Resolved, not worked
    # around: every filesystem argument is made absolute before it reaches
    # `resim.run`.
    out_path = tmp_dir / f"vantage_native_{uuid.uuid4().hex}.mcap"
    argv = [
        str(args.recording.resolve()), "--pipeline", str(args.pipeline.resolve()),
        "--save", str(out_path),
    ]
    for s in args.search:
        argv += ["--search", str(Path(s).resolve())]
    if args.config is not None:
        argv += ["--config", str(Path(args.config).resolve())]
    if args.project:
        argv += ["--project", str(args.project)]
    print(f"$ sim resim {' '.join(argv)}")
    code = resim_cli.run(argv)
    if code != 0:
        raise NativeUnsupported(f"sim resim failed (exit {code}) building the run-spec for {args.recording}")
    return out_path.with_suffix(out_path.suffix + ".spec.json")


def build_native_argv(args) -> list[str]:
    """Maps `build_parser()`'s own parsed args onto `vantage_app.exe`'s
    real argv (`vantage_app.cpp`'s own parsing loop, read in full -- never
    a guess at its shape)."""
    unsupported = [
        name for name, val in (
            ("--workspace", args.workspace), ("--preset", args.preset), ("--at", args.at),
        ) if val is not None
    ]
    if getattr(args, "version", False):
        unsupported.append("--version")
    if unsupported:
        raise NativeUnsupported(
            f"{', '.join(unsupported)}: not supported by the native host -- vantage_app.exe's own argv "
            "has no such flag (confirmed by reading its parsing loop in full), and the Python viewer "
            "that used to support it is deleted (SM-12) -- no fallback exists."
        )
    if args.recording is None:
        raise NativeUnsupported(
            "no recording given: vantage_app.exe has no start page (that was a Python-viewer-only "
            "concept, S-D8, deleted with it -- SM-12) -- pass a recording."
        )
    if not args.recording.is_file():
        raise NativeUnsupported(f"no such recording: {args.recording}")

    tmp_dir = Path(tempfile.gettempdir())
    if args.pipeline is not None:
        spec_json = _resim_to_spec_json(args, tmp_dir)
    else:
        sidecar = args.recording.with_suffix(args.recording.suffix + ".spec.json")
        if sidecar.is_file():
            spec_json = sidecar
        else:
            raise NativeUnsupported(
                f"{args.recording} has no --pipeline and no matching {sidecar.name} sidecar next to it: "
                "vantage_app.exe cannot open a bare recording (R-SIM-5's own 'replay', reading only what "
                "the file already contains) -- its positional argument is always a Resolved Run Spec "
                "(simEngineCreate's run_spec_json_path), never a raw .mcap, and its own argv refuses "
                "--pipeline/--search directly (see this module's own top note). Pass --pipeline (and "
                "usually --search/--config) so this wrapper can resim it for you -- the Python viewer "
                "that used to serve a bare replay is deleted (SM-12), with no native equivalent yet."
            )

    exe = find_vantage_app_exe()
    argv = [str(exe), str(spec_json)]
    if args.config is not None:
        argv += ["--config", str(Path(args.config).resolve())]
    if args.project:
        argv += ["--project", str(args.project)]
    for root in args.plugin_root:
        argv += ["--plugin-root", str(Path(root).resolve())]
    env_path = os.environ.get("ADAS_SIM_PLUGIN_PATH", "")
    for p in env_path.split(os.pathsep):
        if p:
            argv += ["--plugin-root", str(Path(p).resolve())]
    return argv


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        argv = build_native_argv(args)
    except NativeUnsupported as exc:
        print(f"vantage (native): {exc}", file=sys.stderr)
        return 1
    print(f"$ {' '.join(argv)}")
    return subprocess.call(argv)


if __name__ == "__main__":
    sys.exit(main())
