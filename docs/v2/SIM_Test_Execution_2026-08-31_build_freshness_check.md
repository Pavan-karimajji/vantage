# SIM Test Execution — 2026-08-31 — build-artifact freshness check (root, cross-submodule)

**Campaign:** design and build the smallest mechanical check that compares a
build artifact's timestamp against its inputs and warns before anyone trusts
it — the named real-world trigger being two accidental incidents in one
week, both already recorded in this file's own history: `cm_viz` (df) stale
since 2026-08-21, missing viz's `9ca1324` (`Span<T>` fix); `sim`'s own `sil`
library stale since 2026-08-25, missing `450031e`'s topic-canonicalization,
which silently blacked out `WP-22`'s camera panel. This record covers the
*design*; the check itself lives at the superproject root
(`scripts/check_build_freshness.py`), not inside this module, because it is
genuinely cross-submodule — a one-line pointer here, not a duplicate.

## Where it lives, and why

Superproject root `scripts/check_build_freshness.py`, beside the other
hand-run cross-submodule checks already there (`check_invariants.py`,
`check_cross_module_trace.py`) — not inside any one component, since the
failure mode spans repos (a `viz` source change, an `sim`/`df` build not
rebuilt against it). Two things explicitly **not** done, stated so they are
not quietly expected later:
- **Not wired into any automated gate.** Hosted CI is out of scope by
  decision (`misc/START_HERE.md` Decision F, this same session); a
  hand-run check matches that decision rather than fighting it.
- **Not added to any component's `scripts/build.py`/`build.bat`.** Those are
  byte-identical across every repo (`R-BUILD-1..3`); touching them is
  cross-submodule build machinery (`R-BUILD-6`) and far bigger than "the
  smallest mechanical check" this item asked for.
- **Run it by hand, from the superproject root, before trusting a build you
  did not just watch compile** — stated in the script's own top docstring,
  same discipline as `check_invariants.py`/`setup.py` already use.

## What it checks

For every Conan-editable-registered package (`conan editable list
--format=json` — the exact registry the real build graph itself resolves
an editable dependency through, so the check can never name a path the real
graph would not also use), every recognised binary (`.dll`/`.so`/`.exe`/
`.lib`) under any of that package's own `build*/` directories is compared
against the newest file in what actually feeds that package's build —
`src/`/`include/`/`conf/` plus its top-level `CMakeLists.txt`/`conanfile.py`
— never the whole tree (a doc, script or launcher `.bat` edit must not read
as "rebuild me").

## A real bug found and fixed before this shipped, not after

The first working version walked each package's **whole** root as "source."
Run against the real editable registry on this machine, it produced 26
findings — almost all false: one build tree's own internal bookkeeping
(`ALL_BUILD.tlog/ALL_BUILD.lastbuildstate`, rewritten on every reconfigure)
was read as "the source changed," so an artifact in a *different*,
genuinely-untouched build tree was flagged stale against it; CMake's own
compiler-probe binaries (`CompilerIdC.exe`) were treated as real
deliverables; and `mathlib/gui.bat` (a dev launcher, unrelated to the
compiled `.lib`) counted as source. **This is exactly the "confident wrong
answer" this whole task list was warned against, one level down, inside the
tool meant to catch that class of mistake.** Found and fixed before
committing, not reported as a known gap: narrowed `package_source_dirs` to
`src/`/`include/`/`conf/`/recipe files only; excluded `CMakeFiles/` and any
`build`/`build-*` directory from ever counting as "source" (`_is_noise`);
fixed a second bug the same pass, a substring vendored-library match that
also caught this project's own `build-gtest-vs2026` directory name (because
it contains the substring "gtest") — now an exact directory-part match plus
a filename-prefix match instead.

Re-run after the fix, same machine, same registry: **2 findings, both real
and plausible** — `modules/interfaces/build/Release/adas-interfaces.lib`
(250.0h behind its own `conanfile.py`) and
`modules/mathlib/build-sil-vs2026/build/Release/adas-mathlib.lib` (108.6h
behind its own `conanfile.py`). Neither investigated or rebuilt here — that
is the check doing its job, not this pass's own scope.

## Tests

`scripts/tests/test_check_build_freshness.py`, 10 cases, same `unittest`
discipline as `test_check_invariants.py` — including a planted-violation
pair for the two bugs found above (a sibling build tree's own bookkeeping
must not count as source; `build-gtest-vs2026` must not be excluded as
vendored `gtest`).

## Verification

- `python3 -m unittest scripts.tests.test_check_build_freshness -v` (from
  the superproject root) — **10/10 pass.**
- `python3 scripts/check_build_freshness.py` against this machine's real
  Conan editable registry — **2 findings, both plausible**, evidence above.
- `scripts/tests/test_check_invariants.py` / `test_conan_publish.py` (the
  pre-existing root suite) — untouched by this change; last confirmed green
  this same session before this item started (27/27, ~125s, dominated by
  `check_invariants.py`'s own whole-tree `rglob` on this filesystem — not
  re-run a second time for this item since nothing in it changed).

## Not done, and not claimed

- No dependency-graph awareness: the check does not know *which* target a
  consumer actually resolved an editable dependency to — it flags every
  stale binary under every `build*/` dir it finds, by design (stated in the
  script's own docstring), not a gap.
- Not wired into `ci_gate.py`, `build.py`, or any hosted job — by decision,
  not oversight (see "Where it lives, and why" above).
- The two real findings above are reported, not fixed — rebuilding
  `interfaces`/`mathlib` is not this item's scope.
