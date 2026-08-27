# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Vantage launcher -- the front door to `scripts/vantage_native.py` (real
`vantage_app.exe`, `WP-34`) and, via the "Legacy Python viewer" checkbox,
`scripts/vantage.py` / the `sim` CLI (the retiring Python scene/render/
player implementation, `SM-12`, gated separately -- see `modules/sim/CLAUDE.md`).

`vantage.bat` with no arguments opens this (`vantage.bat --legacy` opens it
with the checkbox pre-checked); with direct arguments it goes straight
through to `vantage_native.py` (or, with `--legacy`, `vantage.py`), so every
script, CI job and documented command line keeps working exactly as before
this pass -- this screen's own default just changed to match.

**Why a launcher exists at all.** Vantage has a real argument surface --
recording, plug-in root, project, preset, start time, pipeline, search path,
config path -- and a `.bat` cannot help you choose any of them. It cannot tell
you which plug-in roots exist on this machine, cannot warn you that the one you
picked is known to crash, and cannot show you the command it is about to run.
This can.

**Three deliberate constraints, each with a reason:**

1. **Tkinter, stdlib only -- never PySide6.** The launcher must start on an
   install that has no `viewer` extra, precisely so it can *tell you that* and
   offer the fix, rather than dying with an `ImportError` on the one screen
   whose job is to get you running. Every heavier import happens in the child
   process, never here.

2. **It shows the command it runs, always, and copyably.** Same discipline
   `CampaignWidget.batch_invocation_text` follows for `sim batch` (`R-SIM-16`):
   a GUI that builds an invocation you cannot see or reproduce is a GUI you
   have to trust. This one you can paste into a terminal.

3. **It never re-implements a verb.** Every button spawns `vantage.py` or
   `sim <verb>` as a subprocess. There is no second code path that could
   disagree with the CLI (`GT-9` -- `app/`/`cli/` hold no logic; this is
   dev tooling one level further out, and the same rule applies harder).

**The plug-in-root validator is the point of the whole screen** (`AR-61`). A
component's plug-ins can be loaded from two places and they are *not*
equivalent today:

  - a **source checkout** (`modules/df`) -- works;
  - a **deployed copy** beside the built DLL -- **crashes** `bsd.zone` with a
    `FileNotFoundError` on `<root>/src/project/<project>/default.yaml`, because
    `ctx.model.bundle_dir` resolves to `None` there and the layer falls back to
    a source-tree-shaped path that cannot exist under a deployed root. The
    exception is swallowed on the render thread, so the symptom is an **empty
    layer tree and no error**.

`R-SIM-20` says the deployed copy is the one that should work, and one day it
will. Until `AR-61` closes, this screen refuses to let you discover that at
tick 0: it inspects whatever you pick and says which kind it is, in words,
before you launch.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

SIM_DIR = Path(__file__).resolve().parent.parent
MODULES_DIR = SIM_DIR.parent
VANTAGE_PY = SIM_DIR / "scripts" / "vantage.py"
VANTAGE_NATIVE_PY = SIM_DIR / "scripts" / "vantage_native.py"
CONFIG_PATH = SIM_DIR / "scripts" / "gui_config.json"

#: Where a component's plug-ins live inside whichever root you point at.
PLUGIN_MARKER = Path("sim") / "plugin.yaml"


# --------------------------------------------------------------------------
# discovery -- what exists on THIS machine, so the screen offers real choices
# --------------------------------------------------------------------------

def find_recordings(limit: int = 60) -> list[Path]:
    """Every `.mcap` under `modules/*/tests/**`, newest first.

    Scoped to `tests/` on purpose: a build tree can hold hundreds of scratch
    recordings and none of them is what you meant to open.
    """
    found: list[Path] = []
    for module in sorted(MODULES_DIR.iterdir()):
        tests = module / "tests"
        if module.is_dir() and tests.is_dir():
            found.extend(tests.rglob("*.mcap"))
    found.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return found[:limit]


def find_plugin_roots() -> list[Path]:
    """Every directory carrying `sim/plugin.yaml` -- both checkouts and
    deployed copies, because you should be able to *see* both and be told
    which is which, not have one hidden from you."""
    roots: list[Path] = []
    for module in sorted(MODULES_DIR.iterdir()):
        if not module.is_dir():
            continue
        if (module / PLUGIN_MARKER).is_file():
            roots.append(module)
        for candidate in module.glob("build-*/**/" + PLUGIN_MARKER.as_posix()):
            roots.append(candidate.parent.parent)
    return roots


def _exports_viz_abi(dll_path: Path) -> bool:
    """Best-effort: does this DLL export the real native viz ABI
    (`vizManifest`/`vizAbiVersion`, `viz/abi/manifest_builder.hpp`)? A
    generic export-table probe, not a name -- distinguishes a component's
    real viz plugin from its SIL/compute build (both carry a `.dll` and
    both carry `sim/plugin.yaml`, verified live). Windows-only (`ctypes.
    WinDLL`); on any load failure or off Windows, returns `False` so the
    caller falls through to the honest "cannot confirm" message rather than
    a guessed `ok`.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        dll = ctypes.WinDLL(str(dll_path))
        return hasattr(dll, "vizManifest") or hasattr(dll, "vizAbiVersion")
    except OSError:
        return False


def classify_plugin_root(root: str | Path, *, native: bool = False) -> tuple[str, str]:
    """`(state, message)` for a chosen plug-in root -- `ok` / `warn` / `bad`.

    Two different questions depending on which host will load it:

    `native=False` (the Python viewer, `vantage.py`/`--legacy`): encodes
    `AR-61` so it cannot be tripped over. The distinguishing fact is not the
    path's shape but whether `src/project/` is reachable from it, because
    that is exactly what `df/sim/layers/bsd.py` falls back to reading when
    `ctx.model.bundle_dir` is `None`.

    `native=True` (`vantage_app.exe`, `WP-34`): `AR-61` does not apply --
    the C++ host has no such fallback path at all. But a component's
    DEPLOYED tree carries *two* different built libraries side by side
    (e.g. `df_sil.dll`, the SUT compute engine, and `df_viz.dll`, the real
    viz plugin) and `sim/plugin.yaml` sits beside BOTH of them (it is the
    Python-plugin descriptor, unrelated to the native ABI) -- so "does this
    directory have a `.dll`" is not enough to tell them apart. Verified
    live: pointing `vantage_app.exe --plugin-root` at an SUT-only directory
    (`df_sil`'s own) loads, never paints a window and exits -- the exact
    silent-looking failure a good check exists to catch before launch. The
    real distinguishing fact, also verified live: only the real viz plugin
    exports `vizManifest`/`vizAbiVersion` -- a `ctypes` probe of the DLL's
    own export table, generic across any component (no name in this check),
    not a guess from the directory's shape.

    Takes `str | Path` and tests emptiness on the **string**: `Path("")` is
    `Path(".")`, which is a real, existing directory, so a `Path`-only
    signature reported "no plug-in root here" for an empty box instead of
    "you have not chosen one" -- a wrong answer to a question the user had
    not asked yet.
    """
    text = str(root).strip()
    if not text or text == ".":
        return "warn", "No plug-in root chosen: only the framework's own layers (ego, frame) will draw."
    root = Path(text)
    if not root.is_dir():
        return "bad", f"Not a directory: {root}"
    if not (root / PLUGIN_MARKER).is_file():
        return "bad", f"No {PLUGIN_MARKER.as_posix()} here -- this is not a plug-in root."
    if native:
        libs = sorted(root.glob("*.dll")) + sorted(root.glob("*.so"))
        if not libs:
            return (
                "bad",
                "No built library (.dll/.so) here -- the native host cannot load a bare source "
                "checkout. Point it at the DEPLOYED build directory of the component's OWN VIZ "
                "target (e.g. ..\\df\\build-sil_viz-vs2026\\src\\platform\\df_viz\\Release).",
            )
        viz_libs = [lib for lib in libs if _exports_viz_abi(lib)]
        if viz_libs:
            return (
                "ok",
                f"Deployed build directory carrying a real viz plugin ({viz_libs[0].name}) -- the "
                "form vantage_app.exe needs, verified live (WP-34).",
            )
        return (
            "bad",
            f"{libs[0].name} does not export vizManifest/vizAbiVersion -- this looks like a compute "
            "(SIL) build, not the component's VIZ build. Verified live: pointing the native host at "
            "an SUT-only directory loads, never paints a window, and exits. Point it at the "
            "component's own <name>_viz build directory instead.",
        )
    if (root / "src" / "project").is_dir():
        return "ok", f"Source checkout -- verified working. Layers load from {root.name}/sim/."
    return (
        "warn",
        "DEPLOYED copy (no src/project/). Known to crash bsd.zone with a swallowed "
        "FileNotFoundError -- you get an EMPTY layer tree and no message (AR-61). "
        "Prefer the source checkout until that closes.",
    )


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

#: Per-field help: `(placeholder, tooltip)`. **One table, two surfaces** --
#: the grey ghost text inside an empty box and the hover tooltip are rendered
#: from the same entry, so they cannot drift into saying different things
#: about the same field. Every example below is a real path or value on this
#: repository, not an invented one: `close`/`wide` are the actual
#: `view.viewport.DEFAULT_PRESETS` keys, and `df_only.yaml` is the real
#: pipeline `sut.pipeline: df_only` names.
FIELD_HELP: dict[str, tuple[str, str]] = {
    "recording": (
        "…/df/tests/carla_testruns/bsd/bsd_ego_lane_exit.mcap    (optional)",
        "The .mcap to open.\n\n"
        "LEAVE EMPTY to get Vantage's start page (recent files, Open Recording…, "
        "Probe a Library…) instead of a recording.\n\n"
        "The dropdown lists your recent files first, then every .mcap under "
        "modules/*/tests/**, newest first.",
    ),
    "plugin_root": (
        "..\\df                                   (a component checkout)",
        "Where a component's LAYERS come from -- the picture of that component's "
        "own function.\n\n"
        "Use the SOURCE CHECKOUT: ..\\df\n"
        "Not the built directory yet -- the deployed copy crashes bsd.zone with a "
        "swallowed error and leaves an EMPTY layer tree (AR-61, open).\n\n"
        "LEAVE EMPTY and you still get the framework's own layers (ego, frame) -- "
        "just nothing function-specific.",
    ),
    "project": (
        "base",
        "Which calibration set to resolve geometry from (R-VAR-4).\n\n"
        "Real values in this repo: base · cus1 · 2w_base\n\n"
        "'base' is the no-specific-programme fallback and is what every scenario's "
        "expect: block is written against. Switching this must visibly change the "
        "drawn ego (R-SIM-3).",
    ),
    "preset": (
        "close                                     (or: wide)",
        "Starting viewport zoom. Exactly two exist:\n\n"
        "  close  -- tight around the ego, for zone/warning work\n"
        "  wide   -- more of the road, for approach and cut-in\n\n"
        "LEAVE EMPTY for the default. You can pan and zoom once it is open, so "
        "this only sets where you start.",
    ),
    "at_s": (
        "0                                          (seconds)",
        "Seconds into the recording to open at -- NOT a tick number.\n\n"
        "LEAVE EMPTY to start at 0. Useful when you already know roughly when "
        "the interesting thing happens (e.g. 5 for bsd_ego_lane_exit).",
    ),
    "pipeline": (
        "..\\df\\sim\\pipelines\\df_only.yaml      (only to RESIM)",
        "A pipeline makes this a RESIM -- the component's DLL is re-executed "
        "against the recording, so its outputs (and its layers) actually exist.\n\n"
        "Real one here: ..\\df\\sim\\pipelines\\df_only.yaml\n\n"
        "LEAVE EMPTY to REPLAY: you see only what the file already contains. A "
        "stimulus-only recording then shows bsd.warning as (unavailable) -- that "
        "is correct, not a bug.\n\n"
        "If you set this, you almost certainly need --search and --config too.",
    ),
    "search": (
        "..\\df\\build-sil-vs2026\\src\\platform\\df_sil\\Release",
        "The directory holding the component's built library (df_sil.dll).\n\n"
        "Only needed with a pipeline -- it is how 'impl: dll:df_sil' is resolved "
        "to a real file (P-5).\n\n"
        "Note this is the BUILT directory, and using it here is fine: AR-61 is "
        "about loading LAYERS from there, not the DLL.",
    ),
    "config_path": (
        "..\\df\\build-sil-vs2026\\src\\platform\\df_sil\\Release\\config",
        "The packed config bundle the DLL is initialised with (adasInit).\n\n"
        "Only needed with a pipeline. It is the 'config' folder sitting beside "
        "the built DLL.\n\n"
        "Getting this wrong is how the viewer and the SUT end up reading "
        "different calibration and agreeing only by coincidence (R-SIM-3a).",
    ),
}


class Tooltip:
    """Hover help. Same shape as `df_sim_gui.py`'s own `_Tooltip` -- a
    borderless `Toplevel` shown on `<Enter>`, destroyed on `<Leave>`."""

    def __init__(self, widget: tk.Widget, text: str):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<FocusIn>", self._show, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text, justify="left", background="#ffffe0",
            relief="solid", borderwidth=1, wraplength=560, padx=8, pady=6,
            font=("Segoe UI", 9) if sys.platform == "win32" else None,
        ).pack()

    def _hide(self, _event=None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def attach_placeholder(entry: tk.Entry | ttk.Entry, text: str) -> None:
    """Grey ghost text while the box is empty and unfocused.

    Tk has no native placeholder, and the usual trick -- writing the hint into
    the widget as real text -- is wrong here: this GUI builds a command line
    from these boxes, so a hint that lives in the variable would be *submitted*
    as an argument. This paints a separate label over the entry instead, so the
    underlying `StringVar` stays genuinely empty.
    """
    ghost = tk.Label(entry, text=text, anchor="w", foreground="#8a8a8a",
                     background="white" if sys.platform == "win32" else None)

    def sync(*_):
        if entry.get():
            ghost.place_forget()
        else:
            ghost.place(x=3, rely=0.5, anchor="w")

    entry.bind("<KeyRelease>", sync, add="+")
    entry.bind("<FocusIn>", lambda *_: ghost.place_forget(), add="+")
    entry.bind("<FocusOut>", sync, add="+")
    entry.after(80, sync)


def load_cfg() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}


def save_cfg(**updates) -> None:
    cfg = load_cfg()
    cfg.update({k: v for k, v in updates.items() if v is not None})
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass                                                 # a read-only tree must not break the launcher


def vantage_recent_files() -> list[Path]:
    """Vantage's OWN recent-file list, when it is readable.

    Read through `app.shell.startpage.load_recent_files` rather than
    reconstructing its path: that store lives under
    `render.viewer._config_root()`, which is `QStandardPaths`-derived (`P-7`),
    and hand-rolling the same path here would be the drifting second copy this
    project refuses everywhere. It needs Qt, so it is **best effort** -- the
    launcher's whole point is working without it.
    """
    try:
        sys.path.insert(0, str(SIM_DIR / "src"))
        from adas_sim.player.shell.shell.startpage import load_recent_files
        return list(load_recent_files())
    except Exception:                                        # noqa: BLE001
        return []


# --------------------------------------------------------------------------
# subprocess runner -- one place, streaming into the output pane
# --------------------------------------------------------------------------

class ProcessRunner:
    """Runs one child at a time, streaming stdout+stderr into a queue the Tk
    main loop drains. Threaded rather than `after()`-polled `readline` so a
    chatty child cannot stall the UI."""

    def __init__(self, sink: queue.Queue):
        self._sink = sink
        self._proc: subprocess.Popen | None = None

    @property
    def busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, argv: list[str], cwd: Path) -> None:
        if self.busy:
            self._sink.put(("log", "A command is already running -- stop it first.\n"))
            return
        self._sink.put(("log", f"\n$ {' '.join(argv)}\n"))
        try:
            self._proc = subprocess.Popen(
                argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as exc:
            self._sink.put(("log", f"FAILED to start: {exc}\n"))
            self._sink.put(("done", 1))
            return
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            self._sink.put(("log", line))
        code = self._proc.wait()
        self._sink.put(("log", f"[exit {code}]\n"))
        self._sink.put(("done", code))

    def stop(self) -> None:
        if self.busy and self._proc is not None:
            self._proc.terminate()
            self._sink.put(("log", "[terminated]\n"))


# --------------------------------------------------------------------------
# the window
# --------------------------------------------------------------------------

class LauncherApp:
    def __init__(self, root: tk.Tk, legacy_default: bool = False):
        self.root = root
        root.title("Vantage launcher")
        root.geometry("1000x760")
        root.minsize(860, 620)

        cfg = load_cfg()
        self.events: queue.Queue = queue.Queue()
        self.runner = ProcessRunner(self.events)

        self.recording = tk.StringVar(value=cfg.get("recording", ""))
        self.plugin_root = tk.StringVar(value=cfg.get("plugin_root", ""))
        self.project = tk.StringVar(value=cfg.get("project", "base"))
        self.preset = tk.StringVar(value=cfg.get("preset", ""))
        self.at_s = tk.StringVar(value=cfg.get("at_s", ""))
        self.pipeline = tk.StringVar(value=cfg.get("pipeline", ""))
        self.search = tk.StringVar(value=cfg.get("search", ""))
        self.config_path = tk.StringVar(value=cfg.get("config_path", ""))
        # Default OFF (native, `vantage_app.exe`, `WP-34`) unless the config
        # already had it on, or `vantage.bat --legacy` asked for it.
        self.legacy = tk.BooleanVar(value=bool(cfg.get("legacy", False)) or legacy_default)

        for var in (self.recording, self.plugin_root, self.project, self.preset,
                    self.at_s, self.pipeline, self.search, self.config_path, self.legacy):
            var.trace_add("write", lambda *_: self._refresh())

        self._build()
        self._refresh()
        self.root.after(60, self._drain)

    # -- layout ------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        # --- what to open -------------------------------------------------
        box = ttk.LabelFrame(outer, text="Recording")
        box.pack(fill="x", **pad)
        recs = [str(p) for p in vantage_recent_files()] + [str(p) for p in find_recordings()]
        seen: dict[str, None] = {}
        for r in recs:
            seen.setdefault(r, None)
        self.rec_combo = ttk.Combobox(box, textvariable=self.recording, values=list(seen))
        self.rec_combo.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self._help(self.rec_combo, "recording")
        ttk.Button(box, text="Browse…", command=self._browse_recording).pack(side="left", padx=6)
        ttk.Label(box, text="(leave empty for Vantage's start page)").pack(side="left", padx=6)

        # --- plug-in root, with the validator -----------------------------
        box = ttk.LabelFrame(outer, text="Plug-in root  —  where a component's layers come from")
        box.pack(fill="x", **pad)
        row = ttk.Frame(box); row.pack(fill="x")
        self.root_combo = ttk.Combobox(
            row, textvariable=self.plugin_root, values=[str(p) for p in find_plugin_roots()])
        self.root_combo.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self._help(self.root_combo, "plugin_root")
        ttk.Button(row, text="Browse…", command=self._browse_plugin_root).pack(side="left", padx=6)
        self.root_status = ttk.Label(box, text="", wraplength=940, justify="left")
        self.root_status.pack(fill="x", padx=8, pady=(0, 6))

        # --- run options --------------------------------------------------
        box = ttk.LabelFrame(outer, text="Run")
        box.pack(fill="x", **pad)
        for label, var, key, width, choices in (
            ("project", self.project, "project", 14, ("base", "cus1", "2w_base")),
            ("preset", self.preset, "preset", 14, ("", "close", "wide")),
            ("start at (s)", self.at_s, "at_s", 10, None),
        ):
            ttk.Label(box, text=label).pack(side="left", padx=(8, 2), pady=6)
            if choices is None:
                widget = ttk.Entry(box, textvariable=var, width=width)
            else:
                # A closed set is a dropdown, not a free-text box you can typo
                # into: `preset` accepts exactly `close`/`wide`, and `project`
                # exactly what `src/project/` holds. Offering them removes a
                # whole class of "why did nothing change?".
                widget = ttk.Combobox(box, textvariable=var, width=width, values=choices)
            widget.pack(side="left", pady=6)
            self._help(widget, key)
        ttk.Checkbutton(
            box, text="Legacy Python viewer (--legacy)", variable=self.legacy,
        ).pack(side="left", padx=(16, 6), pady=6)

        # --- advanced ------------------------------------------------------
        adv = ttk.LabelFrame(outer, text="Pipeline  —  only needed to RESIM (compute stage outputs)")
        adv.pack(fill="x", **pad)
        for label, var, key, browse in (
            ("pipeline.yaml", self.pipeline, "pipeline", self._browse_pipeline),
            ("--search (dll dir)", self.search, "search", self._browse_dir_search),
            ("--config", self.config_path, "config_path", self._browse_dir_config),
        ):
            row = ttk.Frame(adv); row.pack(fill="x")
            ttk.Label(row, text=label, width=18).pack(side="left", padx=6, pady=3)
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(side="left", fill="x", expand=True, pady=3)
            self._help(entry, key)
            ttk.Button(row, text="…", width=3, command=browse).pack(side="left", padx=6)
        ttk.Label(
            adv, wraplength=940, justify="left",
            text=("Without a pipeline you are REPLAYING what the file already contains. A "
                  "stimulus-only recording has no stage outputs, so a function's own layers "
                  "will show as (unavailable) — that is correct, not a bug. Give a pipeline "
                  "to compute them."),
        ).pack(fill="x", padx=8, pady=(0, 6))

        # --- the command --------------------------------------------------
        box = ttk.LabelFrame(outer, text="Command that will run")
        box.pack(fill="x", **pad)
        self.cmd_text = tk.Text(box, height=3, wrap="word")
        self.cmd_text.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(box, text="Copy", command=self._copy_command).pack(side="left", padx=6)

        # --- actions -------------------------------------------------------
        bar = ttk.Frame(outer); bar.pack(fill="x", **pad)
        ttk.Button(bar, text="▶  Launch Vantage", command=self.launch_vantage).pack(side="left", padx=4)
        ttk.Button(bar, text="Probe a library…", command=self.probe_library).pack(side="left", padx=4)
        ttk.Button(bar, text="sim doctor", command=self.run_doctor).pack(side="left", padx=4)
        ttk.Button(bar, text="Render snapshot", command=self.render_snapshot).pack(side="left", padx=4)
        ttk.Button(bar, text="Stop", command=self.runner.stop).pack(side="right", padx=4)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side="right", padx=4)

        # --- output ---------------------------------------------------------
        box = ttk.LabelFrame(outer, text="Output")
        box.pack(fill="both", expand=True, **pad)
        self.out = ScrolledText(box, wrap="word", height=14)
        self.out.pack(fill="both", expand=True, padx=6, pady=6)

    def _help(self, widget, key: str) -> None:
        """Attach both surfaces of `FIELD_HELP[key]` to one widget -- the ghost
        placeholder and the hover/focus tooltip. One call site per field, so a
        field can never end up with one and not the other."""
        placeholder, tooltip = FIELD_HELP[key]
        Tooltip(widget, tooltip)
        attach_placeholder(widget, placeholder)

    # -- pickers -----------------------------------------------------------

    def _browse_recording(self) -> None:
        p = filedialog.askopenfilename(
            title="Open recording", filetypes=[("Recordings", "*.mcap *.jsonl"), ("All", "*.*")])
        if p:
            self.recording.set(p)

    def _browse_plugin_root(self) -> None:
        p = filedialog.askdirectory(title="Component checkout or built library directory")
        if p:
            self.plugin_root.set(p)

    def _browse_pipeline(self) -> None:
        p = filedialog.askopenfilename(title="Pipeline", filetypes=[("YAML", "*.yaml *.yml")])
        if p:
            self.pipeline.set(p)

    def _browse_dir_search(self) -> None:
        p = filedialog.askdirectory(title="Directory holding the component DLLs")
        if p:
            self.search.set(p)

    def _browse_dir_config(self) -> None:
        p = filedialog.askdirectory(title="Config bundle directory")
        if p:
            self.config_path.set(p)

    # -- command building ---------------------------------------------------

    def build_argv(self) -> list[str]:
        # `vantage_native.py` refuses `--preset`/`--at` by name (no native
        # equivalent, `vantage_native.py`'s own top note) -- omitted from
        # the native command entirely rather than built and then rejected,
        # since a field this screen still shows for the legacy case would
        # otherwise silently produce a doomed command by default.
        legacy = self.legacy.get()
        argv = [sys.executable, str(VANTAGE_PY if legacy else VANTAGE_NATIVE_PY)]
        if self.recording.get().strip():
            argv.append(self.recording.get().strip())
        flags = [("--plugin-root", self.plugin_root), ("--project", self.project)]
        if legacy:
            flags += [("--preset", self.preset), ("--at", self.at_s)]
        flags += [("--pipeline", self.pipeline), ("--search", self.search), ("--config", self.config_path)]
        for flag, var in flags:
            value = var.get().strip()
            if value:
                argv += [flag, value]
        return argv

    def _refresh(self) -> None:
        state, message = classify_plugin_root(self.plugin_root.get(), native=not self.legacy.get())
        colour = {"ok": "#1a7f37", "warn": "#9a6700", "bad": "#b3261e"}[state]
        prefix = {"ok": "OK", "warn": "WARNING", "bad": "ERROR"}[state]
        if not self.legacy.get() and (self.preset.get().strip() or self.at_s.get().strip()):
            message += (' Note: --preset/--at have no native equivalent and are dropped from this '
                        'command -- check "Legacy Python viewer" to use them.')
        self.root_status.configure(text=f"{prefix}:  {message}", foreground=colour)
        self.cmd_text.delete("1.0", "end")
        self.cmd_text.insert("1.0", " ".join(self.build_argv()))

    def _copy_command(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(" ".join(self.build_argv()))
        self._log("[command copied to clipboard]\n")

    # -- actions ------------------------------------------------------------

    def _persist(self) -> None:
        save_cfg(recording=self.recording.get(), plugin_root=self.plugin_root.get(),
                 project=self.project.get(), preset=self.preset.get(), at_s=self.at_s.get(),
                 pipeline=self.pipeline.get(), search=self.search.get(),
                 config_path=self.config_path.get(), legacy=self.legacy.get())

    def launch_vantage(self) -> None:
        self._persist()
        state, message = classify_plugin_root(self.plugin_root.get(), native=not self.legacy.get())
        if state == "bad":
            self._log(f"Refusing to launch -- {message}\n")
            return
        if state == "warn":
            self._log(f"WARNING: {message}\n")
        self.runner.start(self.build_argv(), cwd=SIM_DIR)

    def probe_library(self) -> None:
        p = filedialog.askopenfilename(
            title="Component library to probe", filetypes=[("Libraries", "*.dll *.so"), ("All", "*.*")])
        if p:
            self.runner.start([sys.executable, "-c",
                               "import sys;from adas_sim.cli import main;sys.exit(main(['probe',sys.argv[1]]))",
                               p], cwd=SIM_DIR)

    def run_doctor(self) -> None:
        argv = [sys.executable, "-c",
                "import sys;from adas_sim.cli import main;sys.exit(main(['doctor']+sys.argv[1:]))"]
        if self.plugin_root.get().strip():
            argv += ["--component", self.plugin_root.get().strip()]
        self.runner.start(argv, cwd=SIM_DIR)

    def render_snapshot(self) -> None:
        rec = self.recording.get().strip()
        if not rec:
            self._log("Pick a recording first -- a snapshot needs one.\n")
            return
        out = SIM_DIR / "logs" / "launcher_snapshot.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        at = self.at_s.get().strip() or "0"
        self._log(f"Rendering {rec} at t={at}s -> {out}\n")
        self.runner.start(
            [sys.executable, "-c",
             "import sys;from adas_sim.cli import main;sys.exit(main(['render']+sys.argv[1:]))",
             rec, "--at", at, "--out", str(out)],
            cwd=SIM_DIR)

    # -- output pump ---------------------------------------------------------

    def _log(self, text: str) -> None:
        self.out.insert("end", text)
        self.out.see("end")

    def _clear(self) -> None:
        self.out.delete("1.0", "end")

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._log(payload)
        except queue.Empty:
            pass
        self.root.after(60, self._drain)


def main() -> int:
    # `vantage.bat --legacy` (no further args) forwards this one flag so
    # the picker opens with "Legacy Python viewer" pre-checked -- the same
    # opt-in this launcher's own direct-args path honours (vantage.bat's
    # own docstring).
    legacy_default = "--legacy" in sys.argv[1:]
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    LauncherApp(root, legacy_default=legacy_default)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
