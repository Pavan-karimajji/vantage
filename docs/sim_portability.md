# Portability — Windows today, Ubuntu tomorrow, no rewrite

Status: **normative for every stage.** There is no Ubuntu machine today. There
will be. This document exists so that the day one appears, the work is
*configuration*, not *porting* — and so that an implementing session never has
to guess which of two behaviours was intended.

Companion to [`sim_architecture.md`](sim_architecture.md) (master) and
[`sim_implementation_plan.md`](sim_implementation_plan.md) (build order). Rules:
root `.claude/rules/sim.md`.

---

## 0. The one-line contract

> **Every rule below is enforced by a test, not by intention.** A portability
> claim that only a human remembers is a portability claim that is already
> false.

The cost of obeying these rules now is a few lines per stage. The cost of
retrofitting them is a rewrite of every path, every process launch and every
file write in the framework — which is exactly the "struggle" this document is
written to prevent.

---

## 1. What is and is not in scope

| | Today | When Ubuntu arrives |
|---|---|---|
| **Framework** (`adas_sim`, pure Python) | Windows | must run unchanged |
| **CLI** (`sim …`) | Windows | must run unchanged |
| **Player GUI** (Qt) | Windows | must run unchanged |
| **Component SIL libraries** (`*.dll`) | Windows, MSVC | rebuilt as `*.so`, GCC/Clang |
| **World-model clients** (`sources/`) | whatever the vendor ships | per-source; a source may legitimately be Windows-only |
| **Packaged player executable** | `.exe` (S-D5) | a second packaging target, not a second codebase |

**In scope now:** everything the framework itself does — paths, process
handling, file I/O, encodings, library loading, packaging inputs.

**Not in scope now:** actually producing Ubuntu binaries of the components, or
an Ubuntu build of the packaged player. Those are build-system work
(`R-BUILD`), scheduled when a machine exists. Nothing here blocks them.

**Deliberately allowed to be platform-specific:** a `sources/` client for a
world model that only ships on one OS. It degrades by *being absent*, with a
named reason (`R-SIM-14`'s capability discipline), never by crashing.

---

## 2. Rules

### P-1 — Never write a path as a string

Every path is a `pathlib.Path`. Never `"a/b/c"`, never `os.path.join`, never a
literal `\` or `/` separator in code.

```python
# wrong
cfg = base + "/config/default.yaml"
cfg = os.path.join(base, "config\\default.yaml")

# right
cfg = base / "config" / "default.yaml"
```

**Why it matters beyond separators:** `Path` also carries case-sensitivity
behaviour. `Config/Default.yaml` resolves on Windows and fails on Ubuntu — see
`P-3`.

### P-2 — Never hard-code an absolute path, anywhere

Not in code, not in a design document, not in a test fixture, not in a comment
that says "for example". Resolution order for anything outside the repo:

1. an explicit argument;
2. an environment variable, documented where it is read;
3. a repo-relative path derived from `Path(__file__)`;
4. a *shape* test (a directory that contains the subdirectories we expect).

Never the current working directory — a script must behave identically run from
the repo root, from `modules/sim`, or from anywhere else.

Enforced by `DC-2` over documents and `UT-A1-4` over code.

### P-3 — Assume a case-sensitive filesystem

Windows is case-insensitive; ext4 is not. A file referenced as `Ego_Params.yaml`
but stored as `ego_params.yaml` works today and breaks the day it moves.

- All new file names are lowercase `snake_case` (`R-NAME-5`).
- Any name read from configuration is compared exactly, never case-folded.
- The config bundle's `bundle.sha256` covers file **names** as well as contents,
  so a case-only rename is a bundle mismatch rather than a silent substitution.

Enforced by `UT-A2-6`: a fixture referencing a differently-cased name must fail
to resolve on **every** platform, not just Linux.

### P-4 — Text is UTF-8, newline is `\n`, on both platforms

Three separate failure modes, one rule each:

| Concern | Rule |
|---|---|
| **Reading** | always `encoding="utf-8"`; never rely on `locale.getpreferredencoding()` |
| **Writing** | always `encoding="utf-8", newline="\n"` — so a file written on Windows and one written on Ubuntu are byte-identical |
| **Console** | reconfigure `stdout`/`stderr` to UTF-8 with `errors="replace"` at entry |

The console rule is not theoretical. A Windows console defaults to `cp1252` and
raises `UnicodeEncodeError` on the em-dashes, arrows and check marks these
design documents are full of; a Linux terminal defaults to UTF-8 and does not.
**This bug was hit while writing the design-evidence harness itself** — see
`docs/py/_common.py`, where the fix is three lines at import time. Every entry
point (CLI, GUI, each `docs/py` script) does the same.

Byte-identical output also matters for `GT-4`-style golden tests: a golden file
that differs only by `\r\n` is a false failure that trains people to ignore
failures.

### P-5 — Library loading is abstracted at exactly one place

`impl: "dll:df_sil.dll"` in a pipeline names a **stem**, not a file name. One
resolver expands it:

| Platform | Pattern searched |
|---|---|
| Windows | `df_sil.dll`, `<stem>.dll` |
| Linux | `libdf_sil.so`, `df_sil.so`, `<stem>.so` |

- Written in `contracts/loader.py`, and nowhere else in the framework.
- A pipeline file is therefore **portable as written** — the same YAML runs on
  both platforms with no edit, which is `R-SIM-16`'s "one project file" promise
  extended across platforms.
- A stem that resolves to nothing is a load error naming **every** pattern
  tried and **every** directory searched — never "file not found".
- `ctypes.CDLL` is used identically on both; calling convention is `cdecl` on
  both for the generic ABI (no `WinDLL`, no `stdcall`).

Enforced by `UT-C1c-14` (resolution table, both platforms, parametrised) and
`UT-C1c-15` (the error message names all candidates).

### P-6 — No shell, no `.bat`, no platform-specific process launch

- `subprocess` is always called with a **list**, never a string, and never
  `shell=True`.
- No framework code invokes `cmd.exe`, PowerShell or `bash`.
- The CLI is a Python entry point (`sim = adas_sim.cli:main` in
  `pyproject.toml`), so the launcher is generated per platform by the installer
  rather than written by us.
- Build machinery (`build.bat` / `build.sh`) is out of this document's scope and
  governed by `R-BUILD-3` — but note it already ships both.

### P-7 — Qt is written once, and the platform-specific parts are named

PySide6 (`OD-1`) runs on both. The parts that differ are enumerated so nobody
discovers them late:

| Concern | Rule |
|---|---|
| Settings/state location | `QStandardPaths.AppConfigLocation` — never `%LOCALAPPDATA%` or `~/.config` written by hand |
| Fonts | never name a font family directly; use `QFontDatabase.systemFont(...)` with the theme table supplying size/weight only |
| High-DPI | `Qt.HighDpiScaleFactorRoundingPolicy.PassThrough` set before the app object, on both |
| Headless | every renderer must work with `QT_QPA_PLATFORM=offscreen`, which is how the GUI is tested in CI and on a machine with no display |
| File dialogs | Qt's own, not native, when a test needs to drive them |

`ST-B3-3` runs the viewer offscreen and captures a frame — the test that keeps
this true.

### P-8 — Time, sorting and randomness are explicit

- Timestamps are **integer nanoseconds** (`t_ns`, `log_time_ns`), never floats
  and never `datetime.now()` inside anything recorded. Already required by
  `R-SIM-14`; restated because float seconds are where cross-platform
  reproducibility usually dies.
- Any iteration whose order reaches an output is **sorted explicitly**.
  `os.listdir` / `Path.iterdir` / `glob` order differs between filesystems, and
  an unsorted directory walk is the classic "works on my machine" recording
  diff.
- Any randomness takes an explicit seed recorded in the run manifest.

Enforced by `UT-A4-8` (two recordings of the same run are byte-identical) and
`UT-D7-6` (a round-trip preserves topic order).

### P-9 — The config bundle is platform-neutral

`R-SIM-3a` packs the bundle beside the library. Consequences here:

- The bundle contains YAML and a manifest — **never** a compiled artefact,
  never a path, never a platform token.
- `bundle.sha256` is computed over UTF-8 bytes with `\n` newlines and
  **sorted** relative POSIX-style paths, so the same source tree produces the
  same hash on both platforms. A bundle built on Windows and one built on
  Ubuntu must hash identically, or the "did the two readers agree?" guarantee
  is platform-dependent — which is worse than not having it.

Enforced by `UT-C5-5`: hash computed from a fixture with mixed line endings and
mixed-case directory iteration order is stable.

### P-10 — Dependencies must exist on both platforms

Every dependency in `pyproject.toml` is checked for a Linux wheel before it is
added. The current set (`pyyaml`, `protobuf`, `mcap`, `numpy`, `PySide6`,
`matplotlib`, `foxglove-sdk`, `pytest`) all ship both. A dependency that does
not is either replaced or moved behind an extra with a named reason.

`opencv-python` is already excluded on other grounds (implementation plan §1);
that exclusion also removes the single most common source of platform-specific
binary trouble.

---

## 3. What an implementing session must do, per stage

Short enough to actually follow:

- [ ] every new path is a `Path`, derived from `__file__` or an argument (`P-1`, `P-2`)
- [ ] every `open`/`read_text`/`write_text` names `encoding="utf-8"`, and writes name `newline="\n"` (`P-4`)
- [ ] every entry point reconfigures the console (`P-4`)
- [ ] every directory iteration that reaches an output is `sorted()` (`P-8`)
- [ ] no new `subprocess` call uses a string or `shell=True` (`P-6`)
- [ ] no new absolute path in code, docs, tests or comments (`P-2`)
- [ ] any new library load goes through `contracts/loader.py` (`P-5`)

This list is repeated as a checkbox block in the implementation plan's
per-stage template, so it is ticked 23 times rather than read once.

---

## 4. The Ubuntu bring-up, when it happens

Written now so the estimate is honest and nobody plans around a guess.

| Step | Work | Depends on |
|---|---|---|
| 1 | `pip install -e modules/sim` and run `pytest` | nothing — should pass on day one if §3 was obeyed |
| 2 | Run `docs/py/run_all.py` | nothing |
| 3 | Build one component as `libdf_sil.so` | `R-BUILD` toolchain work, unrelated to this module |
| 4 | `sim probe libdf_sil.so` and one resim | steps 1 and 3 |
| 5 | Viewer under a real display, and offscreen | step 1 |
| 6 | Package the player for Linux (S-D5 second target) | steps 1–5 |

Steps 1, 2, 4 and 5 are the framework's whole exposure, and each is a command
whose expected output is already specified. **Step 3 is the only real work, and
it is not this module's.**

`ST-D8-1` (implementation plan) is the gate that proves it: the full suite green
on a Linux runner with components absent, skipping exactly the integration tests
that need a built library and naming why.

---

## 5. What is deliberately *not* promised

- **Bit-identical numerical results across platforms.** Different compilers and
  libm implementations produce different last-bit floating-point results.
  Determinism is guaranteed per machine and per build (`R-SIM-5`), and
  `OQ-7` records this as open. A resim baseline is therefore tied to a
  platform, and a recording's manifest already carries enough to detect that.
- **A single packaged binary for both platforms.** Two packaging targets, one
  codebase.
- **macOS.** Nothing here prevents it; nothing here tests it.
