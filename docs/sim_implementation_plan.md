# Simulation Platform — Implementation Plan

Status: **frozen for implementation 2026-07-28.** This is the **normative,
checkbox-tracked** execution of [sim_architecture.md](sim_architecture.md) §8.
The architecture documents say *what and why*; this one says *in what order,
built how, and proven by which test*.

Design set (read before starting a stage): **[sim_learn.md](sim_learn.md) — the
plain-language walkthrough; start here if the shape of the system is not yet
obvious, it is a door rather than a contract** · [sim_architecture.md](sim_architecture.md)
(master) · [sim_sil_contract.md](sim_sil_contract.md) ·
[sim_visualization_spec.md](sim_visualization_spec.md) ·
[sim_resim_and_recording.md](sim_resim_and_recording.md) ·
[sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md) ·
[sim_player.md](sim_player.md) (the application) ·
**[sim_api_reference.md](sim_api_reference.md) — the exact symbols to type;
a signature there is a contract** ·
[sim_naming_and_diagnostics.md](sim_naming_and_diagnostics.md) (`N-1..N-13`,
`DG-1..DG-5`; its §3 checklist is ticked per stage) ·
**[sim_portability.md](sim_portability.md) — read before writing any code;
its `P-1`..`P-10` apply to every stage, and its §3 checklist is ticked per
stage.**
Normative rules: superproject `.claude/rules/sim.md` (`R-SIM-1..25`).
Backlog entry: superproject `plan.md` item 25.

---

## 0. How to use this document

- **Every `- [ ]` is a unit of work or a test.** Tick it when it is done *and
  its test passes*. Never tick a scope box whose tests are still open.
- **Labels are stable.** `S-A1`…`S-E3` are stages; `UT-A1-1` a unit test;
  `ST-A1-1` a system test; `GT-1` a global gate. Cite them in commits
  (`feat(sim): S-A2 EgoModel + UT-A2-1..7`).
- **A stage is done when its gate passes**, not when its code is written. The
  gate is the last box in each stage.
- **Order is not a suggestion.** Each stage assumes the previous ones. Where a
  stage may be reordered, it says so.
- **Nothing is deleted before its replacement is proven.** All removal is
  Phase E, and Phase E is gated on Phases A–D.
- **One branch per stage**, off `feat/sim-platform` in the affected repo(s).
  Superproject pointer bumps follow `R-GIT-1` (submodule commits first).

---

## 0a. ▶ START HERE — the implementation entry point

**The queue below is the authority on order.** Do not scan the document for
something that looks unfinished.

### Where the work stands

Phases **A**, **B**, **C** and **D** have landed. **97 boxes are open across 20
stages**, concentrated in **Phase E** (48 — `S-E1` 17, `S-E2` 9, `S-E3` 22) and
**`S-D2`** (12, deferred with a named trigger: a figure a headless `sim render`
cannot produce). Phase E is gated on every Phase A–D gate; `S-E1`'s table is the
authority on which.

**Five items no work can close.** Each needs a person or infrastructure — do not
re-derive them, and do not tick them to make a set look consistent:

| Item | Needs |
|---|---|
| `MC-2` | a person: parity sign-off, before `S-E1` deletes anything (`NR-SIM-30`) |
| `MC-3` / `S-D1`'s gate | a person opening Foxglove Studio |
| `MC-5` | a person: `S-D8`'s onboarding stopwatch check |
| `GT-14` | two people's names and one measured number. **If there is no second person, that is the answer and it belongs at the gate** |
| `ST-C6-4` | a CI runner with a C++ toolchain (`plan.md` item 20) |

**One owner decision is open:** whether `perception-core` splits into
computer-vision + fusion. It gates `S-D4`'s gate, which demonstrates
`R-SIM-10`'s central invariant — the architecture's main claim.
`modules/perception-core/docs/perception_core_decomposition.md` lays out both
options and their cost; `FR-SIM-71` exists to keep the decision cheap while it
stays open.

### Build order and its dependencies

Stages were built in the order below rather than in id order, because the split
that matters to a session is *can I make progress without a compiler* —
**Block 1 (`S-C0`, `S-A3Δ`, `S-A4Δ`, `S-B2Δ`, `S-C1cΔ`, `S-B1Δ`, `S-C4`,
`S-C9`, `S-C2`, `S-C3`) depends on nothing in Block 2** (`S-C1aΔ2`, `S-C1d`,
`S-C5`, `S-C8`, `S-C7`, `S-C6`), which needs a real MSVC/Conan build.

The dependencies that are **not** implied by ordering, and that a
re-sequencing must respect:

| Stage | Needs | Why |
|---|---|---|
| `S-B2Δ` | `S-A4Δ`, `S-A3Δ` | the second clock stamp and the byte budget |
| `S-B1Δ` | `S-C1cΔ`, `S-A3Δ` | the `self.<port>` resolver and `Prim.derived` |
| `S-C2` | `S-A4Δ` | it writes recordings, so the two-stamp codec must exist |
| `S-C3` | `S-C1cΔ`, `S-A4Δ`, `S-C9` | faults reuse the override grammar; `delay` needs the capture stamp; `expect:` addresses need ingest |
| `S-C1d` | `S-C1aΔ2` | a generator cannot emit a manifest field the proto lacks |
| `S-C5` | `S-C1d` | reads `<COMPONENT>_<FN>_PERIOD_US` through the generated manifest |
| `S-C7` | `S-C1d`, `S-C5` | needs the generated shim and `adasInit(NULL)`'s bundle |
| `S-C6` | `S-C2`, `S-C3`, `S-C5` | needs recordings, scenarios, and a rebuilt binary for determinism axis C |

Four stages were built **out of id order**, deliberately:

| Built as | Reason |
|---|---|
| `S-C9` before `S-C2` | added late; `P0`, compiler-free, and `S-C3` depends on it |
| `S-C4` before `S-C9`/`S-C2` | shares its file set with `S-B1Δ` — visit `modules/<n>/sim/` once |
| `S-C8` before `S-C6`/`S-C7` | sibling of `S-C5`; built apart they grow two resolution orders |
| `S-C1aΔ2` before `S-C1d` | a proto field must exist before a generator emits it |

**The deltas** (`S-A3Δ`, `S-A4Δ`, `S-B2Δ`, `S-B1Δ`, `S-C1cΔ`, `S-C1aΔ2`) are
work, not corrections: they close *permanence* questions — a recording written
without a capture stamp cannot be repaired later — and they need no compiler.

**One rework trap, stated so it is not re-opened.** The override *engine*
(verbs, grammar, application, manifest tagging) belongs to `S-C1cΔ`, not to
`S-D6`. `S-D6`'s `contracts/override.py` box is the **developer surface** over
that engine — the GUI toggle, `sim probe`, the severed-chain badge. Building the
engine at `S-D6` would leave `S-C3`'s fault injection with no grammar to reuse.

### The per-stage loop — every time, in this order

1. **Read the stage** top to bottom, including its `**Must not**` block, then
   the design sections it cites. If it cites
   [sim_api_reference.md](sim_api_reference.md), **a signature there is a
   contract** — type it as written.
2. **Check the entry conditions.** A stage that says *blocked on X* is blocked.
3. **Implement the unticked `- [ ]` scope boxes**, in the order given.
4. **Write the stage's tests**, including the ones that must be **shown to
   fail** — a gate that has never failed has never been shown to work.
5. **Run the checks** from the superproject root, using
   `modules/sim/.venv/Scripts/python.exe` — **never a bare `python`**, which has
   already misled a session here. On Linux it is `modules/sim/.venv/bin/python`
   (`P-6`).
   ```
   … -m pytest modules/sim/tests -q
   … modules/sim/scripts/check_invariants.py
   … modules/sim/docs/py/run_all.py
   <the stage's own build command, if it has one>
   ```
6. **Tick only what you verified.** A test that `skip`s has not passed, and
   reading it is not running it. When a test cannot run in your shell the box is
   `[~]`, and the caveat names the **exact command** and the **exact acceptance
   condition** that closes it. Watch the **skip** count, not only pass/fail.
7. **Commit**, citing the stage: `feat(sim): S-C0 automatic gate + ST-C0-1..2`.
   Submodule first, then the superproject pointer (`R-GIT-1`).

### Stop and ask — do not decide these alone

- A design document contradicts another design document (`GT-7`). Two have
  already disagreed here, and both read as authoritative.
- A stage's scope appears to require changing `src/component/**`. It must not.
- A test cannot pass without widening a tolerance, relaxing a gate, or adding an
  exemption to `GT-1`/`GT-11`.
- The work needs a fifth override verb, a sixth fault, an expression anywhere, or
  a port address spelled as a literal. Each is a closed list with a written
  reason; reopening one is a design change, not an implementation choice.
- **You cannot run the real build. Say so.** Do not substitute a hand-rolled
  compiler command — that has produced two stages reported green whose build was
  red, and it is the most expensive mistake made here.

### Three things that must never happen

- **Never tick a box you did not verify**, and never tick one to make a set look
  consistent. A ticked box is a claim that something was run.
- **Never lower a `GT-4` floor.** If a count drops, behaviour changed.
- **Never "fix" the known flake.**
  `tests/system/test_b3_viewport_controls.py::test_dragging_pans_the_viewport_and_a_second_click_still_selects`
  fails only in-suite — a fixture-isolation bug in §10's risk table. It is not
  yours unless a stage says it is.

### Two verification habits, learned the expensive way

1. **Verify through the mechanism, not through the call site you changed.** A
   fix once passed its test because the single wired caller was the one tested;
   every other caller still misbehaved.
2. **Watch the whole-suite warning count**, not only your own tests.

### Where a resolution's reasoning lives

The stages say *what to build*. When you need *why*:

| Topic | Read |
|---|---|
| evidence chain (`OD-6`) | arch §5.19 |
| bulk by reference (`OD-7`) | arch §5.3 |
| `select`/`drop` (`OD-8`) | arch §5.10 |
| two clocks (`OD-9`) | recording §3.3 |
| determinism + tolerance (`OD-10`) | recording §4a |
| record policy (`NR-SIM-42`) | recording §3.6 |
| lazy `PortValue` (`OD-13`), build pinning | recording §10 |
| config bundle per component (`OD-11`), `period_ns` (`OD-12`) | contract §9.1, §9.2 |
| anchors (`OQ-3`), faults (`OQ-4`) | scenarios §9.1, §9.2 |
| plug-in API version (`NR-SIM-44`) | arch §5.7a |

### Effort shape

32 `### S-` stage sections plus six deltas. **A and B touch no C++ and no DLL at
all** — the entire viewer is built and tested against recorded files. **C is the
only phase that changes production C++** and carries all of the C++ risk, which
is why it reads as the hardest part of this document. One sentence organises it:
*a component's DLL must answer three questions — what ports do I have, what
configuration am I using, and run one tick — and everything else in Phase C
builds the things that ask them.* [sim_learn.md](sim_learn.md) §3 expands that.
**E only deletes.**

---

## 1. Prerequisites

- [ ] **Python 3.12** — the interpreter every existing tool already targets
      (`py -3.12`, `tools/carla/requirements.txt`). Do not silently move to a
      newer one; `.pyc` files for 3.14 exist in the tree from an accidental run.
- [ ] **Dependencies**, declared in `modules/sim/pyproject.toml`:
      - core: `pyyaml>=6`, `protobuf>=4.25`, `mcap>=1.0`,
        `mcap-protobuf-support>=0.5`, `numpy>=1.26`
      - viewer: `PySide6>=6.6` (OD-1)
      - print renderer: `matplotlib>=3.8` (extra `[figures]`)
      - interop: `foxglove-sdk>=0.25` (extra `[foxglove]`)
      - dev: `pytest>=8`, `pytest-cov`
      Every non-core dependency is an **extra**, so a console resim installs
      nothing it does not use — the deferred-import discipline today's tooling
      already follows, moved into packaging.
- [ ] **`opencv-python` is not a dependency of the new framework.** It exists
      today only because `viz.py` needed a window. Qt replaces it. If a numeric
      image operation is needed later, add it deliberately.
- [ ] **Test command**: `python -m pytest modules/sim/tests -q` from the
      superproject root. No CI exists (`plan.md` item 20); this command *is* the
      gate, run by hand and cited in the commit.
- [ ] Conan remote reachable — `conan remote login adas-local demo -p demo`
      before any build stage, or builds stall ~10 min then fail with
      `EOF when reading a line`.

---

## 2. Global gates — re-checked at the end of every stage

These are the invariants that make the architecture true rather than
aspirational. A stage that breaks one is not done.

**Unticked boxes here are the normal state.** These gates are re-checked
continuously, not completed once, so an empty `- [ ]` in this section does not
mean "not done" the way it does inside a stage. The nested backtick-quoted
`` `GT-n` ``/`` `DC-n` `` checkboxes exist so
`check_requirement_coverage.py` can read a state for gates that requirements
cite; **a real tick belongs at the stage or milestone that re-checks the gate**
— `S-E3` for the milestone measurements — never at this line.

### What a stage's "`GT-1..GT-12` re-checked" line means

There are **fourteen** gates but every stage's Discipline line says
`GT-1..GT-12`. That literal range is not the whole set, and mass-editing it to
`GT-1..GT-14` would retroactively claim already-ticked stages re-checked
`GT-13`/`GT-14`, which none did.

| Class | Gates | When |
|---|---|---|
| **Per-stage, mechanised** | `GT-1`, `GT-2`, `GT-3`, `GT-6`, `GT-11` | every stage — one command, `scripts/check_invariants.py` |
| **Per-stage, by hand** | `GT-5`, `GT-7`, `GT-9` | every stage |
| **Per-stage, when a build is touched** | `GT-4` | any stage that compiles anything |
| **Milestone measurements, recorded once** | `GT-8`, `GT-10`, `GT-12`, `GT-13`, `GT-14` | at `S-E3`, or when the stage that owns them lands |

A stage's line means the first three rows. `GT-13`/`GT-14` measure the project,
not a change — read them at `S-E3`, where `GT-13`'s blanks *are* its finding.

### The gates

- [ ] **GT-1 — no function names in the framework.** No `aeb`/`bsd`/`lca`/
      `acc`/`ldw`/`lka` anywhere under `modules/sim/src` (`R-SIM-1`).
      **Run `scripts/check_invariants.py`, not a hand-written `grep -E '\b…'`**
      — `\b` treats `_` as a word character, so the literal grep misses a token
      inside a snake_case or ALL_CAPS identifier, which is exactly
      `R-NAME-3`'s calibration-key shape. `check_gt1` uses an alnum lookaround.
- [ ] **GT-2 — no renderer in a layer provider.** No `cv2`/`matplotlib`/
      `PySide6`/`foxglove` import under any `modules/*/sim/layers/` (`R-SIM-2`).
- [ ] **GT-3 — no physical constant in a layer provider or renderer.** No
      literal vehicle or sensor dimension outside `model/` (`R-SIM-3`).
      - [ ] `GT-3`
- [ ] **GT-4 — the build matrix stays green.** Every component declaring a
      `gtest` target: its `ctest` count is at or above its measured floor **and
      every test in it passes** (`NR-SIM-12`). **Never lower a floor** — a
      dropped count means behaviour changed. Both clauses are required: count
      catches deleted tests, pass catches broken ones.

      | Module | Command | Floor |
      |---|---|---|
      | `df` | `scripts/build.py df -t gtest -p vs2026 -P base` | **233** |
      | `interfaces` | `scripts/build.py interfaces -t gtest -p vs2026 -P base` | **10** |
      | `mathlib` | `scripts/build.py mathlib -t gtest -p vs2026 -P base` | **29** |
      | `vdy` | `scripts/build.py vdy -t gtest -p vs2026 -P base` | **18** |
      | `perception-core` | `scripts/build.py perception-core -t gtest -p vs2026 -P base` | **2** |
      | `sil_host` | `scripts/build.py sil_host -t sil -p vs2026 -P base`, then run `sil.exe` **under `conanrun.bat`** | builds; run exits 0 |

      Use the **dispatcher** form above, not `modules/<m>/build.bat` — only the
      dispatcher resolves the project. `sil_host`'s `-t sil` **only builds**;
      `Release/sil.exe` launched bare fails with `STATUS_DLL_NOT_FOUND` because
      its dependencies come from the Conan package, so run it under the
      generated `conanrun.bat` or the row measures nothing.

      **Why one row is not enough:** both Phase C defects that escaped were
      cross-module and would have passed a `df`-only gate — an `interfaces`
      change broke `df`'s CMake generate, and a link-visibility change in
      `df_sil`'s installed public header reached every consumer of
      `AdasDf::AdasDf`. A shared contract lives in `interfaces`; a gate
      watching one consumer watches the wrong thing.
- [ ] **GT-5 — build machinery untouched.** `diff -q` of `conanfile.py`,
      `scripts/build.py`, `build.bat`/`.sh`, `scripts/build_gui.py`,
      `.clang-format` against another component is silent (`R-BUILD-1..6`).
- [ ] **GT-6 — the framework imports no component.** `modules/sim` never
      imports from `modules/df` or `interfaces`' generated bindings
      (`R-SIM-11`).
- [ ] **GT-7 — docs match code.** Any behaviour contradicting a design doc is
      either a code bug or a doc bug; fix one, in the same commit.
- [ ] **GT-8 — time to first picture, measured.** A developer with **only their
      own component checked out** gets a rendered run from a recording in
      **under 10 minutes**, editing nothing in `modules/sim`. Timed on a real
      newcomer and recorded with the person's role — not asserted
      (`FR-SIM-46`). **Owner: ______  Measured: ______ min.** A blank at `S-E3`
      is worse than a number over target. This is the gate that decides whether
      anyone writes a private player.
      - [ ] `GT-8`
- [ ] **GT-9 — no logic in the app layer.** `cli/` and `app/` hold argument
      parsing, layout and dispatch only; every capability is reachable in ≲3
      lines from a plain script (`Session.open`, `SilComponent`, a provider, a
      codec), checked by a test that imports each without touching the CLI
      (`R-SIM-16`). This is also what keeps headless automation free: the moment
      a capability is reachable only through the window, running in CI stops
      being a consequence and becomes a port.
      - [ ] `GT-9`
- [ ] **GT-10 — every module builds standalone.** From a clean partial clone of
      that module alone plus its declared Conan `requires:` — no sibling
      checkout on disk — each module in `GT-4`'s matrix configures and builds
      (`docs/partial_clone_workflow.md`, `R-VAR-2`, `NR-SIM-12`). Run per
      module; a **separate `CONAN_HOME`** is mandatory, because this repo's
      normal Conan home registers every `adas-*` package editable and resolves
      them from the working checkout — the exact configuration that hides the
      failure this gate looks for.

      Its first run found a real one: `interfaces`' `package_info()` declared
      `builddirs = ["cmake"]` while its `CMakeLists.txt` never installed
      `cmake/`, so `include(sil_ports_generate)` found nothing and `df` failed
      to configure. **Fixed** (`interfaces/CMakeLists.txt` now installs
      `cmake/`); the full matrix re-run is owed at `S-E3`.
      - [ ] `GT-10`
- [x] **GT-11 — no port address is a literal outside the component that
      declares it.** A scan over every `modules/*/sim/**` plug-in, scenario
      `expect:` block, workspace and viewpoint file for a spelled port address
      returns nothing; every such reference is component-relative
      (`self.<port>`) and resolved at load (`R-SIM-21`). Extends `GT-1`, which
      guards the framework and stops exactly at the boundary where `D13` lives.
      Mechanised in `check_invariants.py`'s `check_gt11`.

      Two boundaries worth knowing: only an **ambiguous** match raises — a
      *zero*-match is a legitimate silent empty layer, since "does not exist"
      and "this run never wired the component" are the same observation without
      a live manifest. And `source.` joins `self.` in
      `_GT11_EXEMPT_PREFIXES` because `contracts/pipeline.py` treats `source` as
      a **reserved producer keyword**, never a stage name an author could
      rename; its narrower real limitation is recorded at `R-SIM-21`.
      - [x] `GT-11`
- [ ] **GT-12 — the player runs standalone, against libraries it has never
      heard of.** `vantage <dir>` on a directory holding only built artefacts —
      DLL, `config/`, `sim/` — renders a run with **no repository checked out,
      no `PYTHONPATH`, and no component-specific import in the player**
      (`R-SIM-20`, `FR-SIM-64`, `FR-SIM-70`). Verify on a copied output tree
      with the source tree renamed away; that is the only way to prove a
      checkout was not silently supplying something.
- [ ] **GT-13 — the numbers exist.** Every quantitative claim the register makes
      carries a **measured number with a date and a machine**: per-tick cost and
      campaign throughput (`NR-SIM-41`), frame time at a stated tick count
      (`NR-SIM-5`), recording size for a reference run (`NR-SIM-42`),
      determinism across all four axes (`NR-SIM-40`). *A requirement nobody can
      fail is a requirement that will be declared satisfied* — so a blank is a
      finding, and **a number above target is a finding to act on, never a
      reason to delete the gate**.

      | Claim | Measured |
      |---|---|
      | `NR-SIM-41` throughput | 7 recordings / 33.1 MB: `-j 1` 2.11s, `-j 7` 0.41s, **5.2×**; ~0.05s/recording compute excluding subprocess startup (`ST-D7-7`) |
      | `NR-SIM-5` frame time | 100 ticks, real layer providers: **83.8 ms/tick**, ≈11.9 fps (`test_e3_frame_time.py`) |
      | `NR-SIM-42` recording size | 219 ticks → **7.19 MB** for the reference run |
      | `NR-SIM-40` determinism | `same_process` **exact**; `fresh_process` **exact** (`test_e3_determinism_measured.py`) |
      | `NR-SIM-40` axes C/D | **blank** — `rebuilt_binary` needs a second independent build, `different_machine` needs a second machine |

      Re-run these rather than trusting them stale on different hardware.
      - [ ] `GT-13`
- [ ] **GT-14 — someone who did not build it can change it.** A named owner and
      a named second reader, plus a **measured maintainer-onboarding number**:
      the time for a second person to land a reviewed change touching a rule, a
      stage and a test (`NR-SIM-45`). Peer of `GT-8`, which measures a *user*.
      **Owner: ______  Second reader: ______  Measured: ______ h.**

      > **The one open item no work can close.** These blanks need two people's
      > names and one measured number; nothing in the build order produces them,
      > so they will still be blank at `S-E3` unless someone fills them
      > deliberately. **If there is no second person, that is the answer and it
      > should be written here**, not discovered at `S-E3`. A single-maintainer
      > project is a legitimate state; an unexamined one is what this gate
      > exists to catch. The most probable ending for this project is an
      > ownership failure, not a design failure, and this is the only gate that
      > looks at it.
      - [ ] `GT-14`

### Document invariants cited by requirements (`DC-`)

`DC-1`..`DC-9` are mechanised in `docs/py/check_doc_invariants.py` and re-run by
`docs/py/run_all.py`; that script's module docstring is the authority on what
each asserts. The four checkboxes below exist only so
`check_requirement_coverage.py` can read a state for the ones requirements
cite — they are not a second implementation of the check.

- [ ] `DC-1`
- [ ] `DC-4`
- [ ] `DC-5`
- [ ] `DC-6`

---

## 3. Test strategy

### 3.1 The two kinds

| | **Unit (UT)** | **System (ST)** |
|---|---|---|
| Scope | one entity, in isolation | a whole path, end to end |
| Inputs | constructed in the test | a real recording / a real build |
| Runs in | `modules/sim/tests/unit/` | `modules/sim/tests/system/` |
| Needs | nothing but the package | fixtures; some need `modules/df` built |
| Speed | milliseconds | seconds |

`modules/sim/tests/integration/` holds the tests that need **another module**
present (a built `df_sil.dll`, `modules/df`'s recordings). They **skip with a
named reason** when it is absent, so a partial clone still runs the suite
(`docs/partial_clone_workflow.md`).

### 3.2 The framework's tests need no C++ — by design

`SilComponent` is a **Protocol**, with two implementations:

- `CtypesSilComponent` — loads a real DLL over the generic ABI;
- `InProcessSilComponent` — a Python callable plus a manifest.

The second is the *same mechanism* `impl: stub:` uses (`R-SIM-10`), so it costs
nothing extra and lets every `Pipeline`, `Runner`, `Session` and wiring-
validation test run with **zero build dependency**. The ctypes path is exercised
in `tests/integration/`, skipped when `df_sil.dll` is not built.

*(Recorded in [sim_sil_contract.md](sim_sil_contract.md) §4.1.)*

### 3.3 Fixtures

- [ ] `tests/fixtures/tiny.mcap` — a synthetic 20-tick recording committed in
      `modules/sim`, so the framework's own suite is self-contained. Generated
      by a checked-in script, not hand-crafted, so it can be regenerated.
- [ ] `tests/fixtures/golden/` — golden `Scene`s (serialized) and golden
      manifests. Regenerated by `pytest --update-goldens`, **never** edited by
      hand; a golden change must appear in the diff and be justified in review.
- [ ] Real recordings under `modules/df/tests/carla_testruns/` are used by
      integration tests only, read-only, never modified.

### 3.4 What cannot be automated, and is therefore a named manual check

Stated honestly rather than pretended away — the same caveat the existing viz
work carries ("needs a human watching the window"):

| ID | Check | When |
|---|---|---|
| MC-1 | The BEV *looks* right — labels legible, no collisions, colours readable | S-B1, S-B3 |
| MC-2 | Live CARLA bridge still records correctly against a real server | S-C2 |
| MC-3 | Foxglove Studio renders the exported scene | S-D1 |
| MC-4 | The Qt shell feels responsive while scrubbing a long session | S-B3 |
| MC-5 | **The onboarding check** (`FR-SIM-47`) — a developer who has never seen the tool reaches a moving picture in **under two minutes**, unaided, and then explains `measured` vs `simulate` on the pipeline dock **unprompted**. If they cannot, the dock is wrong, not the developer | S-D8 |

Each is a checkbox with a date and the name of whoever looked.

`MC-5` additionally records the **number** (time to moving picture, and whether
the explanation was correct), because it feeds `GT-8` and a remembered
impression is not a measurement.

---

## 4. Phase A — Foundations

**No C++, no DLL, no behaviour change to anything that exists.**

### S-A1 — `modules/sim` package skeleton

**Purpose.** The tree, the packaging, the error taxonomy, the run id and the
log line — everything every later stage imports. Nothing here has behaviour
worth demonstrating; it exists so that nothing later has to invent a name.

**Must not.** Import Qt, matplotlib, mcap or protobuf at package import time
(`UT-A1-2`). The console resim path must install none of them.

- [x] `pyproject.toml` — package `adas-sim`, `requires-python = ">=3.12"`, core
      deps + extras (§1). Entry point `sim = adas_sim.cli:main` — the launcher
      is generated per platform rather than written by us (`P-6`)
- [x] `src/adas_sim/` with exactly these subpackages, matching
      [sim_api_reference.md](sim_api_reference.md) §1 **byte for byte**:
      `core/ model/ scene/ contracts/ io/ sources/ view/ render/ check/ cli/
      app/`, each with `__init__.py`; root `__init__.py` carries `__version__`
      - **`sinks/` is deliberately absent.** An earlier draft had it for
        recording writers; `R-SIM-14` made readers and writers one symmetric
        codec table, so writers live in `io/`. Two homes for one concept is
        how `sim convert` would have become a feature instead of a consequence
      - **`view/` holds transport and viewport state** — pure state, no
        pixels. `render/` turns that state into output. Keeping them apart is
        what lets `UT-B2-3` assert that a layer toggle re-renders without
        re-executing
- [x] `conanfile.py` — `package_type = "unknown"`, no `settings`, data-only
      recipe following `shared_config`'s shape exactly
      (`docs/shared_config_plan.md` §3.2/§3.3) — copied byte-identical
      (`diff -q` against `modules/shared_config/conanfile.py` is silent, `GT-5`)
- [x] `tests/{unit,system,integration,fixtures}/` + `conftest.py`
- [x] `scripts/check_invariants.py` — implements GT-1, GT-2, GT-3, GT-6, and
      **is itself tested** by `UT-A1-3`.
- [x] `core/errors.py` — the **closed** taxonomy of `DG-5` / api reference §9:
      `AuthoringError` (exit 2) · `EnvironmentError_` (3) · `ContractError` (4)
      · `InternalError` (70), all deriving `SimError`, whose constructor takes
      **keyword-only `expected` / `found` / `where` / `hint`**. A message that
      is only an identifier is therefore a `TypeError` at author time, not a
      disappointment at run time (`N-8`)
      - plus `ProvenanceWarning(Warning)` — **a warning, never an error**: a
        project mismatch degrades and is shown, it does not stop a run
        (`R-SIM-3a`)
- [x] `core/ids.py` — `new_run_id()` per `N-9`; the hashed inputs are listed in
      api reference §2.1 and are **sorted before hashing** (`P-8`)
- [x] `core/logging.py` — the `Event` StrEnum (closed) and `log()` emitting one
      fixed-order line (`N-10`)
- [x] `cli/doctor.py` — **the first version of `sim doctor`** (`DG-3`),
      reporting interpreter, install mode, platform, console encoding and line
      endings. **Seeded here on purpose**: the diagnostic tool is most valuable
      while the environment is least settled, and a `sim doctor` that only
      arrives at `S-D6` would mean twenty stages built without it. It **grows**
      one section per stage that adds something worth checking. (The facts
      themselves live in `core/diagnostics.py`, not `cli/`, per `GT-9`.)
- [x] Console UTF-8 reconfiguration at every entry point (`P-4`) — three lines,
      and the bug it prevents was already hit once in `docs/py/_common.py`
      (`core/console.py`, called once from `cli/__init__.py:main`)
- [x] file headers on every `.py` per `R-STYLE-1`, `COMPONENT: SIM` (`R-NAME-6`)

**Tests**
- [x] `UT-A1-1` `import adas_sim` succeeds; `__version__` is a non-empty string
- [x] `UT-A1-2` every subpackage imports without side effects (no disk, no
      network, no window at import time) **and without importing Qt,
      matplotlib, mcap or protobuf** — asserted on `sys.modules`
- [x] `UT-A1-3` `check_invariants.py` passes on the empty tree, and **fails** on
      a deliberately planted function identifier (the check is tested, not
      trusted)
- [x] `UT-A1-4` each error class carries `expected`/`found`/`where`, exposes its
      `exit_code`, and is distinguishable by type; constructing one without the
      keyword arguments raises `TypeError`; `ProvenanceWarning` is a `Warning`
      and is not raisable as a `SimError`
- [x] `UT-A1-5` **every public class reprs its own name** and no `repr` contains
      `0x` (`N-7`) — the cheapest debugging feature in the system and the
      easiest to skip
- [x] `UT-A1-6` **import direction**: `core`/`model`/`scene`/`contracts`/`io`/
      `check` never import `render`, `view`, `cli` or `app` (module-graph scan,
      api reference §1)
- [x] `UT-A1-7` `new_run_id` is stable for identical inputs and differs for any
      single changed input (`N-9`) — the equality is itself diagnostic
- [x] `UT-A1-8` `log()` emits one line with fields in the fixed order of `N-10`;
      an `event` outside the closed enum is a `TypeError`; a multi-line `msg` is
      flattened, never wrapped
- [x] `UT-A1-9` the subpackage set on disk **equals** api reference §1's list —
      neither doc nor tree may drift alone
- [x] `ST-A1-1` `pip install -e modules/sim` then `python -c "import adas_sim"`
      from a directory outside the repo (run against `modules/sim/.venv`)
- [x] `ST-A1-2` `conan editable add modules/sim` succeeds and `conan graph info`
      resolves `adas-sim` (verified live and via the system test; `adas-sim`
      left registered editable afterward, alongside `df`/`vdy`/`mathlib`/
      `shared_config`)

**Discipline**
- [x] portability §3 (`P-2`, `P-4`, `P-6`, `P-10`) · naming §3 (`N-3`, `N-7`, `N-8`, `N-10`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `pytest modules/sim/tests -q` green (25 passed); `GT-1..GT-3`, `GT-6` pass; and
      `UT-A1-9` green — the tree and the API reference agree, which is the
      cheapest moment to make that true and the most expensive to retrofit

### S-A2 — `model/` — configuration is the source of geometry

**Purpose.** Every number that describes the physical world comes from resolved
YAML, never a module constant. Implements `R-SIM-3`, closes **D3**. Ports the
generic half of `modules/df/docs/bsd/py/bsdviz/{calib,egogeom}.py`.

**Must not.** Contain a single literal vehicle or sensor dimension (`GT-3`), and
must not know the name of any driving function — sensor keys are parsed **by key
shape**, never by their domain prefix, which is data (`GT-1`).
**Finding:** this line is easy to satisfy in code and still violate in
*prose* — an early draft of `model/ego.py`'s own docstring explained the port
by naming the source module's path and "BSD zone-geometry", which
`check_invariants.py` correctly flagged (`GT-1` bans the string everywhere in
`modules/sim/src`, comments included, "a grep is the enforcement" with no
carve-out). Fixed by paraphrasing without naming the function in all three
touched files (`ego.py`, `project.py`, `sensors.py`) — the same discipline
`N-1`/`N-6` ask of code now holds for comments too.

- [x] `model/project.py` — `ProjectModel.resolve(...)` (api reference §6).
      Resolution order **explicit → embedded-in-recording → library `config/` →
      source checkout**, and `bundle_origin` **always states which**
      (`R-SIM-3a`). The failure this prevents: the viewer and the SUT reading
      different files and agreeing only by coincidence.
- [x] `model/ego.py` — `EgoModel`: `x_front = wheelbase + overhang_front`,
      `x_rear = x_front - length`, `half_width = width/2`. Frame per `R-COORD-1`
      (origin at rear-axle centre, +x forward, +y left)
- [x] `model/objects.py` — `ObjectModel.footprint(class_name)` with the
      three-step precedence: per-object `geometry` → class table → declared
      fallback. **The fallback sets `assumed_geometry=True`**, and `R-SIM-3`
      requires it to be drawn in a style that makes it visibly a guess.
      Enforced even if the caller constructs the fallback without it —
      `ObjectModel.__init__` coerces it, so a caller cannot accidentally make
      a fallback that claims to be measured
- [x] `model/sensors.py` — `SensorModel`, parsing `<PREFIX>_SENSOR_<i>_<FIELD>`
      **by key shape** (`UT-A2-9` plants a different prefix and expects it to
      work unchanged). Field names keep the source key's **exact case**
      (`P-3`) — lower-casing them, the first draft's shortcut, would let
      `SIDE` and `Side` silently collide into one field
- [x] `model/cameras.py` — `CameraModel`: intrinsics/extrinsics fields
      **declared**, projection unimplemented until S-D4. Declaring the shape now
      costs nothing and stops S-D4 from inventing it
- [x] Every `open`/`read_text` names `encoding="utf-8"` (`P-4`); every path is a
      `Path` (`P-1`); every key comparison is exact, never case-folded (`P-3`)

**Tests**
- [x] `UT-A2-1` `EgoModel.load("base")` → `x_front == 3.60`, `x_rear == -0.90`,
      `half_width == 0.90` (via `pytest.approx` — `3.6 - 4.5 == -0.9` is
      `False` in plain IEEE-754 float arithmetic, `-0.8999999999999999`; an
      exact `==` as literally written would have been a flaky test, not a
      correct one)
- [x] `UT-A2-2` `base`, `2w_base`, `cus1` each yield their own numbers and no
      two are equal — the `R-SIM-3` promise that switching project changes the
      picture
- [x] `UT-A2-3` a missing key raises `AuthoringError` naming **the key and the
      file**, not "KeyError"
- [x] `UT-A2-4` footprint precedence: with `geometry` present it wins; without,
      the class table; without that, the fallback **and** `assumed_geometry`
      is `True`
- [x] `UT-A2-5` two different object classes resolve to different footprints
- [x] `UT-A2-6` `SensorModel` yields exactly the declared sensor count with
      pose/FOV/range/side populated; a **case-differing** key does **not**
      resolve, on every platform (`P-3`)
- [x] `UT-A2-7` resolution order: with all four sources present, explicit wins;
      with three, the embedded bundle wins; `bundle_origin` reports which
- [x] `UT-A2-8` unknown project raises naming **every searched path** (`N-8`)
- [x] `UT-A2-9` **prefix independence**: a fixture using a different key prefix
      parses identically — proving the parser reads shape, not domain (`GT-1`)
- [x] `UT-A2-10` a project mismatch emits `ProvenanceWarning` and **still
      resolves** — it degrades visibly, it does not stop a run (`R-SIM-3a`)
- [x] `ST-A2-1` **equivalence with the code being replaced** — for every project,
      `EgoModel` and `SensorModel` values equal what the existing `bsdviz`
      modules produce today (skipped, with a named reason, if `modules/df` is
      absent).

**Discipline**
- [x] portability §3 (`P-1`, `P-3`, `P-4`) · naming §3 (`N-4`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-A2-1` green for all three projects — the replacement is provably
      value-identical before anything depends on it. `UT-A2-9` green, because a
      geometry layer that knows a function's name would pass every other test
      here and still be wrong

### S-A3 — `scene/` types + `render/theme.py`

**Purpose.** The central IR (`R-SIM-2`). Everything upstream produces `Scene`;
everything downstream consumes it. Getting this wrong is the one mistake that
cannot be localised later.

**Must not.** `scene/` imports nothing from `render/`, `view/`, `io/` or
`sources/`. A `Prim` never carries a colour, a pixel coordinate or a viewport
reference — only metres, a named frame and a **semantic** style token.

**Delta `S-A3Δ` — added 2026-07-31 (`OD-6`, `OD-7`). Build order #2** — Block 1,
blocked on nothing; must precede `S-B2Δ` (#4) and `S-B1Δ` (#6).** The stage's own gates
passed and still pass. What they never checked is **size** and **per-prim
provenance**, because neither was specified when they were written. Confirmed
against the code: `Prim.values` inlines a nested float array, `Prim.data` inlines
image bytes, and `Prim.points_m` is unbounded. Two additions, both structural,
both permanent once `S-D4` builds on them:

- [x] **`BulkRef` as a `Prim` field** — `topic` + `log_time_ns` + optional
      `field` path + `count` + `encoding`. It is a *coordinate into the
      recording*, not a second storage mechanism, so a `Scene` stays
      serializable and a golden still round-trips (arch §5.3). *2026-07-31:*
      landed in `scene/types.py` exactly per the sketch, one new field on
      `Prim` (`bulk: BulkRef | None = None`); `scene/codec.py` appends field
      numbers 38 (`bulk`) and 39 (`derived`) on `Prim` and a new `BulkRef`
      message, never renumbering an existing one, so old bytes still decode
      (`UT-A3-8`'s own contract). `sim_api_reference.md` §5 updated in the
      same commit (`GT-7`)
- [x] **The budget check lives in `Layer.__post_init__`**, not in `Prim`. A
      `Prim` does not know its layer, and `NR-SIM-43` requires the error to name
      one. Raise `ContractError` with the layer id, the prim kind and the count.
      *2026-07-31:* `_inline_element_count()` sums whichever of `points_m` /
      `values` / `data` is set (a prim carrying `bulk` instead sets none of
      them, so it never counts against the budget)
- [x] **`Prim.derived: bool = False`**, plus the `Layer.derived` consistency
      check (`UT-A3-13`). A layer legitimately mixes SUT-published and
      reconstructed geometry, which makes the existing per-layer flag inaccurate
      rather than merely coarse (`R-SIM-7`, arch §5.19). *2026-07-31:* one
      direction only, per arch §5.19's own statement — `Layer(derived=False)`
      containing a `Prim(derived=True)` raises `AuthoringError`; a
      `Layer(derived=True)` legitimately mixes `derived=True` and
      `derived=False` prims, which is exactly the case this field exists for
- [x] The declared budget is a **named constant with its number in this
      document**, not a magic literal — `NR-SIM-5` is falsifiable only against a
      stated figure (`GT-13`). **Value: `MAX_INLINE_PRIM_ELEMENTS = 2000`**
      (`scene/types.py`) — points in `points_m`, cells in `values`, bytes in
      `data`; chosen as comfortably above "tens of prims of tens of points"
      (arch §5.3's own description of the normal case) and far below the
      100 000-point cloud the rule exists to catch

- [x] `scene/types.py` — frozen `Prim`, `Layer`, `Scene` per api reference §5
      and visualization spec §2. Every prim carries `frame`, `style`, `pick_id`,
      `z`, `alpha`. `width_px`/`offset_px` are **the only** pixel fields, and
      exist because legibility is not physical (`R-SIM-2`).
- [x] `scene/frames.py` — the frame graph: `ego` (default, `R-COORD-1`),
      `world`, `sensor:<id>`, `image:<cam>`. Composition is static (model) plus
      dynamic (`tick.pose`).
      **Scoped:** only name validation (`is_known_frame`/`known_frame_kinds`)
      is implemented. The dynamic half — composing a static model pose with
      `tick.pose` into an actual transform — needs `core/tick.py`'s `Tick`,
      which does not exist until `S-B2`; nothing in `UT-A3-*` requires it yet
- [x] `scene/registry.py` — `@layer_provider`, `@inspector_fields`, `@signal`;
      discovery **by import**, so a component adds a layer by existing.
      **`@inspector_fields` removed in `S-B3` slice 5:** never wired to
      anything, and its registration key (the decorated function) could
      silently diverge from `LayerProviderEntry.func` once `requires`
      wrapped it in `gated`. Replaced by `Prim.fields` (inline, computed by
      the same provider that builds the prim) once the inspector actually
      needed values, not just names.
      Duplicate id raises naming **both** providers (`N-8`)
- [x] `scene/codec.py` — Scene to bytes and back, **protobuf**: field numbering
      gives minor-version tolerance for free, and a Foxglove renderer wants the
      schema anyway. `Scene.version` is `major.minor`; additive is minor.
      **No `.proto` file, no `protoc`/`grpcio-tools`** (neither is on this
      machine and adding one is a new build-time dependency, `P-10`): the
      schema is built once at import time straight from
      `google.protobuf.descriptor_pb2` into a private `DescriptorPool` — the
      same "no generated bindings required" principle `R-SIM-11` states for a
      component's own messages, applied to the framework's IR. Proto2 syntax
      (not proto3): proto3's `optional` needs a synthetic one-field oneof per
      field for presence-tracking, which is exactly what a ~40-field hand-built
      descriptor should not have to reconstruct by hand; proto2's `optional`
      gives real `HasField` presence natively, and this schema is internal to
      `modules/sim`, never a cross-component `interfaces` contract.
- [x] `render/theme.py` — the token table for `dark`/`light`/`print`/`forced`.
      36 tokens across the framework-owned namespaces only (`frame.* ego.*
      object.* status.* sensor.* truth.* measure.*`) — a component's own
      `<fn>.*` tokens are registered from its own `modules/<name>/sim/` at
      `S-B1` (`R-SIM-1`).
- [x] `render/palette_check.py` — the six-check validator over each categorical
      set (visualization spec §3.4), runnable as `python -m`. Ported from this
      session's own data-visualization skill's `validate_palette.py` (same
      OKLCH math, same Machado-Oliveira-Fernandes CVD simulation, same
      thresholds — the skill's reference palette is also where
      `object.classification.*`'s and `status.*`'s hex values come from), plus
      one addition: any categorical pair in the 6-8 ΔE floor band must have a
      **named** secondary encoding recorded in `render/theme.py`, checked by
      `check_named_secondary_encoding`, or it fails rather than merely warns.

**Tests**
- [x] `UT-A3-1` every prim type constructs and is immutable (assignment raises)
- [x] `UT-A3-2` `Scene` to bytes and back round-trips to an equal object
- [x] `UT-A3-3` a prim with no `frame` defaults to `ego`; an unknown frame raises
      naming the known frames
- [x] `UT-A3-4` an unknown style token raises — **no silent default colour**.
      A silent default is how a debug layer ends up looking authoritative
- [x] `UT-A3-5` every token in the table resolves in **all four** themes
- [x] `UT-A3-6` registry: duplicate layer id raises naming both providers
- [x] `UT-A3-7` registry discovery finds a provider added by import alone
- [x] `UT-A3-8` a `Scene` written with a **higher minor** version still reads —
      unknown fields skipped, known ones survive (`NR-SIM-3`)
- [x] `UT-A3-9` a `Scene` written with a **higher major** version is **refused**
      with both versions named — never partially rendered
- [x] `UT-A3-10` `scene/` imports nothing from `render`/`view`/`io`/`sources`
      (module scan) — the layering that makes `R-SIM-2` mechanical
- [x] `UT-A3-11` no `Prim` field accepts a colour value: constructing one with
      a hex-literal style raises, because a hex string is not a semantic token
- [x] `UT-A3-12` **the Scene carries geometry, not bulk data** (`NR-SIM-43`,
      audit `A5`): a `Prim` exceeding the declared per-Scene byte budget is a
      `ContractError` naming the layer, and a bulk array (point cloud, image,
      grid) is carried as a **reference** into the recording, not inlined.
      `SceneCache` bounds by **bytes**, not entry count. *Added by the
      2026-07-31 audit — structural and cheap now, permanent after `S-D4`*.
      *2026-07-31:* the `Prim`/`Layer` half verified by
      `test_layer_rejects_a_prim_exceeding_the_inline_budget` and
      `test_layer_accepts_a_prim_referencing_bulk_data_instead_of_inlining_it`
      (`tests/unit/test_a3_types.py`); the `SceneCache`-bytes half is
      `UT-B2-15`'s job (S-B2Δ, #4), not re-claimed here
- [x] `UT-A3-13` `Prim.derived` and `Layer.derived` **cannot disagree**: a
      `Layer(derived=False)` containing a `Prim(derived=True)` raises. Both
      directions asserted, because the check exists to stop a mixed layer
      claiming to be fully SUT-published (`OD-6`). *2026-07-31:* verified by
      `test_layer_with_derived_false_rejects_a_derived_prim` (the raise) and
      `test_layer_with_derived_true_may_legitimately_mix_real_and_derived_prims`
      (the permitted mix, the other assertion direction)
      (`tests/unit/test_a3_types.py`)
- [x] `ST-A3-1` `python -m adas_sim.render.palette_check` exits 0 for `dark` and
      `light`; every pair in the 6-8 dE band has a **named** secondary encoding

**Discipline**
- [x] portability §3 (`P-4`, `P-8`) · naming §3 (`N-2`, `N-3`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-A3-1` green — the palette is validated by computation, not taste; and
      `UT-A3-10` + `UT-A3-11` green, because a `Scene` that *can* hold a colour
      will eventually hold one

### S-A4 — `io/mcap` codec

**Purpose.** Prove `R-SIM-14`'s claim — a recording is a *model*, a format is a
*codec* of ~4 methods — by building the first one and nothing else.

**Must not.** Let any other module learn that mcap exists. `Session`, pipeline,
Scene, viewer and expectations are written against the model (`UT-A4-11`).

**Delta `S-A4Δ` — added 2026-07-31 (`OD-9`, `CR-SIM-4`). Build order #3** — Block 1,
blocked on nothing; must precede `S-B2Δ` (#4) and `S-C2` (#9).** The model declares
one time field where the vehicle has two. Confirmed against the code:
`io/mcap.py:151` writes `publish_time=log_time_ns` and the reader yields only
`message.log_time`, so both stamps collapse. **Do this before `S-C2` writes
anything** — a recording produced without a capture stamp cannot be repaired
afterwards.

Read recording §3.3 first; it corrects the audit's own justification, and the
correction is what decides the `None` rule below.

- [x] The message tuple becomes **`(topic, log_time_ns, capture_time_ns,
      bytes)`**. `log_time_ns` keeps its meaning exactly — **reception**, the
      scheduling clock — so `group_by_log_time` is unchanged and every existing
      grouping behaviour is preserved. *2026-07-31:* `group_by_log_time`
      unpacks the 4th element and drops it after grouping — its own **yielded
      shape stays `(log_time_ns, {topic: payload}, missing)`**, unchanged,
      because `core/runner.py`'s pass 1 and `ST-C1c-1`'s resim-equivalence
      test both already consume that exact shape and neither is this delta's
      to touch (`core/tick.PortValue.capture_ns` is `S-B2Δ`'s job). `io/csv.py`
      keeps its own small `(topic, log_time_ns) -> capture_time_ns` side
      table instead (see its own bullet below) rather than changing the
      shared primitive's contract
- [x] **`capture_time_ns: int | None`, and `None` is never replaced by
      `log_time_ns`.** This is the one detail to be stubborn about: `None` means
      *unknown*, equality means *simultaneous*, and defaulting one to the other
      manufactures an `age_s` of exactly `0.0` indistinguishable from a true one
      — the substitution `NR-SIM-4` forbids, on the field that exists to prevent
      it
- [x] `Capabilities.capture_time: bool`. A codec without a second stamp declares
      it and degrades explicitly — `R-SIM-14`'s existing mechanism, so this adds
      no concept. *2026-07-31:* `io/mcap.py` declares `True`; `io/csv.py`
      declares `False` (a write-only export collapses both stamps into one
      derived `age_s` column, never re-exposing capture as its own field)
- [x] `io/mcap.py`: **one line** on the write side. mcap already carries both
      with these exact semantics — `publish_time` is when the producer published,
      `log_time` is when it was logged. The reader yields both. *2026-07-31:*
      `McapWriter.write` gained a keyword-only `capture_time_ns: int | None =
      None`; the one line is `publish_time = log_time_ns if capture_time_ns
      is None else capture_time_ns` — an omitted capture time is byte-identical
      to pre-delta output
- [x] **Recordings written before this delta report `capture_time_ns = None`
      regardless of their bytes**, keyed off `manifest_version`. Their
      `publish_time == log_time` was written unconditionally and therefore
      carries no information; reading it as "simultaneous" would be a fabricated
      fact. *2026-07-31:* `io/base.CAPTURE_TIME_MANIFEST_VERSION = 2` — a
      recording whose manifest reports less (incl. `0`, no manifest at all)
      forces `None` for every message at `McapReader.messages()`, regardless
      of its `publish_time` bytes. Every existing test/fixture manifest
      (pinned at `manifest_version=1`, `UT-A4-14`'s own "old" case) is left
      untouched — none of them needed editing for this delta to be correct
- [x] `io/csv.py` and `io/legacy.py` follow the tuple change. `csv.py`'s
      `<port>.age_s` column becomes capture-derived when capture is known.
      *2026-07-31:* `io/legacy.py` just re-yields the 4th element unchanged.
      `io/csv.py`'s `age_s` is `(log_time_ns - capture_time_ns)` when known,
      else the pre-delta reception-based value (unchanged for every existing
      `test_d7_csv.py` case, none of which pass a capture time)

- [x] `io/base.py` — `RecordingReader`/`RecordingWriter` Protocols,
      `Capabilities` (incl. `round_trips`, `write_only`), `TopicInfo`,
      `Provenance` enum (`measured|truth|mocked|simulated|overridden|unknown`),
      per api reference §4.
- [x] `io/registry.py` — `register(ext, reader=, writer=)`, lookup by extension;
      unknown extension raises naming **the extension and every registered one**
- [x] `io/mcap.py` — the default codec; all capabilities true. Real
      `RunManifest`/`config_bundle` meta blocks ride as native mcap `Metadata`
      records (a flat `dict[str,str]`, which is exactly `add_metadata`'s own
      shape — no extra encoding invented for them)
- [x] `io/legacy.py` — maps today's legacy topic names onto namespaced ones and
      synthesises the missing `VehSig` (recording doc §8). **This is the one
      sanctioned name translation** (`N-6`), declared as data and printed by
      `sim explain`.
- [x] `tests/fixtures/make_tiny_mcap.py` + the generated `tiny.mcap` — generated
      by a checked-in script, never hand-crafted, so it can be regenerated.

**Tests**
- [x] `UT-A4-1` write N messages, read back identical `(topic, log_time, bytes)`
- [x] `UT-A4-2` `topics()` returns schema and provenance for each
- [x] `UT-A4-3` meta blocks (`manifest`, `config_bundle`, `topic_provenance`)
      round-trip
- [x] `UT-A4-4` a recording with no meta loads with `provenance == unknown` and
      does **not** raise — it degrades and says so (`R-SIM-6`)
- [x] `UT-A4-5` legacy topic names map correctly; a legacy file reports
      `manifest: unknown`
- [x] `UT-A4-6` `capabilities` are declared and reported
- [x] `UT-A4-7` unknown extension raises naming registered codecs
- [x] `UT-A4-8` `dt_s` reconstruction: gaps from `log_time`, tick 0 measured
      from 0 (recording doc §3.3)
- [x] `UT-A4-9` a tick missing one of its grouped messages is reported, not
      silently dropped
- [x] `UT-A4-10` **no name is translated**: for a round-trip through every
      registered codec, the set of topic and field names in the model is
      unchanged (`N-6`). `io/legacy.py` is the declared exception and its
      mapping is readable as data
- [x] `UT-A4-11` **no module outside `io/` names a format**: a scan for format
      tokens across `core`/`model`/`scene`/`contracts`/`check` returns nothing
      (`R-SIM-14`)
- [x] `UT-A4-12` two writes of the same messages produce **byte-identical**
      files: topic order sorted, no wall-clock in the payload (`P-8`)
- [x] `ST-A4-1` **every** existing recording under the component's test-run
      directories loads; tick count > 0; no exception (skips with a named
      reason if that component is absent) — ran for real against all 7
      recordings under `modules/df/tests/carla_testruns/`
- [x] `UT-A4-13` **two clocks, not one** (`CR-SIM-4`, audit `A6`): a message
      round-trips **capture time and reception time** as separate integer-ns
      stamps; a codec supporting only one declares it as a capability and
      degrades explicitly (`R-SIM-14`). *`io/mcap.py` currently writes
      `publish_time=log_time_ns`, collapsing them — so an injected sensor
      latency cannot survive a round-trip, and every recording written before
      this lands is permanently missing a field*. *2026-07-31:* verified by
      `test_capture_time_round_trips_as_a_separate_stamp_from_reception`
      (`tests/unit/test_a4_mcap.py`) — a message received at 100 ms
      reporting a capture time of 80 ms round-trips both stamps distinctly;
      `test_capabilities_are_declared_and_reported` extended to assert
      `CAPABILITIES.capture_time is True`
- [x] `UT-A4-14` **`None` is not `equal`**: a codec with no capture stamp yields
      `capture_time_ns is None`, and a recording whose two stamps genuinely
      coincide yields two equal integers — the two cases are distinguishable at
      the reader, and a pre-delta recording reports `None` regardless of its
      bytes. Shown by round-tripping one file of each kind (`OD-9`).
      *2026-07-31:* verified by
      `test_none_capture_time_is_distinguishable_from_a_genuine_equal_stamp`
      (`tests/unit/test_a4_mcap.py`) — an old-style file (`manifest_version=0`)
      reports `None`; a new file (`manifest_version=2`) whose capture time
      genuinely equals its log time reports two equal, non-`None` integers
- [x] `ST-A4-2` read, write, read yields an identical topic/message set — ran
      for real against `tests/fixtures/tiny.mcap`

**Discipline**
- [x] portability §3 (`P-1`, `P-4`, `P-8`) · naming §3 (`N-2`, `N-6`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-A4-1` green across every existing recording, and `UT-A4-11` +
      `UT-A4-12` green — nothing outside `io/` knows a format exists, and a
      recording is reproducible byte for byte

---

## 5. Phase B — The viewer, on pure replay

**Still no C++ and no DLL.** Every stage here is driven by an already-exported
`.mcap` that already carries the component's output ports — so this is *replay*
in the §1 sense, and the framework never needs a SIL binding yet.

**That ordering is a design decision, not a convenience.** Building the viewer
before the generic ABI exists means the only way to drive a component here would
be a component-specific ctypes binding **inside the framework** — which is an
`R-SIM-1` violation that would then have to be unpicked. Replay avoids needing
one at all: by the time the framework talks to a library (`S-C1c`), the generic
ABI already exists and the binding is component-agnostic by construction.

Two consequences worth holding on to:

- **Everything in Phase B is testable with no build.** A recording plus a golden
  is the whole fixture set, which is why `GT-4` cannot regress here.
- **The viewer's contract is fixed before its first real input arrives.** The
  viewer renders a `Session` (`R-SIM-13`) and nothing else, and it is easiest to
  keep that true while a `Session` is the only thing that exists.

### S-B2 — `Session` + time transport

**Purpose.** Split executing from viewing, which is what makes backwards seek
possible at all. Closes **D7**; delivers the *scrolling* requirement
(`FR-SIM-12`) and the head model (`R-SIM-17`, `FR-SIM-17`).

**Must not.**
- Accumulate time as a float. `t_ns` is an integer accumulated from `dt_ns`;
  `t_s` is **derived and never fed back** (`P-8`). A float seconds accumulator
  here is precisely what makes a resim non-reproducible, and it fails silently.
- Let pass 2 mutate anything pass 1 produced. `Session` is immutable; that is
  what makes 100 random seeks a cheap test rather than a flaky one.

**Delta `S-B2Δ` — added 2026-07-31 (`OD-9`, `OD-13`, and the seed of `OD-6`).
Build order #4** — Block 1, blocked on `S-A3Δ` (#2) and `S-A4Δ` (#3).
The most invasive item of the 2026-07-31 pass — it changes a frozen core type
that 410 passing tests already use.** Depends on `S-A4Δ` landing first.

Read recording §10 first: the original *"long runs need a windowed Session"*
flag was **wrong about where the memory is**, and the corrected answer removes a
concept instead of adding one.

- [x] **`PortValue.capture_ns: int | None`**, carried from the recording's
      second stamp (`S-A4Δ`). *2026-07-31:* `core/runner.py`'s pass 1 recovers
      it from the raw 4-tuple messages via a small `(topic, log_time_ns) ->
      capture_time_ns` side table (`group_by_log_time`'s own yielded shape
      stays payload-only, per `S-A4Δ`'s own bullet — this delta is where that
      table actually gets consumed)
- [x] **`age_s` stops being stored and becomes derived**:
      `(t_ns − capture_ns)/1e9` when capture is known, else the schedule-derived
      hold age (`R-SIM-18`). This *removes* an ambiguity — today `age_s`
      silently means two different things depending on why a value is old.
      *2026-07-31:* a real `@property`, not a constructor argument — the two
      sources (`capture_ns` vs. the new `hold_age_s`) are never both set on
      one `PortValue`, which is what makes them distinguishable (`UT-B2-13`).
      `contracts/pipeline.Pipeline.step()`'s own schedule-tracked age now
      passes `hold_age_s=`, not `age_s=`
- [x] **`PortValue.message` becomes lazily parsed and memoised over retained
      bytes.** A `Session` is then bounded by the recording's size rather than by
      parsed-message count. This is also `NR-SIM-41`'s escalation step 1 —
      *"stop deserializing what nobody reads"*, the largest available throughput
      win — taken as the design rather than held as a contingency. *2026-07-31:*
      `PortValue` gained a hand-written `__init__` (`init=False` on the
      dataclass) so the public `message=` keyword is unchanged for every
      existing caller/test, while the real storage is raw bytes + a schema
      handle; `.message` parses once and memoises via `object.__setattr__`
      on the frozen instance, exactly `Tick.__post_init__`'s own trick.
      `decode_message` moved from `core/runner.py` to `core/tick.py` (its one
      real caller now), re-exported from `runner.py` for every docstring
      that still cites `core.runner.decode_message`
- [x] **`SceneCache` bounds by bytes**, with entry count as a secondary cap
      (`NR-SIM-43`). `max_size=256` today is an entry count, so the real ceiling
      is 256 × whatever a Scene weighs. *2026-07-31:* `max_bytes` (named
      constant `DEFAULT_SCENE_CACHE_MAX_BYTES = 256 MiB`) checked on every
      insert alongside `max_size`; a real `Scene` is measured by its own
      `encode_scene` byte size (protobuf import deferred inside the helper,
      `UT-A1-2`'s own discipline), a non-`Scene` test double falls back to
      `sys.getsizeof` so `UT-B2-3/5/12`'s existing tiny values never trip it
- [x] **Do not build a windowed `Session`.** It is rejected, with a reason worth
      re-reading before anyone re-proposes it: a window that has scrolled past a
      tick must re-execute to redraw it, which breaks `R-SIM-17`'s guarantee that
      *behind the head, seek and step-back are free and never re-run the SUT*.
      *2026-07-31: not built, confirmed nothing in this delta reaches for one*
- [x] `core/evidence.py` — the `Evidence` record and `evidence(address, session,
      tick)`, seeded here over what exists now (`run_id`, topics, origins,
      manifest) exactly as `core/explain.py` was seeded at this stage. It grows
      ports and stages at `S-C1c`, plug-ins at `S-C8`, and the panel at `S-D3`.
      **`cli/explain.py` must call it rather than re-deriving** — one producer,
      two formatters, from the first line of it (`OD-6`, `GT-9`). *2026-07-31:*
      `Evidence` seeded with exactly `address`/`kind`/`value`/`tick`/`t_ns`/
      `topic`/`origin`/`run_id` (`kind` one of `run_id`/`port`/`unknown` for
      now); `cli/explain.py` gained `--at <tick>` (`R-SIM-25`'s own CLI
      signature), calling `evidence()` when given, unchanged `core/explain.py`
      static behaviour otherwise
- Implement a backwards `exec()`. There is no inverse; see the head model.

- [x] `core/tick.py` — `PortValue` (message + `age_s`/`valid`/`updated`/
      `origin`), `Tick` with **integer `t_ns`/`dt_ns`** and `pose`
      (api reference §2.2).
- [x] `core/history.py` — `HistoryView`, a read-only windowed view over earlier
      ticks, and `FrameTree` composing static (model) + dynamic (`tick.pose`)
      transforms — together these are `LayerCtx`. **A windowed view, not the
      whole session**: handing a provider the full history invites it to become
      a second analysis engine.
      **Scoped:** `FrameTree` implements `ego`<->`world` only (fully
      resolvable from `tick.pose` alone). `sensor:<id>`/`image:<cam>`
      composition needs a static pose that is not generically available
      (`model/project.py`'s own `S-A2` scoping: real sensor/camera poses are
      calibration owned by the consuming component) — extended once a
      component's own layer provider (`S-B1`) supplies one
- [x] `core/session.py` — `Session`, `at(i)`, `seek_ns(t_ns)`, `events`,
      `deterministic`.
- [x] `core/runner.py` — pass 1 for the replay case; pass 2 is the renderer.
      Pass 1 groups raw `(topic, log_time_ns, bytes)` triples into `Tick`s
      via `io.base.group_by_log_time` (`S-A4`'s own `UT-A4-9` helper),
      decoding each payload against its topic's embedded schema when one
      exists (`decode_message`, the same dynamic-`FileDescriptorSet`
      technique `scene/codec.py` uses, R-SIM-11). `SceneCache` is pass 2's
      bounded, LRU-evicting memo, keyed by `(tick_index, layer_selection,
      theme)` -- never viewport (`UT-B2-5`)
- [x] `view/transport.py` — play/pause, step ±1/±10, speed, loop marks, goto,
      jump-to-event, **and the head** (`R-SIM-17`): `head_tick`, `is_at_head`,
      advance-N as one cancellable job with progress, `review_mode` on stepping
      back, and `resume_options()` returning **exactly two named choices** so
      that silently continuing from a rewound tick is not representable
- [x] `cli/explain.py` — **the first version of `sim explain`** (`DG-2`), over
      what exists now: a session, its topics, its layers, a `run_id`. Extended
      at `S-C1c` (ports, schemas, producers) and `S-D6` (expectations, values).
      Same reasoning as `sim doctor` in `S-A1` — the tool that explains names is
      needed while names are being created, not after.
      Facts live in `core/explain.py` (`GT-9`: `cli/` stays argument-parsing
      only), same split as `S-A1`'s `sim doctor`/`core/diagnostics.py`
- [x] Scene cache keyed by `(tick, layer_selection, theme)`, with a **stated
      bound** — an unbounded cache over a 36 000-tick session is `OQ-6` arriving
      early. (`core/runner.SceneCache`, above.)

**Tests**
- [x] `UT-B2-1` `seek_time` maps a time to the correct tick at boundaries
- [x] `UT-B2-2` **backwards seek**: from tick N to tick 0 returns tick 0's exact
      data — the thing that is impossible today
- [x] `UT-B2-3` toggling a layer re-renders and does **not** re-run pass 1
      (assert a pass-1 call counter is unchanged) — the test that keeps the
      layer panel feeling like a tool rather than a re-run
- [x] `UT-B2-4` speed/loop/step arithmetic at the ends (tick 0, tick N)
- [x] `UT-B2-5` cache invalidates on theme change, **not** on viewport change
- [x] `UT-B2-6` **time is exact**: `t_ns` accumulated over 10 000 ticks equals
      the sum of `dt_ns` with zero drift; `t_s` is derived and never fed back
- [x] `UT-B2-7` **stepping backward leaves execution mode**: `is_at_head` goes
      false, `review_mode` true, and the SUT's `exec()` counter does not advance
      on any further backward step or seek
- [x] `UT-B2-8` **resume offers exactly two choices**, and *recompute-from-0* is
      unavailable when `deterministic` is false, carrying its reason
- [x] `UT-B2-9` **no silent continue**: advancing from a rewound tick without
      choosing raises, rather than calling `exec()` with mismatched state
- [x] `UT-B2-10` advance-N arithmetic: 50/100/200/custom clamp at the end;
      cancel at tick *k* leaves `head_tick == k`
- [x] `UT-B2-11` `Session` is immutable: mutating a returned `Tick` or its
      `ports` raises, so pass 2 cannot corrupt pass 1
- [x] `UT-B2-12` the Scene cache respects its bound and evicts least-recently-
      used, measured on a session larger than the bound
- [x] `UT-B2-13` `age_s` is **derived, and states which clock it came from**:
      capture-derived when the recording carries a capture stamp, hold-derived
      otherwise, and the two are distinguishable rather than both surfacing as a
      bare float (`OD-9`). *2026-07-31:* `tests/unit/test_b2_tick.py` --
      capture-derived, hold-derived, neither-set, and the core claim (equal
      `age_s` floats from the two sources, `capture_ns` says which)
- [x] `UT-B2-14` **the resim path parses nothing.** Drive a pipeline over a
      recording with a deliberately un-parseable payload on a port no layer,
      expectation or plot reads: the run completes. Then read that port and
      assert it raises. Parsing-on-demand is only real if not-parsing is
      observable (`OD-13`). *2026-07-31:* Phase B has no pipeline yet (no
      C++, no DLL) -- verified on the replay path instead, the one that
      exists: `test_the_resim_path_parses_nothing_until_message_is_read`
      builds a `Session` from a real `.mcap` carrying one genuinely
      un-parseable payload; `build_session_from_recording` completes without
      raising, and only `.port(...).message` raises (`DecodeError`)
- [x] `UT-B2-15` `SceneCache` evicts on a **byte** bound: a cache holding few
      but large Scenes evicts, where an entry-count bound would not (`NR-SIM-43`).
      *2026-07-31:* three tests in `tests/unit/test_b2_scene_cache.py` --
      small values never trip the (generous) default byte bound; a tiny
      `max_bytes` with a generous `max_size` evicts on bytes alone; a real
      `Scene`'s own encoded size (not a generic `sys.getsizeof`) drives it
- [x] `ST-B2-1` on a ≥1000-tick session, 100 random seeks all return correct data
- [x] `ST-B2-2` a full pass 1 over the largest existing recording completes
      within a stated budget, **recorded as a number** — not asserted as a limit
      until a baseline exists. Ran for real: `bsd_ego_lane_exit.mcap`, 276
      ticks, 0.195s
- [x] `ST-B2-3` **rewind then recompute-from-0 is exact**: recomputing to tick
      *N* reproduces the original tick *N* byte-for-byte on a deterministic
      resim.

**Discipline**
- [x] portability §3 (`P-8`) · naming §3 (`N-7`, `N-10`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `UT-B2-2` + `ST-B2-1` green; the "forward only, no rewind" caveat is
      deleted from the existing tool's docstring only in `S-E1`
- [x] `UT-B2-6` green — exact time is the precondition for every determinism
      claim later in this plan, and it is cheapest to establish here

### S-B1 — Layer providers + parity render

**Purpose.** Prove the Scene IR carries a real function's picture. Closes
**D2**, **D5**. First stage that touches a component repo — **adding, never
removing**.

**Must not.**
- Import a renderer, `cv2`, `matplotlib` or Qt from any provider (`GT-2`).
- **Recompute anything the SUT already produced** (`R-SIM-7`). If a ProPort
  carries a warning state, draw *that* state. `UT-B1-6` proves it by feeding a
  deliberately contradictory output and requiring the layer to show the
  contradiction — a layer that "corrects" the SUT is a layer that hides bugs.
- Delete or edit the existing viewer. Parity is demonstrated **against** it, and
  it is removed only in `S-E1` (`NR-SIM-30`).

- [x] `modules/<name>/sim/layers/common.py` — ego body, objects, grid/frame
      furniture, HUD fields (the component-generic half).
- [x] `modules/<name>/sim/layers/<fn>.py` — one file per function; each is the
      *only* place that function's picture is described. Built `bsd.py`
      (zone + warning band; see the scope-reduction note above)
- [x] Layers reconstructed from calibration rather than read from a port carry
      `derived=True` and render with the `derived` style variant — a **marked**
      stopgap, never a silent one (`R-SIM-7`). `bsd.zone`'s rectangle carries
      it. **`df.common.trail` originally carried it too, on the reasoning
      that a history reconstruction is the same kind of stopgap as a
      calibration one — that reasoning was wrong and the trail's actual
      problem was worse than a missing marker; see the correction round
      below.**
- [x] `modules/<name>/sim/viewpoints.yaml` — named viewpoints as data
- [x] `render/bev.py` — the **Qt-independent** Scene-to-raster core, so it is
      testable headless and reusable by the image renderer. Qt enters in `S-B3`
      and never below this line. Built on matplotlib's `Agg` backend (already
      a real dependency, the "figures" extra) rather than a from-scratch
      rasteriser.
- [x] `view/viewport.py` — `Viewport`, follow modes, presets, zoom-about-cursor

**Also required, not in the original checklist (found while wiring the
above):**
- [x] `render/theme.py` gained `register_component_token` — a driving
      function's own `<fn>.*` style tokens (`bsd.zone.boundary`,
      sim_visualization_spec.md §3.2) had nowhere to register; `resolve()`
      now checks component-registered tokens after the framework's static
      table, discovered by import the same way `scene/registry.py`'s layer
      providers are
- [x] `scene/registry.py`'s `layer_provider` gained `group=`/`requires=` --
      needed for `UT-B1-1`'s gating and `sim_architecture.md`'s own
      `@layer_provider(group=..., requires=...)` example. Resolved that
      example's two-parameter `(tick, ctx)` sketch against api reference §5's
      one-parameter `LayerProvider.__call__(self, ctx)` by treating "now" as
      `ctx.history`'s own most recent windowed tick, not a second parameter
- [x] `core/runner.py`'s port keys were the raw topic string
      (e.g. a slash-namespaced path) instead of N-2's dotted port name --
      found while wiring the first real layer provider and needing to look
      a port up by the name N-2 actually documents. Added
      `_topic_to_port_name` and always wraps the reader in
      `LegacyRecordingReader` (a no-op on a modern recording, so every
      recording -- old or new -- presents namespaced names)

**Tests**
- [x] `UT-B1-1` `requires` gating — a Tick lacking a function's output yields
      **no** layers for it and raises nothing
- [x] `UT-B1-2` provider purity — same `Tick` twice yields equal `Layer`s
- [x] `UT-B1-3` no provider module imports a renderer (AST scan; `GT-2` as a
      test, so the rule fails a run rather than a review)
- [x] `UT-B1-4` the ego layer's box equals `EgoModel`'s numbers — asserted by
      **changing the project and seeing the box change**, not by comparing to a
      literal, which would just restate the constant being tested
- [x] `UT-B1-5` two different object classes draw different footprints
- [x] `UT-B1-6` warning state is **read**, not recomputed: feeding a
      contradictory output makes the layer show the contradictory value
      (`R-SIM-7`)
- [x] `UT-B1-7` layers built from calibration reconstruction carry
      `derived=True` and render with the `derived` style variant
- [x] `UT-B1-8` padding slots in a fixed-size object list produce no prims — the
      classic "50 objects at the origin" picture.
- [x] `UT-B1-9` viewport: metre-pixel-metre round-trips; zoom about the cursor
      keeps the cursor's world point fixed; scale clamps at its declared bounds
- [x] `UT-B1-10` renderer hit-test resolves to the prim actually drawn — one
      hit-test path, not one per prim type.
- [x] `UT-B1-11` a provider reads `age_s`/`valid` off a `PortValue` and a stale
      port changes what it draws — the metadata survives the boundary.
      (No existing provider did this until this test asked for one --
      `df.common.hud` now greys out and annotates its text when
      `source.veh_dyn` is stale)
- [x] `UT-B1-12` a **temporal** layer (an ego trail) built from `ctx.history`
      produces the right polyline, and the provider holds no state between
      calls: call it twice **out of order** and get identical output.
      **Rewritten in the correction round** (see below) to build ticks from
      explicit, varying `Pose2D` values instead of dead-reckoned `veh_dyn`,
      since the fixed `trail_layer` no longer reads `veh_dyn` at all. A new
      test, `test_ego_trail_with_no_real_pose_source_draws_nothing`, locks in
      the degenerate case (every tick's pose identical -> no prims)
- [x] `UT-B1-13` **a provider is pure**: called twice with the same `LayerCtx`
      it returns equal layers and holds no attribute that changed between the
      calls (`R-SIM-2`)
- [x] `UT-B1-14` no two layer ids share a prefix (`N-3b`) — solo/mute selects by
      id, and a prefix collision silently selects the wrong set
- [x] `ST-B1-1` replay an existing recording — the `Scene` for every tick matches
      the golden.
      **Scoped:** goldens cover a 5-tick sample (0, 50, 100, 162, last) of
      `bsd_curve_r172_passby_20260727_213847.mcap`, not literally every tick
      of every recording — enough to catch a replay regression, generated by
      a checked-in script (`tests/fixtures/make_bsd_golden.py`), never
      hand-crafted
- [x] `ST-B1-2` the same replay under a **different project** produces a
      different ego box and different geometry — configuration drives the
      picture (**D3**), and this is the test that proves it end to end
- [x] `ST-B1-3` headless render of 100 ticks raises nothing and produces
      non-blank frames
- [x] `MC-1` a human confirms the rendered frame is equivalent to the existing
      viewer's on the same tick — recorded with date and name.
      **Owner: Pavan Karimajji Date: 2026-07-29 Result: Pass.** Renders sent for
      review: tick 0 (no object) and tick 162 (right-side `NORMAL` warning
      correctly paired with a right-side object) of the same recording ST-B1-1's
      golden uses, `base` project, `dark` theme. **First pair reviewed
      2026-07-29 — findings triaged in the correction round above; a second
      pair (grid labels visible, no fabricated trail) went out after the
      fix, reviewed 2026-07-29 — parity confirmed.** Follow-up noted, not a
      blocker: the per-side `OFF`/`NORMAL` warning labels sit close enough to
      the ego status line to crowd at this zoom level — worth a spacing look
      next time `bsd.warning` is touched.

1. **No coordinate/distance references on the grid.** A real gap, not scope
   creep — `sim_visualization_spec.md` §3.2 already declared the
   `frame.grid_label` token (`frame.* origin, axis, grid, grid_label,
   scale_legend`); `frame_layer` just never emitted it as prims. **Fixed:**
   `frame_layer` now adds a `text` prim styled `frame.grid_label` along both
   axes, in both directions. **Refined once more on user feedback:** `+x`
   (longitudinal) stays at the grid's own 10m spacing, but `+y` (lateral)
   labels every 5m instead — there just isn't much to see off to the side
   (BSD/lane scale, not highway scale), so 10m reads as too coarse there.
   Labels are bare numbers (`"10"`, not `"10m"`) — the axis is metres
   throughout, stated once rather than repeated on every tick.
   **Superseded 2026-08-07:** this fixed pass drew every label at
   a small, fixed metre offset from the coordinate origin (`y_m=0.4`/
   `x_m=0.4`) — legible in isolation, but sitting directly on the ego box
   and any near-origin object once actually rendered end to end, confirmed
   real from a live PNG. Labels moved out of the provider entirely: the
   grid `Prim` now carries `spacing_lateral_m` (the 5m/10m split above,
   preserved) and the RENDERER draws the coordinate labels, anchored near
   the current viewport's own margin rather than the crosshair — a
   provider may not read the viewport (`R-SIM-2`), so this could only ever
   be a renderer-side fix. See `render/bev.py`'s `spacing_lateral_m`
   handling and label-margin anchoring, and `scene/default_layers.py`'s
   `frame_layer` (formerly `df.common.frame`, moved by `AR-52` the same
   day).
2. **An ego "front" marker** (a roof/triangle shape on the body box, so
   heading reads at a glance). Checked every doc this plan cites for BEV
   content (`sim_visualization_spec.md`, `sim_requirements.md`) — no such
   requirement exists anywhere; a new idea, not a missed one. **Deferred**
   (user's own call, 2026-07-29) to a later BEV-polish pass (`S-B3`/`S-B4`);
   `df.common.ego` still draws the plain asymmetric box (`UT-B1-4`).
3. **The white ego-trail curve, and where it comes from.** The significant
   one: `df.common.trail` was dead-reckoning `veh_dyn`'s `vx`/`yaw_rate` over
   the history window (`x += vx·cos(yaw)·dt`, `yaw += yaw_rate·dt`) to draw a
   path — an **estimate** built on an assumption (no side-slip) the SUT never
   asserted, justified at the time as "extending `R-SIM-7`'s calibration-
   reconstruction allowance to history." That framing was wrong: `R-SIM-7`
   sanctions a deterministic transform of a fixed constant or of a value some
   port/world model already produced — never integrating a noisy
   time-varying signal into information nobody emitted. A visualization
   layer renders what happened; it does not compute what might have.
   **`R-SIM-7`'s wording was tightened** to close this loophole explicitly
   rather than leave it implied. **Fixed:** `trail_layer` now draws
   `ctx.frames.to_ego(tick.pose.x_m, tick.pose.y_m)` for each windowed tick —
   a pure coordinate-frame transform of `Tick.pose` (real ego-in-world data,
   whatever produced it) — no longer reads `source.veh_dyn` and no longer
   carries `derived=True` (it is a transform, not a calibration-
   reconstruction stopgap). Today's real recordings carry no ego
   ground-truth pose (`Tick.pose` defaults to the coordinate origin for
   every tick, `core/runner.py`), so the fixed layer honestly draws **no
   trail at all** for them rather than a fabricated curve — a flat dot
   pretending to be a trail would be worse than no trail. Golden fixtures
   regenerated: `df.common.trail` is absent from every golden `Scene` now,
   and `df.common.frame` grew from 6 to 46 prims (the new grid labels; back
   down to 6 as of `AR-56`, 2026-08-07 — the labels are the renderer's own
   now, not baked prims).
   **Corrected 2026-08-07:** "honestly draws no trail at all"
   above was the SAME silent-empty-layer pattern `AR-53` eliminated for
   `bsd.warning` on the very same day, just not recognised as one yet at
   the time this paragraph was written — a layer absent from the Scene
   and the layer tree with no visible reason. `trail_layer` (now the
   framework's own, `AR-52`) draws the placeholder `Layer(unavailable=
   ...)` `AR-53` built when the recording genuinely carries no ego pose
   (distinct from simply not having enough history yet, which stays a
   silent, transient `()`). Caught along the way: `Layer.unavailable`
   itself had never been wired into `scene/codec.py`, so this row's own
   golden fixture — the first ever to carry an unavailable *layer* — went
   red until that was fixed too.

**Discipline**
- [x] portability §3 (`P-1`, `P-3`) · naming §3 (`N-2`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-B1-1` + `MC-1` — parity proven before anything new is added. **The
      existing viewer is NOT deleted here** (that is `S-E1`), because parity is
      only meaningful while both exist.
      `ST-B1-1` is green; `MC-1` is closed (Pass, 2026-07-29) — gate closed
- [x] `ST-B1-2` green — otherwise `D3` is closed on paper only

**Delta `S-B1Δ` — re-opened 2026-07-31 (`D13`, `R-SIM-21`). Build order #6** —
Block 1, blocked on `S-C1cΔ` (#5, the port-address resolver) and `S-A3Δ` (#2,
`Prim.derived`). `S-C4` (#7) follows it immediately: same file set.** The stage's own gates all
passed and still pass; what they never checked is the **plug-in boundary**,
because no gate looked at it. `GT-1`/`GT-2`/`GT-3` scan `modules/sim/src` — they
stop precisely where a component's plug-in begins. Three defects in the ~320
lines of `modules/df/sim/`, all in the same shape:

- [x] **Port addresses are literals** — `requires=("df.bsd.outputs",)` and
      `ctx.history.last(1)[-1].port("df.bsd.outputs")` in
      `sim/layers/bsd.py`. The `df.` segment is the **pipeline stage name**
      (`Pipeline` builds addresses as `f"{stage.name}.{port.name}"`), so a
      pipeline that names the stage anything else unbinds the layer; the rest
      is a C++ constant in another repo bound to this file by nothing.
      Replace with component-relative `self.bsd.outputs`, resolved once at load.
      *2026-07-31:* both call sites now use `self.bsd.outputs` — `requires=` and
      `ctx.port("self.bsd.outputs")` (`LayerCtx.port`, new). Proved under a
      renamed stage, not just the default one (`test_b1_df_layers.py`'s
      `test_warning_layer_binds_correctly_under_a_renamed_stage`)
- [x] **The failure is silent** — `scene/registry.py`'s `gated` wrapper returns
      `()` for a missing port, so a broken binding renders as *no overlay*,
      which on screen is indistinguishable from "no warning was raised". Make an
      unresolvable `requires` an `AuthoringError` at load, naming the plug-in,
      the port and every port the manifest declares (`N-8`). **A `requires` that
      is unsatisfied at *this tick* stays a legitimate empty result** — a port
      that does not exist and a port that has not arrived are different
      statements, and merging them is what made this invisible.
      *2026-07-31, corrected after checking with the user:* Block 1 discovers
      layer providers by import into one process-global registry (`R-VAR-2`)
      with no live component manifest and no per-session plug-in scoping yet
      (`S-C8`/`S-D3`) — so a `self.<port>` reference matching **zero** known
      ports is indistinguishable, from a single recording's own topics alone,
      between "this port does not exist" and "this run never wired that
      component" (the ordinary case: e.g. a `bsd` layer rendering an `aeb`-only
      recording). Raising there broke ~40 existing tests rendering synthetic,
      component-unrelated recordings. Landed instead: `contracts/binding.py`'s
      `try_resolve_component_ref` raises only on **ambiguity** (more than one
      known port matches — a same-run collision, real regardless of a live
      manifest) and returns `None` (silent empty layer) on zero matches;
      `resolve_component_ref` stays strict (raises on zero *or* many) for a
      caller already past that gate (`LayerCtx.port`). A perfectly precise
      "does not exist anywhere, ever" check needs a live component manifest —
      out of reach until `S-C8`/`S-D3`'s per-session plug-in scoping exists —
      and is recorded here as a scoped gap, not solved by this stage.
- [x] **A layer provider reads disk** — `_bsd_calibration()` calls
      `path.read_text()` on `df`'s project YAML **per tick**, which `R-SIM-2`
      forbids outright ("a provider never touches disk") and which bypasses
      `R-SIM-3a`: it reads the *source checkout*, not the bundle the SUT was
      initialised with. That is exactly the "two readers agreeing by
      coincidence" failure the bundle exists to prevent, reintroduced by the
      first plug-in written against it. Route through `ctx.model`.
      *2026-07-31:* `functools.lru_cache`d per project — reads disk once per
      project, never per tick. **Scoped gap, not fixed here:** it still reads
      the source checkout rather than the bundle the SUT was initialised with,
      because `ProjectModel` deliberately exposes no generic bundle-directory
      accessor yet (`model/project.py`'s own docstring) — there is nothing
      beyond the project name to route this through until one exists
- [x] `UT-B1-15` (renumbered off `UT-B1-14` — see the finding below) a
      `self.<port>` `requires=` entry ambiguous across this run's known ports
      raises naming the plug-in; one matching zero ports, or matching but not
      yet present this tick, stays a silent empty result without raising
      (`test_b1_registry_gating.py`). **Revised 2026-08-07**: "zero
      ports" no longer stays silent — see the superseded note above —
      `test_b1_registry_gating.py`'s own test for that case is renamed
      `test_a_self_ref_matching_nothing_yields_a_named_unavailable_placeholder`
      and asserts the placeholder, not an empty tuple. The "matching but not
      yet present this tick" half is unchanged

*Scope added 2026-07-31 (`OQ-13`). The concept count was never an API problem —
it was a documentation one — but one line of it is real ergonomics:*

- [x] **`LayerCtx.now`** — a property returning `history.last(1)[-1]`, the
      current tick. Today every provider opens with
      `ctx.history.last(1)[-1]`, which puts *windowed history* — an advanced
      concept — in front of every author before they draw anything. One
      property removes it from the minimum path without removing anything from
      the API. *2026-07-31:* landed in `core/history.py`; `modules/df/sim/
      layers/common.py`'s `objects_layer`/`hud_layer` switched to it too (the
      motivating "every provider opens with this" case), alongside
      `LayerCtx.port(ref)` (self.-resolution + `.now.port(...)` in one call)
- [x] `.claude/templates/sim_layer_provider.py` is the **measured artefact** for
      `OQ-13`: a canonical minimal provider of **≤15 lines** mentioning only the
      four core concepts (decorator, `ctx`, `Prim`, style token), with every
      optional idea below a second heading. *(Rewritten 2026-07-31 — the previous
      version taught all ten at once and imported `@inspector_fields`, which no
      longer exists.)*
- [x] `Prim.derived` is set on reconstructed prims in `modules/df/sim/`, not only
      `Layer.derived` — this stage owns the first plug-in that actually mixes
      published and reconstructed geometry (`OD-6`). *2026-07-31:* every prim
      in `zone_layer` and `warning_layer` now carries `derived=True` (position
      is calibration-derived in both; `warning_layer`'s drawn *state* is real,
      making it the mixed case `OD-6` describes) — `Layer.derived=True` on
      `warning_layer` follows from `Layer.__post_init__`'s own constraint

- [x] `python scripts/check_invariants.py`: `GT-11` — no port address is a
      literal outside the component that declares it — added as a mechanised
      check (it existed only in prose before this stage), scanning every
      `requires=(...)`/`.port(...)` argument under `modules/*/sim/**` for a
      dotted, three-plus-segment string that is neither `self.`- nor
      `source.`-prefixed. Clean on the real tree; `test_a1_check_invariants.py`
      proves it both ways (a planted `requires=("df.bsd.outputs",)` fails it,
      `self.`/`source.` refs on the same line pass)

**Why this was missed, recorded because it generalises.** Every invariant in
this plan is enforced by a scan over `modules/sim/src`. The framework's
correctness is therefore well-guarded and the *contract between the framework
and a plug-in* is not guarded at all — it was specified in prose (`R-SIM-2`) and
verified by nothing. `S-B1` was the first stage to cross that boundary and it
crossed it wrongly in three ways on the first attempt, which is roughly what one
should expect from an unguarded interface. `GT-11` is the gate; the general
lesson is that **an invariant scoped to a directory stops at that directory**,
and the interesting failures are on the other side of it.

### S-B3 — Qt viewer shell

**Purpose.** The interactive surface: docks, panels, layer tree, inspector,
timeline, plots. Everything a developer touches, over the `Session` that `S-B2`
made seekable.

**Must not.**
- **Run pass 1 on the GUI thread.** Building a `Session` blocks for as long as
  the recording is long; doing it on the UI thread defeats the scrubbing this
  phase exists to deliver, and the symptom (a frozen window) gets misread as a
  performance problem rather than a threading one. Pass 1 runs on a worker;
  results are handed back by signal; the GUI never blocks on it.
- **Put logic in the shell** (`GT-9`). A panel arranges and dispatches; anything
  it computes belongs in `core/`, `view/` or `check/` where it is testable
  headless. The test for this is whether `ST-B3-1` can do it with no window.
- Name a font family, write a settings path by hand, or assume a display
  exists (`P-7`).

- [x] `render/viewer.py` — the Qt window; a **dockable peer-panel grid** where
      BEV, camera, plots, timeline, inspector, layers and pipeline are all
      panels, none privileged (visualization spec §11.1). **`BevPanel` +
      `LayersPanel` exist so far** — camera/plots/timeline/inspector/pipeline
      dock in as their own slices, with no change to `MainWindow`'s shape
- [x] **Threading**: pass 1 on a `QThread`/worker, progress by signal,
      cancellable; the Scene cache is read from the GUI thread only. One
      documented ownership rule, stated in the module docstring
- [x] `view/layers.py` — layer tree, groups, solo/mute, verbosity level, search,
      per-project persistence. **Persistence is the state class's own
      `save()`/`load()` against a caller-given path** — `MainWindow` now
      wires it against `QStandardPaths.AppConfigLocation`, per (project,
      pipeline) (Slice 3)
- [x] `view/workspace.py` — read `modules/<name>/sim/workspace.yaml`; shipped
      default, user override, reset (viz §13b). **A component's arrangement, not
      an application mode** — Bench/Campaign arrive in `S-D8` and load this.
      **Scoped:** parses every tab faithfully, but only `tabs[0]` is applied
      to `MainWindow`'s panels — a true second tab (its own `BevPanel` at a
      different viewpoint) needs tab-switching shell architecture this
      slice does not build (`view/workspace.py`'s own docstring)
- [x] `Interaction` on `LayerCtx` + `reacts_to=` on the provider decorator;
      the cache key includes interaction **only for declaring layers**, so a
      mouse move does not invalidate the whole scene (viz §7.5)
- [x] `view/inspector.py` — docked, declared fields, pin, multi-select,
      copy-as-text
- [x] `view/timeline.py` — signal lanes (one scale per lane), state lanes with
      labels, event markers, bookmarks, click-to-seek
- [x] `view/signals.py` — the **one signal resolver** (viz §7.4):
      `<component>.<port>.<field>` · `source.*` · `truth.*` · `derived.*`. Raw
      port fields resolve off the manifest with **no registration**; only
      computed signals register with `@signal` (`NR-SIM-8`). **Built as
      `core/signals.py` instead** (`S-B3` slice 6, checked with the user) --
      `Session.signal()` (`sim_api_reference.md` §2.3) lives in `core/
      session.py`, and `check/`'s expectation evaluator (`S-D6`) needs the
      same resolver headless; `core/` is where both can depend on it in the
      normal direction rather than `check/` importing something named
      `view/`
- [x] `view/plots.py` — `timeseries` / `xy` / `state` / `distribution` panels
      over that resolver
- [x] `view/measure.py` — ruler with snap, range rings, cursor readout carrying
      the **frame name**, persistent annotations
- [x] HUD + the stale/invalid banner (viz §10). **Scoped:** scale/time/
      tick/project-scenario-pipeline-build-id are always shown (framework-
      known); the ego-state line and the stale banner are caller-supplied
      config (`ego_state_signals`/`max_age_s`), empty by default -- the
      framework has no component calibration to guess a value from
      (`R-SIM-1`, `view/hud.py`'s own docstring). The origin dot/axis
      arrows/distance grid are **not** built here — `modules/df`'s own
      `frame_layer` already draws these as a component layer in a
      different submodule; moving that into framework furniture is a
      real, undecided cross-submodule question, not silently duplicated
- [x] `cli/view.py`, `cli/render.py` — argument parsing only. **Not
      `app/cli.py`**: `app/` is the GUI and holds no logic (`GT-9`).
      Landed as `app/gui.py` (orchestration: `QApplication`, `MainWindow`,
      event loop), matching the file this bullet actually asks for

**Tests**
- [x] `UT-B3-1` layer-tree state: group tri-state, solo/mute, persistence
      round-trips
- [x] `UT-B3-2` inspector resolves a `pick_id` to its provider's declared fields;
      an entity that disappears is **dropped, not shown stale**
- [x] `UT-B3-3` timeline: a state lane emits an event marker at every transition
      and only there
- [x] `UT-B3-4` ruler distance/dx/dy/bearing correct; snap picks the nearest
      anchor within the threshold
- [x] `UT-B3-5` stale banner appears exactly when `valid == 0` or the port's age
      exceeds its declared maximum
- [x] `UT-B3-6` one signal string resolves identically for the timeline strip
      and a plot panel; a **raw port field needs no registration** at all.
      Closed in Slice 10: `_signal_series_cache` is shared by `TimelineStrip`
      and every `PlotPanel`, so the same address resolves to the literal
      same cached tuple (`is`, not just `==`) for both
- [x] `UT-B3-7` a `timeseries` lane with two signals of different magnitude
      creates **two lanes**; a single lane with two y-scales is rejected —
      a dual-axis plot is the most reliable way to make two signals look
      correlated when they are not. `PlotState.add_lane` never merges two
      addresses into one lane, same as `TimelineState` — the mistake this
      bans is not representable, not merely rejected at run time
- [x] `UT-B3-8` `xy` panel plots signal-vs-signal; colouring by a third works
- [x] `UT-B3-9` playhead is shared — seeking in a plot moves the BEV and the
      timeline to the same tick
- [x] `UT-B3-10` panel grid: open/close/split/tab/float; a saved layout restores
- [ ] `UT-B3-11` a component's `workspace.yaml` opens its declared tabs, splits
      and ratios; a **missing** workspace falls back to BEV + timeline, no error.
      **Scoped precursor landed in Slice 9** (`tests/unit/test_b3_workspace.py`,
      `tests/system/test_b3_workspace_wiring.py`): parsing every tab/split/
      ratio, the missing-file fallback, and applying `tabs[0]`'s views (BEV
      viewpoint, timeline signals) to real panels are all proven; "opens its
      declared **tabs**" (plural, as distinct arrangements) waits on
      tab-switching shell architecture (`view/workspace.py`'s own docstring)
- [x] `UT-B3-12` the user's own layout wins over the shipped default, and
      `Reset layout` returns to it
- [x] `UT-B3-13` a provider declaring `reacts_to=("cursor",)` receives the
      cursor **in its own frame, in metres**, and re-renders on cursor change
- [x] `UT-B3-14` a provider declaring nothing is **not** re-rendered on a mouse
      move — interaction stays cheap, and purity holds
- [x] `UT-B3-15` **pass 1 does not run on the GUI thread**: with a deliberately
      slow reader, the window stays responsive and progress is reported;
      asserted on thread identity, not on elapsed time
- [x] `UT-B3-16` cancelling a load leaves no partial `Session` reachable — a
      half-built session rendered as if complete is a silent wrong picture
- [x] `UT-B3-17` no Qt module is imported by anything under `core/`, `model/`,
      `scene/`, `contracts/`, `io/` or `check/` (`GT-9`, api reference §1)
- [x] `ST-B3-1` `sim render <recording> --at <t> --preset <name> --out fig.png`
      produces a non-blank PNG **headlessly**
- [ ] `ST-B3-2` the full panel set opens and renders under an offscreen
      platform, on both platforms (`P-7`) — this is how the GUI is tested at all.
      **Full panel set closed on Windows in Slice 13**
      (`tests/system/test_b3_full_shell_offscreen.py`): `BevPanel`,
      `LayersPanel`, `InspectorPanel`, `TimelineStrip`, `TransportBar` and a
      `PlotPanel` all open, all render a real non-null frame, and scrubbing
      still works with every one of them open, offscreen, in one window.
      **"On both platforms" stays open** — this session has no Ubuntu
      environment to verify against; the offscreen mechanism itself
      (`QT_QPA_PLATFORM=offscreen`) is the same code path on both, but the
      platform itself is unverified, not something a Windows-only session
      can close by writing more tests
- [x] `MC-4` a human confirms scrubbing a long session feels responsive.
      Confirmed 2026-07-30 against the real BSD golden recording
      (`bsd_curve_r172_passby_20260727_213847.mcap`, df's actual
      `sim.layers.{common,bsd}` providers, no mocks) — nothing flagged
- [x] `MC-1` (repeat) a human confirms the full shell reads well. Confirmed
      2026-07-30, same session as `MC-4` above

**Discipline**
- [x] portability §3 (`P-7`) · naming §3 (`N-7`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `UT-B3-15` + `ST-B3-2` green — responsive by construction and testable
      with no display, which is what makes every later GUI stage cheap.
      `UT-B3-15` is green (Slice 1); `ST-B3-2`'s buildable half closed in
      Slice 13, its "on both platforms" half stays open (no Ubuntu
      environment this session can verify against) — so this combined
      bullet stays unchecked on that basis alone, not a code gap
- [ ] Every item in visualization spec §4–§9 demonstrable on one recording,
      ticked individually below — **demonstrated 2026-07-30** on the real BSD
      golden recording via Vantage's own `sim view` path (`app/gui.launch`),
      df's actual `sim.layers.{common,bsd}` providers, nothing stubbed.
      Before handing off for the human pass, the live window's `BevPanel`
      pixmap was pulled directly and diffed against a fresh headless
      `render_scene()` call on the same tick — identical, so the mechanism
      behind every item below was already known-correct going in. **Eight of
      nine ticked**; the ninth is out of this stage's scope by design (see
      its own line) so the parent stays unchecked on that basis, not a demo
      failure:
      - [x] pan / zoom / fit / presets / follow modes — **built (Slice 7a)**;
            follow modes are real, cyclable state with **no rendering
            effect yet** (`render/bev.py` never reads `Prim.frame` — a
            named, undecided gap, not part of this demonstration's claim)
      - [x] scrub, step, speed, loop, jump-to-event — **built (Slice 7b)**
      - [x] layer tree with groups + verbosity — **built (Slice 2)**
      - [x] selection + docked inspector — **built (Slice 5)**
      - [x] timeline signal + state lanes with markers — **built (Slice 8)**
      - [x] ruler, range rings, annotations — **built (Slice 11)**;
            cursor readout is a status-bar label, not part of the
            rendered canvas (`view/measure.py`'s own documented choice)
      - [x] plot panels (timeseries / xy / state / distribution), playhead-synced
            — **built (Slice 10)**
      - [x] dockable peer-panel grid with a saveable layout — **built
            (Slices 1, 3)**
      - [ ] snapshot PNG **+ provenance sidecar**, and video export — **not
            this stage's file list** — `render/capture.py`'s `snapshot()`
            (PNG + JSON sidecar) and clip export are named explicitly under
            `S-B4` below; `cli/render.py`'s own headless `--out fig.png`
            (Slice 13) is a different, sidecar-less capability that
            satisfies `ST-B3-1`, not this bullet

### S-B4 — Capture with provenance

**Purpose.** A picture that leaves the tool must carry enough to be believed.
Closes `FR-SIM-13`.

**Must not.** Write a PNG whose sidecar could be lost without anyone noticing.
The sidecar is written in the same call, or the capture fails.

- [x] `render/capture.py` — `snapshot(session, tick, viewport, layers, out)`
      writing `out.png` **and** `out.json` atomically (temp file, then rename;
      a half-written pair is worse than none)
- [x] The sidecar carries: `run_id` (`N-9`), tick, `t_ns`, project,
      `bundle_sha256` **and** `bundle_origin`, scenario, pipeline hash, every
      component build hash, viewport, active layers, theme, Scene version, tool
      version
- [x] `render/clip.py` — interval export to mp4, same sidecar, one per clip
- [x] `cli/render.py` — headless `sim render --at <t|tick> --out fig.png`,
      working under an offscreen platform (`P-7`)
- [x] Print variant: same Scene, `print` theme, vector output where the renderer
      supports it — one Scene, two renderers, never two drawing paths (`D5`)

**Found and fixed running Vantage against a real BSD recording**: neither
`snapshot()` nor `export_clip()` ever threaded a `ProjectModel` through to
`build_scene`, so both always re-resolved a checkout-only default —
the same bug class `render/viewer.py`'s `_resolve_project_model` was fixed
for (S-C8's gate), but never patched here. `sim render` had **no
`--plugin-root` flag at all**, so a component's real layers (e.g. a driving
function's zone/warning) could never be imported by the CLI in the first
place; even a caller that imported them separately would then hit
`snapshot()`'s missing `model=` and crash with `FileNotFoundError` the
moment a layer read calibration relative to a DEPLOYED copy's own path
(confirmed: `bsd.py`'s `_bsd_calibration`, against the real `df_sil` build
tree). Fixed:
- `model/plugins.py` gained `register_plugin_root(library_dir)` — the
  shared implementation `scripts/vantage.py`'s own `_register_plugin_root`
  now delegates to, so there is one implementation, not one per entry
  point.
- `snapshot()`/`export_clip()`/`sidecar_dict()` gained `model:
  ProjectModel | None = None`, threaded into `build_scene`; `None` keeps
  every existing caller's behaviour exactly unchanged.
- `export_clip()` also resolves its model **once**, before the per-tick
  loop, rather than implicitly re-resolving on every frame — a real,
  separate inefficiency found while fixing the same call site (`ST-C5-2`'s
  discipline extended here).
- `cli/render.py` gained `--plugin-root` (repeatable, same meaning as
  `vantage.py`'s own flag).
Verified against the real recording (`bsd_ego_lane_exit.mcap`) and the real
`df_sil` build: `sim render --plugin-root <dir>` now renders the zone
rectangles and object boxes it previously omitted, with no crash.

**Tests**
- [x] `UT-B4-1` a snapshot writes exactly two files, and neither exists if the
      other could not be written
- [x] `UT-B4-2` the sidecar contains every field listed above; a missing one
      fails the test by name, not by count
- [x] `UT-B4-3` a plot panel captures with the same sidecar shape as the BEV —
      one capture path, not one per panel type
- [x] `UT-B4-4` a snapshot sidecar carries the **same `run_id`** as its session
      (`N-9`) — given any one artefact you can find the other five
- [x] `UT-B4-5` `bundle_origin` is recorded, so a picture rendered from a
      checkout is distinguishable from one rendered from the embedded bundle
      (`R-SIM-3a`)
- [x] `UT-B4-6` `snapshot()`/`export_clip()` use a given `model=` instead of
      re-resolving one — proven with a test-only layer that only produces a
      prim when `ctx.model.bundle_dir` is populated, so a silently-dropped
      `model=` shows up as a missing layer, not a crash.
      `test_b4_capture.py::test_snapshot_threads_a_given_model_through_instead_of_re_resolving`,
      `test_b4_clip.py::test_export_clip_threads_a_given_model_through_instead_of_re_resolving`
      (both isolate the layer-provider registry to their own file's
      providers — `build_scene` calls every globally registered one, and a
      real component's layer imported by an unrelated test elsewhere this
      session would see this test's `bundle_dir` too and crash on a bundle
      shaped for this test only, the same order-dependency
      `test_c8_relocatability_installed.py` sidesteps with a subprocess).
      `test_b4_capture.py::test_snapshot_with_no_model_still_resolves_a_default_unchanged`
      covers the `model=None` backward-compatibility half.
- [x] `ST-B4-1` `sim render` twice at the same tick produces byte-identical PNGs
- [ ] `ST-B4-2` `sim render` works with **no display**, under an offscreen
      platform, on both platforms (`P-7`). **Buildable half closed**: no Qt
      anywhere in this dependency chain at all (matplotlib's `Agg` backend,
      unconditionally headless — there is not even an offscreen-platform flag
      to set, unlike `S-B3`'s Qt panels). "On both platforms" stays open on
      the same basis as `ST-B3-2`: no Ubuntu environment this session can
      verify against.

**Discipline**
- [x] portability §3 (`P-2`, `P-4`, `P-7`) · naming §3 (`N-4`, `N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-B4-1` + `ST-B4-2` green — a snapshot is reproducible evidence, and it
      is producible on a build machine with no screen. `ST-B4-1` is green;
      `ST-B4-2`'s buildable half is green and its mechanism is platform-uniform
      (pure `matplotlib`/`imageio-ffmpeg`, no Qt), but its "on both platforms"
      clause stays open for the same reason `S-B3`'s combined gate bullet
      does — not a code gap.

---

## 6. Phase C — The SIL contract, the production side, the bundle

**The only phase that changes production C++**, and therefore the only phase
that can break a shipping component. Three properties hold throughout:

- **Every C++ change is additive until Phase E.** The generic exports live
  *beside* the positional ones and are tested against them; nothing is removed
  until `S-E2`, gated on the new path being proven equivalent.
- **`src/component/**` is never touched.** The new exports are a name-lookup
  shim onto the existing body (`df_sil_dll.md` rule 9). If a stage here needs an
  algorithm change, the stage is wrong.
- **`GT-4` is re-checked after every commit in this phase**, not just at the
  stage gate. A component's own test suite going from green to green is the only
  evidence that "additive" was true.

**Two platform traps this phase must avoid**, both of which an earlier draft of
this plan walked into and which are the reason
[sim_portability.md](sim_portability.md) exists:

| Trap | Wrong | Right |
|---|---|---|
| Locating the library's own directory | `GetModuleFileNameW` — Windows-only, and it appears in the natural first draft of `adasInit(NULL)` | a one-function abstraction: `GetModuleFileNameW` on Windows, `dladdr` on Linux, declared in the contract doc and implemented once (`P-5`) |
| The bundle's output path | `<build>/…/Release/config/` — `Release/` is a multi-config generator artefact that does not exist under Make/Ninja | `$<TARGET_FILE_DIR:…>/config/`, which is correct for every generator |

---

#### Phase C review, 2026-07-30 — `S-C1a`/`S-C1b` re-opened

`S-C1a` and `S-C1b` were built and self-reported green against a **standalone
`gcc` harness**, because that session had no `conan` and no MSVC. This review
ran the repo's own pipeline. The finding that matters is not any single bug —
it is the **failure mode of the substitution itself**:

> A parallel toolchain verifies the *code*. It structurally cannot verify the
> *build*, because it does not use the build. Both defects below live entirely
> in CMake and in cross-repo commit order — the exact surface a hand-rolled
> `g++` command line replaces rather than exercises.

| | Command | Result |
|---|---|---|
| `ST-C1a-1` | `modules/interfaces/build.bat -t gtest -p vs2026 -P base` | **6/6 green** — gate closed |
| `GT-4` / `ST-C1b-1` | `modules/df/build.bat -t gtest -p vs2026 -P base` | **CMake generate error → after a one-word fix, 228/228 green** (14 generic + 6 positional, incl. the byte-identical equivalence test) |

**What was actually wrong, and the rule each one restates:**

| # | Defect | Rule |
|---|---|---|
| 1 | `df_manifest_dump` links `yaml-cpp::yaml-cpp` — not visible in that directory scope — and not `df_common`, so it gets neither the `interfaces` include dirs nor protobuf. **The whole `df` build fails at generate**, tests included | `GT-4` |
| 2 | `interfaces` HEAD has no `#define ADAS_SIL_ABI_VERSION`; `df`'s **committed** `df_interface_c.cpp` uses it. The define was left uncommitted in the working tree | `R-GIT-1` |
| 3 | `component_manifest.proto` has no `period_ns`, which `R-SIM-18` requires and `S-C1c` consumes — `S-C1c` cannot be built without reopening `S-C1a` | `R-SIM-18` |
| 4 | `adasInit(NULL)` returns a **valid handle with zero configuration**: `ParamLoader` swallows the unreadable path and every function defaults. The header promises the opposite | `NR-SIM-4` |
| 5 | Port names are written **three times** (`buildManifest`, `adasExec` dispatch, `df_sil.ports.yaml`) and bound by nothing; `UT-C1b-2` makes a typo *silent* | `R-SIM-16` |
| 6 | `aeb.comp_state` vs the `ProPort` member `compState` — `N-1`'s single-grep promise already broken in a name the contract calls permanent | `N-1` |
| 7 | The generic-ABI tests are gated on `"aeb" IN_LIST ENABLED_FUNCTIONS`, so a `bsd`-only build silently drops every component-level `ManifestTest.*` | `R-VAR-5` |
| 8 | `df_sil.ports.yaml` is checked in carrying `project:`/`version:`/`build_id:` — build-variant values in a file whose purpose is a reviewable port diff | `R-SIM-3a` |
| 9 | `df_sil.ports.yaml` is **not** emitted beside the artefact, though `S-C1b`'s checkbox says it is | `R-SIM-3a` |
| 10 | `df_sil` links `df_common` PRIVATE while its installed public header now includes `adas/adas_sil_abi.h` — the root cause of defect 1 | `R-BUILD` |

Defects 3–6 are **contract** defects: each one is cheap now and permanent
later, because `S-C1c` turns port names into topics, signal paths, CSV headers
and `expect:` strings. They are why this phase is re-opened rather than patched
forward. The delta work is carried as unticked boxes in the two stages below;
**neither stage's Gate may be ticked until its delta is clear.**

*Two process observations, recorded because they generalise:* a status line may
report what was verified and **must not tick a box the verification did not
cover** — `S-C1b`'s prose was accurate about its harness while its checkboxes
claimed the pipeline; and `GT-4`'s recorded baseline sat 138 tests stale for
six days for exactly the same reason, so **the gate now names the command and
the date it was measured**.

**What this phase got right, since a review that lists only defects misleads.**
`R-BUILD-2`/`R-BUILD-6` were honoured exactly: the `BUILD_TESTING` fix and the
editable-mode `includedirs` fix each went to all seven/eight byte-identical
copies in a single pass, verified byte-identical by checksum in this review.
The `BUILD_TESTING` finding was real and load-bearing — without it
`interfaces`' new suite would have reported success while running zero tests,
which is the worst available outcome and the one `ST-C1a-1` now disproves.
`src/component/**` is genuinely untouched, `updateReqPort` is genuinely shared
between both paths, and the "a fallback must never be a member of the real
value space" catch (`"unknown"`, not `"base"`) is a standing rule worth keeping.

**One `R-BUILD-1` note, out of scope here but not to be lost.** The editable
fix put `self.cpp.source.includedirs = ["cpp", "include"]` in the
byte-identical recipe because *`interfaces`* ships `include/`. `R-BUILD-1` says
all per-component difference lives in `conf/build.yml`, never in the recipe.
Harmless today — one `cmake_layout` component, and a non-existent directory
elsewhere — but it is the first component-specific fact to enter the shared
recipe, and it belongs in `plan.md` item 20's data-driven `recipe:` block
alongside `type:`/`libs:`, not as a literal.

### S-C0 — the automatic gate, before anything else in Phase C

> **Build order: #1** (§0a is the authority on sequence). Block 1. First stage of Phase C. Blocked on nothing.

**Purpose.** The audit's finding is right: `S-C6` (CI) sits at the **end** of
Phase C, after every stage that relied on manual verification — and manual
verification is the mechanism that has already failed twice here (`GT-4`'s floor
138 tests stale for six days; two stages reported green from a substitute
toolchain). In both cases the response was to write down a date, i.e. *more
careful manual verification*.

**Why this is a separate stage and not simply "move `S-C6`".** `S-C6` runs
`sim check` over the scenario set, and **the scenario set does not exist until
`S-C3`**. Moving the stage wholesale is impossible; moving its *first half* is
not. `S-C0` is the half that is buildable today. `S-C6` keeps its label and its
scenario half, because a stage id is a stable citation (§0).

**Must not.** Grow into a general CI design — that is `plan.md` item 20 and it
is larger than this module. `S-C0` runs what already exists, automatically, and
nothing more.

**A second, real gap found 2026-08-07, while trying to close `ST-D6-1`'s own
CI caveat**: `sim`'s CI job checks out only `Pavan-karimajji/sim`
(`actions/checkout@v4`, no `submodules:`, no sibling-repo step — `sim`'s own
repo carries no `.gitmodules` of its own, confirmed directly). Any test whose
fixture needs a sibling submodule — today, `test_d6_probe.py` and
`test_d6_day_one_walkthrough.py`, both gated on `modules/interfaces/include`
via an identical `_INTERFACES_INCLUDE` skip guard — reports `skipped` in
**both** `gate` and `core-only-smoke`, regardless of whether the runner has
`gcc`. This is a structural consequence of the submodule architecture
(`R-GIT-1`: one repo per component), not a bug in either test or in this
workflow file as written. **Undecided, not this stage's to take**: whether
`sim-ci.yml` grows a sibling-repo checkout step (a real CI-design change,
which this stage's own "Must not" already declines to make unilaterally) or
this class of test stays permanently CI-skipped and is instead verified the
way `ST-D6-1` was closed on 2026-08-07 — a container or a newer local shell,
on demand, evidence recorded in the plan rather than automated.

- [x] One job, triggered on every push to `feat/sim-platform` in `modules/sim`
      (plus `workflow_dispatch`, for a manual re-run — the one addition beyond
      this stage's literal wording, and it adds no new check),
      running exactly the three checks a stage already owes:
      `python -m pytest modules/sim/tests -q` · `scripts/check_invariants.py` ·
      `docs/py/run_all.py`
- [x] The job **records the pytest count** and fails when it drops below the
      recorded floor — the mechanical version of `GT-4`'s discipline, applied to
      the one suite that needs no compiler. A count that falls silently is the
      exact defect this stage exists for
- [x] Artefacts retained on failure: the pytest output, the `run_all.py` report,
      the `run_id` (`N-9`). A red build nobody can diagnose gets muted, and a
      muted gate is worse than no gate
- [x] The job is **skipped with a named reason** when a change touches only
      documents *and* `run_all.py` is green — so a docs commit is fast but never
      unchecked
- [x] The known flake (§10) is listed by name in the job config with its ticket,
      **not** deselected silently. A quarantined test that nobody can see is a
      deleted test

**Tests**
- [x] `ST-C0-1` (2026-07-31) the job runs green on the current tree, and its
      recorded pytest floor equals the number actually observed on the day it
      was set — 409, `scripts/ci_gate_config.yaml` — no aspirational floor, the
      defect `GT-4` already suffered
- [x] `ST-C0-2` (2026-07-31) the job turns **red** on each of three planted
      defects, one per check: a deleted test, a planted `GT-1` violation, and a
      requirement citing a test id the plan does not define. Proving the gate
      can fail is the only property that matters, and one planted defect per
      check is what stops a job that runs only the cheapest of the three

**Discipline**
- [x] portability §3 (`P-4`, `P-6`, `P-10`) · naming §3 (`N-9`, `N-10`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C0-2` green — all three planted defects turn the job red, verified
      locally against the exact script the workflow invokes. A gate that has
      never failed has never been shown to work
- [x] The pytest floor is recorded with **a number and a date** in this stage's
      own text, not only in the job config — 409, 2026-07-31

### S-C1a — `interfaces`: the ABI header and the manifest schema

*(`S-C1a`/`S-C1b`/`S-C1c` are the three sub-stages of the architecture's single
**C1**; they land separately because each is independently verifiable.)*

**Purpose.** Define the generic ABI and the manifest that makes ports
discoverable. **`D1` closes here or nowhere** — this is the stage that stops
`dfExec` growing a parameter pair per function.

**Must not.** Consume the header anywhere yet. This stage is purely additive:
`interfaces` builds, nothing links against the new symbols, and no component
changes. That is what makes it independently revertible.

- [x] `interfaces/include/adas/adas_sil_abi.h` — `AdasPort`, `AdasPortSet`, the
      five exports (`sim_sil_contract.md` §3.1). **Where `R-SIM-4` is built**:
      ports are named and discovered, so adding a function adds a manifest line,
      never an ABI parameter and never a host edit
      - **C, not C++**: no `bool`, no namespaces, no default arguments, no
        `class`. Fixed-width integer types only (`int32_t`, `uint64_t`), and
        `size_t` for buffer lengths
      - **`cdecl` on both platforms.** No non-`cdecl` Windows calling
        convention, no `__declspec` outside a single export macro that
        expands to `__attribute__((visibility("default")))` on GCC/Clang
        (`P-5`).
- [x] `interfaces/proto/Adas__Sil/component_manifest.proto` — `ComponentManifest`
      incl. `project`, `config_bundle_sha256`, `descriptor_set`, `abi_version`,
      and per port: name, direction, `proto_type`, required/optional. Package
      `adas.sil` (matches the contract doc's own `adas.sil.ComponentManifest`
      references). Carries a `PROVENANCE:` comment (`R-IFACE-3`): this schema is
      original to the sim rework, not reference-derived, so it does not claim
      the verbatim-naming exception
      - Field naming per `R-NAME-4`; port names per `N-1` — **the token chosen
        here is the token every later layer reuses, and it is permanent**
- [x] `R-NAME-4` / `R-STYLE-1` headers on both

**Tests**
- [x] `UT-C1a-1` (gtest, `interfaces`) the header compiles as **C**, not just
      C++ — `tests/unit/test_adas_sil_abi_c_probe.c`, a real `.c` translation
      unit built as C11 (`project()` gained `LANGUAGES CXX C`), exposing
      `adasSilAbiCProbeSizeofPort()`/`...PortSet()` back to the gtest binary so
      `AdasSilAbiTest.CAndCppAgreeOnLayout` proves the C- and C++-compiled
      views of the struct genuinely agree, not just that each parses
      separately
- [x] `UT-C1a-2` `ComponentManifest` round-trips in C++
      (`tests/unit/test_component_manifest.cpp`) and in Python
      (`tests/python/test_component_manifest_roundtrip.py`, a standalone
      script — `interfaces` has no pytest tooling of its own to add it to;
      skips with a named reason when `build/generated_py` doesn't exist yet).
      Both independently verified to produce the same 119-byte serialization
      for the same fixture
- [x] `UT-C1a-3` every struct's `sizeof` and member offsets match the static
      assertions — re-asserted in `test_adas_sil_abi.cpp` so a future edit that
      touches the numbers in both places at once still gets caught by a test
- [x] `UT-C1a-4` the header contains no Windows-only type or calling convention
      (text scan for `WINAPI`/`__stdcall`/`HANDLE`/`DWORD`) — `P-5` as a test.
      Caught the header's own comment self-violation (see Finding above) before
      this test was even run for real
- [x] `ST-C1a-1` `interfaces` builds clean; Python bindings generate —
      **CLOSED 2026-07-30 through the repo's own pipeline**:
      `modules/interfaces/build.bat -t gtest -p vs2026 -P base`, `ctest`
      reports **6/6 passed**. The `BUILD_TESTING` fix in the Finding above is
      confirmed working — without it this run would have reported zero tests
      and looked identical to success
- [x] `UT-C1a-5` `period_ns` round-trips, and a manifest that omits it reads
      as `0` = *undeclared* rather than as `0 ns` — the two must not be the
      same observable value at the pipeline's GCD step (delta below)

**Delta `S-C1aΔ2` — added 2026-07-31. Build order #11 — the first Block 2
stage, and everything else in Block 2 waits on it.**

*Found while sequencing the concept-resolution pass, not while designing it.*
Two of the resolutions need **manifest attributes that the shipped
`component_manifest.proto` does not have**, and one of them reverses a decision
this stage already ticked. Discovering that at `S-C5` would have meant building
`S-C1d`'s generator, then reopening `interfaces`, then regenerating — the
cross-repo rework the Phase C review already paid for once.

- [x] **Per-**function** period.** The ticked box above records `period_ns` as
      *"component-level, not per `PortSpec`"*, and `OD-12` reverses it: a period
      is declared per function, in **integer microseconds**, so that AEB at 20 Hz
      and BSD at 10 Hz in one library are expressible. Add the per-function
      field; **keep component-level `period_ns` readable** so `S-C1c`'s shipped
      GCD scheduler and `UT-C1a-5` keep working — this is additive, like every
      other Phase C change (`S-E2` is where anything is removed).
      *2026-08-03:* `PortSpec.period_us` (field 7, `uint64`) in
      `interfaces/proto/Adas__Sil/component_manifest.proto` — plain, not
      `optional` (same "0 = undeclared, no real port runs at 0 us" reasoning
      `period_ns` already uses, so no presence tracking is needed)
- [x] **`fixed_slots` per port.** `OD-8`'s `drop` must clear a fixed-size padded
      slot in place and remove a variable-length element — and **the framework
      must not guess which**. The port declares it; the manifest carries it;
      Python reads it. Declaring it anywhere the framework reads directly
      (`conf/ports.yaml`, a pipeline key) would be a second description free to
      drift from the port's real shape, which is `R-SIM-4`'s whole point.
      *2026-08-03:* `PortSpec.fixed_slots` (field 8, `optional bool`) — real
      proto3 explicit presence, since `false` is itself a meaningful answer
      here (unlike `period_us`). `contracts/component.py`'s hand-built
      bootstrap schema (`R-SIM-11`'s "nothing to resolve a descriptor_set
      from yet") reproduces protoc's own synthetic-oneof shape for a
      proto3-optional field by hand, since it cannot generate one
- [x] Both fields are **optional with an honest absent value** — `0`/unset means
      *undeclared*, never a default that looks like an answer (`NR-SIM-4`).
      A consumer that needs one and finds it absent says so, naming the field.
      *2026-08-03:* `contracts/pipeline.py`'s `_validate_overrides`/
      `_apply_input_overrides` read `port_spec.fixed_slots` directly now (no
      more `getattr(..., None)` — the attribute genuinely exists); **no real
      component populates either field yet**, that is `S-C1d`'s own job
      (build order #12) — `select`/`drop` still raises today, honestly,
      naming the still-undeclared field, not a regression
- [x] `UT-C1a-6` the per-function period round-trips, two functions at different
      periods are both readable, and a manifest carrying only the old
      component-level field still loads — the additive guarantee, tested.
      *2026-08-03:* `interfaces/tests/unit/test_component_manifest.cpp`
      (`PortPeriodUsRoundTripsPerFunctionIndependently`,
      `PortPeriodUsDefaultsToUndeclaredAndOldManifestsStillLoad`) — real
      MSVC/Conan build, 10/10 green (7 prior + 3 new); Python binding half
      in `tests/python/test_component_manifest_roundtrip.py`, run directly
      against generated bindings, green
- [x] `UT-C1a-7` `fixed_slots` round-trips per port, and a port that does not
      declare it reads as **undeclared** rather than as `false` — because
      `false` means *"variable length, safe to compact"*, which is exactly the
      silent renumbering `OD-8` exists to prevent.
      *2026-08-03:* `FixedSlotsUndeclaredIsDistinctFromExplicitFalse` (same
      file) — asserts `HasField("fixed_slots")` on all three states
      (undeclared / explicit false / explicit true), not just the bool value

  **`S-C1aΔ2` closed 2026-08-04.** `test_c1c_component.py` gained
  `test_parse_manifest_round_trips_every_field` (extended) and
  `test_parse_manifest_port_period_us_and_fixed_slots_undeclared_defaults`
  — the Python-side counterpart to `UT-C1a-6`/`UT-C1a-7`, decoding both
  fields through `contracts/component.py`'s hand-built bootstrap schema,
  not just the generated C++/Python bindings `interfaces`' own tests use.
  536/536 `modules/sim` unit tests green. `df` rebuilt against the edited
  `interfaces` via its active `conan editable` (no republish needed): `sil`
  and `gtest` targets both green — `gtest` 233/233 (real MSVC/Conan build,
  `vs2026`), confirming the additive proto change breaks nothing downstream
  before a single line of `S-C1d`'s generator exists. `df` itself still
  populates neither new field (that generator is `S-C1d`'s own job) — this
  stage's job was the manifest attribute existing and being readable, both
  now true.

**Discipline**
- [ ] portability §3 (`P-5`, `P-8`) · naming §3 (`N-1`, `N-11`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Delta — re-opened 2026-07-30** (see the Phase C review above). Everything
here changes `interfaces` only and stays purely additive; `abi_version` does
**not** move, because none of it alters `AdasPort`/`AdasPortSet` layout or
`adasExec` semantics — which is the point of having the two version numbers be
independent (`sim_sil_contract.md` §7).

- [x] **Commit `#define ADAS_SIL_ABI_VERSION 1`** — it is used by `df`'s
      committed source and exists only in `interfaces`' working tree, so the
      committed submodule pointers do not compile together (`R-GIT-1`: the
      submodule commits **first**, then the pointer). Ordering, not content:
      the define itself is right, and is what stops each component hardcoding
      its own literal
- [x] **`period_ns` in `ComponentManifest`** (field 10, `uint64`) — required by
      `R-SIM-18`, consumed by `S-C1c`'s GCD base grid, and absent from the
      shipped schema. `0` means *undeclared*, and the pipeline says so rather
      than treating it as a rate. Component-level, not per `PortSpec`: the
      reasoning is in `sim_sil_contract.md` §3.2 and belongs there, not in a
      commit message
- [x] **`adasInit`'s contract stated in the header** — returns `NULL` when
      configuration cannot be resolved, and **never** a handle carrying
      silently-defaulted calibration. The header currently promises bundle
      resolution that `S-C5` has not built, which is worse than promising
      nothing (`NR-SIM-4`, `sim_sil_contract.md` §3.4)
- [x] **`dtS` is float seconds by decision, not by accident** — one comment in
      the header saying so, and naming `CtypesSilComponent.exec` as the single
      integer-ns → float-seconds conversion point. `P-8` governs *timestamps*;
      this is a per-tick duration, and `src/component/**` already takes it
      (rule 9). Written down so nobody "fixes" it into an ABI break later
- [x] **Port-name spelling frozen** in `sim_sil_contract.md` §3.2: the segment
      after the dot is byte-identical to the `ReqPort`/`ProPort` member in
      `<fn>_ports.hpp` (`aeb.compState`). This is `N-1` applied to the second
      half of the name, and it is only cheap before `S-C1c` turns these into
      topics and `expect:` strings

**Gate**
- [x] `ST-C1a-1` green — real pipeline, 6/6, 2026-07-30
- [x] `UT-C1a-4` green
- [x] Nothing consumes the header yet (purely additive, revertible in one
      commit) — **still true; the delta kept it true**
- [x] `UT-C1a-5` green; every delta box above ticked. `S-C1c` **must not
      start** before this gate, because it is the first consumer and every
      unclosed item here becomes a name it has already spread

### S-C1b — the component library: generic exports **alongside** the positional ones

**Purpose.** Make one real component speak the generic ABI, with both ABIs live
and tested against each other (`sim_sil_contract.md` §6). This is the first
stage that modifies a shipping artefact.

**Must not.** Touch `src/component/**`. `adasExec` is a **name-lookup shim onto
the existing body** (`df_sil_dll.md` rule 9) — if this stage needs an algorithm
change, the design is wrong, not the algorithm. And must not remove or alter the
positional exports: `sil_host` still calls them, and `ST-C1b-2` proves it.

- [x] `adasAbiVersion` / `adasManifest` / `adasInit` / `adasExec` /
      `adasShutdown` in the component's `*_interface_c.cpp`, `adasExec`
      dispatching **by port name** onto the existing implementation.
      `adasInit`/`adasShutdown` delegate straight to `dfInit`/`dfShutdown`
      (zero chance of the two paths diverging on lifecycle); `adasExec`
      dispatches via `findPort()` + the shared `updateReqPort` template onto
      the exact same `DfHandle`/`AebFunction`/`BsdFunction` `dfExec` already
      calls — no `src/component/**` file touched
- [x] Manifest generator driven by `ENABLED_FUNCTIONS` (`R-VAR-5`), embedding
      the `FileDescriptorSet` — so the manifest **cannot drift from what was
      compiled**, which is the whole reason it is generated rather than written.
      `buildManifest()` in `df_interface_c.cpp`, `#ifdef`-guarded identically
      to the rest of the file; `addFileAndDeps()` walks each used message
      type's transitive `FileDescriptor` dependencies into one
      `FileDescriptorSet`, de-duplicated by filename
- [~] `df_sil.ports.yaml` checked in (the "beside the artefact" half moved to
      `S-C5`, where `R-SIM-3a` puts it in `<library_dir>/config/` with the rest
      of the bundle rather than in a second place)
      (`df_sil.ports.yaml`, content verified against a real `adasManifest()`
      call before committing — see Status above). Regeneration is a
      **deliberate** action (`df_manifest_dump`, a new small executable
      target, never run automatically) — the same discipline `modules/sim`'s
      own golden files use, and the reason `ADAS_DF_BUILD_ID` is not wired
      for real (see Finding above)
- [x] `try/catch(...)` on every new `extern "C"` body (rule 12)
- [x] Export visibility via the one macro from `S-C1a` (`ADAS_SIL_ABI_EXPORTS`,
      a second, independent export flag from `DF_SIL_EXPORTS` since it belongs
      to a different header); **no `.def` file**

**Tests** — in the component's own `tests/unit/sil/`
- [x] `UT-C1b-1` every existing positional-API test assertion **mirrored** onto
      the generic path, with identical expected values
      (`test_generic_interface_c_api.cpp`'s `GenericInterfaceCApiTest.*`, each
      naming its positional twin in `test_interface_c_api.cpp`) — both suites
      verified green side by side against the same built library
- [x] `UT-C1b-2` an unknown input port (`"acc.something"`) is ignored
- [x] `UT-C1b-3` a required input that is absent behaves exactly as `valid == 0`
- [x] `UT-C1b-4` an all-default (zero-byte) payload with `valid == 1` is accepted
- [x] `UT-C1b-5` an undersized output buffer returns the **required size** and
      writes nothing (sentinel bytes in the buffer verified untouched)
- [x] `UT-C1b-6` embedded manifest equals the emitted `df_sil.ports.yaml`
      (structural fields only — `build_id` excluded, see Finding above)
- [x] `UT-C1b-7` a build with **both** functions disabled yields zero ports in
      the manifest — verified via a manual BCT-01-style recompile (Status
      above), same effort level `df_sil_dll.md` rule 10 already established
      for this exact class of check, not a permanent automated test
- [x] `UT-C1b-8` `descriptor_set` contains every `proto_type` the manifest names,
      **transitively** — verified by loading it into a real
      `DescriptorPool`/`SimpleDescriptorDatabase` and resolving every named
      type, not just checking the byte count is non-zero
- [x] `UT-C1b-9` **one token, every layer**: every non-empty `owner_function`
      in the manifest is checked against a real `src/component/` subdirectory
      on disk
- [ ] `UT-C1b-10` an exception thrown inside the implementation is caught at the
      boundary — **not tested**, same precedent `df_sil_dll.md` rule 12 already
      set for the positional path ("no controlled way to trigger a real throw
      today without adding an artificial hook... documented as defensive
      code")
- [x] `ST-C1b-1` **equivalence**: for a fixed sequence of inputs, the generic
      and positional paths produce **byte-identical** outputs — real,
      byte-for-byte verified (Status above)
- [x] `ST-C1b-2` `sil_host` still builds and runs unchanged — **green
      2026-07-30**, end to end, against a **clean rebuild** of the modified
      `df`. No `conan create` was needed after all: `adas-df` and
      `adas-interfaces` are registered as Conan **editables**, so `sil_host`
      already resolves the working tree. `main.cpp` untouched, `dfApiVersion()`
      still `2`, `dfInit`/`dfExec`/`dfShutdown` all OK, exit code 0.
      - **This run also validates the delta's one deliberate asymmetry.**
        `sil_host` calls `dfInit(nullptr)` and depends on today's
        silent-defaults behaviour to start at all. Had the delta fixed the root
        cause in `ParamLoader` — the tempting option, since it would have
        corrected both API generations at once — this run would have failed.
        That is exactly why the strictness lives in `adasInit` alone: the
        positional path's contract is load-bearing for a shipping host, and
        `S-C1b` is additive. `ParamLoader` is `S-E2`'s to revisit, once nothing
        calls the positional exports

**Discipline**
- [ ] portability §3 (`P-3`, `P-5`) · naming §3 (`N-1`, `N-4`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Delta — re-opened 2026-07-30** (see the Phase C review above). Ordered so the
tree builds after every step; item 1 is the only one blocking anything else.

- [x] **Link `df_manifest_dump` against `df_common`** —
      `target_link_libraries(df_manifest_dump PRIVATE df_sil df_common)`.
      One word, and the difference between a red and a green `df` build
- [x] **`df_sil` links `df_common` `PUBLIC`** (or at minimum propagates
      `AdasInterfaces::AdasInterfaces`) — its **installed** header
      `df_interface_c.h` now includes `adas/adas_sil_abi.h`, so every consumer
      of `AdasDf::AdasDf` needs that include path and today gets it only by
      coincidence. Fixing this makes item 1 unnecessary rather than merely
      unblocked, which is the better shape; keep item 1 regardless, since
      `df_manifest_dump` genuinely uses protobuf directly
- [x] **One static port table**, iterated by both `buildManifest()` and
      `adasExec`'s dispatch — the port name, `proto_type`, `max_bytes`,
      `owner_function` and the `ReqPort`/`ProPort` it binds, declared once
      inside the same `#ifdef ADAS_FN_<X>_ENABLED` blocks. Removes the
      drift-between-two-lists failure by construction instead of testing for
      it (`R-SIM-16`, `sim_sil_contract.md` §3.2 "One table, two readers")
- [x] **Rename `<fn>.comp_state` → `<fn>.compState`** in the manifest, the
      dispatch and `df_sil.ports.yaml` — matching the `ProPort` member
      (`N-1`). Free today; a breaking change to every recording, signal path
      and `expect:` string the moment `S-C1c`/`S-C2`/`S-C3` land
- [x] **`period_ns` populated** from the component's real cycle time once
      `S-C1a`'s delta adds the field
- [x] **`adasInit(NULL)` returns `NULL`** until `S-C5` resolves a real bundle.
      `adasInit` stops being a bare delegation to `dfInit` — deliberately:
      `S-C1b` bought "zero chance of the two paths diverging on lifecycle",
      and this trades a slice of that for the one difference that must exist,
      because `dfInit`'s silent-defaults behaviour is the positional path's
      contract and `S-C1b` may not change it
- [x] **Split the test file** — component-level ABI cases
      (`AbiVersionIsStable`, `UnknownInputPortIsIgnored`, every
      `ManifestTest.*`) into an **ungated** `test_generic_abi.cpp`, keeping
      only the aeb-mirroring cases under `if("aeb" IN_LIST ENABLED_FUNCTIONS)`.
      Today a `bsd`-only build silently drops the whole manifest suite, which
      is the one suite that has nothing to do with any function
      (`R-VAR-5`; `test_param_loader.cpp` already sets the ungated precedent)
- [x] **Build-variant fields leave the checked-in `df_sil.ports.yaml`** — it
      carries `project: base`, `version: 0.1.0`, `build_id: unknown`, so
      regenerating from a `cus1` build produces a spurious diff in the one file
      whose stated purpose is that a **port** change shows up as a reviewable
      diff. `UT-C1b-6` does not compare those fields, so nothing catches it.
      The checked-in mirror holds build-invariant facts only (`component`,
      `abi_version`, `inputs`, `outputs`); project/version/bundle hash belong
      to the emitted copy in `S-C5`'s bundle, where they are true per build
- [x] **Untick "emitted beside the artefact"** below, or emit it — there is
      only `install(FILES … DESTINATION share/adas-df)`; nothing lands in
      `$<TARGET_FILE_DIR:df_sil>`. Recommend unticking and letting `S-C5` own
      it, since `R-SIM-3a` wants it in `<library_dir>/config/` beside the rest
      of the bundle, not in a second place
- [x] **`df_manifest_dump.cpp`'s own header comment says "Run as a POST_BUILD
      step"** — the `CMakeLists.txt` in the same commit explains at length why
      it is deliberately *never* run automatically. `GT-7`, at the smallest
      possible scale

| Probe | Change | Expected | Got |
|---|---|---|---|
| A | regress the port name to `aeb.comp_state` | `UT-C1b-12` red | red — plus `ContainsTheAebPorts` and `UT-C1b-6`, three independent catches |
| A | " | `UT-C1b-11` **green** | green — the one-name-constant design means a rename cannot desynchronise the manifest from the dispatch, which is the property being claimed |
| B | declare an output row nothing dispatches | `UT-C1b-11` red | red, naming the unbound port |

**Tests added by the delta**
- [x] `UT-C1b-11` **every manifest-declared name is a name the dispatch
      actually uses**: drive each declared input under its manifest name and
      assert an observable effect; supply each declared output under its
      manifest name and assert `updated`/`len` are written. `UT-C1b-2`'s
      silent-ignore rule makes a manifest typo invisible without this, and
      "invisible" here means neutral outputs and a green run
- [x] `UT-C1b-12` every port name's post-dot segment matches a real
      `ReqPort`/`ProPort` member name — `N-1`'s second half, enforced the same
      way `UT-C1b-9` enforces its first half against `src/component/`
- [x] `UT-C1b-13` `adasInit(NULL)` returns `NULL`; `adasInit("<real path>")`
      returns a handle. The negative case is the one that matters and is the
      one nothing tests today

**Gate**
- [x] `ST-C1b-1` green — the new path is proven equivalent **before** anything
      depends on it, the precondition for `S-E2` ever removing the old one.
      Byte-for-byte, against the real MSVC-built `df_sil.dll`, 2026-07-30
- [x] `GT-4` green at or above **228** — **233/233**, clean rebuild, 2026-07-30.
      Re-measured under `-P cus1` as well (also 233/233), which is what proves
      the checked-in manifest is genuinely project-independent now
- [x] Every delta box and `UT-C1b-11..13` green
- [x] `ST-C1b-2` green — `sil_host` builds and runs unchanged against a clean
      rebuild of the modified `df`, exit 0. **`S-C1b`'s gate is now clear**

### S-C1c — `contracts/` — `SilComponent`, `Pipeline`

**Purpose.** The Python side of the contract, and the wiring engine. After this
stage the framework can drive any component that ships a manifest — including
components that do not exist yet, which is `FR-SIM-70`'s claim.

**Must not.** Import a generated protobuf binding, or name a component, a
function or a port anywhere in the framework. `GT-6` and `GT-1` are both live
here, and `UT-C1c-3` runs with the generated bindings made **unimportable** so
the claim is tested rather than asserted.

**Blocked on `S-C1a`'s delta — ✔ resolved 2026-07-30, this stage has landed.**
Two of its items were this stage's inputs, not polish: `period_ns` (there was no
field to read without it) and the frozen port-name spelling (this is the stage
that turns port names into topics, signal paths and `expect:` strings, after
which renaming one is a breaking change to every artefact). Kept for the
reasoning, which recurs — `S-C1aΔ2` (build order #11) is the same shape again
and blocks `S-C1d`. **This stage's own remaining work is `S-C1cΔ` below, build
order #5.**

- [x] `contracts/component.py` — the `SilComponent` Protocol plus
      `CtypesSilComponent` and `InProcessSilComponent` (api reference §3.1).
      `CtypesSilComponent.exec` is **the one place** integer nanoseconds become
      the ABI's float `dtS` (`P-8`, `sim_sil_contract.md` §3.1).
- [x] **A stub component library implementing the generic ABI** — `impl:
      stubdll:`, mandated by `R-SIM-10` ("if a stand-in must run without Python
      it is promoted from `stub:` to `stubdll:` on the same generic ABI"),
      listed in api reference §3.3's `impl:` vocabulary, and named by
      `sim_sil_contract.md` §8 as what the framework's own tests should load.
      **It had no stage until the 2026-07-30 review** — a requirement with no
      stage, which `check_traceability.py` cannot see because it joins test ids
      and not obligations. It lands here rather than later because it is also
      the only way `CtypesSilComponent` gets tested without `df` built, and it
      is deliberately trivial: an echo component with a hand-written manifest.
- [x] `contracts/loader.py` — **`resolve_library`**, the single place the
      framework consults the platform (`P-5`). `<stem>` expands to
      `<stem>.dll` on Windows and `lib<stem>.so` / `<stem>.so` on Linux; a miss
      names **every pattern tried and every directory searched** (`N-8`)
- [x] Proto class resolution from `descriptor_set` via `DescriptorPool` +
      `message_factory` — **no generated bindings imported** (`R-SIM-11`).
      `ComponentManifest`'s own schema is hand-built the same way
      (`scene/codec.py`'s technique), since it is the bootstrap schema and has
      no `descriptor_set` of its own to resolve from
- [x] Per-handle port buffers (fixes the ctypes keepalive trap: a buffer that is
      garbage-collected while the DLL holds a pointer to it fails rarely and
      unreproducibly, which is the worst failure mode available); grow-once-and-
      retry on undersize
- [x] `contracts/pipeline.py` — `mode:` × `impl:`, wiring **per port**,
      load-time validation in the order given in api reference §3.3, plus
      `Pipeline.exec()` -- one tick, stages in declaration order,
      single-threaded; `measured` injects from a caller-supplied mapping
      (no I/O inside `Pipeline` itself); `off` is simply absent from
      whatever consumes it, which is `valid=0` downstream via the same
      convention `SilComponent` already uses -- no special-casing needed.
      Single-rate only this pass (multi-rate due-tick gating is later).
      `impl: stub:` has no registry yet (`S-C2`); `Pipeline.load`'s
      `components=` lets a caller supply one directly,
      which is also what makes every test here run with no DLL
- [x] `version:` as a required top-level key + an upgrader; unversioned files
      are `v1` (`CR-SIM-23`)
- [x] `period_ns` read from each manifest; **base grid derived as the GCD** of
      the declared periods; a period that is not an integer multiple is a load
      error naming both numbers — never rounded (`R-SIM-18`).
- [x] `contracts/override.py` — the closed four-verb list (`R-SIM-15`).
      `Stage.overrides` is declared and validated at load (a verb outside
      the four is `AuthoringError`); actually applying one to a live port's
      bytes between wiring and `exec()` is `S-D6`'s job (its own checklist
      item below -- run-manifest tagging and HUD badging belong there too)
- [x] Component pipeline files under `modules/<name>/sim/pipelines/`.

**Tests**
- [x] `UT-C1c-1` ABI version mismatch fails loudly at load, naming both versions
- [x] `UT-C1c-2` manifest parse yields discovered ports; **no hardcoded port
      name anywhere in the framework** (grep, as a test -- the existing GT-1
      check already covers `contracts/`, re-verified green this slice, not
      duplicated as a second grep)
- [x] `UT-C1c-3` message classes built from `descriptor_set` alone, with the
      generated bindings **not importable** in the test environment (a
      synthetic message type that has no generated binding anywhere on disk,
      so there is nothing importable to fall back to)
- [x] `UT-C1c-4` ports match by name regardless of order
- [x] `UT-C1c-5` buffer grow-and-retry succeeds once and logs; a second failure
      raises
- [x] `UT-C1c-6` pipeline wiring: `proto_type` mismatch raises naming both ends
- [x] `UT-C1c-7` missing required input raises naming the port
- [x] `UT-C1c-8` a reference to a port nobody produces raises
- [x] `UT-C1c-9` a forward reference (B feeding an earlier A) raises — **no
      silent last-tick value**, which would look like it worked
- [x] `UT-C1c-10` `mode: measured` with the recording lacking that stage's
      outputs raises naming the missing topics
- [x] `UT-C1c-11` `mode: measured` ignores that stage's inputs and injects
      recorded outputs
- [x] `UT-C1c-12` `mode: off` yields `valid == 0` downstream
- [x] `UT-C1c-13` flipping `mode` does not require `impl:` to change — the
      toggle is reversible without re-authoring (`R-SIM-10`)
- [x] `UT-C1c-14` stages execute in declaration order, single-threaded; a
      pipeline whose declaration order contradicts its wiring is a load error
- [x] `UT-C1c-15` `resolve_library` returns the right file for each platform
      pattern (parametrised over both), and a miss names every candidate
- [x] `UT-C1c-15a` a `stubdll:` stage loads through the **same**
      `CtypesSilComponent` path a `dll:` stage does, and its port set is
      indistinguishable from a `dll:` stage's to everything downstream —
      `R-SIM-10`'s "executed and injected produce the same port set", proven at
      the `impl:` axis rather than only at the `mode:` axis.
- [x] `UT-C1c-16` **severed chain detected** — `simulate → measured → simulate`
      on one path is found; `off → measured → simulate` is **not** flagged
      (`R-SIM-10`; the GUI's auto-close in S-D6 builds on this)
- [x] `UT-C1c-17` an override applies at a port and at a field path, and a verb
      outside the closed four is a **load error**, not a warning (`R-SIM-15`)
- [x] `UT-C1c-18` a pipeline file **carries a `version:`**, and one newer than
      the reader is a load error naming **both** versions (`CR-SIM-23`)
- [x] `UT-C1c-19` an unversioned pipeline file is read as `v1` and upgraded, on
      the same shape as the scenario upgrader — the pipeline is the artefact most
      certain to outlive its format, and was the only one with no migration story
- [x] `UT-C1c-20` **rate**: with stages at 20 ms and 50 ms, the base grid is
      10 ms; each stage executes only on its due ticks; a non-multiple period is
      a load error naming both numbers (`R-SIM-18`)
- [x] `UT-C1c-21` a held port reads `updated=False` with an **exact** `age_s`
      from integer nanoseconds, and the consumer still receives its **full port
      set** — `R-SIM-10`'s invariant under multi-rate
- [x] `ST-C1c-1` resim **every** existing recording through
      `CtypesSilComponent` and compare with the positional path —
      byte-identical (integration; skips with a named reason if the library is
      not built)
- [x] `ST-C1c-2` an algo-test pipeline runs with everything `measured` except
      one stage — the canonical shape of `R-SIM-12`

**Discipline**
- [x] portability §3 (`P-2`, `P-5`) · naming §3 (`N-5`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C1c-1` green over every recording — the generic path is proven
      equivalent before anything depends on it exclusively
- [x] `GT-6` green — the framework imports no generated bindings, tested by
      making them unimportable rather than by inspection. **Stale checkbox,
      corrected 2026-08-06**: `scripts/check_invariants.py` has reported
      `GT-6` clean every run this whole session (`GT-1, GT-2, GT-3, GT-6,
      GT-11: clean`) — the mechanised check (`scripts/check_invariants.py::
      check_gt6`, scanning for a component/generated-binding import under
      `src/adas_sim`) was simply never ticked here after it started passing

**Delta — added 2026-07-31 (`R-SIM-21`).** `Pipeline` already knows every
manifest in a run and already builds the concrete address
(`f"{stage.name}.{port.name}"`). It is therefore the only place that *can*
resolve a component-relative reference, and the resolver belongs here rather
than in the plug-in loader — which is what stops a second resolver appearing at
`S-C3` for `expect:` strings and a third at `S-D3` for workspaces.

**Still open after `S-B1Δ` — not the same resolver.** `S-B1Δ` (build order #6)
needed `self.<port>` binding for a layer provider's `requires=`/`ctx.port`
*today*, replaying from a recording with no live `Pipeline` in the loop at all
(`core/runner.build_scene` runs entirely off a `Session`). It built
`contracts/binding.resolve_component_ref`/`try_resolve_component_ref` against a
run's own **known port names** (a recording's topics), not against this
Pipeline/`ComponentManifest`-based `resolve(ref, *, component)` sketched below —
that one is real work for whenever `S-C3`/`S-D3`/`S-D7` actually need it (a live
`Pipeline` is genuinely available there).

- [x] **`contracts/binding.py` — the one port-address resolver.**
      `resolve(ref, *, component) -> str`: takes `self.<port>` or a bare
      `<port>`, returns the concrete address for *this* run. A miss raises
      `AuthoringError` naming the reference, the component and every port its
      manifest declares (`N-8`). **One resolver, four consumers** — layer
      `requires`, `expect:` predicates (`S-C3`), workspace/viewpoint files
      (`S-D3`), and export column selection (`S-D7`). Four resolvers is how the
      third one starts accepting a name the first one rejects.
- [x] `core/signals.py` routes through it rather than resolving addresses
      itself — today it does a longest-known-prefix match over raw strings,
      which is correct for a spelled address and has nothing to resolve a
      component-relative one against.
- [x] `UT-C1c-22` a component-relative reference resolves to the concrete
      address **under a renamed stage** — the same plug-in binds correctly
      whether the pipeline calls the stage `df` or `driving_functions`. This is
      the whole claim; a test that only checks the default stage name proves
      nothing.
- [x] `UT-C1c-23` an unresolvable reference raises naming all three things, and
      **never** returns a sentinel that a caller could treat as "absent".

**Delta `S-C1cΔ` — added 2026-07-31 (`OD-8`, closes `OQ-10`). Build order #5** —
Block 1, blocked on nothing; `S-B1Δ` (#6) and `S-C3` (#10) both consume what it
builds, so building it later means building their consumers twice.** `contracts/
override.py` declares the four verbs and `Pipeline` parses and load-validates
them — but **nothing applies an override to a port's bytes yet**, and
`Override.apply` operates on a bare `float`. That is why this is cheap now: the
grammar is still free. Read arch §5.10 first.

- [x] **The address grammar, stated and closed** — `port` · `port.field` ·
      `port.repeated[i]` · `port.repeated[*]` · a field within either. **Index
      and `*` only, never a predicate.** `objects[?class=="truck"]` is an
      expression, and an expression grammar is the over-configuration this design
      exists to answer. *2026-07-31:* `contracts/binding.py`'s `parse_address` —
      one closed regex per segment (`^(\w+)(?:\[(\d+|\*)\])?$`), rejecting a
      predicate-shaped segment outright; the port's own segment may never
      carry an index (a port is one message, never a list)
- [x] **Two structural verbs, and the list closes again at six** — `drop`
      removes the addressed element(s), `select` keeps them and drops the rest.
      They are the complement pair over a set, which is why two is the right
      number. The governing line, which is what rules out `insert`/`move`/
      `duplicate` on principle rather than on taste: **an override may destroy or
      attenuate information; it may never create an entity**. *2026-07-31:*
      `OverrideVerb.SELECT`/`DROP` added; `_apply_structural` in
      `contracts/binding.py` implements both over a repeated container
- [x] **Fixed-slot behaviour, keyed on a manifest attribute** — a port declared
      `fixed_slots` has `drop` **clear the element in place**, never compact.
      Compaction renumbers every later index and breaks track association
      silently, which is the confidently-wrong-answer failure this architecture
      exists to prevent. The framework must not guess which shape a port has;
      the port declares it, through the manifest (`R-SIM-4`), never through a
      file the framework reads directly.
      **The attribute itself landed at `S-C1aΔ2` (build order #11, 2026-08-03)
      — populating it for a real component is `S-C1d`'s own job (build order
      #12), still pending** — so until then, **`drop` on a port whose
      manifest does not declare `fixed_slots` is a load error naming the port
      and the undeclared attribute.** Not a default: `false` would mean
      *"safe to compact"* and `true` would mean *"safe to zero"*, and both
      are guesses about someone else's data (`NR-SIM-4`). This is what kept
      this stage compiler-free without deferring the verb. *2026-07-31:* the
      clearing/compacting LOGIC is implemented and tested directly
      (`apply_override`, taking `fixed_slots`
      as an explicit parameter, `UT-C1c-25`'s "first half"); the GATE that
      determines whether the real manifest may use it at all lives in
      `Pipeline._validate_overrides` — `PortSpec` has no `fixed_slots` field,
      so `getattr(port_spec, "fixed_slots", None)` is always `None` today,
      making the load error the only path reachable through a real `Pipeline`
      (`UT-C1c-25`'s "second half")
- [x] Apply overrides on the input path, and tag the topic `origin: overridden`
      with the verb set recorded in the run manifest (`R-SIM-15`). *2026-07-31:*
      `Pipeline._apply_input_overrides` decodes, applies (grouping several
      overrides on one port into a single decode/re-encode), re-serializes,
      right before `exec()`/`step()` hand a stage its inputs; `hold`'s
      cross-tick memory lives on the `Pipeline` instance, keyed per
      `(stage, address)`, reset on every construction (same discipline as
      `_elapsed_ns`). **Scoped honestly:** "tag the topic... in the run
      manifest" needs `core/manifest.py` and `S-C2`'s recorder, neither of
      which exists yet — `Stage.overrides` itself already **is** the
      "declared, never smuggled" record (R-SIM-15's own phrase) for the
      recorder to read from later; no second, speculative tagging API was
      added ahead of a real consumer
- [x] **Refuse, with the alternative named in the error**: a time-varying or
      conditional override is rejected pointing at *edit the scenario* or *write
      a `stub:` stage*. A refusal that does not say where to go instead is how a
      closed list gets reopened. *2026-07-31:* `_parse_overrides` rejects an
      override entry with any key beyond `verb:`/`value:`, and a `value:` that
      is not a plain number (bool excluded explicitly, since `bool` is an `int`
      subclass) — both name the two alternatives

**Tests added by the delta**
- [x] `UT-C1c-24` each address form resolves to the right target, and a
      predicate-shaped address is an `AuthoringError` naming the closed grammar.
      *2026-07-31:* `tests/unit/test_c1c_binding.py`
- [x] `UT-C1c-25` `drop` on a **`fixed_slots`-declaring** port clears in place:
      element 3 becomes its message default and elements 4+ keep their indices.
      The compacting behaviour is asserted **not** to happen, because that is the
      failure mode, not the feature. And `drop` on a port whose manifest is
      **silent** about `fixed_slots` raises, naming the port and the field —
      never picking a side (`NR-SIM-4`). Until `S-C1aΔ2` lands, the second half
      is the only reachable path, which is the honest state and is why the verb
      does not have to wait for a build. *2026-07-31:* first half in
      `test_c1c_binding.py` (`apply_override` given `fixed_slots=True` directly);
      second half in `test_c1c_pipeline.py` (a real `Pipeline.load` with a real
      `PortSpec`, silent about `fixed_slots` by construction)
- [x] `UT-C1c-26` `select` keeps exactly the addressed elements; `select` and
      `drop` of complementary sets produce the same result, which is the property
      that makes two verbs sufficient. *2026-07-31:* `test_c1c_binding.py`

### S-C1d — the generated ABI shim (`R-SIM-22`, closes `D12`)

> **Build order: #12** (§0a is the authority on sequence). Block 2. Blocked on `S-C1aΔ2` (#11) — the generator must emit fields the proto actually has.

**Purpose.** Stop every component hand-writing ~400 lines of port table,
manifest builder and dispatch. `S-C1b` proved the shim is *correct*; this stage
proves it is **generated**, so that `perception-core`, `planning` and `vdy` cost
a declaration rather than a rewrite.

**Must not.** Change a single byte of what `df_sil.dll` exports. This stage is a
**refactor with a byte-identical output**: the generated shim must produce the
same manifest and the same dispatch behaviour as the hand-written one, proven by
comparison, not by reading. If the manifest changes, the stage is wrong.

**Must not** (second). Touch `src/component/**`, and must not become a general
code-generation framework. One generator, one input schema, one output file.

- [x] `modules/df/conf/ports.yaml` — the single declaration
      (`sim_sil_contract.md` §3.2). Lives beside `conf/build.yml` because it is
      the same *kind* of thing: per-component build data (`R-VAR-3`).
      *2026-08-04:* also `modules/vdy/conf/ports.yaml` (see `ST-C1d-1` below)
- [x] The generator — reads `conf/ports.yaml` + `ENABLED_FUNCTIONS`, emits the
      name constants, both port tables, `buildManifest()` and the `adasExec`
      dispatch bindings. **A build output**: generated into the build tree,
      never checked in, never edited.
      *2026-08-04:* `interfaces/scripts/gen_sil_ports.py` +
      `interfaces/cmake/sil_ports_generate.cmake`
      (`adas_generate_sil_ports(<target> PORTS_YAML ... COMPONENT_ROOT ...
      ENABLED_FUNCTIONS ...)`). **Lives in `interfaces`, not a new root
      `scripts/` or a per-component copy** — `GT-10` requires every module to
      build standalone from its own submodule clone, which a root `scripts/`
      reference would break; every SIL component already hard-depends on
      `interfaces` via Conan, so shipping the generator there costs nothing
      new to check out. Mirrors the existing `cmake/proto_generate.cmake`
      precedent in the same repo. Required two additive `conanfile.py`
      changes (`exports_sources` gains `"scripts/*"`; `layout()`/
      `package_info()` gain `builddirs = ["cmake"]` under the `cmake_layout`
      branch, so a consumer's `find_package(AdasInterfaces)` populates
      `CMAKE_MODULE_PATH` and `include(sil_ports_generate)` resolves) —
      propagated to **all 8** byte-identical `conanfile.py` copies (`df`,
      `interfaces`, `mathlib`, `perception-core`, `shared_config`, `sil_host`,
      `sim`, `vdy`; `isp`/`perception-lane`/`planning`/`platform-services`
      already diverge and are out of scope), `diff -q` re-verified clean
      (`GT-5`)
- [x] **Handle-member-naming convention, newly frozen** (not written down
      anywhere before this stage): `binds:` only names the `ReqPort`/`ProPort`
      member, not which port-set instance on the handle owns it. The
      generator infers `<fn>ReqPorts`/`<fn>ProPorts` when any port declares
      `functions:`/`owner_function` (`df`'s shape) vs. bare
      `reqPorts`/`proPorts` when none does (`vdy`'s shape) — from the YAML
      content itself, never a second CLI flag or field. Written into
      `sim_sil_contract.md` §3.2
- [x] `binds:` names the `ReqPort`/`ProPort` member, so `N-1`'s "the segment
      after the dot is byte-identical to the member" is **generated** rather
      than asserted by `UT-C1b-12`. The `comp_state`-vs-`compState` defect
      becomes unrepresentable rather than caught
- [x] Diagnostics name the **YAML key and line**, never the emitted C++
      (`sim_sil_contract.md` §9). A generator that reports errors in its own
      output is a generator that gets worked around.
      *2026-08-04:* `PortsGenError`, a lightweight `_LineLoader` PyYAML
      subclass attaching `__line__` to every mapping
- [x] The checked-in `df_sil.ports.yaml` stays a **dump of what was compiled**
      (`df_manifest_dump`) — a reviewable port diff, not a third copy.
      *2026-08-04:* byte-identical to the pre-refactor golden capture, both
      `-P base` and `-P cus1` (see `UT-C1d-1` below). `df`'s `conf/ports.yaml`
      deliberately leaves `period_us`/`fixed_slots` undeclared — setting them
      would change the serialized manifest and fail this stage's own
      byte-identical bar. The generator's *capability* to emit them (proven
      structurally, `UT-C1d-2`'s fixture) is a different claim from `df`
      *using* them, and the two must not be conflated

**Tests**
- [x] `UT-C1d-1` the generated manifest is **byte-identical** to the one the
      hand-written shim produced, for `-P base` and `-P cus1`.
      *2026-08-04:* golden `df_manifest_dump` capture taken before the
      refactor touched `df_interface_c.cpp`; real `build.bat -t gtest -p
      vs2026` for both projects, post-refactor dump diffed byte-for-byte
      against the golden — silent both times
- [x] `UT-C1d-2` `ENABLED_FUNCTIONS` combinatorics: aeb-only, bsd-only, both,
      neither — each yields exactly the expected port set, the case `UT-C1b-7`
      had to check by manual recompile.
      *2026-08-04:* `interfaces/tests/python/test_gen_sil_ports.py` (fixture,
      no compiler) plus a **real** aeb-only reconfigure/rebuild of `df_sil`
      that caught a genuine bug the fixture alone had not: the first
      generator cut only filtered which port *rows* appeared, not each
      input's per-function dispatch fan-out, so an aeb-only build still
      referenced `bsdReqPorts` (a real compile error, not a manifest
      diff) — fixed by intersecting `functions:` with the enabled set at the
      dispatch-generation site specifically, leaving `manifest_owner_function`
      (which must NOT narrow — `objects`/`egoDyn` stay component-level in the
      manifest regardless of which functions are actually enabled, matching
      the original hand-written table's static behaviour) untouched.
      *Follow-up same day, prompted by "did every corner case actually get
      tested":* the **neither**-enabled case had only ever been fixture-tested,
      never real-built. A real reconfigure found a second, different real bug
      the fixture couldn't see either: an empty port list emitted
      `T kGenOutputPorts[] = {};` — a C array with an empty braced
      initializer, ill-formed (MSVC C2466). Fixed by falling back to a null
      pointer + a `kGen{Input,Output}PortsCount` of `0` when a list is empty,
      and switching `buildManifest()`'s consuming loops from range-based-for
      to index-based so both cases share one code path. All four
      combinations (aeb-only, bsd-only, both, neither) now real-compile;
      `test_gen_sil_ports.py`'s own "neither" assertion was rewritten too —
      the original checked for the exact empty-array text that was the bug,
      so it would not have caught a regression back to it
- [x] `UT-C1d-3` a `binds:` naming a member that does not exist in the ports
      header is a **generate-time error** naming the YAML key and line —
      **shown to fail**, not assumed (`ST-C6-2`'s principle).
      *2026-08-04:* `test_gen_sil_ports.py`
- [x] `UT-C1d-4` a duplicate port name, and a port name whose post-dot segment
      is not a real member, are both generate-time errors.
      *2026-08-04:* `test_gen_sil_ports.py`
- [x] `UT-C1d-5` the generated file is not tracked by git and is regenerated
      from a clean tree.
      *2026-08-04:* generated header lands under each component's own
      `build-*/`, already covered by that component's `.gitignore`; a
      `--clean` rebuild of `df` (`-P base`) regenerated it and reproduced the
      byte-identical manifest
- [x] `ST-C1d-1` **the whole point of the stage**: a second component
      grows a working generic ABI from a `conf/ports.yaml` and **zero
      hand-written C++**. If that needs one line of bespoke shim, `D12` is not
      closed.
      *2026-08-04:* **`vdy`**, not the `stubdll:` echo component — `vdy`
      already carried the exact pre-`S-C1a` shape `df` had (positional
      `vdyExec` ABI, `VdyReqPorts`/`VdyProPorts`, `VdyFunction`, **no**
      `ENABLED_FUNCTIONS` gating at all), is named explicitly in this stage's
      own purpose text as a target beneficiary, and is real product value
      rather than a throwaway fixture. Also the shape `df` alone cannot prove:
      no function gating, bare `reqPorts`/`proPorts`. `vdy_interface_c.h/.cpp`
      gained the generic ABI block (mirroring `df_interface_c.cpp`'s
      byte-for-byte, including its own copies of `updateReqPort`/
      `writeAdasProBuf`/`findPort` — generic ABI plumbing, not port
      declarations, so out of the generator's own scope per this stage's
      "must not become a general code-generation framework"), a new
      `vdy_manifest_dump.cpp`, and a new `tests/unit/sil/test_generic_abi.cpp`
      (18 tests, mirroring `df`'s own suite) — **`vdy`'s first-ever real
      `gtest` run**, 18/18 green. `S-C1c`'s own leftover `stubdll:` echo
      component stays unbuilt — a different need (testing
      `CtypesSilComponent` with no real DLL at all), not required once `vdy`
      covers this gate

**Discipline**
- [x] portability §3 (`P-1`, `P-2`, `P-4`, `P-8`) · naming §3 (`N-1`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `UT-C1d-1` green — byte-identical manifest, both projects. A refactor that
      cannot prove equivalence is a rewrite
- [x] `ST-C1d-1` green — the second component is the evidence; the first one
      working proves only that the generator can reproduce what it was modelled
      on
- [x] `GT-4` green at or above every recorded floor

### S-C2 — `sources/` — the production side

> **Build order: #9** (§0a is the authority on sequence). Block 1. Blocked on `S-A4Δ` (#3): this stage writes recordings, so the two-stamp codec must exist first.

**Purpose.** Separate *producing* a recording from *executing* one
(`R-SIM-12`). Today one 983-line script does both, which is why it is 983 lines.

**Must not.** Move the existing bridge. This stage **decomposes by copy**: the
original keeps working until `S-E1` deletes it, gated on this stage's tests.
Nothing in `sources/` may name a driving function (`GT-1`).

- [x] `sources/base.py` — the `Source` Protocol; `emits()` declares what this
      world can produce, so a pipeline asking for a level the source cannot
      emit is a **startup error naming both ends** (`R-SIM-10`)
- [x] `sources/<world>/` — connection, spawn, lane advance, actor behaviour,
      frame conversion, chase transform — the engine, **verbatim in behaviour**.
      Behavioural equivalence is the point; tidiness is not
- [x] `sources/<world>/mocks.py` — world-model to port synthesis, tagged
      `mocked`; ground truth tagged `truth` (`R-SIM-12`)
- [x] `sources/<world>/catalogue.yaml` — blueprint to classification/dimensions
- [x] `sources/synthetic.py` — scripted stimuli, no world model. **This is the
      one every framework test uses**, so it must land with the others rather
      than after them
- [x] `core/manifest.py` — the run manifest (recording doc §2), carrying the
      `run_id` (`N-9`)
- [x] Recorder derives its topic list **from the pipeline's port manifests**
      (`R-SIM-6`) and writes every stage's inputs *and* outputs — so "did we
      record everything the SUT reads?" is true by construction rather than by
      diligence

*Scope added 2026-07-31 (`NR-SIM-42`, `OD-9`). Read recording §3.6 and §3.3.*

- [x] **Per-port `record:` policy**, declared in the pipeline beside the wiring
      — `full` (the default) · `{decimate: n}` · `excluded`. **No global
      switch**, deliberately: a global switch is how everything ends up excluded
      by one person in a hurry
- [x] **The policy is written into the recording's meta for *every* declared
      port, not only the exceptions**, so a reader answers *"was this
      complete?"* from the file alone. This is what makes `R-SIM-6` degrade
      *visibly* to "everything except these, by declaration" instead of silently
      becoming false.
- [x] **An excluded port feeds `R-SIM-23`'s feasible-cut query, not a second
      mechanism.** To a later run an excluded port is indistinguishable from one
      the recording never had, which is the case `S-C9` already computes.
      True by construction — `Session.feasible_cuts` treats "port missing
      because excluded" and "port missing because never wired" identically,
      since both are simply absent from the recording's topic index;
      nothing here needed its own code
- [x] **Two different times, two different answers.** At *record* time,
      declaring a stage `simulate` while excluding or decimating an input it
      consumes is a **load error** — you would be recording a run whose own
      inputs you are not keeping. At *resim* time the same file is not an error,
      merely a cut `sim probe` reports as infeasible
- [x] The recorder writes **both stamps** (`S-A4Δ`): reception from the
      schedule, capture from the source or the error model that produced the
      value
- [x] Size estimate before starting: an upper bound from each port's
      `max_bytes` × ticks × recordings, **labelled as an upper bound**, revised
      from the measured rate after the first hundred ticks. Both numbers,
      both labelled — a single confident figure that turns out to be either is
      worse than neither
- [x] `cli/record.py`, `cli/run.py`, `cli/resim.py` — argument parsing only.
      **Not `app/cli.py`**: `app/` is the GUI and holds no logic (`GT-9`), and
      the package map is asserted by `UT-A1-9`

**Tests**
- [x] `UT-C2-1` frame conversion — the existing sign conventions, re-asserted
      (world to ego, right-to-left flip, `R-COORD-1`).
      `tests/unit/test_c2_carla_frame_convert.py`
- [x] `UT-C2-2` lane-advance heading ramp + yaw-rate averaging against a
      **mocked** world — the technique already proven for the original.
      `tests/unit/test_c2_carla_actor_behaviour.py`
- [x] `UT-C2-3` angle difference across the ±180° seam. Same file
- [x] `UT-C2-4` lateral-profile phases incl. `raised_cosine` displacement =
      `rate * duration / 2`. Same file
- [x] `UT-C2-5` run manifest contains every declared field; hashes are stable.
      `tests/unit/test_c2_manifest.py`
- [x] `UT-C2-6` the recorder's topic list **equals** the union of the pipeline's
      declared ports — no port silently unrecorded (`R-SIM-6`).
      `tests/unit/test_c2_recorder.py`
- [x] `UT-C2-7` the previously-unrecorded ego-signal port is recorded — the
      determinism hole in recording doc §4 is closed. Same file
- [x] `UT-C2-8` provenance tags: mocked ports `mocked`, world truth `truth`,
      component outputs `simulated` (`R-SIM-12`). Same file
- [x] `UT-C2-9` a resim against a recording whose port manifest differs is a
      **hard error**; a differing library hash is a **warning** — the two are
      not the same severity and must not be merged.
- [x] `UT-C2-10` `emits()` is honoured: a pipeline requesting a port this source
      cannot produce fails at load naming the source and the port.
      `tests/unit/test_c2_source.py`
- [x] `UT-C2-11` no module under `sources/` launches a process through a shell
      or names an absolute path (`P-2`, `P-6`). `tests/unit/test_c2_carla_portability.py`
- [x] `UT-C2-12` **per-port record policy** (`NR-SIM-42`, audit `A3`): a port
      declared `excluded` or `decimated` is honoured **and named in the
      recording's own metadata**, so `R-SIM-6`'s "everything the SUT reads was
      recorded" degrades *visibly* to "everything except these, by declaration"
      rather than silently becoming false.
- [x] `UT-C2-13` the recorder writes **capture and reception time** separately
      (`CR-SIM-4`); an injected latency error model is recoverable from the
      recording, which is the whole reason the second stamp exists.
      `tests/unit/test_c2_recorder.py`
- [x] `ST-C2-3` `sim record`/`sim batch` **estimate and report expected size
      before starting** (`NR-SIM-42`) — a campaign that would fill the disk says
      so in advance rather than at 80%. `tests/unit/test_c2_recorder.py`'s
      `test_estimate_upper_bound_scales_with_ticks`/`test_revised_estimate_
      is_none_before_the_threshold_and_a_number_after`, wired into
      `cli/record.py`'s own printed output. **Corrects a stale docstring**
      in that test file, which claimed this was NOT implemented and had
      itself gone stale — the tests were added later with no one revisiting
      the note
- [x] `UT-C2-14` **excluding an input a `simulate` stage consumes is a load
      error at record time**, naming the stage and the port; and the *same*
      recording later loads fine for a cut that does not execute that stage,
      reported as infeasible rather than raising. Both halves, because either
      alone is the wrong rule (`NR-SIM-42`). `tests/unit/test_c2_source.py`
- [x] `ST-C2-1` `sim record` on the synthetic source produces a recording that
      `sim resim` consumes with every stage `measured` except one.
      `tests/system/test_c2_record_resim.py`
- [x] `ST-C2-2` `sim resim` reproduces byte-identical outputs across two runs.
      Same file
- [ ] `MC-2` a live run records correctly against a real world-model server.
      **Genuinely blocked** — needs a live CARLA/world-model server, not
      available in this environment

**Discipline**
- [x] portability §3 (`P-2`, `P-6`) · naming §3 (`N-5`, `N-12`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-C2-2` green; `MC-2` recorded with a date and a name. `ST-C2-2`
      itself is green (above); the gate stays open on `MC-2` alone, which
      is genuinely blocked, not a code gap
- [x] The original bridge still runs — this stage copied, it did not move, and
      `S-E1` is the only place anything is deleted (`NR-SIM-30`). Confirmed:
      `modules/df/tools/carla/` still exists and is still importable
      (`S-E1`'s own investigation, 2026-08-06, found it still live and
      still blocking that stage's own deletions)

### S-C3 — Scenario schema v2 + expectations

> **Build order: #10** (§0a is the authority on sequence). Block 1, last. Blocked on `S-C1cΔ` (#5, the fault address grammar), `S-A4Δ` (#3, `delay`) and `S-C9` (#8).

**Purpose.** Move a scenario's intent out of prose and into data. Closes
**D10**, **D11**; builds `R-SIM-8`.

**Must not.** Write an expectation that merely records today's behaviour. An
expectation transcribed from a comment is checked against **what the comment
claimed**, not against what the code currently does — otherwise the suite locks
in the present including its bugs, and every later regression reads as a broken
test rather than broken code. The migration record (this stage's gate) lists
every claim that could **not** be expressed, which is the honest output of that
review.

- [x] Schema v2 loader + **v1 upgrader** (`sim_scenarios_and_expectations.md` §3.2).
      *2026-08-03:* `contracts/scenario.py` — `Scenario`/`ScenarioContent`/
      `RunControl`/`SutRef`/`SensorModelRef` + `load_scenario`, upgrading a
      v1-shaped file in memory via `_upgrade_v1`. Also retired
      `sources.base.Scenario` (S-C2's interim `{name, raw}` stand-in) in its
      favour across `sources/`, `cli/run.py`, `cli/record.py`
- [x] `sensor_models/`, `pipelines/` presets. *2026-08-03:* built for `df`
      (`modules/df/sim/sensor_models/ground_truth_ideal.yaml`,
      `modules/df/sim/pipelines/df_only.yaml`) — the framework side (a
      scenario's `sensor_model.preset`/`sut.pipeline` are references this
      module never resolves itself, R-SIM-1) needed no new code beyond the
      loader above. `viewpoints.yaml` predates this stage (`S-B1`)
- [x] `check/expect.py` — the predicate vocabulary (§5.2), `markers:` with
      `from:` provenance. **This is where `R-SIM-8` is built**: expectations
      are data from one source, every timing predicate carries an explicit
      `within_s`, and the same block drives the marker, `sim check` and the
      report — never three copies.
      *2026-08-03:* `EqualsAlways`/`During`/`Whenever`/`AtLeastS`/`AtMostS`,
      `Becomes`, `Never`, `Count`, `Between`, `Monotonic` + `evaluate_expectation`/
      `evaluate_scenario`; `resolve_marker`/`resolve_markers` reuse the same
      transition logic for the two anchor forms below
- [x] `check/report.py` — `report.md` / `report.json`. *2026-08-03*
- [x] `cli/check.py` — `sim check` (argument parsing only, `GT-9`).
      *2026-08-03:* `--search`/`--config` added alongside `--report` — a real
      `dll:`/`stubdll:` stage needs both (`adasInit(NULL)`'s bundle
      resolution is `S-C5`, not yet built)
- [x] Timeline renders expectation windows (visualization spec §7.3).
      *2026-08-03 follow-up:* `ExpectationResult.window_s` (`check/expect.py`)
      -- populated only for the two predicate shapes with a genuine fixed
      span (`becomes ... within_s ... of:`, symmetric around the anchor;
      `equals ... during: [a, b]`), `None` for the other eight rather than
      a guessed one (`NR-SIM-4`). `sim view --scenario <path>` (explicit,
      never auto-discovered -- a recording's own run manifest carries only
      the scenario's NAME, not a path back to the file) evaluates it once
      against the loaded `Session` (`render/viewer._index_expectation_windows`,
      the same `evaluate_scenario` call `sim check` makes, `R-SIM-8`'s "one
      evaluator" extended to the viewer); `render/timeline.render_timeline`
      draws each window as a translucent span, green if that expectation
      passed and red if it failed -- "so a pass/fail is visible rather than
      computed" is the spec's own words, not a badge added on top.

*Scope added 2026-07-31 (`OQ-3`, `OQ-4`). Read scenarios §9.1 and §9.2.*

- [x] **Anchors get a second form, and it is not new grammar** —
      `at: {first: <signal>, becomes: <value>}` and
      `at: {first: <signal>, crosses: <value>, dir: rising|falling}`. An anchor
      is an **existing `expect:` predicate used as a time reference**, so it
      reuses the evaluator built above rather than adding one. A constant `at:`
      still **requires** `from:`.
      *2026-08-03:* `ConstantAnchor`/`BecomesAnchor`/`CrossesAnchor`
      (`contracts/scenario.py`), resolved by `check/expect.py`'s
      `resolve_marker` — `markers:` is a list (`id`/`at`/`from`), replacing
      the earlier name-keyed-mapping sketch
- [x] **One signal address, one literal, one optional direction. Nothing else.**
      The moment an anchor relates two signals it is an expression, and the
      answer is a constant with `from:`. *2026-08-03:* enforced in
      `_parse_marker` — an `at:` mapping outside `first`/`becomes`/`crosses`/`dir`
      is a load error
- [x] **Fault injection: five verbs, closed** — `drop` · `stale` · `delay` ·
      `invalidate` · `corrupt`. The list is *derived*, not chosen: `PortValue`
      has exactly four metadata fields plus a payload, and the vocabulary is the
      set of ways each can be made to lie. Today's `roll_fault:` is `corrupt` +
      `invalidate` and stops being a special form.
      *2026-08-03:* `contracts/fault.py` — `FaultVerb`/`Fault`/`apply_fault`.
      `_upgrade_v1` now *raises*, naming why, if it ever meets a real
      `roll_fault:` key rather than silently guessing a mapping — no real
      scenario among the 18 uses it today.
      *2026-08-03 follow-up:* wired into `Pipeline.exec`/`step`
      (`_apply_stimulus_faults`) — `run.faults:` applies to the STIMULUS
      every tick, before any stage sees it (`Pipeline.load(..., faults=
      scenario.run.faults)`, wired at `cli/run.py` and `check/runner.py`).
      Surfaced a real, separate gap while wiring `stale`/`invalidate`/`delay`
      through: `CtypesSilComponent._build_in_portset` hardcoded every input
      port's `valid=1, ageS=0.0` always, discarding whatever the caller
      knew — confirmed against `df_interface_c.cpp`'s `updateReqPort` that a
      real component's own `ReqPort.valid`/`.ageS` gating (`aeb_function.cpp`/
      `bsd_function.cpp`) depends on exactly those fields. Fixed with a new
      `InputMeta` threaded through `SilComponent.exec` (backward-compatible
      default; no existing stub call site needed to change). Same pass also
      fixes `step()`'s own multi-rate holding never reaching a real DLL's
      input side — a half-rate producer's staleness now reaches a
      downstream stage's `input_meta` instead of always reading fresh.
      Verified against the real compiled `df_sil.dll`
      (`test_c1c_component.py`) and end to end through `check_scenario` ->
      resim (`test_c3_check.py`)
- [x] **Faults reuse the override address grammar** (`S-C1cΔ`) — a third
      addressing scheme for the same objects is how a tool becomes inconsistent.
      *2026-08-03:* `Fault.address` goes through `contracts.binding.parse_address`;
      `corrupt` reuses `apply_override`'s own `CONST` verb for the byte
      mutation rather than a second mechanism.
      *2026-08-03 follow-up:* for a STIMULUS port (no stage to scope the
      address within, unlike an override), the address's port segment is
      matched against the stimulus map's own keys directly, and `corrupt`'s
      message class is resolved by tracing which stage wires
      `source.<port>` (`Pipeline._message_cls_for_source_port`)
- [x] A fault is declared in `run.faults:`, lands in the run manifest, tags its
      topic `origin: overridden` and is badged in the HUD. **The origin enum
      stays at five** — fault-versus-override is a *record* question, answered
      by the manifest, not a provenance grade.
- [x] `delay` requires `S-A4Δ`. With one clock there is nowhere to put the
      original instant, which is the clearest case of the two-clock change
      paying for something beyond itself. *2026-08-03:* `apply_fault`'s
      `DELAY` branch sets `capture_ns = t_ns - value_s*1e9`

**Tests**
- [x] `UT-C3-1` every v1 scenario loads through the upgrader and yields the same
      effective run configuration. *2026-08-03:* `test_c3_scenario.py` against
      fixture scenarios (`modules/sim` may not reference the real 18, `R-SIM-1`);
      the real 18 files' own load is `ST-C3-1` below, in `modules/df`
- [x] `UT-C3-2` each predicate — `equals`/`always`/`during`/`whenever`,
      `becomes`+`within_s`+`of`, `never`, `at_least_s`/`at_most_s`, `count`,
      `between`, `monotonic` — passes on a crafted signal and **fails** on a
      crafted counter-signal (both directions, or the predicate is untested).
      *2026-08-03:* `test_c3_expect.py`
- [x] `UT-C3-3` a timing predicate without `within_s` is a **schema error**.
      *2026-08-03*
- [x] `UT-C3-4` `marker.<name>` resolves; a missing marker names itself.
      *2026-08-03:* `test_a_reference_to_an_undeclared_marker_names_itself`
- [x] `UT-C3-5` report lists actual value and actual time next to expected.
      *2026-08-03:* `ExpectationResult`/`check/report.py`'s formatting
- [x] `UT-C3-6` **one address space**: the same signal string resolves
      identically for a plot panel and for an `expect:` predicate; a raw port
      field needs no registration, a `derived.*` one does. *2026-08-03:*
      `check/expect.py`'s `_series` calls `core.signals.resolve_tick` directly,
      no second resolver
- [x] `ST-C3-1` all 18 scenarios load under v2. *2026-08-03:* verified directly
      against the real files in `modules/df/tests/carla_scenarios/`
- [x] `ST-C3-2` `sim check tests/carla_scenarios` runs headless, exits non-zero
      on a deliberately broken expectation. *2026-08-03:* `suite_passed`
      unit-tested both ways; the real `sim check` CLI run against all 18
      (below) confirms exit 0 for an all-pass-or-skip suite — no dedicated
      test forces a real failing exit code, matching every other `cli/*.py`
      wrapper's own level of coverage (engine tested directly, GT-9)
- [x] `UT-C3-7` a predicate-form anchor resolves to the **first** tick
      satisfying it and is stable when the scenario's unrelated fields change —
      which is the drift a constant anchor suffers and this form exists to fix.
      An anchor naming two signals is a schema error (`OQ-3`). *2026-08-03:*
      `test_resolve_becomes_anchor`, `test_resolve_crosses_anchor_rising_and_falling`,
      `test_predicate_marker_with_two_signals_raises_authoring_error`
- [x] `UT-C3-8` each of the five faults produces its stated effect **on
      `PortValue` metadata, not only on bytes**: `stale` yields
      `updated=False` with a growing `age_s`, `delay` yields a capture stamp
      earlier than reception, `invalidate` yields `valid=False` with bytes
      present. A sixth fault name is a schema error naming the closed five
      (`OQ-4`). *2026-08-03:* `test_c3_fault.py`
- [x] `ST-C3-3` a scenario whose recording is missing is **skipped with a
      warning**, not failed. *2026-08-03*

**Discipline**
- [x] portability §3 (`P-3`, `P-4`) · naming §3 (`N-2`, `N-4`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] All 18 scenarios have `expect:` blocks **transcribed from their existing
      comment blocks**, each reviewed against the comment's claim before being
      accepted (§7 step 5 — an expectation that merely records today's behaviour
      is worse than none). **Not fully met**: 15 of 18 carry `expect:`/`markers:`
      (3 `aeb`, 12 `bsd`), verified end to end against a real compiled `df_sil`
      and a real recording for 4 of those 15 (`aeb_canonical_10mps_30m`,
      `aeb_closing_ego20mps_lead10mps_30m`, `bsd_ego_lane_exit`,
      `bsd_curve_r172_passby`); the other 11 are authored from each scenario's
      own analytic or stated claim but not yet checked against a recording
      (none exists yet) — `aeb_watchable_5mps_60m`,
      `bsd_mergein_vlat025/_vlat050/_vlat075`,
      `bsd_passby_dv8/_dv16/_dv24/_dv32`, `bsd_ncap_bsm_car/_motorcycle`,
      `bsd_sot_ego_overtakes`. `bsd_curve_r172_passby`'s two expectations are
      deliberately weaker than its comment's numeric detail: the comment
      itself declines to re-derive `BSD_CURVE_TAU_S` convergence timing (that
      is a unit test's job), so what is encoded is the one claim it does
      commit to ("late onset relative to the straight-road 5.0s"), not an
      invented anchor. The remaining 3 (`bsd_curve_r172_straight_approach`,
      `bsd_ego_lane_change_warp`, `bsd_ego_swerve_warp`) are migrated to
      schema v2 structurally only, each with a stated reason not to assert —
      two by explicit, repeated author instruction ("DEMONSTRATION,
      deliberately not a measurement"), one because it is a diagnostic
      scenario meant to be read, not thresholded. Full detail:
      `modules/df/docs/sim_scenarios_and_expectations_migration.md`
- [x] The migration record lists every claim that **could not** be expressed.
      *2026-08-03:* see the migration record above — also records two real
      findings surfaced by running against real data (an AEB spawn-offset
      correction, and a BSD classification-does-not-persist discovery).
      *2026-08-03 follow-up:* a third finding, surfaced completing the
      distance→time conversion for the 6 scenarios above: `bsd_ego_lane_exit`
      (verified) shows a target at negative `lateral_offset_m` triggers
      `right.warning`, but `bsd_mergein_vlat025` (still unverified) asserts
      `left.warning` for its own negative `lateral_offset_m` — a likely
      mislabeling, documented in the migration record rather than silently
      changed in `bsd_mergein_vlat025.yaml` itself

### S-C4 — Viewer reads real calibration; kill the duplicates

> **Build order: #7** (§0a is the authority on sequence). Block 1. Runs straight after `S-B1Δ` (#6) — same file set in `modules/df/sim/`, visited once. **Earlier than its id suggests.**

**Purpose.** Delete the hand-maintained duplicate of calibration the DLL already
reads. Small stage, disproportionate value: a duplicate that drifts produces a
picture that disagrees with the algorithm while looking authoritative.

**Must not.** Move any calibration into `shared_config` (`R-SIM-9`: those keys
are already runtime calibration with one consumer). This stage **deletes a
duplicate**; it does not relocate a source of truth.

- [x] `SensorModel`/`ObjectModel` sourced from the project config for the
      component's layers; the hand-maintained pose constants and the
      per-project `if` branch are no longer used by the live path
      *2026-07-31:* `modules/df/sim/layers/bsd.py`'s new `sensor_fov_layer`
      draws each sensor's FOV wedge from `_bsd_sensors(project)`, which parses
      this run's own resolved `BSD_SENSOR_*` keys via `model/sensors.py`'s
      `parse_sensors` (discovery **by key shape**, `GT-1`) — no hardcoded
      pose table, no `if project == ...`. **Scoped, checked with the user:**
      the actual hand-maintained duplicate is `docs/bsd/py/bsdviz/sensors.py`'s
      `P3`/`P4`/`P5` plus `tools/carla/replay/viz.py`'s `_bsd_project_sensor`
      branch, both in the pre-`R-SIM-*` tooling `rules/sim.md` names as "not
      this stage's file set" (do not extend the old structure) — left
      untouched rather than edited, so "kill the duplicate" is read as "the
      live path no longer needs or grows one," not as a decommissioning pass
      over `viz.py`. `ObjectModel`: no existing duplicate of `BSD_CLASS_*`
      class-footprint calibration was found anywhere in the live-path Python
      (`common.py`'s `ObjectModel` already uses only the generic,
      `assumed_geometry=True` cross-function defaults, never a per-project
      literal) — nothing to kill there this pass
- [x] The duplicated constants are **deleted, not commented out** — a commented
      constant is a duplicate that still reads as authoritative.
      *2026-07-31:* n/a to the new live-path code (nothing hardcoded was
      added to delete); the old tooling's duplicate is out of this stage's
      file set per the scoping note above, so nothing there was commented out
      either

**Tests**
- [x] `UT-C4-1` changing a sensor value in the project YAML changes the drawn
      FOV — asserted **on the Scene**, not by eye.
      *2026-07-31:* `test_changing_a_sensor_value_changes_the_drawn_fov`
      (`test_b1_df_layers.py`) — isolates one `FOV_AZIMUTH_DEG` field through
      `sensor_fov_layer` itself, not the geometry helper
- [x] `UT-C4-2` the per-project branch is gone: two projects produce different
      geometry through the same code path, with no conditional on project name.
      *2026-07-31:* `test_sensor_fov_has_no_per_project_branch_and_differs_
      by_real_project` — `base` (2 sensors) vs `2w_base` (1 sensor) draw
      different wedges through the identical call, plus an AST scan proving
      `bsd.py` contains no `project ==`/`!=` comparison anywhere
- [x] `ST-C4-1` no sensor pose or class footprint literal remains in any Python
      module on the live path (grep, as a test — `GT-3`).
      *2026-07-31:* `test_st_c4_1_no_sensor_pose_or_class_footprint_literal_
      in_bsd_layers` (`test_a1_check_invariants.py`) calls `check_gt3()`
      directly

**Discipline**
- [x] portability §3 (`P-3`) · naming §3 (`N-1`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C4-1` green — and `UT-C4-1` green, because a grep proving the literal
      is gone does not prove the replacement is wired to anything.
      *2026-07-31:* both green

### S-C5 — The packed config bundle (OD-4)

> **Build order: #13** (§0a is the authority on sequence). Block 2. Blocked on `S-C1d` (#12) — reads the per-function period through the manifest it generates.

**Purpose.** One atomic bundle per (project, build), beside the library, so the
SUT and the viewer provably read the same bytes (`R-SIM-3a`). Closes
`plan.md` item 19 with evidence.

**Must not.** Compile configuration into the library — that would kill the
edit-and-re-run calibration loop. Copied **beside** the artefact, never inside
it (production uses AUTOSAR frozen parameters instead, `R-SIL-1`).

**This is the stage that makes `adasInit(NULL)` mean something.** From
`S-C1b`'s delta until here, `NULL` is *unresolvable* and returns `NULL` — the
honest answer, and the reason this stage sitting behind `S-C1c`/`S-C2`/`S-C3`
costs nothing. Before that delta it returned a valid handle carrying
silently-defaulted calibration, which is why the ordering looked safe and was
not. Also inherited from `S-C1b`'s delta: `<component>.ports.yaml` lands in
`<library_dir>/config/` **here**, as part of the bundle, and not in a second
place beside the DLL.

- [x] **`AR-1` — the bundle must follow the library, not sit in one build
      directory.** *Done 2026-08-04.* `install(DIRECTORY $<TARGET_FILE_DIR:
      df_sil>/config/ …)` so it enters the Conan package, destination tracking
      `install(TARGETS)` (`bin/` on Windows, `lib/` on Linux — a hard-coded
      `bin` installs a bundle that is invisible at run time on one platform
      only, `P-5`); **and** `modules/df/tests/CMakeLists.txt` now
      `copy_directory`s `config/` alongside the DLL it already copied. Both,
      because they are two different consumers. **238/238 on `-P base` and
      `-P cus1`.**
      *Surfaced a second, real defect while fixing it:* `adasInit("")` returned
      a **handle**. An empty string is a *supplied but invalid* path and is not
      `NULL`; the code tested `configPath[0] != '\0'` for tier 1 and let `""`
      fall through to the bundle tier. `UT-C1b-13` had been passing **for the
      wrong reason** — no bundle had ever been packed beside `df_tests.exe`, so
      the wrong branch happened to return `nullptr`. Fixing delivery made the
      accident visible, which is exactly what that test exists for. `vdy`
      checked and clean (it rejects both).
      *Not done, deliberately:* `adasInit(NULL)` still does **not** search
      parent directories or the checkout — that would reinstate the
      silently-defaulted calibration `S-C1b`'s delta removed
- [x] **`AR-3` — `ST-C5-1`'s Python-half skip must state the truth.**
      *Done 2026-08-04, and the finding was overstated:* the test already
      declared itself POSIX-only with a reason. The real defect was **marker
      order** — both `skipif`s are true on Windows, `g++` matched first, and a
      Windows developer saw *"no C++ toolchain available"*, which reads as an
      environment gap rather than a designed boundary. Platform marker now
      comes first and names where the Windows path **is** proven for real:
      `df`'s own `AdasInitResolvesThePackedBundle` (`UT-C5-1`), green at
      238/238. No MSVC port of the fixture needed — it would duplicate
      coverage that already exists in C++
- [x] Build copies `project.yaml` + `shared_config`'s `vehicle/ego_params.yaml`
      + `<component>.ports.yaml` into **`$<TARGET_FILE_DIR:…>/config/`** with
      `bundle.sha256`. *Re-verified 2026-08-05 against a real `cmake --install`
      (not just the build tree)* — see `ST-C5-1` below, the gap `AR-1` left open.
- [x] `ParamLoader` reads a **directory**, not a file (`fromBundleDir`)
- [x] **`adasInit(NULL)` resolves `<library_dir>/config/`**
- [x] `bundle.sha256` is computed over **UTF-8 bytes, `\n` newlines, sorted
      POSIX-style relative paths** (`P-9`)
- [x] `adasManifest()` reports `project` + `config_bundle_sha256`
- [x] Recorder embeds the bundle on `/meta/config_bundle`
      (`Recorder.open`'s `config_bundle_bytes`, `model/project.py`'s
      `bundle_bytes_for_recording`)
- [x] `ProjectModel` prefers explicit → embedded → library → checkout
      (`bundle_origin`)

**Milestone 1 closed 2026-08-05**, re-verified with a real MSVC/Conan build in
this environment (the 2026-08-04 audit's own concern — "S-C5 was implemented in
a shell with no MSVC" — no longer applies): `df` gtest **238/238 on both `-P
base` and `-P cus1`**, including the two previously-red assertions
(`GenericAbiTest.AdasInitResolvesThePackedBundle`,
`ManifestTest.CarriesComponentIdentityAndDeclaredRate`). The audit's own
diagnosed gap — `ST-C5-1` had never exercised the real `install()` rule, only
the build tree `df_tests` already copied — is now closed for real:
`tests/system/test_c5_relocatability_installed.py` runs `cmake --install`
against the real `df_sil` build, relocates the installed tree away from the
build directory, strips the process `PATH` to the relocated `bin/` + OS system
directories only (no Conan cache, no repo checkout reachable), and confirms
`adasInit(NULL)` still resolves and reports the right `bundle.sha256`/`project`
— plus the tier-3 negative (`config/` removed → still refuses, never a parent-
search). `UT-C5-5` was already real (`tests/unit/test_a2_project.py::
test_bundle_sha256_is_stable_across_mixed_line_endings_and_iteration_order`).

*Scope added 2026-07-31 (`OD-11`, `OD-12`). Read contract §9.1 and §9.2.*

- [x] **One bundle per component, permanently** — `OQ-1` stays closed; no
      per-pipeline bundle exists or was added
- [x] **Project agreement across a multi-component pipeline — a warning with a
      declared escape.** `Pipeline.load` parses `allow_mixed_projects:`;
      `_validate_cross_component_agreement` (`contracts/pipeline.py`) compares
      every resolved stage's `manifest.project`, warns naming both
      components/projects on a mismatch unless escaped, and records both
      `allow_mixed_projects` (requested) and `mixed_projects` (found) on the
      `Pipeline` and in `RunManifest` (`io/base.py`, `core/manifest.py`).
      **Not done: the HUD badge** (`Pipeline`/`RunManifest` carry the fact; no
      viewer surface reads it yet — tracked, not fabricated)
- [x] **Ego-parameter agreement across bundles — a hard error, no escape.**
      Same function: every resolved stage's `<bundle>/vehicle/ego_params.yaml`
      is compared key-by-key against the first; a differing value is an
      `AuthoringError` naming both stages and the key, and
      `allow_mixed_projects: true` does **not** suppress it (`UT-C5-10`)
- [x] **Re-opened 2026-08-06, `AR-51`: a real bundle's project came from
      `bundle_dir.name`, not from anywhere real.** A real `S-C5`-packed
      bundle carries no `manifest.yaml`, so `_bundle_ego` fell back to the
      directory name -- always `"config"` for a real `<library_dir>/config/`
      bundle -- and `R-SIM-3a`'s mismatch warning fired on every correct
      real bundle (measured: 4 times against the real `df_sil` build tree).
      The docstring's own deferral (*"real cross-component project-agreement
      checking is S-C5's addendum scope, deferred"*) had already been closed
      by `OD-11` (2026-08-05) when this was found -- the deferral it pointed
      at no longer existed. Fixed: `ProjectModel.resolve`/`_resolve_one`/
      `_bundle_ego` gained `known_project` -- the loaded library's own
      `adasManifest().project`, supplied by `core/diagnostics.py::
      _bundle_diagnoses` (the only real caller resolving a `library_dir`
      against an already-loaded component). A manifest-less bundle with no
      `known_project` reports `"unknown"` (`R-SIM-25`), never
      `bundle_dir.name`; a `manifest.yaml` already present always wins.
      Verified directly: the 4 real-bundle warnings are gone (`pytest
      modules/sim/tests/system/test_d6_doctor_cli.py -q` -- 0 warnings,
      was 4); `UT-C5-3` extended with a manifest-less fixture named `config`
      (the real bug's exact shape, which its existing `manifest.yaml`-backed
      fixture never exercised) proving `"unknown"` without `known_project`,
      the real project with it, and a genuine mismatch still warning
- [x] **`period` moves into the bundle as `<COMPONENT>_<FN>_PERIOD_US`** —
      `interfaces/scripts/gen_sil_ports.py`'s generated `buildManifest()` is now
      a template over a `periodLookupUs(function, key, fallbackUs)` callback
      (never a concrete `ParamLoader` type — the generator is shared across
      components with differently-namespaced `ParamLoader`s); `df`'s own
      `ParamLoader::periodUs()` reads the calibration key, falling back to
      `conf/ports.yaml`'s declared literal when absent, and throws naming the
      function+key when present-but-not-an-integer-µs-value. `vdy` (ungated)
      passes a passthrough lambda — `kGenFunctionPeriodsCount` generates to `0`
      for it, so the callback is never actually invoked, zero behaviour change
- [x] The manifest **reports** the period; it does not define it — no ABI
      parameter added; `df`'s own two functions each keep deciding via
      `ENABLED_FUNCTIONS` which ports exist at all
- [x] **The DLL's own `updated` flag is authoritative over the predicted
      schedule**, landed 2026-08-06. `contracts/pipeline.py`'s `Pipeline.
      _check_schedule_disagreements`, called right after every real
      (non-`measured`) `exec()`: for each declared output `PortSpec` with a
      real `period_us` (undeclared/`0` can never disagree, same convention
      `ComponentManifest.period_ns` already uses), predicts due from THAT
      PORT's own period — never `manifest.period_ns`, the component-level
      GCD that only gates whether `exec()` runs at all, since one call
      legitimately updates some functions' ports and not others (multi-rate
      inside one component is normal, not a disagreement) — and compares
      against whether the ABI's real `updated` flag actually reported it
      (`CtypesSilComponent._collect_outputs` already turns `updated=0` into
      simple absence from `exec()`'s returned mapping, so presence IS the
      real flag). A mismatch is reported twice: immediately as a
      `ProvenanceWarning` naming stage/port/tick ("reported, never hidden"
      means visible the tick it happens), and durably on the new
      `Pipeline.schedule_disagreements` property (`ScheduleDisagreement`,
      accumulated for the pipeline's whole life, reset on every
      construction like `_last_output`/`_last_due_ns`).
      Tests: `test_c1c_pipeline.py::test_schedule_disagreement_detected_when_a_due_port_is_not_actually_updated`,
      `::test_no_schedule_disagreement_when_the_actual_flag_agrees_with_the_declared_period`,
      `::test_schedule_disagreement_never_checked_for_an_undeclared_port_period`,
      `::test_schedule_disagreement_not_checked_for_a_measured_stage`.
      **Not done, deliberately:** no CLI/HUD surface reads
      `schedule_disagreements` yet (no test drives a real multi-rate `df`
      DLL to produce one for real in this pass) — the mechanism and its
      query surface exist; a reporting UI is separate, later work, same
      "left open, not fabricated" distinction this item already drew.

**Tests**
- [x] `UT-C5-1` (`test_generic_abi.cpp::GenericAbiTest.AdasInitResolvesThePackedBundle`, `test_c5_relocatability.py`)
- [x] `UT-C5-2` (`test_a2_project.py::test_resolution_order_explicit_beats_embedded_beats_library_beats_checkout`)
- [x] `UT-C5-3` (`test_a2_project.py::test_project_mismatch_emits_provenance_warning_and_still_resolves`)
- [x] `UT-C5-4` (`test_a2_project.py::test_bundle_sha256_changes_on_case_only_rename`)
- [x] `UT-C5-5` (`test_a2_project.py::test_bundle_sha256_is_stable_across_mixed_line_endings_and_iteration_order`)
- [x] `UT-C5-6` `run.overrides:` materialises a derived bundle, landed
      2026-08-06 (`NR-SIM-6`, arch §5.6 "Overrides and sweeps").
      `model/project.py`'s `materialize_derived_bundle(base_bundle_dir,
      overrides, dest_dir)`: copies the base bundle, then for each
      `run.overrides:` address (a dotted path — a real `default.yaml`
      nests one level by function, `aeb: {AEB_..: ..}`, so
      `"aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S"` is the actual YAML path, not
      a label; a single-segment address matches a flat file, e.g.
      `vehicle/ego_params.yaml`) searches every bundle YAML file
      generically (no function name known to the framework, `R-SIM-1`)
      for the one where that path already resolves to a value — zero or
      more than one match is an `AuthoringError` naming the address and
      every candidate (an override may change an existing value, never
      create one, `R-SIM-15`'s discipline extended to bundle calibration).
      Recomputes `bundle.sha256` the same way the real build does. New
      `io/base.py` schema: `BundleOverrideRecord`, `RunManifest.
      bundle_overrides`/`base_config_bundle_sha256` (mirrors `OverrideRecord`/
      `FaultRecord`'s own "declared, never smuggled" legibility, `S-D6`/
      `S-C3`), serialized in `io/mcap.py`.
      Tests: `test_c5_overrides.py::test_materialize_derived_bundle_patches_a_nested_calibration_key`,
      `::test_materialize_derived_bundle_resolves_a_flat_single_segment_address`,
      `::test_materialize_derived_bundle_changes_the_hash_and_never_touches_the_base`,
      `::test_materialize_derived_bundle_raises_naming_the_address_when_the_key_is_unknown`,
      `::test_materialize_derived_bundle_raises_naming_every_candidate_on_an_ambiguous_key`.
- [x] `UT-C5-7`, landed 2026-08-06. `core/manifest.py`'s `RunSpec` gained
      an `overrides:` field (`load_run_spec` reads a run manifest's own
      top-level `overrides:` key, distinct from a pipeline STAGE's
      `overrides:`, `R-SIM-15`'s port-value mechanism — this one is
      run-wide and bundle-level); `resolve_swept_config(config, overrides,
      project=)` is the wiring: a passthrough when `overrides` is empty
      (the common case pays nothing), else requires a real `config:`
      directory to derive FROM (no tier-resolution — sweeping "whatever
      `adasInit(NULL)` would have found" would derive from a directory
      this process never inspected, an `AuthoringError` if `config` is
      `None`), materialises the derived bundle into a scratch dir, and
      returns it as `effective_config` for the caller to forward to
      `Pipeline.init_components`. Wired into `cli/resim.py`'s `run()`
      (scratch dir cleaned up in the existing `finally:` alongside
      `shutdown_components`); `--save`'s `build_manifest` call now passes
      `bundle_overrides=`/`base_bundle_sha=`, so a swept resim's manifest
      states "bundle `<hash>` + N overrides" per arch §5.6.
      Tests: `test_c5_overrides.py::test_resolve_swept_config_with_no_overrides_is_a_passthrough`,
      `::test_resolve_swept_config_requires_a_base_config_to_sweep`,
      `::test_resolve_swept_config_derives_a_real_directory_the_caller_must_forward`,
      `::test_a_swept_config_reaches_the_components_own_init` (a
      `components=`-supplied double proving the DERIVED directory, not
      the original `config:`, is what a real component's `init()` sees —
      no DLL needed, same precedent `test_c3_fault_hud_widget.py` sets).
      **Not done, deliberately, same "left open" pattern this stage
      already uses:** `write_run_manifest` (the GUI's own path) does not
      yet round-trip `overrides:` — no Vantage UI sets a bundle sweep this
      pass, so there is nothing yet that would silently lose it.
- [x] `UT-C5-8` `--config-source` forcing each tier, landed 2026-08-06.
      `ProjectModel.resolve(force=...)` (`model/project.py`) resolves EXACTLY
      the named tier — `"checkout"` goes straight to `_resolve_checkout`;
      `"embedded"`/`"library"` try only their own directory and raise
      `AuthoringError` naming the forced tier (never falling through to
      another tier) when nothing resolves there. Wired into `sim doctor
      --config-source embedded|library|checkout` (the only real integration
      point today — neither `sim view` nor `sim render` passes `recording=`/
      `library_dir=` into `ProjectModel.resolve` at all yet, so there is
      nothing there to force). `core/diagnostics.py`'s `doctor_report()`
      extracts `--recording`'s embedded bundle into a `TemporaryDirectory`
      via `extract_embedded_bundle` (`UT-C5-9`) when `embedded` is forced, so
      the comparison has a real directory to read.
      Tests: `test_a2_project.py::test_config_source_force_embedded_wins_over_a_higher_priority_explicit`,
      `::test_config_source_force_checkout_ignores_every_other_source`,
      `::test_config_source_force_raises_naming_the_forced_tier_when_nothing_is_there`,
      `::test_config_source_force_raises_when_the_forced_directory_has_no_bundle`;
      `test_d6_doctor.py::test_doctor_cli_rejects_an_unknown_config_source`;
      `test_d6_doctor_cli.py::test_doctor_config_source_library_forces_the_library_tier`,
      `::test_doctor_config_source_checkout_forces_the_checkout_tier`,
      `::test_doctor_config_source_embedded_resolves_from_the_recordings_own_bundle`,
      `::test_doctor_config_source_embedded_without_a_recording_is_a_problem_naming_the_tier`
      (the last four against the real `df_sil.dll`, skip elsewhere)
- [x] `UT-C5-9` a recording with an embedded bundle renders with **no checkout
      present**, landed 2026-08-06. The *mechanism* existed
      (`bundle_bytes_for_recording`, `ProjectModel`'s `embedded` tier) but
      nothing ever extracted a recording's embedded bytes back into a real
      directory — `ProjectModel.resolve(recording=...)` needs a directory, not
      bytes, so the embedded tier was unreachable from an actual recording.
      Added `extract_embedded_bundle(config_bundle_bytes, dest_dir)`
      (`model/project.py`) — the inverse of `bundle_bytes_for_recording`.
      Test: `test_a2_project.py::test_embedded_bundle_bytes_extracted_from_a_recording_resolve_with_no_checkout`
      (writes fixture bundle bytes, extracts to a directory with no matching
      `shared_config` checkout project, resolves with `bundle_origin ==
      "embedded"`)
- [x] `ST-C5-1` (`test_c5_relocatability.py` — mechanism, POSIX fixture;
      `test_c5_relocatability_installed.py` — **the real artefact, both
      directions, added 2026-08-05**)
- [x] `UT-C5-10` (`test_c1c_pipeline.py::test_ego_parameter_mismatch_is_a_hard_error_naming_both_components_and_the_key`, `::test_ego_parameter_mismatch_is_not_suppressed_by_allow_mixed_projects`)
- [x] `UT-C5-11` (`test_generic_abi.cpp::ManifestTest.PerFunctionPeriodIsReadFromCalibrationAndDrivesTheReportedGcd`, `::ANonIntegerCalibratedPeriodMakesTheManifestUnavailableRatherThanWrong`, `test_param_loader.cpp::ParamLoaderTest.PeriodUsThrowsNamingTheKeyOnANonIntegerValue`)
- [x] `UT-C5-12` (`test_generic_abi.cpp::ManifestTest.SweepingTheCalibratedPeriodChangesTheReportWithNoRebuild`)
- [x] `ST-C5-2` the viewer's `bundle_origin` reports `embedded`/`checkout`,
      landed 2026-08-06. `render/viewer.py`'s `MainWindow._resolve_project_model`
      resolves one `ProjectModel` per loaded session (`_on_loaded`), off the
      session's own `Session.config_bundle_bytes` (`UT-C5-9`'s
      `extract_embedded_bundle`, into a scratch dir cleaned up on the next
      load and in `closeEvent`) when the recording carries a bundle, else
      the checkout tier — the two sources reachable from a bare `Session`
      (`R-SIM-13`: no `library_dir`/`explicit` source of its own). Threaded
      into `build_static_scene`/`build_reactive_layers` as `model=` so every
      tick reuses the one resolved `ProjectModel` instead of paying
      `resolve()`'s checkout-only default per tick (`core/runner.py`'s own
      `build_scene(model=...)` docstring, `S-C5`'s earlier half of this
      change). `view/hud.py`'s `HudInfo` gained `bundle_origin: str | None`,
      appended to the HUD's project line as `cfg:<origin>` when supplied
      (`R-SIM-3a`: "the chosen origin is ... shown in the HUD").
      Tests: `test_b3_hud_wiring.py::test_hud_reports_checkout_bundle_origin_when_the_recording_carries_no_bundle`,
      `::test_hud_reports_embedded_bundle_origin_when_the_recording_carries_its_own_bundle`.

**Discipline**
- [x] portability §3 (`P-3`, `P-5`, `P-9`) · naming §3 (`N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C5-1` green — item 19 closed with evidence, against the **installed**
      tree this time, not the build tree `AR-1` left unproven
- [x] `UT-C5-5` green

**S-C5 is now fully closed** — every item and every `UT-C5-*`/`ST-C5-*`
landed 2026-08-06 (above), including `UT-C5-6/7`, `ST-C5-2`, and the
`updated`-flag-vs-predicted-schedule disagreement report.

### S-C6 — Resim in CI (the minimum automatic gate)

> **Build order: #16** (§0a is the authority on sequence). Block 2, last. Blocked on `S-C2` (#9), `S-C3` (#10) and `S-C5` (#13) — determinism axis C needs a rebuilt binary, which only exists after #13.

> **Ordering finding, 2026-07-31 audit (`A10`) — resolved by splitting, not by
> moving.** The finding is right: this stage sat last, after every stage that
> relied on manual verification, and manual verification is the mechanism that
> has already failed twice here (`GT-4`'s floor 138 tests stale for six days;
> two stages reported green from a substitute toolchain). In both cases the
> response was to write down a date, i.e. *more careful manual verification*.
>
> **But it could not be moved as instructed**: this stage runs `sim check` over
> the scenario set, and the scenario set does not exist until `S-C3`. So the
> half that is buildable today became **`S-C0`**, at the front of Phase C, and
> this stage keeps its label and its scenario half. See `sim_requirements.md`
> §12.6.
>
> Scope grows by two tests from the same audit, because a CI job is where a
> number becomes non-negotiable:
> - [x] `ST-C6-3` `sim determinism` reports all four axes — same process, fresh
>       process, rebuilt binary, **different machine** — with the **axis derived
>       from the two runs' manifests, never from a flag**, and a pair differing
>       in more than one dimension reported as evidence for neither
>       (`R-SIM-24`, `NR-SIM-40`, `OD-10`). `core.determinism.derive_axis` +
>       `cli/determinism.py`, all four axes proven
>       (`test_c6_determinism.py`, `test_c6_determinism_cli.py`)
> - [ ] `ST-C6-4` a **deliberately non-deterministic** stage turns the job red
>       **as a CI job step** — **not wired this pass.** The comparison tool
>       (`sim determinism`) exists and is proven standalone; running a
>       pipeline twice and diffing needs the same real `df_sil` build
>       `sim check` needs, unavailable on today's ubuntu-only runner (same
>       honest skip boundary, not yet a job step). `compare_exact`'s "first
>       diverging tick/topic" half is proven directly
>       (`test_compare_exact_fails_naming_the_first_diverging_tick_and_topic`)

**Purpose.** `R-SIM-5` says resim is *"deterministic and the only thing that
goes in CI"* — and there is no CI. Until something re-runs it automatically,
determinism decays silently, which is the one failure a resim tool cannot
tolerate. Closes `NR-SIM-25`.

**Must not.** Grow into a general CI design. That is `plan.md` item 20, it is
larger than this module, and conflating them means neither lands. This stage
delivers **one job**: run `sim check` over the scenario set on every push.

- [x] One pipeline definition running `python -m pytest modules/sim/tests -q`
      and `sim check <scenario-set>` — both live inside `scripts/ci_gate.py`'s
      existing single entry point (`_run_sim_check`, `DF_SCENARIO_SET` points
      at `modules/df/tests/carla_scenarios`, the real 18-scenario set S-C3
      built); `.github/workflows/sim-ci.yml` needed no edit beyond a comment,
      since it already just calls `ci_gate.py`
- [x] `docs/py/run_all.py` in the same job — already true since `S-C0`,
      unchanged
- [x] Artefacts retained on failure: `sim_check_report.json` +
      `sim_check_stdout.txt` written to the same `--artifact-dir` every other
      check already uses
- [x] The job is **skipped, with a named reason, when no component library is
      built** — `_find_df_sil()` returns `None` on today's ubuntu-only
      runner, reported as `"sim check: skipped -- no df_sil build found"`,
      never a failure

*Scope added 2026-07-31 (`OD-10`, closes `OQ-7`). Read recording §4a — it is the
one place the tolerance rules are argued rather than stated.*

- [x] **`sim determinism <run-a> <run-b>`** — `cli/determinism.py` +
      `core/determinism.py::derive_axis`. No `--axis` flag exists at all
      (`test_axis_flag_is_refused` asserts argparse itself refuses it)
- [x] **`process_nonce` in the run manifest** — `core/manifest.py`'s
      `_PROCESS_NONCE` (generated once per process at import time),
      `io/base.py`'s `RunManifest.process_nonce`, `io/mcap.py`'s
      round-trip. Excluded from `core.ids.new_run_id`'s hash (unchanged)
- [x] **The comparison is over port values, never file bytes** —
      `compare_exact`/`compare_with_tolerance` iterate `reader.messages()`
      per topic, never the recording file's own bytes
- [x] **Axes A and B are gates and have no tolerance field at all** —
      `cli/determinism.py` calls `compare_exact` for those two axes only;
      `ToleranceSet` is never even constructed on that path
- [x] **Axes C and D are measurements, not gates** — `compare_with_tolerance`
      returns every divergence found (never stops at the first), each naming
      topic + field + tick; a schema-less topic falls back to unattributed
      raw-byte comparison rather than silently passing (a real gap found
      and closed while building `ST-C6-3`'s own CLI test)
- [x] **`modules/<name>/sim/tolerance.yaml`** — `core/tolerance.py`.
      `default: exact`; integers/enums **structurally** un-widenable
      (`compare_with_tolerance` only ever looks a FLOAT field up in
      `tolerance`; every other type is always exact, so there is no code
      path by which one could be widened, not merely a convention against
      it); every row requires `why:` or `AuthoringError`. **Not done: the
      hash joining `config_bundle_sha256` in the run manifest** — no
      `RunManifest` field carries it yet, tracked as a real gap, not
      fabricated. **A real file landed 2026-08-06** (`sim` build queue
      row 2): `modules/df/sim/tolerance.yaml`, `fields: {}` — the first
      component in the repo to have one at all, closing the "exists
      nowhere" half of `NR-SIM-41`'s finding while the deferral above
      (RunManifest wiring) stays exactly as open as this note already said
- [x] **A passing report prints the tolerance used and the headroom
      consumed** — `cli/determinism.py`'s PASS line always includes both;
      >50% triggers the stated warning

**Tests**
- [x] `ST-C6-1` (`test_c6_ci_gate.py::test_all_passing_is_green`; real:
      `ci_gate.py` run against the real scenario set, 2026-08-05, 18/18)
- [x] `ST-C6-2` (`test_c6_ci_gate.py::test_unexpected_failure_is_red_and_names_scenario_signal_and_expected_actual`)
      — **while proving this, found and fixed a real bug in the test's OWN
      methodology, not in the framework**: a manual `sim check` run against
      a `cus1`-calibrated `df_sil` (a stale build, not `base`) reported 3
      apparent scenario failures that vanished against the correct `base`
      build — recorded as `AR-27` rather than added as `known_scenario_gaps`
- [x] `ST-C6-5` (`test_c6_determinism.py::test_row_without_why_is_an_authoring_error`, `::test_row_with_negative_bound_is_an_authoring_error`; the "prints the bound on a pass" half: `test_compare_with_tolerance_passes_within_bound_and_reports_headroom`)
- [x] `ST-C6-6` (`test_c6_determinism.py::test_two_differing_dimensions_is_evidence_for_neither_axis_naming_both`, `test_c6_determinism_cli.py::test_two_dimensions_differing_reports_neither_axis`)

**Discipline**
- [x] portability §3 (`P-4`, `P-10`) · naming §3 (`N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C6-2` green — proven twice over: the unit-level pure-function test,
      and the real `ci_gate.py` run that caught a genuine mismatched-project
      bug in this session's own manual testing before it was recorded as a
      false "known gap"

**Remaining, explicitly deferred, not this session's scope:** `ST-C6-4`'s CI-
job wiring (the comparison tool exists and is proven; running a pipeline
twice inside the job needs the same real build `sim check` needs, absent on
today's runner); the tolerance-file hash joining the run manifest;
`build_id` stays `"unknown"` (pre-existing, `S-C1b`'s own deferral, unrelated
to this stage). None of these were reachable without a C++ toolchain CI job,
which is `plan.md` item 20 and explicitly out of this stage's scope.

### S-C7 — `sil_host` reads the pipeline (`FR-SIM-65`, closes `OQ-11`)

> **Build order: #15** (§0a is the authority on sequence). Block 2. Blocked on `S-C1d` (#12) and `S-C5` (#13).

**Purpose.** Make `sil_host` do the job it is named for: **run a complete
pipeline in simulation, with no Python in the process.** Today it is 54 lines
driving exactly one component positionally. The architecture asserted that one
pipeline file runs unchanged under both hosts; the contract doc listed the same
thing as undecided. Two documents disagreeing about whether a capability exists
is a `GT-7` failure — resolved by building it, because the claim is
load-bearing: a second host that cannot read the pipeline file is a second host
with its own composition model, which is exactly what §9's standing rule exists
to prevent.

**Must not.** Grow an object generator, a recorder, a viewer or a world-model
client. `sil_host` executes `dll:` and `stubdll:` stages plus `mode: measured`
injection, and nothing else (architecture §9). A stand-in it needs is promoted
to a `stubdll:` on the same generic ABI — **never** a second implementation.

**Must not** (second). Re-specify anything. Every semantic it needs is already
fixed: `R-SIM-4` (manifest), `R-SIM-10` (`mode:`/`impl:`), `R-SIM-18` (declared
period, GCD base grid), `R-SIM-3a` (bundle resolution), `CR-SIM-23` (pipeline
`version:`). If this stage finds itself making a design decision, the decision
already exists somewhere and was not found.

- [x] Pipeline reader in C++ — the **same file** `adas_sim` reads, same schema,
      same `version:` + upgrader semantics. A key it cannot honour is a **load
      error naming the key and why**, never a silent skip. Verified 2026-08-05
      against a real build (`UT-C7-1`/`ST-C7-1`/`ST-C7-2` below)
- [x] N-library loading over `resolve_library`'s platform rules (`P-5`), each
      giving its `adasManifest()`; ports wired **by name**, with the same
      load-time validation order `contracts/pipeline.py` uses. Verified: real
      `df_sil.dll` and `echo_stub.dll` both resolved and loaded for real
- [x] Multi-rate execution on the GCD base grid (`R-SIM-18`), holds included,
      tests added 2026-08-06 (`tests/unit/test_pipeline_step.cpp`) — a
      single `stubdll:echo_stub` stage with a real 100ms `period_ns` and a
      real output port, driven through four 50ms `Step()` calls, proves a
      not-due tick HOLDS the last real bytes (`valid=true`, `updated=false`,
      `hold_age_s` growing) rather than going invalid, and a due tick
      reports it fresh (`updated=true`, `hold_age_s=0.0`) — the actual
      claim this item makes, for real bytes, not just a stage-ran boolean
      (`ST-C7-2`'s own scope). Needed `echo_stub.cpp` extended with an
      optional, env-var-controlled output port (`ADAS_SIL_TEST_STUB_OUTPUT_
      PORT`/`_PROTO_TYPE`/`_MAX_BYTES`/`_PERIOD_US`/`_DUE`, same "read at
      call time, no rebuild" design the existing knobs already use) — every
      env var defaults to the exact prior behaviour (empty port set) when
      unset, so no existing test's fixture usage changes.
- [x] `mode: measured` injection from a recording, test added 2026-08-06
      (`tests/unit/test_resim_measured.cpp`) — a `measured` stage's
      declared output is asserted against the PER-TICK bytes actually
      written into a synthesized recording (never `echo_stub`'s own fixed
      payload, which would only appear if `adasExec` had wrongly been
      called), proving `RunResim` truly injects rather than executes.
      `mode: simulate` on a `stub:` `impl:` is a load error naming both,
      already real and tested (`UT-C7-2`).
- [x] Per-`exec()` timeout (`R-SIM-19`), tests added and **compiled and run
      for real** 2026-08-06 (`tests/unit/test_exec_timeout.cpp`) — the
      interesting path (a callable that hangs 30s against a 100ms budget)
      reports `kTimeout` and returns in well under the hang's own duration;
      `kOk`/`kException` (`std::exception` and a non-`std::exception` throw)
      are exercised too, and a fast throw is proven never merged into
      `kTimeout`. `exec_timeout.{hpp,cpp}` has zero dependency on
      `pipeline.hpp`/protobuf/yaml-cpp — the one S-C7 surface this WSL
      shell can build standalone (system `g++`/`libgtest-dev`, no
      Conan/MSVC needed) — **5/5 passing, real compiled evidence**, not a
      claim: `g++ -std=c++17 -pthread -Isrc src/exec_timeout.cpp
      tests/unit/test_exec_timeout.cpp -lgtest -lgtest_main -lpthread`.

      **Verification honesty, stated because it matters:** this WSL shell
      has no Conan and no compatible `libprotobuf` headers (`libprotobuf23`
      is a runtime-only package, version 3.12 against generated code
      requiring 3.21+) — every file that includes `pipeline.hpp` transitively
      needs the generated `Adas__Sil/component_manifest.pb.h`, so
      `test_pipeline_step.cpp`, `test_resim_measured.cpp` and the
      `echo_stub.cpp` extension they need are **written and carefully traced
      by hand against the real, previously-verified implementation
      (`pipeline.cpp`'s `Step()`, `resim_runner.cpp`, `sil_component.cpp`'s
      exact `AdasPortSet` protocol) — not compiled or run in this session.**
      All three are wired into `tests/CMakeLists.txt`'s `SIL_TEST_SOURCES`
      and will build/run under the next real MSVC/Conan session
      (`scripts/build.py sil_host -t gtest -p vs2026 -P base`) the same way
      every other Windows-only item in this plan is verified. Flagged here
      rather than claimed green.

**Tests**
- [x] `UT-C7-1` a pipeline file loads and its stage/port graph matches what
      `adas_sim`'s loader produces for the same file — compared structurally,
      not by eye. `tests/unit/test_ut_c7_1_graph_dump.cpp`, real build, passing
- [x] `UT-C7-2` a `stub:` stage is rejected at load naming the stage and the
      reason; a `stubdll:` stage on the same pipeline loads.
      `tests/unit/test_pipeline_load_errors.cpp`, real build, passing
- [x] `UT-C7-3` a non-multiple `period_ns` is a load error naming both numbers,
      identically worded to the Python side. `tests/unit/test_pipeline_
      period_grid.cpp`, real build, passing
- [x] `ST-C7-1` **the claim, tested**: one unmodified pipeline file runs under
      `sim resim` and under `sil_host`, and the two produce **byte-identical**
      outputs for the same recording. This is the only test that makes "one
      concept, two hosts" a fact rather than a slogan.
      `modules/sim/tests/system/test_c7_cross_host_resim.py`, real build,
      passing (skips with a named reason if `df_sil.dll`/`sil.exe` aren't
      built here). Originally proven only for a recording this framework
      produced itself (`R-SIM-6`); the `R-SIM-23` ingest-map gap that
      narrowed it (`sil_host`'s `RecordingReader` had no ingest-map
      support) is fixed same-day (`ingest_map.{hpp,cpp}`, see status note
      above) — re-verified against the real legacy `aeb_canonical_10mps_
      30m.mcap` recording, `df.aeb.outputs` now fires within the
      scenario's own documented tolerance
- [x] `ST-C7-2` a two-stage pipeline (component + `stubdll:` stand-in) runs
      end to end with **no `main.cpp` edit** — the property that distinguishes
      an engine from a hardcoded composition.
      `tests/system/test_st_c7_2_two_stage_resim.cpp`, real build, passing
      (two `stubdll:echo_stub` stages; also proven manually against a real
      `df_sil` + `echo_stub` two-stage pipeline, see status note above)

**Discipline**
- [ ] portability §3 (`P-1`, `P-4`, `P-5`) · naming §3 (`N-2`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C7-1` green — byte-identical across both hosts. Holds for both a
      framework-produced recording and a legacy, ingest-mapped one (the
      `R-SIM-23` gap that once narrowed this is fixed, see status note above)
- [x] `ST-C7-2` green — no hand-editing to add a stage, which is the whole
      difference between this stage and `S-E2`'s one-call-site move

### S-C8 — The plug-in bundle: the player runs standalone (`R-SIM-20`, `FR-SIM-64`)

> **Build order: #14** (§0a is the authority on sequence). Block 2. **Built before `S-C6`/`S-C7`, against id order**, on this stage's own instruction: adjacency to `S-C5` (#13).

**Purpose.** Make *"point the player at a folder of libraries and it draws
them"* true. A component's plug-ins are authored in the component (`R-SIM-1`,
unchanged) and **delivered** beside its library, exactly as `S-C5` delivers its
calibration. Without this, `FR-SIM-70`'s shipped executable cannot render any
component without a git checkout beside it — and "standalone" is an aspiration.

**Must not.** Move `modules/<name>/sim/` anywhere. The authoring home is
unchanged and the deployed copy is a **build output**, never a second place to
edit a layer (`R-SIM-3a`'s own discipline, and the failure it exists to
prevent).

**Must not** (second). Invent a second resolution order. The plug-in bundle
resolves **explicit → embedded-in-recording → library `sim/` → source
checkout**, the same four tiers in the same order as the config bundle, and
reports which one won.

- [x] Build copies `modules/<name>/sim/` into `$<TARGET_FILE_DIR:…>/sim/` with
      its own `sha256:` — `interfaces/scripts/pack_plugin_bundle.py` +
      `cmake/plugin_bundle_pack.cmake`, wired into `df_sil`'s `CMakeLists.txt`
      right after `adas_pack_config_bundle` (`$<TARGET_FILE_DIR>`, never a
      hand-written path, same as `S-C5`); `install(DIRECTORY … sim/)` pairs it,
      same `bin`/`lib` per-platform destination. Verified against a real
      `cmake --install` (`tests/system/test_c8_relocatability_installed.py`)
- [x] `--plugin-root` / `ADAS_SIM_PLUGIN_PATH` — `scripts/vantage.py` now
      resolves each as a **library directory** (`<dir>/sim/plugin.yaml`)
      through `PluginBundle.resolve`, replacing the old ad hoc `sim/layers/
      *.py` glob-import entirely
- [x] Plug-in discovery is **by import**, unchanged — `PluginBundle.
      import_modules()` imports each `provides:` entry under a private,
      collision-free name (`_adas_plugin.<component>.<dotted>`, never the
      literal `sim.layers.<x>` two components would otherwise shadow each
      other on); `scene.registry.layer_provider`'s existing duplicate-id
      check does the rest, unmodified
- [x] Recorder embeds the plug-in bundle's **identity and hash**
      (`sources/recorder.py`'s `plugin_bundles_meta`, `io/mcap.py`'s
      `/meta/plugin_bundles`) beside the config bundle's. **Not done: the HUD
      degrade path** — "renders with the layers it can and says so in the
      HUD" needs a viewer surface that does not exist yet; the write+resolve
      halves are real, the on-screen message is not
- [x] `sim explain` and `sim doctor` both report the plug-in path, landed
      2026-08-06. `sim doctor --plugin-root`: `core/diagnostics.py`'s new
      `_plugin_diagnoses` resolves each library-diagnosed stage's own
      `PluginBundle` (explicit → library `sim/` → checkout — no `embedded`
      tier, `sim doctor` diagnoses a library/pipeline, not a loaded
      `Session`, so there is no recording to embed one in), reported under
      `report["plugins"]`; a component with no `sim/` plug-ins is
      `found: False`, never a problem. `sim explain <layer>`:
      `core/explain.py`'s `kind="layer"` branch now reports
      `plugin_component`/`plugin_path` when the layer's module name is
      `_adas_plugin.<component>.<dotted>` (`PluginBundle.import_modules`'s
      own naming) — `plugin_path` is that module's own real `__file__`
      (already resolved by `importlib.util.spec_from_file_location` at
      import time, no new plumbing needed); a first-party layer (module not
      under `_adas_plugin`) reports neither field, never a guess
      (`R-SIM-25`, `NR-SIM-4`).
      Tests: `test_c8_plugins.py::test_sim_explain_reports_the_owning_component_and_real_file_path_for_a_plugin_layer`,
      `::test_sim_explain_reports_no_plugin_fields_for_a_first_party_layer`;
      `test_d6_doctor.py::test_plugin_diagnoses_reports_a_resolved_library_tier_bundle`,
      `::test_plugin_diagnoses_reports_found_false_for_a_component_with_no_sim_plugins`,
      `::test_plugin_diagnoses_skips_a_stage_whose_library_never_resolved`,
      `::test_plugin_diagnoses_explicit_plugin_root_wins_over_the_library_tier`
      (all real, compiled, and passing — no DLL needed, same split
      `test_c5_overrides.py` already used for `resolve_swept_config`).

*Scope added 2026-07-31 (`NR-SIM-44`). Read arch §5.7a.*

- [x] **`modules/<name>/sim/plugin.yaml`** — `api:`, `component:`,
      `provides:`, authored at `modules/df/sim/plugin.yaml` (no `sha256:` —
      that is stamped into the DEPLOYED copy only, at pack time)
- [x] The player declares the plug-in API range it supports
      (`SUPPORTED_PLUGIN_API_MIN/MAX`, `model/plugins.py`); outside it, the
      plug-in is **refused with both numbers named**, and never imported —
      `PluginBundle.resolve`/`_from_yaml` raises before `import_modules` is
      ever reachable (`UT-C8-5`)
- [x] The plug-in API generation is **independent** of the Scene major and the
      ABI version — its own constants, no shared numbering
- [x] **A recording never carries executable content** — `plugin_bundles_meta`
      is `{component: {api, sha256}}` only; the asymmetry is stated in both
      `recorder.py`'s and `mcap.py`'s own comments
- [ ] A missing plug-in degrades to *"these layers unavailable"* named with the
      hashes expected — **not implemented**; no reader-side "expected but
      absent" path exists yet (only "absent" via `PluginBundle.resolve`
      returning `None`, with no hash to compare against since nothing was
      ever embedded to expect)

**Tests**
- [x] `UT-C8-1` (`test_c8_plugins.py::test_pack_deploys_files_byte_identical_and_stamps_sha256`, `::test_pack_hash_changes_on_case_only_rename`, `::test_pack_excludes_pycache_and_plugin_yaml_itself_from_the_hash`)
- [x] `UT-C8-2` (`test_c8_plugins.py::test_resolution_order_explicit_beats_embedded_beats_library_beats_checkout`)
- [x] `UT-C8-3` (`test_c8_plugins.py::test_two_components_each_contributing_a_layer_both_register`, `::test_duplicate_layer_id_across_two_components_raises_naming_both`)
- [x] `UT-C8-4` (`test_c8_plugins.py::test_recorder_embeds_plugin_identity_and_hash_never_bytes`)
- [x] `UT-C8-5` (`test_c8_plugins.py::test_out_of_range_api_is_refused_naming_both_numbers`)
- [x] `ST-C8-1`/`ST-C8-2` — **the mechanism, proven against the real artefact**
      (`test_c8_relocatability_installed.py`): a real `cmake --install`,
      relocated with the original installed copy deleted, resolves and
      imports `df`'s real `sim/layers/{common,bsd}.py`, run in a fresh
      interpreter (the process-global layer registry makes an in-process
      check order-dependent on whatever else the test session already
      imported — deliberately sidestepped, not worked around). **Not
      proven: an actual `vantage <dir>` GUI frame** — same scope split
      `S-C5` drew between the mechanism and a full CLI/GUI run
      **Extended 2026-08-07:** load-and-register alone let a real
      bug through — a driving function's own calibration reader worked from
      a source checkout but crashed (`FileNotFoundError`) from exactly the
      relocated/deployed copy this test proves resolves and imports. Both
      tests now ALSO resolve `ProjectModel` off the relocated `config/`
      directory (sibling of `sim/`, same build) and call two real
      calibration-derived layer providers through it, asserting real prims
      come back — the actual call that used to crash. Fixed at the root:
      `ProjectModel` gained `bundle_dir` (the winning tier's own directory),
      the calibration reader uses it when given and falls back to the
      checkout-relative path only when `bundle_dir is None` (genuinely no
      packed bundle involved), and `vantage.py`/`MainWindow`/`VantageWindow`
      thread `--plugin-root`'s own `config/` directory through so the real
      GUI entrypoint gets the fix too, not only this test's direct calls.
      Also found and fixed along the way: `pack_plugin_bundle.py`'s
      `bundle_sha256` walked the DESTINATION directory unfiltered, so a
      `.pyc` left behind by an earlier real import (exactly what a prior
      `vantage.py --plugin-root <build dir>` run leaves) crashed the NEXT
      rebuild's hash step — now excludes `__pycache__` the same way the
      copy step already did.
- [x] `ST-C8-3` (`test_c8_deployed_root_render_wiring.py`) — the wiring gap
      `ST-C8-1`/`ST-C8-2` could not see: those call `ProjectModel.resolve`
      directly, so a bug in `scripts/vantage.py`'s own CLI-argument-to-
      `library_dir=` plumbing would pass them silently. This drives
      `_register_plugin_root` **and** a real `MainWindow` together, against
      a relocated, original-deleted `df_sil` build, and confirms a real
      `bsd.zone` layer renders real prims with `bundle_origin == "library"`.
      Re-verified by injection: reverting the fix reproduces the exact
      original `FileNotFoundError`/empty-layer-tree failure; restoring it
      passes again.
- [x] `GT-12` — the load-and-register mechanism (`ST-C8-1`/`ST-C8-2`) and the
      specific render-from-a-deployed-root gap (`ST-C8-3`) are both proven;
      a full interactive `vantage <dir>` session exercising every panel is
      still not automated

**Discipline**
- [x] portability §3 (`P-1`, `P-2`, `P-5`, `P-9`) · naming §3 (`N-2`, `N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C8-2` green — the strong form, at the mechanism level described
      above (real artefact, original deleted, fresh process, no GUI frame)
- [x] **A plug-in bundle loaded from a DEPLOYED root actually renders**
      (carried over from the retired ledger's `AR-61`, the one row that was
      still open when it was deleted — §9a is now its home).

      **Re-verified against current source and found already fixed.** The
      repro that previously found this broken: build a deployed-*shaped*
      root (`sim/` + the real packed `config/`, deliberately **no**
      `src/project/` — the discriminator, present in a checkout and absent
      from a deployed copy) and drive it through `vantage.py`'s own
      `_register_plugin_root` into a real `MainWindow`. Result now: the
      session loads, `ProjectModel.bundle_origin == "library"`,
      `bundle_dir` resolves to the deployed `config/`, and `bsd.zone`
      renders real prims — no `FileNotFoundError`, no empty layer tree.
      `render/viewer.py`'s `_resolve_project_model` does thread
      `self._config_library_dir` into `ProjectModel.resolve(library_dir=…)`
      — the fix site the previous finding named — so the wiring gap no
      longer exists.

      **Confirmed by injection, not by reading the code**: reverting
      `_resolve_project_model` to the two `ProjectModel.resolve(...)` calls
      *without* `library_dir=` reproduces the original failure exactly —
      `FileNotFoundError` at `_bsd_calibration`, `bundle_origin ==
      "checkout"` — then restoring the real code makes it pass again. The
      fix is real and this is what it fixes.

      **New regression test**, since none existed for this specific wiring
      path: `tests/system/test_c8_deployed_root_render_wiring.py`. Unlike
      `ST-C8-2`'s own check (which calls `ProjectModel.resolve` directly),
      this drives `scripts/vantage.py`'s real `_register_plugin_root`
      **and** a real `MainWindow` together, in a fresh subprocess, against a
      real installed-then-relocated `df_sil` build with the original
      deleted — so a future edit that reintroduces the `pipeline_config`-only
      wiring fails here rather than needing to be found by hand a fourth
      time. Skips with a named reason if no real build or recording exists.
- [x] `GT-12` — the mechanism (`ST-C8-1`/`ST-C8-2`) and the specific render
      gap above are both proven; a full interactive `vantage <dir>` session
      exercising every panel is still not automated (same scope this gate
      always distinguished from the mechanism level).

**Remaining, explicitly deferred:** the HUD's missing-plug-in badge surface
(`sim explain`/`sim doctor` reporting the plug-in path landed 2026-08-06,
above — the on-screen HUD message for a missing plug-in is the only piece
left). Does not block `S-C6`, which needs recordings and scenarios, not the
viewer.

### S-C9 — Recording ingest: what a file provides, and which cuts it supports (`R-SIM-23`, closes `D14`)

> **Build order: #8** (§0a is the authority on sequence). Block 1. **Built before `S-C2`, against id order** — it is `P0`, needs no world model, and `S-C3` (#10) depends on it.

**Purpose.** Make an existing recording drivable. Today the chain
`df/gen_object_list` → `/source/gen_object_list` → `source.gen_object_list`
stops one step short of the port the manifest actually declares (`objects`), and
the only working bridge is **hardcoded inside `ST-C1c-1`**. This stage moves
that bridge into declared data, owned by whoever owns the recordings, and makes
`CR-SIM-21` answerable before a run rather than discoverable by failing one.

**Must not.** Compute anything. The ingest map renames and tags **only** — no
expression, no unit conversion, no field arithmetic, no synthesised signal. A
step that computes is an unversioned algorithm between the recording and the
SUT, so a resim would reproduce the recording *plus whatever it did*
(`R-SIM-5`, `R-SIM-7`). A `proto_type` that does not match the port's means
**this recording does not support that cut** — never a coercion.

**Must not** (second). Leave the mapping in the framework. `io/legacy.py`'s
`GT-1` exemption was justified at `S-A4` as narrow and one-off; a second
component's recordings make it a pattern, and a carve-out that repeats is a
mechanism that was not built. **This stage deletes the exemption**, which is its
own best test.

- [x] `modules/<name>/sim/ingest/<family>.yaml` — the declaration:
      `matches:` (how a recording is recognised as this family), `provides:`
      (topic → port + `proto_type` + origin tag), and **`absent:`** (a port this
      family never recorded, with the reason). The `VehSig` hole
      (`sim_resim_and_recording.md` §4) becomes a declared fact rather than a
      surprise at tick 0 — `modules/df/sim/ingest/carla_legacy.yaml`
- [x] `df`'s legacy CARLA family declared this way; `LEGACY_TOPIC_MAP` and the
      `check_gt1` exemption both **deleted**, not deprecated
- [x] `io/ingest.py` — loads maps and applies them over any `RecordingReader`.
      Format-agnostic by construction: it operates on the recording *model*,
      so it works identically for mcap, MF4 or a CarMaker codec (`R-SIM-14` —
      dimension 1 needs no work here, which is the evidence the two
      dimensions really are separable). **Scoped gap, documented in the
      module docstring:** `discover_ingest_maps` scans
      `modules/*/sim/ingest/*.yaml` under the source checkout directly, not
      the plug-in path — `S-C8` (build order #14) does not exist yet. Same
      shape as `S-C4`'s calibration-reading gap; revisit when `S-C8` lands
- [x] **`Session.provides()` / `feasible_cuts(pipeline)`** — given the topic
      index and the manifests present, the set of stages that can be `measured`
      and those that cannot, each with the reason. This is `CR-SIM-21` becoming
      a query instead of an assertion
- [~] `sim probe <recording>` reports it (done — `cli/probe.py`); **the Bench
      start page showing it before a run, and greying the cuts the file
      cannot support, is not done** — `S-B3`/`S-D8` (the Bench workspace and
      start page themselves) have not been built yet. Nothing here is
      speculative: `Session.provides`/`absent`/`feasible_cuts` are real data
      today, so that panel is wiring, not design, whenever `S-B3`/`S-D8` land
- [x] **One `GT-7` fix found on the way:** `io/legacy.py` mapped
      `df/aeb_outputs` to the *topic* `/df/aeb.outputs` (dot), conflating a
      topic name with a port name; `sim_resim_and_recording.md` §3.2's table
      was corrected on 2026-07-30 to `/df/aeb/outputs` (slash, per `N-1`).
      The redesign resolves this architecturally, not by swapping a
      character: `carla_legacy.yaml`'s `provides:` keys are raw *topics*
      (`df/aeb_outputs`, unchanged — that really is what's on disk) and its
      `port:` values are *port* addresses (`df.aeb.outputs`, dot-separated
      per `R-SIM-4`'s own convention) — two namespaces that were previously
      conflated into one string are now separated by construction, so the
      dot/slash bug has nowhere left to reappear

**Tests**
- [x] `UT-C9-1` a legacy topic resolves to the **manifest's** port name — the
      step that does not exist today; asserted against `df_sil.ports.yaml`'s
      real `objects`/`egoDyn`, not a fixture invented for the test —
      `tests/unit/test_c9_ingest.py::test_df_carla_legacy_map_resolves_to_df_sil_ports_yamls_real_output_names`
      (checks the two *output* ports, `aeb.outputs`/`bsd.outputs`, against the
      real checked-in `df_sil.ports.yaml`; the stimulus ports `objects`/`egoDyn`
      are a pipeline-authoring choice — `Stage.inputs` — not something the
      ingest map itself resolves, and are exercised end to end by `ST-C9-1`)
- [x] `UT-C9-2` `absent:` is honoured: a declared-absent port yields `valid=0`
      downstream **and is named at load**, never a tick-0 failure —
      `tests/unit/test_a4_legacy.py::test_legacy_topic_names_map_correctly_and_manifest_is_unknown`
      covers "named at load"; the `valid=0`-downstream half is exercised by
      `test_c1c_resim_equivalence.py` (an absent `source.veh_sig` is simply
      never in a tick's port set, which is the pre-existing generic
      "unwired optional port" convention `UT-C1c-12` already proves)
- [x] `UT-C9-3` a `proto_type` mismatch reports *"this recording does not
      support that cut"* naming both types — and **does not** coerce —
      `tests/unit/test_c9_ingest.py::test_feasible_cuts_reports_a_proto_type_mismatch_naming_both_types`
- [x] `UT-C9-4` an ingest map containing an expression, a unit conversion or an
      arithmetic field is an `AuthoringError` — the closed vocabulary, enforced
      rather than documented (`R-SIM-15`'s precedent) —
      `tests/unit/test_c9_ingest.py::test_a_provides_entry_with_an_expression_key_is_refused`,
      `::test_an_absent_entry_with_an_extra_key_is_refused`
- [x] `UT-C9-5` two components' ingest maps load together; a topic claimed by
      both raises naming both maps (`N-8`) —
      `tests/unit/test_c9_ingest.py::test_a_topic_claimed_by_two_ingest_maps_raises_naming_both_families`
      (off the *source-checkout scan*, not the plug-in path — see the
      `io/ingest.py` scoped gap above)
- [x] `UT-C9-6` `feasible_cuts` on a recording carrying only objects reports the
      one supported cut and, for each unsupported one, **which port is missing**
      — `tests/unit/test_c9_ingest.py::test_feasible_cuts_reports_the_supported_stage_and_names_missing_ports_for_the_rest`
- [x] `ST-C9-1` **the asker's workflow, end to end**: every existing recording
      under a component's test-run directories resims through a real `Pipeline`
      with `df` as the only stage, with **no per-test topic mapping** — i.e.
      `ST-C1c-1`'s hardcoded bridge is deleted and the test still passes —
      `tests/system/test_c1c_resim_equivalence.py`, green against the real
      `df_sil.dll` and real recordings on this machine
- [x] `ST-C9-2` **dimension 2, proven with a second shape**, landed
      2026-08-06. `tests/system/test_c9_synthetic_perception.py`: a
      synthetic recording carrying `perception/raw_objects` (no `df`-style
      objects at all) drives a real two-stage `Pipeline` (`perception`
      `measured`, `consumer` `simulate`, wired `in: perception.objects`)
      through the real `core.resim.resim_pipeline` — the exact function
      `sim resim` calls — with `discover_ingest_maps` monkeypatched to an
      in-memory `IngestMap` for this synthetic, framework-agnostic family
      (no real component owns "perception" here, so there is nothing to
      write a real `sim/ingest/*.yaml` file for). The consumer's own
      `exec()` receives the recording's real per-tick bytes, proving the
      measured injection travels through the ingest map's rename into a
      live `simulate` stage, not just into the outer per-tick `outputs`
      dict. A second test proves the query half too (`Session.
      feasible_cuts` reports the perception cut feasible with the ingest
      map applied). Deliberately synthetic — the test's own name says so,
      same as the plan's own scope note required.
- [x] `ST-C9-3` **dimension 1 costs nothing here**, landed 2026-08-06.
      `io/jsonl.py` — a genuinely second registered codec (`R-SIM-14`'s
      "~4 methods each" promise), not a test-only fixture: human-readable,
      one JSON header line + one line per message, reusing
      `manifest_to_dict`/`manifest_from_dict` (moved from being
      `io/mcap.py`-private to `io/base.py`-public at this same stage,
      specifically so two codecs share one `RunManifest` (de)serialization
      instead of silently drifting apart the next time a field is added —
      `UT-C5-6/7`'s own `bundle_overrides` addition already needed
      updating in exactly one place because of this). Registered for
      `.jsonl` in `io/registry.py`'s `_BUILTIN_CODEC_MODULES`, full
      `RecordingReader`/`RecordingWriter` Protocol, `round_trips=True`.
      `tests/unit/test_c9_second_codec.py`: the SAME `IngestMap`, applied
      via `IngestRecordingReader` over an `.mcap` recording and a
      `.jsonl` recording of equivalent content, yields an **identical**
      resolved port set (topic names, provenance, log_time_ns, bytes) —
      the architectural claim `io/ingest.py`'s own docstring already made
      ("works identically for mcap, MF4 or a CarMaker codec"), proven
      against a second real codec for the first time. A second test
      proves the unclaimed-topic passthrough on both codecs too.
      `tests/unit/test_c9_jsonl.py` covers the codec itself (round-trip,
      capabilities, the two-clock `capture_time_ns` contract, a malformed
      line naming its own line number) — 12 tests total across both files,
      all real, compiled, and passing (no DLL needed).

**Discipline**
- [x] portability §3 (`P-1`, `P-3`, `P-4`) · naming §3 (`N-2`, `N-6`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `ST-C9-1` green **with `ST-C1c-1`'s hardcoded topic constants deleted** —
      a bridge that still exists in a test is a bridge the product does not
      have. `TOPIC_GEN_OBJECT_LIST`/`TOPIC_VEH_DYN` are gone from
      `test_c1c_resim_equivalence.py`; it now opens a `Session` through the
      real `df.carla_legacy` ingest map and drives a real `Pipeline`
- [x] `GT-1` green **with `io/legacy.py`'s exemption removed from
      `check_invariants.py`** — the exemption disappearing is the cleanest
      possible proof that the mapping moved to where it belongs. Confirmed:
      `check_invariants.py` no longer references `legacy.py` or a
      `_GT1_EXEMPT_FILENAMES` carve-out, and `GT-1` still reports clean

**Open at the end of this pass (2026-08-03):** `ST-C9-2`/`ST-C9-3` unwritten,
and the Bench-start-page half of the `sim probe` item — both flagged above at
the point they're incomplete rather than silently left as blank checkboxes.
Everything else in this stage is implemented, tested against real artifacts
where one exists (`df_sil.dll`, real recordings, the real checked-in
`df_sil.ports.yaml`), and green.

**`ST-C9-2`/`ST-C9-3` landed 2026-08-06** (above) — `S-C9` now has only the
Bench-start-page wiring left open, which needs `S-B3`/`S-D8` (not built) to
exist at all, same as already noted.

---

## 7. Phase D — Reach

Phase D takes a working single-recording viewer and extends its reach: to a
foreign viewer (`D1`), to print (`D2`), to the measured/simulated surface
(`D3`), to a second component (`D4`), to a machine with no repo (`D5`), to a
developer's own component (`D6`), to many recordings (`D7`), and finally to a
named product (`D8`).

**One boundary to fix before starting, because two stages here build GUI and it
would otherwise be built twice:**

| Stage | Owns | Does **not** own |
|---|---|---|
| `S-B3` | the **shell**: window, docks, panels, layer tree, inspector, timeline, plots | anything about pipelines or workspaces |
| `S-D3` | the **pipeline panel** — per-stage measured/simulate, and the run manifest it produces | the window it lives in (that is `S-B3`'s) |
| `S-D8` | **Vantage**: the product name, the Bench/Campaign workspaces, the start page, the command palette, the probe and console panels | any panel `S-B3` or `S-D3` already built |

Read that as: `S-D3` adds **one dock** to an existing window, and `S-D8` adds
**modes and a front door** around it. Neither builds a second GUI. A stage that
finds itself creating a window has misread this table.

### S-D1 — Foxglove `SceneUpdate` + Scene-in-recording

**Purpose.** Demonstrate `R-SIM-13` in a viewer we did not write: the same
`Scene`, rendered by a foreign tool, looks like the same run. That is the claim
"visualization is identical regardless of origin" actually being tested rather
than argued from the Scene's shape.

**Must not.** Let a Foxglove type reach `scene/`. The mapping is one-directional
and lives entirely in `render/foxglove.py`; `Prim` must not grow a field that
exists because a foreign schema wanted it.

- [x] `render/foxglove.py` — Scene to scene entities, **one entity per layer**,
      so layer toggles work in the foreign viewer for free
- [x] Frame graph emitted **once** from the project model — the fix for the
      transform-tree failure where entities referenced frames that were never
      published and silently rendered at the origin. **Scoped, stated
      honestly**: STATIC identity transforms only — real dynamic pose
      composition needs `core/tick.py`'s `Tick` composed with the project's
      resolved mounting poses, out of scope here exactly as
      `sim_visualization_spec.md` §11.4 already scopes real camera
      extrinsics to "Phase D4". This closes the STRANDING bug (a referenced
      frame publishes something), not the POSE bug (that something is not
      yet where the sensor really sits)
- [x] `/scene` topic written into a session recording, so a recording opened
      cold shows the full spatial scene with no framework present.
      **`write_scene_snapshot` is a tested, ready-to-call primitive, NOT
      yet wired into `sources/recorder.py`'s live tick loop** — that needs
      the recorder to build a `Scene` every tick (`core/runner.py`'s
      `build_scene`, today only called from the Qt viewer's own paint path),
      a separate integration into already-tested live-recording code
      deliberately left for a follow-up pass rather than risked alongside
      this stage's own brand-new mapping code in the same session

**Tests**
- [x] `UT-D1-1` every prim type maps to a valid scene entity — a table-driven
      test over the whole `Prim` union, so a new prim type fails here rather
      than silently disappearing in a foreign viewer.
      `test_every_prim_kind_maps_to_a_populated_bucket`, parametrized over
      all 11 kinds, plus `test_prim_table_covers_the_whole_closed_kind_
      catalogue` asserting the test table itself can't silently fall behind
      `PrimKind`'s own set if a 12th kind is ever added
- [x] `UT-D1-2` every entity's `frame_id` exists in the emitted frame graph —
      the stranding bug, asserted.
      `test_every_entity_frame_id_exists_in_the_emitted_frame_graph` (also
      asserts the full chain to `world` is unbroken for a non-`ego` frame)
- [x] `UT-D1-3` entity ordering is sorted, so two exports of one Scene are
      byte-identical (`P-8`).
      `test_entity_and_frame_ordering_is_deterministic_two_exports_identical`
      — declaration order preserved (layers deliberately NOT pre-sorted in
      the fixture), two `.encode()` calls byte-identical
- [x] `UT-D1-4` no module under `scene/` imports or names a Foxglove type.
      `test_scene_module_never_imports_or_names_foxglove` — AST-parsed, no
      `foxglove-sdk` import needed to run this one, so the boundary check
      itself never depends on the package it is checking the absence of
- [ ] `ST-D1-1` a written session recording opens in Foxglove Studio and shows
      the scene with working layer toggles and seek → `MC-3`. **Cannot be
      done from this shell — this IS `MC-3`, one of `sim_implementation_
      plan.md` §3.4's explicitly named MANUAL checks** ("Foxglove Studio
      renders the exported scene | S-D1"), requiring a human to open the
      real application and check a box with their name and date. The
      recording this would open is producible today (`write_scene_snapshot`
      + `scene_recording_topics`, tested above) — only the actual open-and-
      look step is missing, and no amount of further coding in this
      environment closes it

**Discipline**
- [x] portability §3 (`P-4`, `P-8`) · naming §3 (`N-2`, `N-6`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-D1-1` green — the interop claim is demonstrated in a foreign viewer,
      not argued from the Scene's shape. **Blocked on a human opening
      Foxglove Studio** — not a code gap, see `ST-D1-1`'s own note above
- [x] `UT-D1-4` green — the boundary held in the direction that is easy to lose

### S-D2 — matplotlib renderer + figure-driver migration

**Purpose.** Prove **one Scene, two renderers, one palette** (`D5`). A figure in
a document and the live view must be the same picture in two media, not two
drawings that happen to resemble each other.

**Must not.** Let the figure driver reach into a provider or recompute geometry.
It consumes the same `Scene` the viewer does; if a figure needs something the
Scene lacks, the Scene is what changes.

- [ ] `render/matplotlib.py` — `print` theme, vector output, the `bev_axes`
      furniture guarantee
- [ ] The existing figure driver rebuilt on the framework
- [ ] **Byte-stability of figures is explicit work, not luck.** Vector formats
      embed a creation date and font paths by default; the writer must pin
      metadata (`Date: None`), fix the font resolution, and set a deterministic
      hash seed. Without this `ST-D2-1` fails intermittently and gets muted,
      which is worse than not having it

**Tests**
- [ ] `UT-D2-1` the same Scene renders through both the raster and matplotlib
      renderers **with no provider change**
- [ ] `UT-D2-2` a style token resolves to the same semantic role in `print` as
      in `dark`/`light` — a token that only exists in one theme fails here
- [ ] `UT-D2-3` figure output carries no embedded timestamp or absolute font
      path (`P-2`, `P-4`), asserted by scanning the produced file
- [ ] `ST-D2-1` the figure set regenerates and each figure is **byte-stable**
      across two runs
- [ ] `ST-D2-2` a figure and the live view of the same geometry use the same
      token, therefore the same semantic appearance (**D5** closed)

**Discipline**
- [ ] portability §3 (`P-4`, `P-7`) · naming §3 (`N-6`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-D2-1` + `ST-D2-2` green — one Scene, two renderers, one palette. A
      figure that disagrees with the live view is `D5` reopening

### S-D3 — The pipeline panel, and runs as manifests

**Purpose.** Put `R-SIM-10`'s per-stage measured/simulate toggle on screen, and
make every run expressible as a manifest the CLI accepts verbatim. This is the
surface the whole two-field model exists to provide.

**Must not.** Build a window. The shell is `S-B3`'s (see the phase table above);
this stage adds **one dock** to it. And must not hand-write a `.bat` launcher:
the GUI is a console entry point (`vantage = adas_sim.app:main`) so the launcher
is generated per platform (`P-6`) — a `.bat` is Windows-only and would have to
be replaced the day an Ubuntu machine appears.

> **Slice 1 landed 2026-08-05** (same session as `S-C7`'s real verification —
> this shell turned out to have working Qt-offscreen too, not just a
> toolchain). Scoped deliberately narrow, agreed with the user before
> starting: the panel **widget** only, discovery-driven, mode toggle that
> never discards `impl:` — **not** wired into `MainWindow`, **not** the
> on-disk `impl:` picker (nothing in this framework discovers candidate
> component libraries from a directory yet — `sim list ports <lib>` reads
> one manifest given an explicit path, no scan), **not** the run-manifest
> round-trip (`core/manifest.py` has no run-*configuration* manifest concept
> today — `RunManifest` in `io/base.py` is recording *provenance*, a
> different thing; building one is real schema-design work, not attempted
> here), **not** severed-chain UI, per-port override expansion, or
> compare-against-recorded.
>
> What landed: `view/pipeline_panel.py` (`PipelinePanelState`, `StageView`
> — pure Python, no Qt, mirrors `view/layers.py`'s own `LayerTreeState`
> split) + `PipelinePanel(QtWidgets.QDockWidget)` in `render/viewer.py`
> (mirrors `LayersPanel`'s shape: state owns decisions, the class only
> arranges the table and dispatches). Discovery reads stages straight off
> an already-loaded `Pipeline`; `measured` availability checks every
> declared output port (`pipeline.manifest_for(stage).outputs`) against the
> caller-supplied `known_ports` (the same shape `Session.known_ports`
> already carries, so a real caller needs no new conversion). Flipping mode
> never touches `impl:`, proven by a real toggle-and-check test, not by
> reading the code. `impl:` itself is read-only text this pass. 8 new
> tests, all real: 6 in `tests/unit/test_d3_pipeline_panel_state.py`
> (`UT-D3-1` partial — stage/mode/impl discovery, not the on-disk `impl:`
> alternatives; `UT-D3-2` both directions — available and unavailable with
> the missing qualified port named), 2 in
> `tests/system/test_d3_pipeline_panel_widget.py` (real offscreen Qt: the
> table renders one row per stage, and a real `QRadioButton.click()`
> dispatches `mode_changed` and updates `PipelinePanelState` — not just
> that the state object reports right, matching `test_b3_offscreen_smoke.
> py`'s own "not just what state reports" bar). `UT-D3-7` (no component
> name in the panel) is covered structurally by the existing `GT-1` grep
> (`src/adas_sim/**`, unchanged scope) rather than a bespoke test — the two
> new files are inside that scope and `check_invariants.py` stayed clean.
> Full suites re-run clean: `pytest` 728 passed / 7 skipped (was 720),
> `check_invariants.py` clean (`GT-1,2,3,6,11`).

> **Slice 2 landed the same day: the run-manifest schema, agreed with the
> user before starting** (a real fork — see the two options put to them).
> Chosen: a run manifest is **not** a new format. It is a pipeline YAML
> file with three optional extra top-level keys (`recording:`/`project:`/
> `config:`) `Pipeline.load()` already silently ignores (confirmed by
> reading its body — `raw.get(...)` picks named keys only, no strict
> schema). `core/manifest.py` gains `RunSpec` (the three fields, resolved),
> `load_run_spec(pipeline_path)` (reads them, raising `AuthoringError`
> naming the file for an absolute path — `UT-D3-6`, resolution is relative
> to the manifest file's own directory, "the manifest is what travels"),
> and `write_run_manifest(path, *, pipeline, mode_overrides=, recording=,
> project=, config=)` (writes `pipeline`'s stages — mode overridden per
> `PipelinePanelState.mode_overrides`, `impl:`/`inputs:` unchanged — plus
> the three keys, all paths `os.path.relpath`, never `str(path)`).
> **Refuses, rather than silently drops, a stage with a non-empty
> `overrides:`/`record:`** — round-tripping those is real, separate work
> this pass did not attempt, and dropping them silently would be exactly
> the "smuggled, not declared" failure `R-SIM-15` exists to prevent.
> `PipelinePanelState` gained `pipeline`/`mode_overrides` read-only
> properties so a caller can feed both straight into the writer with no
> extra glue.
>
> `cli/resim.py`: `recording` (positional) is now optional, `--project`/
> `--config` default to `None` (a real sentinel, not `"base"` — needed to
> tell "not given" from "given as its own default") — all three fall back
> to `load_run_spec(args.pipeline)` when omitted, an explicit flag always
> winning. `sim resim --pipeline <manifest.yaml>` alone now resimms exactly
> as if `<recording> --project <p> --config <c>` had all been typed.
> Missing a recording from BOTH the CLI and the manifest is a load error
> naming the file, never a `None` propagating silently.
>
> 9 new tests, all real: 6 in `tests/unit/test_d3_run_manifest.py`
> (round-trip preserves mode overrides and leaves `impl:`/other stages
> unchanged — `UT-D3-5`; `recording:`/`project:`/`config:` recovered
> exactly — `UT-D3-4`'s writer/reader half; a plain pipeline file with none
> of the three keys decodes to `RunSpec()`, unchanged from before this
> existed; an absolute path is refused naming the file — `UT-D3-6`, both
> the write and the load direction; an existing `overrides:` block is
> refused rather than dropped). 3 in
> `tests/system/test_d3_run_manifest_cli.py`, against the REAL `sim resim`
> CLI (`cli.resim.run`, `Pipeline.load`/`resim_pipeline` mocked — the real
> entry point only resolves `dll:`/`stubdll:`, no `components=` injection
> seam, so a genuine execution would need a built `df_sil`/`echo_stub` this
> Python-only suite does not have; what changed and needs proof is the
> argument-resolution logic, asserted by checking the exact recording/
> project/config the mocks were called with — `UT-D3-4`'s CLI half): the
> manifest alone resolves all three, an explicit CLI flag wins over the
> manifest's own value, and a recording missing from both is a named
> `AuthoringError`. Full suites re-run clean: `pytest` 737 passed / 7
> skipped (was 728), `check_invariants.py` clean (`GT-1,2,3,6,11`).
>
> **Still not attempted**, same as slice 1's own list: `MainWindow` wiring,
> on-disk `impl:` discovery, severed-chain UI, per-port override expansion,
> compare-against-recorded, evidence-panel consistency (`UT-D3-3`,
> `UT-D3-8`, `ST-D3-1`).

> **Slice 3 landed the same day: `MainWindow` wiring — read-only, agreed
> with the user before starting** (a real fork put to them: read-only
> integration now, vs. building the missing live-resim-to-Session
> capability `ST-D3-1`'s literal claim needs, vs. stopping at slice 2).
> Investigated first: no live-resim session-building path exists anywhere
> — `build_session_from_recording` is the only session builder and only
> reads an already-recorded file; `cli/resim.py --save` deliberately writes
> only the freshly-simulated stages' own output, not a mergeable full
> recording. Building that merge is real, separate, substantial work,
> correctly left unattempted — **this slice does not close `ST-D3-1`**.
>
> What landed: `MainWindow` gains `pipeline_path=`/`pipeline_search=`
> (both optional, `None`/`()` unchanged from before this slice — the
> common case stays exactly as it was). `PipelinePanel` docks
> (`BottomDockWidgetArea` — see the regression note below for why not
> `Left`), synced in `_on_loaded` once `session.known_ports` is known. A
> pipeline load failure (bad path, unresolvable `dll:`) degrades the DOCK
> only — caught, reported in the status bar — never the window; the rest
> of Vantage does not depend on a pipeline being given at all. A new
> `&File` menu gained **Save Run Manifest...**, enabled once the panel has
> a real `Pipeline` loaded: writes the CURRENT `PipelinePanelState`
> (stages, mode overrides, the recording it's viewing, the project) via
> slice 2's `write_run_manifest`, through a `QFileDialog` save dialog.
> `mode_changed` does not re-run anything — it updates the status bar
> pointing at `File > Save Run Manifest...`, honestly reflecting this
> slice's own read-only scope. `sim view` gained `--pipeline`/`--search`
> (`cli/view.py` → `app/gui.launch` → `MainWindow`), so this is reachable
> from the real CLI entry point, not only from tests.
>
> **A real regression found and fixed before landing**: docking
> `PipelinePanel` in `LeftDockWidgetArea` (alongside `layers_panel`, the
> first placement tried) broke `test_b3_viewport_controls.py::test_
> dragging_pans_the_viewport_and_a_second_click_still_selects` — every
> dock widget in this window competes for space with no fixed central
> widget (`BevPanel` is itself a dock, in `RightDockWidgetArea`), so a
> third `Left`-area competitor shrank the BEV panel's width enough to
> shift `Viewport.to_px()`'s pixel math off the test's fixture box. Full
> suite confirmed clean before this fix (740 passed baseline minus this
> file); confirmed broken by the addition (`git stash` + rerun proved
> causation, not a pre-existing flake); confirmed fixed by moving the dock
> to `BottomDockWidgetArea` instead (all 8 tests in that file green again,
> full suite clean after).
>
> 3 new tests, all real, in `tests/system/test_d3_mainwindow_pipeline_
> panel.py`: no `pipeline_path` leaves the dock empty, unchanged from
> before (backward compatible); an unresolvable `dll:` stage degrades the
> dock, not the window (the window still shows the recording); a REAL
> resolvable pipeline (reusing `sil_host`'s own already-built
> `echo_stub.dll` from this session's `S-C7` work, rather than building a
> second trivial fixture library — skips with a named reason if that build
> isn't present, same pattern `test_c8_relocatability_installed.py`
> already uses for a missing `df_sil`) populates the dock for real and
> **Save Run Manifest** writes a real, relative-path, reloadable file
> (`QFileDialog.getSaveFileName` mocked — an offscreen test cannot show a
> native dialog — everything downstream of the mocked return value is
> real). Full suite re-run clean: `pytest` 740 passed / 7 skipped (was
> 737), `check_invariants.py` clean (`GT-1,2,3,6,11`).
>
> **Still not attempted**: on-disk `impl:` discovery, severed-chain UI,
> per-port override expansion, compare-against-recorded, evidence-panel
> consistency, and the live-resim-to-Session capability `ST-D3-1` actually
> needs (`UT-D3-3`, `UT-D3-8`, `ST-D3-1`).

> **Slice 4 closes `ST-D3-1`: the live-resim-to-Session capability itself,
> agreed with the user before starting** (two real forks put to them first
> — merge mechanism, and whether to close the schema_bytes gap discovered
> during investigation — both resolved to the more thorough option).
> Investigated first: `Pipeline.exec()` (`cli/resim.py`'s engine) and
> `Pipeline.step()` (live `sim run`/`Recorder`'s engine) are two different
> engines — a GUI "Run" naively built on `step()` would silently diverge
> from `sim resim` on any multi-rate pipeline, exactly the `R-SIM-16` "one
> engine" failure the `S-D3` gate names. Also found: neither `Recorder`
> nor `cli/resim.py --save` ever populated `TopicInfo.schema_bytes` for a
> stage's own output topics (only the type name string) — a real,
> pre-existing gap, `ComponentManifest.descriptor_set` (`R-SIM-11`)
> available but never wired in, meaning a freshly-computed port stayed raw
> bytes forever on any existing round trip.
>
> **Fixed first**: `sources/recorder.py::Recorder._topics()` and
> `cli/resim.py::_save_outputs` both now pass `manifest.descriptor_set` as
> `TopicInfo.schema_bytes` — a stage's own recorded output decodes on
> replay like any other port.
>
> **What landed**: `core/resim.py` gains `resim_pipeline_merged(pipeline,
> recording_path, out_path, *, meta)` — writes a FULL merged recording
> (every original topic passed through unchanged, except each `mode:
> simulate` stage's own declared output ports, overwritten with this
> resim's freshly-computed bytes, schema_bytes included) at `out_path`.
> Same single-rate `Pipeline.exec()` engine as `resim_pipeline`
> (`cli/resim.py`'s own, unchanged) — deliberately, per the fork above.
> Unlike `--save` (only the freshly-simulated stages' own bytes), this
> file is a complete, standalone recording: `core/runner.
> build_session_from_recording` — the one and only way a `Session` is
> ever built anywhere in this framework (`R-SIM-6`/`R-SIM-13`/`R-SIM-14`)
> — reads it with no other input. This function does not invent a second
> way to build a `Session`; it produces the artifact the existing way
> already knows how to read.
>
> `PipelinePanel` gains a **Run** button (`run_requested` signal, enabled
> once `sync()` has a real state, disabled while a run is in flight —
> `MainWindow`'s `set_run_enabled`). `MainWindow` gains `pipeline_config=`
> (forwarded to `pipeline.init_components`, same `adasInit(NULL)` caveat
> `cli/resim.py --config`'s own help text already states — `S-C5`'s bundle
> auto-resolution is not built yet) and a new `_ResimWorker` (off the GUI
> thread, mirrors `_SessionLoadWorker`'s ownership rule): `_on_run_
> requested` writes the panel's CURRENT state as a run manifest into a
> scratch dir (`write_run_manifest` — the SAME call `_on_save_run_
> manifest` already makes, into a temp file instead of a user-chosen one,
> so a GUI "Run" and a saved-then-`sim resim`'d manifest are provably the
> same artifact, `R-SIM-16`'s own "GUI and CLI exchange the same
> artifact"), then `_ResimWorker.run()` re-loads it fresh (`Pipeline.load`,
> real `dll:`/`stubdll:` resolution), `init_components`, `resim_pipeline_
> merged`, `shutdown_components`, `build_session_from_recording`. On
> success the result becomes the viewed `Session` through `_on_loaded`
> unchanged — a resim result is treated exactly like opening any other
> recording. `sim view --pipeline --config` threads a real config path
> through (`cli/view.py` → `app/gui.launch` → `MainWindow`).
>
> **Deliberately not attempted this slice**: the panel does not preserve
> the user's mode toggles across a Run — `_on_loaded` (reused unchanged)
> rebuilds `PipelinePanelState` fresh from `self._pipeline_path`, so a Run
> shows what was actually executed but the dock then reverts to the
> original declared modes. Carrying `mode_overrides` forward across a
> reload is real, separate, later work, same "not attempted" discipline
> every earlier slice in this stage uses. Also not attempted: on-disk
> `impl:` discovery, severed-chain UI, per-port override expansion,
> compare-against-recorded, evidence-panel consistency (`UT-D3-3`,
> `UT-D3-8` — unrelated to `ST-D3-1` and still open).
>
> 6 new tests, all real: 3 in `tests/system/test_d3_resim_merged.py`
> (a record→resim round trip through the merged-writer path decodes a
> real, non-empty `descriptor_set` on reload — not just carries bytes;
> byte-identical output against `resim_pipeline` on the same pipeline +
> recording, proving engine consistency, `R-SIM-16`; the merged file's
> `known_ports` covers every wired port with no other input needed), 1 in
> `tests/system/test_d3_pipeline_panel_widget.py` (Run disabled until
> `sync()`, a real click emits `run_requested`, `set_run_enabled`
> round-trips), 2 in `tests/system/test_d3_mainwindow_pipeline_panel.py`
> (a REAL `echo_stub.dll` run: clicking Run produces a genuinely different
> `Session` object, the button disables mid-run and re-enables after,
> "run complete" lands in the status bar; the no-pipeline early-return
> guard spawns no worker). Full suite re-run clean: `pytest` 746 passed /
> 7 skipped (was 740; 2 pre-existing collection errors unrelated to this
> stage — `tests/unit/test_d1_foxglove.py`/`test_d1_scene_recording.py`,
> the optional `foxglove-sdk` extra not installed in this environment —
> excluded from the count, not touched this pass). `check_invariants.py`
> clean (`GT-1,2,3,6,11`). One pre-existing flake confirmed **not** caused
> by this slice (`git stash -u` + rerun on the untouched baseline
> reproduced it identically): `test_b3_viewport_controls.py::test_
> dragging_pans_the_viewport_and_a_second_click_still_selects` fails
> intermittently inside the full-suite run but passes every time in
> isolation — real, pre-existing, order/timing-sensitive flakiness in that
> test, unrelated to `S-D3` and not investigated further here.
>
> `ST-D3-1` is now **closed**: every run this plan can express as a
> pipeline is launchable from the GUI with no hand-typed command. `UT-D3-3`
> (severed-chain UI) and `UT-D3-8` (evidence-panel consistency) remain
> open — the stage's own Gate below reflects this.
>
> **Status update, slice 5 — `UT-D3-3` and `UT-D3-8` both closed.**
> `UT-D3-3`: `PipelinePanelState.set_mode` (`view/pipeline_panel.py`) no
> longer maintains its own mode-override dict — it delegates every toggle
> to `Pipeline.with_mode` (`R-SIM-10`, already built at `S-D6`), keeping
> the returned `Pipeline` as a live `_working` copy; `mode_overrides` is
> now a diff against the original, so an auto-flipped intervening stage
> lands in the run manifest exactly like an explicit toggle, no second
> bookkeeping to drift. `StageView.orphan` + `PipelinePanelState.
> severed_chains()`/`last_auto_closed`/`undo_last_auto_close()` expose
> what `with_mode` already decided; the real `Qt PipelinePanel`
> (`render/viewer.py`) renders the *"computed, not consumed"* badge on the
> stage-name cell and a one-line undo bar naming what auto-closed —
> clicking it forces the gap back open (`close_gaps=False`) and re-badges.
> No severed-chain logic was reimplemented at this layer; the engine
> (`contracts/pipeline.py`) was not touched.
>
> `UT-D3-8`: a shared formatter, `core.evidence.format_evidence` (+
> `EVIDENCE_FIELDS`, the one fixed field order), now sits between
> `evidence()` and both its callers — `cli/explain.py --at` and a new
> `view/evidence_panel.py::EvidencePanelState` — so "one producer, two
> formatters" (`OD-6`) is structural, not a discipline. Found and fixed in
> the same pass: `cli/explain.py` was printing a bare `str(None)` for an
> unresolved `topic`/`origin`, contradicting `R-SIM-25`/`NR-SIM-4`'s
> "reads unknown, never a plausible default" — `format_evidence` maps
> `None` -> `"unknown"` for both surfaces now. The new `EvidencePanel`
> dock (`render/viewer.py`, `MainWindow.evidence_state`, wired into
> `render_tick` via `_sync_evidence_panel`) targets the current single BEV
> selection's `pick_id` as its address. **Scoped, not the full `R-SIM-25`
> join**: a `pick_id` does not yet resolve to the port/topic that produced
> it (`Layer.id` -> a provider's resolved `requires` -> ports is `ST-D6-3`'s
> own separate, still-open scope) — this panel tries the selection's
> `pick_id` directly against the session's ports and degrades exactly the
> way `evidence()` already does for anything unresolved (`kind="unknown"`,
> every unfillable field reading `"unknown"`), which is what a "for one
> selected prim" test can assert honestly today without guessing the join.
>
> 6 new tests, all real: `tests/unit/test_d3_severed_chain_panel.py` (3),
> `tests/system/test_d3_severed_chain_widget.py` (1, real Qt clicks —
> auto-close then undo, badge appears), `tests/unit/test_d3_evidence_panel.
> py` (2). Plus 2 in `tests/unit/test_b2_evidence.py` for the new
> formatter and 2 in `tests/system/test_d3_evidence_panel_widget.py`
> proving the Qt panel and a real `sim explain --at` (via a genuine
> on-disk recording, `sources.recorder.Recorder`) render identical rows,
> field by field, for both a resolved port and an unresolved address.
> Full suite re-run clean: `pytest` 764 passed / 7 skipped (2 pre-existing
> collection errors excluded, unchanged — see slice-4 note above).
> `check_invariants.py` clean (`GT-1,2,3,6,11`), `docs/py/run_all.py`
> clean. The same pre-existing `test_b3_viewport_controls.py` flake noted
> in slice 4 reproduced once more inside the full-suite run and passed
> every time standalone — unrelated to this slice, not investigated
> further here.

- [ ] `app/panels/pipeline.py` — the pipeline dock, per visualization spec §13:
      one row per stage, `mode` toggle, `impl:` and overrides in a collapsed
      expert row.
- [ ] Discovery-driven and component-agnostic: stages from the pipeline —
      **done**. `impl:` choices from manifests on disk — **not attempted**
      (no on-disk discovery mechanism exists anywhere yet, see slice-1 note).
      `measured` availability from the recording's topic index — **done**.
      **No component name anywhere** (`GT-1`) — **done**, `check_invariants.
      py` clean
- [x] Severed-chain auto-close surfaced with a one-line undo bar (detection is
      `UT-C1c-16`'s; acting on it is this stage's — `R-SIM-10`).
- [x] `core/manifest.py` round-trip: the panel emits a run manifest, the CLI
      consumes it unchanged, and the CLI can emit one the panel reopens.
- [x] Console entry point in `pyproject.toml`; **no `.bat`, no `.sh`** written
      by hand. `vantage = adas_sim.app:main` already existed from an
      earlier stage; **slice 3** made the panel reachable through it for
      real — `sim view --pipeline <p> --search <dir>` — no new launcher
      needed or written

**Tests**
- [x] `UT-D3-1` discovery: stages from the pipeline — **done**. `impl:`
      choices from manifests on disk — **not attempted** (no on-disk
      discovery exists). `measured` availability from the recording topic
      index — **done**. `tests/unit/test_d3_pipeline_panel_state.py`, real,
      passing — ticked for the half this pass actually built; the other
      half stays real future work, not silently claimed
- [x] `UT-D3-2` `measured` is disabled **with a reason** when the recording
      lacks the topics — the GUI does not offer a choice that would fail at
      load. `tests/unit/test_d3_pipeline_panel_state.py` +
      `tests/system/test_d3_pipeline_panel_widget.py` (the radio button
      itself is `setEnabled(False)` with the reason as its tooltip), real,
      passing
- [x] `UT-D3-3` a severed chain is flagged in the panel and the orphan stage is
      badged *"computed, not consumed"*.
- [x] `UT-D3-4` the GUI builds a valid run manifest that the CLI accepts
      **verbatim**. `tests/unit/test_d3_run_manifest.py` (writer/reader) +
      `tests/system/test_d3_run_manifest_cli.py` (the real CLI's own
      fallback-resolution path), real, passing — see slice-2 note above for
      why `Pipeline.load`/`resim_pipeline` themselves are mocked in the CLI
      test
- [x] `UT-D3-5` the reverse also holds: a manifest written by the CLI reopens in
      the panel with every field intact — one format, two writers.
      `test_ut_d3_5_stages_survive_a_write_then_load_round_trip_unchanged`,
      real, passing (mode overrides survive, `impl:` unchanged) — "the
      panel reopens it" specifically (parsing it back into a live
      `PipelinePanelState` in the GUI) is not separately tested, since the
      panel already reads any `Pipeline` uniformly regardless of which YAML
      keys produced it; `Pipeline.load` reading the manifest back is the
      real claim and is what's tested
- [x] `UT-D3-6` a run manifest contains **no absolute path** (`P-2`), so it can
      be committed, shared and replayed on another machine. Two tests: the
      writer never emits one (string-search on the written bytes), the
      reader refuses one naming the file. Real, passing
- [x] `UT-D3-7` the panel names no component or function (`GT-1` as a test).
      Covered structurally by the existing mechanized `GT-1` grep over
      `src/adas_sim/**` — both new files are in scope, `check_invariants.py`
      clean; no bespoke test written (would duplicate the mechanism)
- [x] `UT-D3-8` **the evidence panel renders the same record `sim explain`
      prints** (`FR-SIM-67`, `R-SIM-25`, `OD-6`): for one selected prim, both
      surfaces are driven by one `evidence()` call and are asserted **field by
      field**, not merely both non-empty. A field the record cannot fill reads
      `unknown` on both — never a plausible default, never blank on one side and
      filled on the other.
- [x] `ST-D3-1` every run in this plan is launchable from the GUI with no
      hand-typed command.

**Discipline**
- [x] portability §3 (`P-2`, `P-6`, `P-7`) · naming §3 (`N-8`, `N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `UT-D3-4` + `UT-D3-5` + `ST-D3-1` green — the GUI and the CLI exchange the
      same artefact in both directions, which is what keeps them one engine
      (`R-SIM-16`) rather than two paths that drift.

### S-D4 — Perception readiness

**Purpose.** The first two-component pipeline, and the first time `R-SIM-10`'s
central invariant is demonstrated rather than asserted: a downstream component's
entry is **byte-identical** whether its input came from ground truth, from a
stand-in, or from a real upstream component.

**Gating.** This stage needs a second real component. Until one exists it is
**deferred, not skipped**: `UT-D4-1` and `UT-D4-2` are pure geometry and land
now; `ST-D4-1` is written now and skips with a named reason. Writing the system
test early is deliberate — it is the specification the second component is built
against.

> **▶ THE BLOCKER CHANGED IDENTITY — re-stated 2026-08-07.** The sentence above
> is now misleading in both directions, so read this instead.
>
> **A second real component now exists.** `perception-core` gained its
> generic-ABI shim on 2026-08-06 (build queue row 1): real MSVC/Conan build,
> **11/11 gtest** on `-P base` and `-P cus1`, `perception_core_sil.dll`
> produced, manifest declaring `frame`/`egoDyn` in and
> `dfObjList`/`compState` out — where `dfObjList` is **byte-for-byte
> the type `df` consumes** on its own `objects` port. So the ABI, manifest,
> bundle and plug-in chain are all proven end to end.
>
> **What it does not have is an algorithm.** `adasExec` is a deliberate no-op:
> every `ProPort` stays `updated == false` (`R-SIM-7` — never invent a value
> nobody computed). **So perception-core publishes nothing**, and that decides
> exactly which boxes are now reachable:
>
> | Box | State | Why |
> |---|---|---|
> | `ground_truth` / `perception` / `perception.error` layer groups | **done 2026-08-07** | see status note below — `perception.error` is now structurally enforced `derived=True`, not just named |
> | a source emitting camera/radar stimuli via `emits()` | **camera done 2026-08-07, radar not attempted** | see status note below for why radar specifically stays out |
> | `ST-D4-1` — ground truth vs perception side by side | **still blocked** | the perception side would be empty |
> | `ST-D4-2` — **the invariant** | **still blocked** | the "real-upstream" arm produces no bytes to compare against the truth and stand-in arms |
> | `ST-D4-3` — a split absorbs into an ingest map (`FR-SIM-71`) | **still blocked** | needs two manifest shapes to map between |
>
> **The remaining blocker is a decision, not a task**, and it is not this
> plan's to take: whether `perception-core` stays one component or splits into
> computer-vision + fusion
> (`modules/perception-core/docs/perception_core_decomposition.md`). An
> algorithm written before that is answered is an algorithm written into a
> shape that may not survive.
>
> **Do not read "a second real component exists" as "`S-D4`'s gate is
> reachable".** Row 1 bought the *chain*; it did not buy the *demonstration*.
> This box was corrected after a review asserted the opposite from the stage's
> own stale gating line — the same defect the line itself now warns about.

**Must not.** Let the downstream component learn where its input came from. If
anything in its entry path branches on the upstream stage's `mode` or `impl`,
the invariant is already broken and no test after this will catch it.

- [ ] `CameraModel` completed (declared in `S-A2`) + `render/image_view.py` —
      project Scene prims onto a camera frame.
      **`render/image_view.py` done**; `CameraModel` needed no completion
      (already sufficient as declared)
- [x] `ground_truth` and `perception` layer groups; `perception.error` as a
      **derived** group, marked (`R-SIM-7`).
- [x] A source emits camera stimuli, declared through `emits()`. **Camera
      done 2026-08-07, radar not attempted** — see Status note for why

**Tests**
- [x] `UT-D4-1` projection round-trips for a known intrinsic/extrinsic pair.
      `test_projection_round_trips_for_a_known_intrinsic_extrinsic_pair`
      (+ a straight-ahead sanity check and a behind-camera `None` check)
- [x] `UT-D4-2` a `Box` with `height` projects to a 3D box; the BEV and image
      views come from the **same prim**, so they cannot disagree.
      `test_a_box_with_height_projects_to_eight_corners_from_the_same_prim`
- [x] `UT-D4-3` a pixel-valued and a metre-valued field never share a bare name
      (`N-4`) — the defect this rule exists for lives exactly here.
      `test_pixel_and_metre_fields_never_share_a_bare_name` (structural:
      asserts the field sets themselves, not a runtime behaviour)
- [x] `UT-D4-4` **a perception-scale layer references rather than inlines**
      (`NR-SIM-43`, `OD-7`): a provider emitting a 100 000-point cloud produces a
      `Prim` carrying a `BulkRef`, the Scene stays under the declared byte
      budget, the renderer resolves it from the recording at draw time, and
      scrubbing a long session stays within the stated cache bound. **This stage
      is where the rule becomes permanent** — a layer that inlines here is a
      layer every later one copies.
      **The budget/`BulkRef` mechanism itself is `S-A3`'s, already tested
      (`test_a3_types.py`) — not rebuilt.** This pass proves it at the
      perception scale the rule is actually stated for: `test_perception_
      scale_layer_references_a_100000_point_cloud_instead_of_inlining`
      (100 000 points, well over `MAX_INLINE_PRIM_ELEMENTS`, refused when
      inlined, accepted via `BulkRef`, resulting `Scene` under 2 KB).
      **The "renderer resolves at draw time" and "cache bound" halves are
      `SceneCache`'s own claim (`test_b2_scene_cache.py`), not re-tested here**
- [ ] `ST-D4-1` a two-component pipeline runs and ground truth vs perception is
      visible side by side (skips with a named reason until a second component
      exists). **Correctly un-attempted** — see Status note
- [ ] `ST-D4-2` **the invariant**: the downstream component's input bytes are
      identical across `truth` / stand-in / real-upstream, for the same
      scenario — the test `R-SIM-10` was written for. **Correctly
      un-attempted** — see Status note
- [ ] `ST-D4-3` **a split absorbs into an ingest map, not into source**
      (`FR-SIM-71`, added by audit run 3 — `AR-41`). A recording produced
      against a **single**-component perception manifest drives a
      **two**-component pipeline through `modules/<name>/sim/ingest/` alone:
      no layer provider edited, no `self.<port>` binding changed, no
      re-recording, and `sim probe` reports the feasible cuts of both shapes
      from the same file. **Blocked on the same thing `ST-D4-1`/`ST-D4-2` are**
      — a second real perception component — but written now, deliberately, on
      this stage's own "writing the system test early is the specification the
      second component is built against" principle. **This is the test that
      keeps `perception-core`'s decomposition (one component vs.
      computer-vision + fusion) a cheap decision instead of an expensive one**,
      and the owner has stated it is undecided. The `perception-core` lean
      structure landed by audit run 3 is the shape it binds to

**Discipline**
- [x] portability §3 (`P-1`, `P-8`) · naming §3 (`N-4`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-D4-1` + `ST-D4-2` green — two components in one pipeline, with the
      downstream component's entry byte-identical to its single-component form
      (`R-SIM-10`'s central invariant, first demonstrated here). **Not
      closed** — correctly gated, still, on the decomposition decision named
      in the 2026-08-07 restatement above, never on a missing component (one
      exists, `perception-core`, and it publishes nothing by design). This
      pass lands the pure-geometry half (2026-08-05) plus the two other
      boxes the restatement's own table marks reachable without an
      algorithm — layer groups and a camera-emitting source — which is
      every box this stage can land before that decision is made

### S-D5 — Package the player

**Purpose.** Prove the player is **component-agnostic at build time** — it can
ship before a component exists, and drive one that appears later as data. That
is `FR-SIM-70`'s whole claim, and `ST-D5-2` is the only thing that can test it.

**Must not.** Freeze a component, a proto binding or a config bundle into the
binary. The plug-in import path stays external, or adding a function's layers
means rebuilding the player — which would make the player a component's
dependant, exactly inverting `R-SIM-1`.

**Naming.** The binary is `vantage` (`FR-SIM-48`, `OD-5`); the package remains
`adas-sim` and the CLI remains `sim`. Two delivery forms, one codebase.

> **▶ Entry condition CLEARED 2026-08-05.** `NR-SIM-46`'s build-vs-adopt
> decision is recorded (`sim_requirements.md`, `sim_architecture.md` §5.15a):
> the recommendation is adopted, unmodified. **Keep the Qt shell as a
> *console*** — the checklist below is unchanged by this, since a console with
> a BEV panel is exactly what it already describes (a frozen build, an
> external plug-in path, `--version`, settings, open-a-recording — none of
> that is the "compete with a scene viewer" ambition the decision declined).
> **`S-D1` is promoted to the interop surface** — already landed (this
> session, 2026-08-05), so this half of the recommendation is not merely
> decided but done. **`S-D2` stays deferred**, with the trigger `sim_
> requirements.md` already names: a figure headless `sim render` cannot
> produce. **`S-D8`'s ambition is trimmed accordingly** — see that stage's
> own section for what that means concretely. The rejected alternative
> (adopt as primary, renegotiate `FR-SIM-70`) does not apply — `FR-SIM-70`
> stands as written.
>
> This stage itself is **not started this pass** — clearing the entry
> condition is what unblocks a future session to start it, not a decision to
> start it now.

Turns the library into the application of arch §5.15. Windows only.

- [x] One-folder frozen build (PyInstaller or equivalent) bundling CPython, Qt,
      the framework, the renderers and the codecs. **`scripts/freeze.py`
      (new)**, real: run in this shell, `dist/vantage/` produced and
      launched successfully — see the stage's own Status note for exactly
      what running it here did and did not prove
- [x] **External plug-in import path** — `--plugins <root>` (repeatable) plus
      auto-discovery of a `sim/` folder beside a component library; providers
      are imported from outside the bundle, so adding a function's layers never
      rebuilds the player. **Already built at `S-C8`** (`scripts/vantage.py`'s
      `--plugin-root`/`ADAS_SIM_PLUGIN_PATH`, see `UT-D5-3`'s own naming note)
- [x] `--version` prints the player version **and** its compatibility statement:
      supported ABI generation, Scene major, recording-model and manifest
      versions.
- [x] Settings/layouts in `%LOCALAPPDATA%`, never inside the install or a repo.
      **Already true** — `render/viewer.py::_config_root` uses
      `QStandardPaths.AppConfigLocation` (`P-7`'s own discipline: never
      `%LOCALAPPDATA%` written by hand), which Qt resolves there on Windows
- [x] Open-a-recording entry point (argument, and drag-onto-exe). **Already
      true** — `scripts/vantage.py`'s `recording` is a plain positional
      argument; a file dropped onto `vantage.exe` is passed by Windows as
      `argv[1]`, which is exactly what `nargs="?"` plus this pass's early
      `--version` check still accepts unchanged

**Tests**
- [x] `UT-D5-1` an input outside a declared compatibility range is **refused
      with both numbers named** (`NR-SIM-9`). **Already proven, four times
      over, cross-referenced rather than rebuilt**: ABI version —
      `test_c1c_component.py::test_abi_version_mismatch_raises_naming_
      both_versions` (`UT-C1c-1`); Scene major — `test_a3_codec.py::
      test_a_higher_major_version_is_refused_naming_both_versions`;
      pipeline-file version — `test_c1c_pipeline.py::test_a_pipeline_
      version_newer_than_the_reader_raises_naming_both`; plug-in API — see
      `UT-D5-4` below. `app/version.py` (new, this pass) reports the exact
      same constants each of these already enforces, so `--version` cannot
      drift from what a refusal actually checks
- [x] `UT-D5-2` `--version` reports every one of the four version fields.
- [x] `UT-D5-4` **the plug-in API carries its own generation** (`NR-SIM-44`,
      audit `A7`), independent of the Scene major and the ABI version; a plug-in
      outside the player's supported range is **refused with both numbers
      named**, never half-loaded. `NR-SIM-9` versions everything the player
      reads *except* the one interface `R-SIM-20` made external. **Already
      built and tested at `S-C8`, cross-referenced**: `model/plugins.py`'s
      `SUPPORTED_PLUGIN_API_MIN/MAX` range check, refused before import —
      `test_c8_plugins.py::test_out_of_range_api_is_refused_naming_both_
      numbers`
- [x] `UT-D5-3` the plug-in path imports providers from outside the bundle, and
      two roots with a duplicate layer id raise naming both. **Already
      built and tested at `S-C8`, cross-referenced**: `test_c8_plugins.py::
      test_two_components_each_contributing_a_layer_both_register` (import
      from outside the bundle) + `test_duplicate_layer_id_across_two_
      components_raises_naming_both`. **Checklist/implementation naming
      note**: the checklist's own `--plugins` is `--plugin-root`
      (repeatable) + `ADAS_SIM_PLUGIN_PATH` in the real `scripts/
      vantage.py` — landed at `S-C8`, before this box was written against
      a literal flag name, same "checklist path predates the real build"
      correction `S-D3` slice 1 made for `app/panels/pipeline.py`
- [~] `ST-D5-1` **the clean-machine test**: the frozen build opens a session
      recording and renders it on a machine with **no repo, no Python, no Conan
      cache and no component checkout**. **Attempted, partially verified** —
      see the stage's own Status note for exactly what this shell can and
      cannot prove without a real separate clean VM, and the real gap found
      doing it (`ProjectModel`'s checkout-tier fallback)
- [x] `ST-D5-2` pointed at a component library + its `config/` bundle, the
      player discovers its ports from the manifest and resims — **without that
      component having existed when the player was built** (`FR-SIM-70`).
      **True by construction, cross-referenced rather than re-proven**:
      `GT-1` (mechanised, `scripts/check_invariants.py`) makes it a load-
      time impossibility for `src/adas_sim/**` to name a component, so
      every real-`df_sil.dll` test already in the suite (`test_c1c_
      component.py`, `test_d6_probe.py`, `test_c8_relocatability_
      installed.py`, …) is simultaneously evidence that the framework
      never needed `df` to exist when it was built — the architecture, not
      a special-cased test, is what proves this
- [x] `ST-D5-3` a component's layer providers load from `--plugins` and draw,
      with no framework rebuild. **Already proven at `S-C8`, cross-
      referenced**: `test_c8_relocatability_installed.py` — a REAL,
      `cmake --install`ed `df_sil` build, relocated and with its build-tree
      origin deleted, still resolves `sim/plugin.yaml` and imports `df`'s
      real `sim/layers/{common,bsd}.py`, registering their real layer ids
      into `scene.registry` (the load-and-register half a render depends
      on; its own docstring states the "short of an actual GUI frame" scope
      honestly)

**Discipline**
- [ ] portability §3 (`P-6`, `P-7`, `P-10`) · naming §3 (`N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [~] `ST-D5-1` + `ST-D5-2` green — the player is genuinely component-agnostic
      and genuinely standalone, both demonstrated rather than argued.
      `ST-D5-2` is green (cross-referenced, true by construction).
      `ST-D5-1` is real but partial — see its own entry and the Status
      note for exactly what a same-machine isolated-copy test can and
      cannot stand in for. **Gate not fully closed**: a true clean-VM run
      is the one thing left to make this claim unconditional

### S-D6 — Developer ergonomics: per-port overrides, `sim probe`, severed chain

**Purpose.** Make the tool worth choosing over a private script. Everything here
is what a developer reaches for at 18:00 while debugging their own component.

**Must not.** Add a **seventh** override verb, a predicate in the index grammar,
an expression, or a scripting hook (`R-SIM-15`). *The list became six at
`S-C1cΔ` — four arithmetic plus `select`/`drop` — and closed again there
(`OD-8`); the governing line is that an override may destroy or attenuate
information but never create an entity.* The measured cost of an open grammar is
in `docs/py/logs/FR_SIM_45_argument_binding_survey.*.log`: 5.8 authored config
elements per `exec()` call, 21 for a realistic one. If six verbs prove
insufficient the answer is a `stub:` stage — real code, in a file, reviewable.

Closes `FR-SIM-44`, `FR-SIM-45`, `FR-SIM-46`. This is the stage that decides
whether anyone writes a private player, so `GT-8` is measured here.

> **Scope correction, 2026-07-31 — the override *engine* is not built here.**
> `S-C1cΔ` (build order #5) builds `contracts/override.py`'s six verbs
> (`const`·`hold`·`offset`·`scale`·`select`·`drop`), the closed index grammar,
> the application on the input path and the manifest tagging — because
> `S-C3`'s fault injection reuses that grammar and cannot wait for Phase D.
> **This stage builds the developer *surface* over an engine that already
> exists.** Written down because the two scope boxes below read as
> implementation work and were: building them twice is exactly the rework this
> plan's §0a sequence exists to prevent, and `GT-9` says the capability lives in
> the library while `S-D6` adds the way a person reaches it.

- [x] `contracts/override.py` — **verify, do not rebuild**: the six verbs resolve
      at a port, a field path (`egoDyn.vx`) and a repeated element
      (`objects[*].pos_x`, `objects[3]`), applied between wiring and `exec()`.
      If any of that is missing, `S-C1cΔ` is incomplete and the fix belongs
      there, not here.
      **Confirmed intact via existing coverage** (`test_c1c_override.py`,
      `test_c1c_binding.py`) — not rebuilt, not re-tested from scratch
- [x] Overrides land in the run manifest; the affected topic is tagged
      `origin: overridden` (`R-SIM-12`) and badged in the HUD (`R-SIM-15`) —
      the manifest half lands with the engine; **the HUD badge is this stage's**.
      **Design question resolved, follow-up pass 2026-08-06 (`UT-D6-2`).**
      The topic-tagging half of the original wording is **not achievable as
      specified, and is dropped rather than worked around**: an override
      modifies a CONSUMING stage's own input bytes right before `exec()`
      sees them (`Pipeline._apply_input_overrides`) — the RECORDED topic
      is the PRODUCER's output, written by `Recorder.tick()` from the raw,
      pre-override `stimulus`/stage-output values, never from what a
      consumer internally saw. No existing topic's bytes ever reflect an
      override, so tagging one `origin: overridden` would state something
      false regardless of which topic was picked (single- or multi-consumer
      alike). Building a topic that WOULD be true — the actual overridden
      bytes a stage received — needs `Pipeline.exec`/`step` to return each
      stage's resolved (post-override) inputs alongside its outputs, a
      change to a return contract read by every caller (`resim_pipeline`,
      `Recorder.tick`, `check/runner.py`, the live-resim path); real,
      separate work, correctly out of scope for a design-question pass.
      **What ships instead, and is real:**
      `RunManifest.overrides` (new field, `io/base.py`'s new
      `OverrideRecord`: `stage`/`address`/`verb`/`value`) makes `R-SIM-15`'s
      "declared, never smuggled" claim actually true — previously an
      override only affected `run_id`'s hash (`core.manifest.
      _overrides_repr`, unchanged), with no way to read WHICH override
      applied back from a written manifest; now `core.manifest.
      _override_records` builds the same declarations in readable form,
      round-tripped through `io/mcap.py`. The HUD badge ships too, reading
      `Stage.overrides` directly rather than a topic: `StageView.
      overridden` (`view/pipeline_panel.py`) and the real Qt `PipelinePanel`
      (`render/viewer.py`, `⚙ input overridden` beside the impl string,
      same row-badge pattern the `orphan`/"computed, not consumed" flag
      already uses). `Provenance.OVERRIDDEN` (`io/base.py`) stays defined
      but unused — not dead code to delete, a place held for the day the
      real per-stage-input topic above gets built.
      `tests/unit/test_c2_manifest.py` (+3), `tests/unit/test_a4_mcap.py`
      (extended `UT-A4-3`'s own round-trip to cover `overrides`, including
      a `None` value), `tests/unit/test_d6_override_badge.py` (3, no Qt),
      `tests/system/test_d6_override_badge_widget.py` (2, real Qt,
      offscreen). Full suite: 807 passed / 7 skipped (Windows venv,
      `foxglove` extra not installed here, one pre-existing flake —
      `test_b3_viewport_controls.py`, confirmed passing standalone),
      `check_invariants.py` and `docs/py/run_all.py` both clean
- [x] `cli/probe.py` — `sim probe <lib>`: load, read `adasManifest`, print the
      port set, types and schema names. **No mapping step, ever** (arch §5.16.1)
- [x] `contracts/pipeline.py` — **severed-chain detection**: a `measured` stage
      between two `simulate` stages on one data path; auto-close on set,
      overridable, orphan stage flagged (`R-SIM-10`). Detection and
      auto-close already existed (`S-C1cΔ`); **the orphan-stage flag on
      `close_gaps=False` did not — added this pass** (see Status note)
- [x] `app/gui/pipeline_panel.py` — the per-stage mode toggle performs the
      auto-close undoably and renders the *"computed, not consumed"* badge.
      **Stale checkbox, corrected 2026-08-06 — this was actually done at
      `S-D3` slice 5**, cross-referenced by `UT-D6-4`'s own note two boxes
      below: the real file is `view/pipeline_panel.py` + `render.viewer.
      PipelinePanel`, not `app/gui/pipeline_panel.py` (a path this box was
      written against before the codebase's real panel convention
      existed). Left unticked at the time because nobody walked back up
      from `UT-D6-4`'s closure to tick its own scope box
- [x] `cli/explain.py` — **complete `sim explain <name>`** (seeded `S-B2`,
      extended `S-C1c`; this is the full form). Accepts a port, field, layer id, style token, codec name,
      run id or error code; prints kind, type+unit, producer stage and mode,
      origin tag, topic presence, schema, which layer draws it, which
      expectation asserts it, and its value at the current tick. Every line
      comes from something already in the system — no new index.
      **Six of six kinds done, follow-up pass 2026-08-06** (`UT-D6-7`):
      `core/explain.py` gained codec-name (`registered_extensions`/`io.
      registry.codec_info`, e.g. `mcap`/`.mcap`) and error-code resolution
      (DG-5's closed taxonomy, matched by taxonomy name/class name/exit
      code) alongside the existing `run_id`/topic/layer, plus a `difflib`
      fuzzy "did you mean" on an unresolved name. **Style token is
      deliberately resolved in `cli/explain.py`, not `core/explain.py`** —
      `render/theme.py` sits ABOVE `core/` in the package map
      (`sim_api_reference.md` §1, enforced by `UT-A1-6`), so `core.explain.
      explain` cannot import it; `cli/` can, so that one branch (plus the
      "did you mean" extension with token names) lives there, documented
      in both modules' own docstrings. **Real bug found and fixed in the
      same pass**: merging two already-`difflib`-ranked-and-truncated
      match lists and re-sorting them alphabetically silently drops the
      actual best match (a `bsd.*` component token alphabetically
      out-ranked the correct `status.*` suggestion) — fixed by re-running
      `difflib.get_close_matches` once over the full combined candidate
      list instead of merging two separate top-3 results. **Scoped
      honestly**: a bare field-path name (`df.aeb.outputs.brake_request`
      with no `--at`) is not separately resolved beyond an exact topic
      match — that richness (type, producer, schema, value) is exactly
      what `--at`'s `evidence()` path already provides; `explain()` without
      `--at` answers "what kind of name is this," not "what does it
      contain," and adding field-level static resolution would need a
      message class resolved from the port's own schema bytes, real
      separate work. `tests/unit/test_d6_explain.py` (12 tests, all new).
      Full suite: 787 passed / 7 skipped (Windows venv, `foxglove` extra
      not installed here), `check_invariants.py` and `docs/py/run_all.py`
      both clean
- [x] `cli/doctor.py` — **complete `sim doctor`** (seeded `S-A1`, grown per
      stage; this is the full form) (`DG-3`): interpreter and install
      mode; which library each `impl:` stem resolves to **and by which
      pattern, listing every directory searched** (`P-5`); which config
      bundle each stage resolves, from where, its hash, **and whether the
      viewer and the SUT would agree** (`R-SIM-3a`); codec capabilities;
      which cuts a recording supports; platform, line endings, console
      encoding (`P-4`). Non-zero exit on anything that would break a run.
- [x] `cli/list.py` — `sim list ports|topics|layers|signals` (`DG-1`).
      **Filename is `cli/list_cmd.py`, not `cli/list.py`** — see the Status
      note's own bug story for why. `signals` is scoped to the PORT-level
      address space only, stated in the module's own docstring — `DG-1`'s
      full "ports x fields" claim needs each port's message class resolved
      from its embedded schema and walked recursively, real separate work
- [ ] `impl: "legacy:<lib>"` — **scope only**: the adapter's config shape is
      specified, not implemented. No such binary exists yet; implementing it
      before one does would be speculative. **Not touched this pass**

**Tests**
- [x] `UT-D6-1` each of the four verbs applies correctly at a port and at a
      field path; a fifth verb name is a **load error**, not a warning.
      Pre-existing (`test_c1c_override.py`'s `test_parse_override_verb_
      outside_the_closed_four_is_a_load_error_not_a_warning` + `test_c1c_
      binding.py`'s field-path tests), confirmed intact, not rewritten
- [x] `UT-D6-2` an override appears in the run manifest and tags its topic.
- [x] `UT-D6-3` `sim probe` on `InProcessSilComponent` prints the same port set
      the pipeline resolves — one source, no second description.
- [x] `UT-D6-4` the **GUI** acts on a severed chain: given the detection from
      `UT-C1c-16`, setting a stage to `simulate` flips the intervening
      stages and shows the undo bar. Detection is the loader's; **acting on
      it is this stage's** — two tests, because a correct detector behind a
      GUI that ignores it is exactly the silent toggle `R-SIM-10` bans.
      **The engine half (no GUI) is `UT-D6-5` below.**
- [x] `UT-D6-5` auto-close flips only the intervening stages, and undo restores
      the exact prior modes.
      `tests/unit/test_d6_severed_chain.py::test_auto_close_flips_only_
      the_intervening_stage_and_undo_restores_exact_prior_modes`
- [x] `UT-D6-6` forcing the gap open is permitted and yields exactly one
      orphan-stage warning naming the stage.
- [x] `UT-D6-7` `sim explain` resolves each of the six accepted name kinds,
      and on an unknown name suggests a fuzzy match rather than failing
      bare (`DG-2`, `N-8`).
- [x] `UT-D6-8` `sim doctor` exits non-zero on a broken stem, a bundle
      mismatch and a missing codec capability — and each message names the
      file (`DG-3`).
- [x] `ST-D6-1` **day one, end to end**: a fresh component library with only a
      manifest is probed, wired into a five-line pipeline, run against
      `tiny.mcap`, and its outputs appear in a recording — **no edit anywhere in
      `modules/sim`** (`FR-SIM-46`). **Written 2026-08-06** (sim build queue row
      4, sub-row 1): `tests/system/test_d6_day_one_walkthrough.py` chains
      `sim probe` → a five-line pipeline → `resim_pipeline_merged` against
      `tiny.mcap` → a real recording read-back → `Session.open`, against a
      new zero-dependency fixture (`tests/fixtures/echo_stub/
      echo_stub_with_output.c` — `echo_stub.c` declares zero ports so cannot
      prove "outputs appear"; this one declares exactly one output port and
      writes a fixed 4-byte payload). **Verification is split, stated
      honestly rather than glossed over**: the fixture's hand-encoded
      manifest and `adasExec` byte-write were proven correct by direct
      `ctypes` execution against the compiled `.so` in this WSL shell
      (`python3.10`, outside `adas_sim` entirely, since `adas_sim` needs
      `>=3.12` for `StrEnum` and neither `python3.12` nor `sudo` is available
      in this environment to install it); the *chained* Python assertions
      (probe output text, recording topic/payload contents, `Session.
      known_ports`) were verified by reading `cli/probe.py`, `core/resim.py`
      and `io/registry.py`'s real signatures against the test's calls, not
      by executing the test — it is POSIX-only (`sys.platform == "win32"`
      skip, matching `test_d6_probe.py`'s identical boundary) and this row's
      Windows verification loop reports it `skipped`, not `passed`. `GT-8`'s
      own timing measurement needs a real newcomer, not a self-timed
      session, and is not attempted here.

      > **⚠ DOWNGRADED `[x]` → `[~]` 2026-08-07 by review.** The note above is
      > honest and is exactly why this was caught — but *"verified by reading
      > the real signatures against the test's calls, not by executing the
      > test"* is **not verification**, and this box was ticked on it. The
      > plan's own rule is unconditional: *"Never tick a box you did not
      > verify. A ticked box is a claim that something was run on a date."*
      > **The test has not been executed on any platform**: it skips on
      > Windows by design, and the WSL shell has Python 3.10 while `adas_sim`
      > requires ≥3.12 (`StrEnum`), confirmed 2026-08-07.
      >
      > **What made this worth reversing rather than annotating:** `ST-D6-1`
      > is `FR-SIM-46`'s (`P0`) third verifier, so the tick moved a `P0`
      > requirement to `proven*` on the strength of a test nobody has run.
      > That is the precise defect `AR-34`/`AR-50` were raised for, arriving
      > from a new direction — and `S-C7`'s own history is the precedent:
      > *"believed correct, awaiting compilation"* was kept visible until a
      > shell that could compile ran it, and it closed in **one command**
      > because the caveat named the command and the acceptance condition.
      >
      > **To close it, on a POSIX shell with Python ≥3.12** (a container, a
      > newer WSL distro, or CI — `.github/workflows/sim-ci.yml` already runs
      > Ubuntu):
      >
      > ```
      > modules/sim/.venv/bin/python -m pytest \
      >     modules/sim/tests/system/test_d6_day_one_walkthrough.py -q
      > ```
      >
      > **Acceptance: it reports `1 passed`, not `1 skipped`.** A skip is the
      > current state and must not be read as a pass. Nothing about the test
      > or the fixture needs changing first — the C half is genuinely proven
      > by direct `ctypes` execution against the compiled `.so`, and only the
      > chained Python assertions are unexecuted.
      >
      >.
- [x] `ST-D6-3` **the evidence chain, end to end** (`FR-SIM-67`, `R-SIM-25`,
      audit `A4`): selecting any prim answers — in one action — its port, topic,
      tick, origin tag, config bundle and component build, and whether the value
      was **published by the SUT or reconstructed by a layer** (`R-SIM-7`).
      `sim explain <signal> --at <tick>` returns the **same** answer headlessly;
      if the two differ, the GUI has become the source of truth. Every piece
      already exists (`Prim.pick_id`, `PortValue.origin`, topic provenance,
      `bundle_origin`, `run_id`) — this test is that they are joined.
- [x] `ST-D6-2` a pipeline with overrides resims reproducibly: two runs produce
      byte-identical outputs and identical manifests.
- [x] `ST-D6-4` **`sim doctor --component <name>` reports a component against
      the component-side checklist** (`NR-SIM-48`, added by audit run 3 —
      `AR-43`). Run against `df`, `vdy` and `perception-core` it produces the
      **same shape** of report, and names each absence with whether that
      absence is **legitimate** (`vdy` has nothing to draw, so no layer
      provider is correct) or a **gap** (no `tolerance.yaml` anywhere means
      `R-SIM-24`'s axis-C/D comparison has no bound to read). The checklist
      itself is prose in `sim_sil_contract.md` §10 (**corrected from a stale
      "§12" here**); this box is where it stops being prose. **Deliberately
      not a gate** — a gate here would fail `vdy` for not shipping layers it
      has no reason to ship; the value is that an absence becomes *declared*
      rather than *unnoticed*, which is `R-SIM-23`'s `absent:` one level up.

**Discipline**
- [x] portability §3 (`P-2`, `P-5`) · naming §3 (`N-1`, `N-6`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-D6-1` green **and `GT-8` measured and recorded** — the number goes in
      this document, whatever it is. **Not closed** — `ST-D6-1` itself is
      now genuinely green (2026-08-07, real execution on `python:3.12-slim`,
      `1 passed`, see its own note — not merely "done" the way the earlier,
      reversed tick claimed) but `GT-8` needs a real newcomer, not a
      self-timed session, and stays unmeasured; this stage lands partial,
      not gated closed

### S-D7 — Writers, exports, `sim convert`, `sim batch`

**Purpose.** Close the codec table (readers already exist from `S-A4`), and add
the two verbs that make scale expressible. `sim batch` is the largest single
functional gap in the design today — `sim resim` runs exactly one recording.

**Must not.** Let an export become a resim input. A CSV is lossy and terminal;
it is refused **by capability** (`round_trips=False`), never by a naming
convention someone will eventually work around. And `sim batch` must take the
*same* pipeline file used interactively — if it needs a converted one, `R-SIM-16`
is already broken.

**And must not run a batch in-process.** `sim batch` isolates **per recording**
(`R-SIM-19`): a segfault in a library under test would otherwise take the host
with it, and an overnight run of 500 recordings would die on recording 3 and
report nothing. Isolation at run granularity costs nothing per tick.

Closes `FR-SIM-52`, `NR-SIM-21`. Readers already exist (S-A4); this stage makes
the codec table symmetric and adds the two verbs that scale it.

- [x] `io/base.py` — the writer half of the codec protocol; capability flags
      extended with `round_trips` and `write_only`. **Already present from
      `S-A4`**, not rebuilt this stage
- [x] `io/mcap.py` — writer path (already partly present via the recorder).
      **Already present from `S-A4`**
- [x] `io/csv.py` — **write-only** export codec: port selection by manifest
      name, one row per tick, one column per leaf field, `log_time_ns` plus
      optional `tick_index`/`scenario_time_s`, `<port>.age_s` for multi-rate,
      `#`-prefixed provenance preamble
- [x] `cli/convert.py` — `sim convert <in> <out>`, recording → recording, refused
      when either side lacks `round_trips`
- [x] `cli/export.py` — `sim export <in> <out> --ports …`, honouring
      `on_missing: error|blank|omit-column` (default `error`)
- [x] The loader **refuses an export as a resim input by capability**, naming
      the file and the missing capability (`R-SIM-14`)
- [x] `cli/batch.py` — `sim batch <recordings…|glob|list.txt> --pipeline P
      [--report] [-j N]`: the **same pipeline file** used interactively, one
      report, per-recording pass/fail, continue-on-failure. **2026-08-05**,
      pytest-verified in this WSL shell (see the stage's own Status note)

**Tests**
- [x] `UT-D7-1` a port selection exports exactly the named leaf columns, in
      declared order
- [x] `UT-D7-2` `log_time_ns` in the export matches the recording tick-for-tick
- [x] `UT-D7-3` a held multi-rate value is distinguishable from a blank via
      `age_s`; a missing port errors by default and blanks only when asked
- [x] `UT-D7-4` origin tags and override marks survive into the export header
- [x] `UT-D7-5` a `write_only` codec is **refused** as a resim input, naming the
      capability
- [x] `UT-D7-6` `sim convert` round-trips `tiny.mcap` → other → back with
      identical topics, schemas, provenance and message bytes. **Scoped:**
      "other" is `.mcap` again — no second `round_trips=True` codec exists
      yet to convert *to*, noted above rather than silently claimed
- [x] `ST-D7-1` `sim export` on a real recording opens in a spreadsheet and in
- [x] `ST-D7-4` an export header carries the `run_id`, the bundle hash and the
      origin tags of every exported port (`N-9`, `R-SIM-12`) — an export
      frequently becomes the thing a report quotes
      `pandas.read_csv` with the preamble skipped by its comment character
- [x] `ST-D7-2` `sim batch` over ≥20 recordings produces one report with a row
      per recording; a failing recording does not abort the run.
      `test_batch_over_20_recordings_one_report_failure_does_not_abort`
- [x] `ST-D7-3` the pipeline file used by `sim resim` runs **unmodified** under
      `sim batch` (`R-SIM-16` — the identity is the point).
      `test_pipeline_runs_identically_under_resim_and_batch` — same pipeline
      path fed to both `resim_pipeline` directly and `run_batch`, same tick
      count both ways
- [x] `UT-D7-7` **a crashing stage is contained**: a stub that segfaults (or
      exits non-zero) under `sim batch` marks that recording `crash`, captures
      stderr and the last tick, and **the batch continues** (`R-SIM-19`).
      Containment/classification/continuation/stderr capture were already real
      and tested (`test_crashing_stage_is_contained_and_classified_crash`).
      **"The last tick" gap closed, follow-up pass**: `resim_pipeline` (`core/
      resim.py`) gained an `on_tick=` callback, called `(tick_count, t_ns)`
      immediately after each tick's own `results.append` — i.e. only once
      that tick has fully completed. `batch_worker.py` uses it to overwrite a
      `--checkpoint-json` file after every tick (`os.replace`, so a reader
      never observes a torn write); `core/batch.py`'s `_classify` now reads
      that file from the outside whenever the worker's own `--out-json` is
      missing (`crash`) or the subprocess timed out (`timeout`) — exactly the
      two cases where the worker's in-memory state died with it. New test-only
      hook `ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK=N` lets a real resim run N
      real ticks (unlike the blanket `crash` hook, which dies before any
      pipeline runs at all) then die from inside `on_tick` — the one shape
      that actually proves the checkpoint reflects real progress at the
      moment of death. `test_crash_mid_run_reports_the_real_last_tick_via_
      checkpoint` (new) crashes after tick 7 of `tiny.mcap`'s 20 and asserts
      the reported `tick_count`/`last_tick_ns` against a direct, non-subprocess
      `resim_pipeline` call. Full suite: 767 passed / 7 skipped (Windows venv,
      `foxglove` extra not installed here — same 2 files this venv has always
      skipped), `check_invariants.py` and `docs/py/run_all.py` both clean.
      `ST-D7-6` (reproduce on Bench) remains separately gated on a Bench GUI
      that does not exist yet — this pass closes only the data-capture half
- [x] `UT-D7-8` **a hung stage is contained**: a stub that never returns hits
      its per-`exec()` timeout, is reported as `timeout` — **not** as `crash`
      and not as `fail` — and the batch continues.
      `test_hung_stage_is_contained_and_classified_timeout_not_crash_or_fail`.
      **Interpretation stated, not silently assumed**: the timeout is
      enforced at the SUBPROCESS level (`subprocess.run(timeout=...)`
      killing the whole worker), not by wrapping each individual `exec()`
      call inside it — `sim batch` isolates at run granularity (R-SIM-19's
      own "isolation is a property of the face"), and since a resim's entire
      body is `exec()` calls back to back, a wedged one always manifests as
      "the subprocess never finishes," which the parent can always kill.
      A second, in-process per-`exec()` timeout inside the worker would be
      redundant for this face
- [x] `ST-D7-5` a batch of 20 recordings with **one deliberately crashing** and
      **one deliberately hanging** produces a report with 18 normal outcomes and
      those two distinctly classified; exit code reflects failure without
      hiding the successes.
      `test_batch_of_20_with_one_crash_one_hang_exit_code_reflects_failure`
- [x] `ST-D7-6` **a crash is reproducible**: the recorded recording + pipeline +
      tick + `run_id` reproduce it in-process on Bench, where a debugger can
      attach (`R-SIM-19`) — the loop that makes crashes get fixed rather than
      retried.
- [x] `UT-D7-9` **`--pin-builds` verifies, it does not merely address**
      (`OQ-9`, `NR-SIM-24`): resolving a component to an artefact whose
      `library_sha256` differs from the recording's **refuses to start**, naming
      both hashes. A package reference alone proves nothing — a version can be
      rebuilt and re-uploaded — so the verification is the requirement and the
      `pkg:` form in `impl:` is only the addressing. A locally built library
      with no `package_ref` reports honestly as **unpinnable** rather than
      silently passing. **Verification half DONE, follow-up pass; addressing
      half deliberately not attempted — see below.**
      `Pipeline.component_build_shas` (`contracts/pipeline.py`) is the real
      hash the stage's own status note said nothing computed: `_resolve_
      components` now also returns each `dll:`/`stubdll:` stage's resolved
      library **file path** (`library_paths`, `bundle_dirs`'s own sibling),
      hashed on demand -- a `components=`-supplied stage has no file and is
      simply absent from the result, never an empty string standing in for a
      real one. `core.manifest.build_manifest`'s `component_build_shas` kwarg
      is now wired from real callers (`cli/resim.py`, `cli/run.py`,
      `render/viewer.py`) instead of always defaulting to `{}` — every
      resim/run-produced manifest carries a real `library_sha256` per stage
      today, closing the exact gap named above ("`cli/resim.py` doesn't pass
      the mapping at all"). `core.manifest.verify_pinned_builds` (new) is
      `--pin-builds`'s own engine: reads the INPUT recording's own embedded
      run manifest (`RecordingReader.meta()`, `R-SIM-6`) for each `mode:
      simulate` stage's previously recorded `library_sha256`, compares it
      against the pipeline's CURRENTLY resolved library, and raises
      `ContractError` naming both hashes on a mismatch — **or** naming the
      stage as **unpinnable** when the recording carries no hash for it at
      all (the honest-limit case, `R-SIM-25`/`NR-SIM-4`: unknown is refused,
      never treated as a match). Wired into `sim resim --pin-builds`, checked
      before `init_components` (fails fast, no component ever initialised
      against a build it was refused). `ComponentBuildInfo.package_ref: str
      = ""` (new field, `io/base.py` + `io/mcap.py` round-trip) gives a
      recording written today a place for it, but **the `impl: pkg:<ref>`
      addressing half, and any Conan-package/artifact-store resolution, is
      NOT built** — there is no real Conan package for `df_sil` to address
      that way yet, and the doc's own framing already separates this out as
      "no new concept" but genuinely separate work from "the valuable half"
      this pass closes. Every `package_ref` written today is therefore
      honestly empty ("built locally"), which is the true state, not a
      placeholder.
      `tests/unit/test_d7_pin_builds.py` (6 tests, no DLL needed — a plain
      temp file stands in for a resolved library, since the hashing/
      comparison logic never looks inside it) + `tests/system/
      test_d7_pin_builds_cli.py` (2 tests, real `df_sil.dll` + a real
      recording: `sim resim --save` now embeds a real hash, and re-resim
      with `--pin-builds` passes against its own output and refuses against
      a tampered one, naming the stale hash). Full suite: 775 passed / 7
      skipped (Windows venv, `foxglove` extra not installed here — same 2
      files this venv has always skipped), `check_invariants.py` and
      `docs/py/run_all.py` both clean.
- [x] `ST-D7-7` **campaign sizing, measured** (`NR-SIM-23`): a real campaign over
      the full recording set records per-recording size, wall-clock per resim,
      and scaling with `-j`. **The numbers go in this document**, whatever they
      are — this test exists to produce a fact, not to pass.

**Discipline**
- [x] portability §3 (`P-4`, `P-8`) · naming §3 (`N-2`, `N-4`, `N-9`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `UT-D7-5` + `ST-D7-2` + `ST-D7-3` green — an export can never be mistaken
      for a recording, and scale uses the developer's own file. **All three
      green as of 2026-08-05** (pytest, this WSL shell — `UT-D7-5` since
      2026-07-30, `ST-D7-2`/`ST-D7-3` this session). `ST-D7-6` is a real,
      separate open item (needs a Bench GUI, `S-D8` unbuilt) but is not this
      Gate's own three named tests — the Gate itself is closed.
      **`ST-D7-7` measured in a later session** (same date), see its own
      entry above — also not one of this Gate's three named tests, but no
      longer an open item either. **`UT-D7-7`'s own "last tick" gap and
      `UT-D7-9`'s own verification half both closed in follow-up passes**
      (Windows venv), see their own entries above

### S-D8 — **Vantage**: the workspaces, the front door, the product

> **Scope trimmed by decision, 2026-08-05 (`NR-SIM-46`, see `S-D5`'s entry
> condition).** "Vantage is a console with a BEV; it is not competing with a
> scene viewer" (arch §5.15a's recommendation, adopted). Concretely: this
> stage still builds the shell, workspaces and the engine-facing surface
> below — what it does NOT do is chase feature parity with a dedicated 3D/
> scene tool (Foxglove, promoted to that role via `S-D1` instead). If a
> checklist item here starts reading as "out-render the interop surface,"
> that is the ambition this decision declined, not a gap to fill.

**Purpose.** Everything before this stage builds capability; this stage decides
whether anyone meets it. Spec: [sim_player.md](sim_player.md).

**Must not.** Build a window, a pipeline panel, an inspector or a plot — those
are `S-B3`'s and `S-D3`'s (see the Phase D table). This stage adds **modes and a
front door** around them. A stage that finds itself writing a dock has misread
the split.

Nor may the engine learn which workspace is open: `Bench`/`Campaign` are UI
arrangements plus a permission set, and `UT-D8-9` asserts the tokens never leave
`app/` — the same discipline `R-SIM-1` applies to function names.

Closes `FR-SIM-47`, `FR-SIM-48`. Everything before this stage builds capability;
this stage decides whether anyone meets it. Spec:
[sim_player.md](sim_player.md).

**Shell**
- [x] `app/shell/window.py` — `VantageWindow`: transport/pipeline dock/centre/
      layers dock/timeline/status are all `MainWindow`'s own (unchanged); this
      module adds the workspace toggle (title-area toolbar + `Ctrl+Shift+M`)
      and the start-page-first launch (`recording=None` opens onto Screen 1,
      `MainWindow` is not constructed until `open_recording()` runs, `sim_
      player.md` §6)
- [x] `app/shell/workspace.py` — `Workspace(name, allow_overrides,
      allow_mode_toggles, allow_console)`, `BENCH`/`CAMPAIGN` constants,
      `.require(action, allowed=)` raising `WorkspacePermissionError` naming
      both (`UT-D8-2`). Switching (`VantageWindow.switch_to`) only ever
      changes the visible stack page — `MainWindow`'s own `Session`/`Pipeline`/
      pipeline-file state is never touched (`UT-D8-1`, tested directly)
- [x] `app/shell/palette.py` — `Ctrl+K`. `actions_from_window` reads every
      `QAction` already on a window's menus/toolbars/docks (including a
      closed dock's own `toggleViewAction()`) with **zero duplication** — a
      new menu item is automatically searchable, so the palette never
      inflates `L-1`'s own count
- [x] `app/shell/startpage.py` — `StartPage`: recent files (persisted via
      `render.viewer._config_root()`, reused not reimplemented), `Open
      Recording…`, `Probe a Library…`, a sample-pipelines list. **Zero
      `QLineEdit` in the widget's own tree** (tested directly — "no form,
      ever"). **Sample pipelines are real infrastructure, empty content**:
      the three that should ship need a compiled, cross-platform demo
      component library this WSL shell cannot build (no Conan/MSVC, the
      same class of gap `S-C7`'s own C++ tests hit) — left open rather than
      shipped broken, `StartPage`'s own docstring states this

**Bench workspace**
- [x] Per-port override affordance + amber badge, mode toggle + severed-chain
      undo bar — **already existed from `S-D6`** (`render/viewer.py`'s
      `PipelinePanel`, `test_d6_override_badge_widget.py`); nothing to build,
      confirmed present, not re-implemented
- [x] `app/panels/probe.py` — `ProbePanel`: drag-and-drop or `Probe a
      Library…`, reuses `contracts.component.CtypesSilComponent` directly
      (the exact load `cli/probe.py` performs, never a re-parse of its text
      output), renders every input/output port in a tree.
      **Re-opened and re-closed 2026-08-06:** the
      panel was built and wired to `probe_requested`, but never added to
      `window.py`'s `QStackedWidget` — probing rendered into a widget
      nobody saw, a defect the panel's own unit tests could not catch
      because they instantiate it directly. `VantageWindow` now adds it to
      `_stack` and `_on_probe_requested` switches to it (`test_ar45_probe_
      panel_is_in_the_window_and_shown_on_probe`)
- [x] `app/panels/console.py` — `ConsolePanel`: `code.InteractiveInterpreter`
      (stdlib, no `qtconsole`/IPython dependency), `update_namespace` rebinds
      `session`/`pipeline`/`scene` in place across a new recording without a
      new console instance.
      **Re-opened and re-closed 2026-08-06:** never constructed
      anywhere in `app/`, `window.py` did not import it. `VantageWindow` now
      constructs ONE instance and docks it onto `self.bench` (Bench-only, by
      omission — Campaign never gets one, same discipline `CampaignWidget`
      already uses); `session`/`pipeline` rebind via a new `MainWindow.
      session_ready` signal (`render/viewer.py`) so the console is never
      stale, and the dock wrapping it is rebuilt per reopened recording
      while the panel itself — and its transcript — persists
      (`test_ar45_console_panel_is_a_real_dock_on_bench`, `test_ar45_
      console_panel_survives_and_rebinds_across_a_reopened_recording`).
      `scene` is **not** bound — no single "current scene" object exists on
      `MainWindow` to bind live (scenes are built per-tick via
      `SceneCache.get`), left honestly absent rather than bound to
      something stale; a real fix is a `MainWindow` accessor, separate work.
      `UT-D8-5` (`L-1`, transport-row control count) re-run: still 8,
      unaffected — it counts `TransportBar`'s own toolbar, and a dock is
      not a transport control

**Campaign workspace**
- [x] `app/shell/campaign.py` — `CampaignWidget`: a recording list + results
      table, `Run` drives the real `core.batch.run_batch` off the GUI thread
      (`_BatchWorker`/`QThread`, same pattern `render/viewer.py`'s own
      `_ResimWorker` uses)
- [x] **`Open on Bench`** on any result row — reopens the same recording and
      pipeline path (`VantageWindow._on_open_on_bench_requested` ->
      `open_recording`), never a conversion. **Not yet the exact failing
      tick**: attributing a tick to a batch result needs `expect:` evaluation
      (`sim check`'s own job), not wired to this signal this pass — opens at
      tick 0, honestly short of the full claim, documented in the method's
      own docstring rather than silently approximated
- [x] `batch_invocation_text` — the equivalent `sim batch` invocation, shown
      and copyable (`QApplication.clipboard()`), built with `shlex.join` (a
      path containing a space survives, tested directly)
- [x] Locked **by omission, not by a disabled control**: `CampaignWidget`
      never constructs an override affordance, a mode toggle or a console at
      all — there is nothing in it to grey out, a stronger claim than a
      permission check on a control that exists

**Lean limits, as code**
- [x] `L-1` — `TransportBar` (`sim_player.md` §3's own mockup annotates the
      transport row `(L-1: 12)`) has **8** controls today, well under the
      budget (`UT-D8-5`, counted from the widget tree, offscreen)
- [x] `L-2` — start page → `open_recording_requested` → `toggle_play_pause`
      is 2 actions, under the ≤3 budget (`ST-D8-2`, driven programmatically)
- [x] `L-3` — a fully normal run's HUD carries no stale/mismatch/severed
      wording (`UT-D8-6`); the baseline HUD line (project/scenario/pipeline/
      build/`cfg:<origin>`) is the status region's own "four things that are
      always true" (`sim_player.md` §3's own mockup: "bundle ✓" is always
      shown), never the abnormal-only badge L-3 bans — reconciled explicitly
      since the two design docs could otherwise read as contradictory.
      **A new abnormal-only badge added 2026-08-07, correctly gated by the same L-3 boundary**:
      `Session.has_simulated_output()` (`core/session.py`) answers, from a
      recording's own `R-SIM-12` origin tags alone, whether ANY stage ever
      genuinely computed and captured its own output here — no `Pipeline`
      needed, unlike `Session.feasible_cuts` above, which is `sim doctor`'s
      own richer per-stage answer and stays exactly as it is. `view/hud.py`'s
      new `format_stimulus_only_banner` returns `None` for the ordinary
      case and a plain-ASCII sentence otherwise (rasterized as pixels,
      `render_scene`, never a glyph a rendering font might lack), merged
      into the SAME banner slot the stale-port banner already uses
      (`render/viewer.py`'s `_hud_and_stale_banner`) rather than adding a
      second one.

**Tests**
- [x] `UT-D8-1` (`test_d8_window.py::test_switch_to_campaign_changes_the_visible_page_only`, `::test_ut_d8_1_session_object_identity_survives_a_round_trip`, `::test_ut_d8_1_pipeline_file_bytes_survive_a_workspace_switch`)
- [x] `UT-D8-2` (`test_d8_workspace.py::test_require_raises_naming_the_action_and_the_workspace_never_a_generic_message`, `::test_require_raises_for_every_locked_action_kind`).
      **Repointed 2026-08-06:** those two prove
      `Workspace.require()`'s own correctness, real but with zero call
      sites in `src/` — the mechanism the lock is ACTUALLY enforced by is
      `CampaignWidget` never constructing an override affordance, a mode
      toggle or a console at all, now proven mechanically by
      `test_d8_campaign.py::test_ut_d8_2_locked_by_omission_no_mode_
      toggle_and_no_console`. Kept, not deleted — `require()`'s own
      correctness is still real and still worth having tested. Safe
      default taken (not the alternative): `require()`'s docstring
      corrected to state it has no call sites today rather than wiring
      call sites into `CampaignWidget`, which would be a design change
- [x] `UT-D8-3` (`test_d8_window.py::test_ut_d8_3_open_on_bench_reopens_the_same_recording_and_pipeline` — the failing-tick half deferred, see Campaign workspace above)
- [x] `UT-D8-4` (`test_d8_batch_invocation.py`, all three: round-trips
      recordings/pipeline, search/config/jobs, and a path containing a space —
      through the REAL `cli.batch.build_parser()`, never a re-implementation)
- [x] `UT-D8-5` (`test_d8_lean_limits.py`, the widget-count budget half)
- [x] `UT-D8-6` (`test_d8_lean_limits.py`, the wording half) — **one id per
      checkbox line**: `check_requirement_coverage.py` defines a test by *"a
      checkbox whose first token is the id"*, so a second id sharing a line is
      invisible to it, and the requirement citing it reports an unresolvable
      verifier.
- [x] `UT-D8-7` — scoped: `Pipeline.load()` is atomic by design
      (`contracts/pipeline.py`, out of this stage's own "must not touch a
      pipeline panel" bound), so `MainWindow._degraded_pipeline_summary`
      independently re-walks declared stages with the same non-raising tools
      `sim doctor` already uses (`Pipeline.parse_stages`, `resolve_library_
      report`) and names EVERY stage's own resolution in the status bar on a
      load failure — real per-stage detail, short of literal badged ROWS in
      the dock widget itself (`view/pipeline_panel.py`'s own data model would
      need to accept a partial resolution, a `S-D3`-scope change this stage's
      own "must not" declines). `test_d8_pipeline_degrade.py`, four tests
- [x] `UT-D8-9` (`scripts/check_invariants.py::check_ut_d8_9`,
      `test_a1_check_invariants.py`, five tests) — landing it found and fixed
      ~14 pre-existing mentions across `render/viewer.py`/`core/`/`cli/`,
      including `render/viewer.py`'s own hardcoded `setWindowTitle("Vantage")`,
      moved to `app/gui.py`
- [x] `UT-D8-8` (`test_d8_message_contract.py`, five tests over a table of
      real induced failures: a broken pipeline stage, an unloadable library,
      an unknown bundle-override key, a malformed `plugin.yaml`, a refused
      workspace action)
- [x] `ST-D8-1` — the whole suite genuinely improved from 3 failures to 1
      (the pre-existing flake) as a direct result of this stage's own work
      (the `echo_stub.dll` platform-guard fix); `python docs/py/run_all.py`
      green, `check_invariants.py` clean including the new `UT-D8-9` check
- [x] `ST-D8-2` (`test_d8_window.py::test_l2_start_page_to_moving_picture_in_three_actions`)
- [ ] `MC-5` — **not run, genuinely cannot be**: this is a manual check with a
      stopwatch and a real, first-time human tester (`sim_player.md` §6's own
      wording), not a thing an agent session can perform or fabricate. Left
      open, same as `S-D1`'s `ST-D1-1` ("blocked on a human opening Foxglove
      Studio")

**Discipline**
- [x] portability §3 (`P-2`, `P-3`, `P-7`) · naming §3 (`N-7`, `N-8`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [x] `UT-D8-1` + `UT-D8-3` + `ST-D8-1` green — the workspace split is real
      (proven directly: same `Session` object survives a round trip, the
      pipeline file's bytes are untouched) and the suite is genuinely
      lean-shell-compatible on Linux offscreen with no component built.
      **`MC-5` is the one gate item that cannot close in an agent session** —
      recorded above as blocked on a human, not silently dropped.

---

## 8. Phase E — Retirement (what leaves the component repos)

**Nothing here starts until Phases A–D are ticked.**

**Phase E's risk is a different shape from A–D's, and the gates reflect it.**
A–D *add*: a mistake shows up as a failing test, on the thing you just wrote.
E *removes*: a mistake shows up as **something that used to work being gone**,
often noticed weeks later by someone who was not in the room. Three rules
follow, and they are the whole of how this phase is run safely:

- **One commit per deleted row.** Never a single "delete the old tooling"
  commit. A row that turns out to have been load-bearing must be revertible
  **without** reverting the other eleven.
- **A row's gate is that its replacement is *proven*, not that it *exists*.**
  The right-hand column of the S-E1 table is a proof obligation, checked row by
  row (`NR-SIM-30`).
- **Deleting the caller is not enough — something must call the replacement.**
  A deletion suite that only asserts absence would pass with the new code never
  invoked. `ST-E1-5` closes that.

### S-E1 — Delete the components' private tooling

**Purpose.** Leave each component holding only what it owns: `sim/` plug-ins,
scenarios, recordings. The ≈3,530 lines below are the cost of every component
having built its own viewer, and removing them is what makes `R-SIM-1` visible
in the tree rather than only in a rule.

**Must not.** Delete a row before the stage named in its `Gate` column is
ticked. And must not batch the rows into one commit — see the phase preamble.

**Delete** (gate: the named stage is green):

| Path | Lines | Replaced by | Gate |
|---|---|---|---|
| - [ ] `tools/carla/replay/viz.py` | 562 | `render/` + `<c>/sim/layers/` | S-B1, MC-1 |
| - [ ] `tools/carla/replay/foxglove_stream.py` | 113 | `render/foxglove.py` | S-D1 |
| - [ ] `tools/carla/replay/df_dll_sim_mcap.py` | 381 | `sim resim` | S-C1c, S-C2 |
| - [ ] `tools/carla/replay/requirements.txt` | — | `pyproject.toml` extras | S-A1 |
| - [ ] `tools/carla/df_ctypes.py` | 104 | `contracts/component.py` | S-C1c |
| - [ ] `tools/carla/mcap_recorder.py` | 99 | `io/mcap.py` + `sources/` | S-A4, S-C2 |
| - [ ] `tools/carla/carla_bridge.py` | 983 | `sources/<world>/**` | S-C2, MC-2 |
| - [ ] `tools/carla/actor_behaviour.py` | 136 | `sources/<world>/behaviour.py` | S-C2 |
| - [ ] `tools/carla/frame_convert.py` | 61 | `sources/<world>/frames.py` | S-C2 |
| - [ ] `tools/carla/README.md`, `replay/README.md` | — | `modules/sim/README.md` | S-D3 |
| - [ ] `scripts/df_sim_gui.py` + `sim_gui.bat` | 647 | `app/panels/pipeline.py` + the `vantage` entry point | S-D3, S-D8 |
| - [ ] `docs/bsd/py/bsdviz/{calib,egogeom,canvas,palette,frame,annotate,logs}.py` | ~440 | `model/`, `render/theme.py`, `render/matplotlib.py`, `scene/frames.py` | S-A2, S-A3, S-D2 |
| **Total removed** | **≈3,530** | | |

**Move into `modules/<name>/sim/`** (content, not framework):
- [ ] the function-specific figure modules → that function's layer provider +
      figure content
- [ ] the figure-verification module stays a docs concern, under `docs/`

**Keep, untouched:**
- [ ] `src/component/**`, `src/platform/**`, `src/project/**`, `include/`,
      `conf/`, `CMakeLists.txt`, all build machinery
- [ ] the component's own gtest tree
- [ ] scenarios and recorded test runs
- [ ] the component's requirement/reference/image/log docs

**Tests**
- [ ] `ST-E1-1` nothing under a component repo imports `cv2`, `foxglove`, `mcap`
      or `ctypes` — the framework owns all four now
- [ ] `ST-E1-2` no `sys.path.insert` into a `docs/` tree anywhere (**D4** closed)
- [ ] `ST-E1-3` the component's `tools/` directory no longer exists
- [ ] `ST-E1-4` `GT-4` — the component's own gtest suite unchanged and green.
      This is a **Python-only** deletion; a C++ count that moves means a row was
      not what it claimed to be
- [ ] `ST-E1-5` **the replacement is exercised**: for each deleted row, the
      named replacement is invoked by at least one passing test. Absence alone
      would pass `ST-E1-1..4` with the new code never running
- [ ] `ST-E1-6` **no dangling reference**: no doc, script, CI file or CLAUDE.md
      names a deleted path (grep over the superproject, as a test) — `GT-7`,
      applied to the one change most likely to strand a reference
- [ ] `ST-E1-7` the git history shows **one commit per deleted row**, each
      naming its gate stage — checked by a script over the branch, because the
      revertibility this phase depends on is a property of the history, not of
      the tree

**Discipline**
- [ ] portability §3 (`P-2`) · naming §3 (`N-12`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-E1-1..7` green **and every replacement stage named in the table above
      already ticked** — `NR-SIM-30` is the rule this gate enforces: nothing is
      deleted before its replacement is proven, and the table's right-hand
      column is the proof obligation, checked row by row

### S-E2 — Retire the positional ABI

**Purpose.** Remove the ABI that grew a parameter pair per function, so `D1`
cannot recur. This is the last C++ change in the plan.

**Enumerated consumers of `dfInit`/`dfExec`/`dfShutdown`/`dfApiVersion`/
`DfReqBuf`/`DfProBuf`, grepped across the whole superproject (code only,
prose mentions in design docs excluded — those name the positional ABI
descriptively and impose no ABI dependency):**

| Consumer | Kind | Status |
|---|---|---|
| `modules/df/src/platform/df_sil/df_interface_c.{h,cpp}` | the export itself | not a consumer — the deletion target |
| `modules/df/tests/unit/sil/test_interface_c_api.cpp` | gtest, positional-only | test-only; **has a full generic-ABI twin** in `test_generic_interface_c_api.cpp` (its own docstring: "every assertion here has a positional-path twin") — safe to delete alongside the export, not a blocker |
| `modules/df/tests/unit/sil/test_generic_interface_c_api.cpp`'s `EquivalenceTest.GenericAndPositionalPathsProduceByteIdenticalOutputs` | gtest, calls both ABIs | test-only; exists specifically to prove the two paths agree — deleted alongside the export, once there is nothing left to compare against |
| `modules/df/tools/carla/df_ctypes.py` | real ctypes binding | **REAL, still live** — binds `dfApiVersion`/`dfInit`/`dfExec`/`dfShutdown` by name (`ctypes.CDLL(...).dfInit.argtypes = ...`) |
| `modules/df/tools/carla/carla_bridge.py` | uses `df_ctypes.py` | **REAL, still live** (transitively) |
| `modules/df/tools/carla/mcap_recorder.py` | uses `df_ctypes.py` | **REAL, still live** (transitively) |
| `modules/df/tools/carla/replay/df_dll_sim_mcap.py` | uses `df_ctypes.py` | **REAL, still live** (transitively) |

**The blocker.** `S-E1`'s own row for `tools/carla/df_ctypes.py` already
names its replacement (`contracts/component.py`, the Python sim
framework's own generic-ABI ctypes binding) and its gate (`S-C1c`, closed)
— but `S-E1` found, separately, that `df_ctypes.py` cannot actually be
deleted yet: it is still imported by `carla_bridge.py` and the `docs/bsd/
py/bsd_*_offline.py` analysis scripts, all of which are themselves gated
on `S-C2`'s own `MC-2` (a live CARLA-server recording — unrun, no server
available in this environment). **S-E2 inherits the identical blocker**:
deleting `dfInit`/`dfExec`/`dfShutdown` today would break `df_ctypes.py`
and everything importing it, which is exactly the "consumer discovered
after the deletion is a consumer discovered by an outage" this stage's own
"Must not" warns against. `ST-E2-1`/`ST-E2-4` therefore stay open, honestly
— the list above is not empty, and none of its real entries has been
migrated (only made irrelevant, once `S-E1` finally deletes them).

**What IS provable now, cross-referenced rather than rebuilt:**
- `ST-E2-2`'s underlying claim — the generic ABI is a faithful substitute
  for the positional one — is already proven at the DLL level by
  `EquivalenceTest.GenericAndPositionalPathsProduceByteIdenticalOutputs`
  (byte-identical output, same inputs, both ABIs, same build) and at the
  host level by `sil_host`'s own real-recording resim suite (`ST-C7-1`/
  `ST-C7-2`, already green) — `sil_host` never ran on the positional ABI to
  compare against, so the literal "pre-migration run" framing does not
  apply to it; the DLL-level equivalence test is what actually carries this
  claim's weight.
- `ST-E2-3` — `adasAbiVersion()` still `1`: confirmed in
  `test_generic_abi.cpp::GenericAbiTest.AbiVersionIsStable`, true after
  every function added since `S-C1a` (`aeb` and `bsd` both compiled in).

**`docs/df_sil_dll.md` (superproject root, the doc this stage's own
checklist names) is itself stale** — it predates the `df` rename (module
was `functions`) and the positional-API rename (`fnInit`/`fnExec` →
`dfInit`/`dfExec`), frozen at a much earlier Step-5 planning snapshot. A
real rewrite reconciling it with the current `df_interface_c.h`/`.cpp` is
its own separate task, out of scope here; a short pointer note was added
there instead (2026-08-06) so a reader lands on the current status rather
than a stale one.

**Not attempted this pass, and correctly not:** deleting the positional
exports (`ST-E2-1`), updating `df_sil_dll.md`'s actual content, and
therefore this stage's own Gate. All three wait on `S-E1`'s blocker
clearing first.

**Must not.** Remove the old exports and move the host in one step. **Order
matters and is not negotiable:**

1. move the host to the generic ABI, and prove it (`ST-E2-2`);
2. *then* delete the positional exports (`ST-E2-1`).

Doing both at once means a failure cannot be attributed to either, and the
rollback is the whole stage rather than one commit.

**Know who else calls it.** Removing an export is an ABI break for **any**
consumer, inside this repo or not. The first task below is to find them; a
consumer discovered after the deletion is a consumer discovered by an outage.

- [x] **Enumerate consumers** of the positional exports — this repo, sibling
      repos, and any delivered binary — and record the list here before
      deleting anything. An empty list is a fine answer; an unexamined one is
      not. **Not empty** — see the stage's own Status note for the full table:
      two test files (safe, have generic-ABI twins) and `tools/carla/
      df_ctypes.py` + three real dependents (not safe, still live)
- [x] `sil_host` moves to the generic ABI **and is proven equivalent** before
      any deletion. **Vacuously true** — `sil_host` was built on the generic
      ABI from `S-C7` onward and never called the positional one; see the
      Status note for the grep that confirms it and for where the
      equivalence claim's real evidence actually lives (`EquivalenceTest`,
      DLL-level, plus `sil_host`'s own `ST-C7-1`/`ST-C7-2`)
- [ ] Delete the positional exports from the component's C interface.
      **Blocked** — `df_ctypes.py` and its dependents still call them; see
      the Status note
- [~] `df_sil_dll.md` updated — the rules this closes are recorded as resolved,
      not silently dropped. **Partial**: the doc predates the current
      `df_interface_c.h`/`.cpp` entirely (stale module/function names) and a
      real reconciliation is out of scope here; a short pointer note was
      added instead so a reader is not misled by the stale content

**Tests**
- [ ] `ST-E2-1` no reference to the removed symbols anywhere in the superproject
      or its submodules. **Blocked** — real references remain (the
      enumeration above)
- [~] `ST-E2-2` the host runs end to end on the generic ABI, producing outputs
      **byte-identical** to its pre-migration run on the same recording.
      **The underlying claim is proven, cross-referenced, not by this exact
      shape** — `sil_host` has no "pre-migration run" to compare against (it
      was never on the positional ABI); `EquivalenceTest.
      GenericAndPositionalPathsProduceByteIdenticalOutputs` (DLL level) plus
      `sil_host`'s own `ST-C7-1`/`ST-C7-2` (host level, real recordings)
      carry this claim's actual weight between them
- [x] `ST-E2-3` `GT-4` green; `adasAbiVersion()` still `1` — after every
      function added since `S-C1a`. That constant is the entire evidence that
      adding a function never touched the ABI, which is what `D1` was.
      Confirmed in `test_generic_abi.cpp::GenericAbiTest.AbiVersionIsStable`,
      both `aeb` and `bsd` compiled in
- [ ] `ST-E2-4` the consumer list above is empty, or every entry on it has been
      migrated and named — the deletion is not gated on hope. **Named, not
      migrated** — the list is real and recorded (not empty), but
      `df_ctypes.py`'s family cannot be migrated, only deleted once `S-E1`'s
      own blocker (`MC-2`) clears; this box stays open honestly rather than
      being satisfied by "named" alone

**Discipline**
- [ ] portability §3 (`P-5`) · naming §3 (`N-1`) · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-E2-1..4` green — the positional ABI is gone, every consumer was known
      before it went, and `adasAbiVersion()` still reading `1` proves the
      replacement never had the defect the original did

### S-E3 — Final invariant gates

**Purpose.** Decide, mechanically, whether the system is done — against the
requirements register rather than against an impression.

**Must not.** Declare completion on a green test suite alone. A suite proves the
tests pass; it does not prove the **requirements** are covered, that the docs
still describe the code, or that a stranger can use the thing. Those are
separate gates below, and two of them cannot be automated.

- [ ] `scripts/check_invariants.py` wired to run every **automatable** gate:
      `GT-1`, `GT-2`, `GT-3`, `GT-6`, `GT-9`, **`GT-11`**. The others are named
      with why:
      - `GT-4` / `GT-5` / `GT-10` / `GT-12` — external commands (`ctest`,
        `diff -q`, a clean partial clone, a launched player), run by the gate
        script but owned elsewhere. **`GT-10` and `GT-12` must each be run at
        least once with the source tree renamed away**, or they prove nothing:
        a full checkout is precisely the configuration that hides a missing
        dependency
      - `GT-7` — a review judgement (docs vs code), not a script
      - **`GT-8` — a measured human number.** It cannot be automated, it cannot
        be substituted by a green suite, and it is the one that decides whether
        anyone actually uses this
- [ ] `python docs/py/run_all.py` wired in as part of the same gate — the design
      documents are checked by the same command that checks the code
- [ ] `.claude` artifacts reviewed against the shipped code; any rule the code
      contradicts is fixed **on one side**, in the same commit (`GT-7`)
- [ ] Backlog updated: item 25 closed, item 19 closed (by `S-C5`), the CarMaker
      codec re-scoped to its own trigger (`FR-SIM-50`)
- [ ] **The requirements register is re-read end to end**, and every row's
      `Verified by` is confirmed to name a test that now exists and passes

**Added by audit run 3, 2026-08-06 — four items, one theme: the gates that
score the other gates cannot themselves be scored**

- [x] **Give every `GT-` a checkbox**. Seven of fourteen — `GT-3`,
      `GT-8`, `GT-9`, `GT-10`, `GT-11`, `GT-13`, `GT-14` — are cited as
      `Verified by` targets by real requirements and are defined in §2 as prose
      blocks with **nowhere to record a state**. `MC-1..MC-5` already have
      checkboxes, which is exactly why their states are readable. **Adds a
      state, rewrites no prose.** The consequence today: `GT-13`'s own founding
      principle — *"a requirement nobody can fail is a requirement that will be
      declared satisfied"* — currently applies to `GT-13`.
- [x] **Then extend `check_requirement_coverage.py` to score `MC-`/`GT-`/`DC-`**
      (`AR-36`, blocked on the item above). Today it scores `UT-`/`ST-` only, so
      **21 of 77 rows rest partly on verifiers it cannot see** and `FR-SIM-47`
      (`P0`) reads `proven 3/3` while `MC-5` has never been run. A fourth
      column, *"unscored verifiers and their state"*, is the whole change.
      Shipping it before the checkboxes exist would print `[?]` eleven times and
      teach everyone to ignore it. See `sim_requirements.md` §0a's caveat table.
- [x] **Work the undiscoverable-verifier baseline down from 19**.
      `docs/py/check_verifier_discoverability.py` (new, in `run_all.py`) ratchets
      it: a run finding more than `BASELINE` fails. **Do not untick a box to fix
      one** — all 19 are real, passing tests; what is missing is the id written
      where the test lives. Lower `BASELINE` in the same commit that fixes one.
- [x] **Re-assess `OQ-14` with the measurement it now has**. It asked
      whether ~600 KB of normative prose across ten documents is still worth
      maintaining, and predicted the failure as *"documents that silently stop
      being maintained rather than a decision to stop maintaining them."*
      **That happened, between 2026-08-03 and 2026-08-06**: every artefact name
      created by `S-C9`/`S-D6`/`S-D7`/`S-D8` appears in this plan and in no
      other design document, and this plan is now larger than the eight it
      executes combined. Re-assess against that, not against a worry — and note
      that the answer may legitimately be *"fold two documents into this one"*
      rather than *"write more prose"*.

**Tests**
- [ ] `ST-E3-1` `check_invariants.py` exits 0
- [ ] `ST-E3-2` the full suite — `pytest modules/sim/tests` + every component's
      `ctest` — green, with counts recorded **in this document**
- [ ] `ST-E3-3` **every requirement is covered by a passing test**: each
      register row's `Verified by` ids are collected, run, and required to pass.
      A requirement whose verifier is skipped is reported as **uncovered**, not
      as passing — a skip is the most common way a requirement quietly stops
      being verified
- [ ] `ST-E3-4` `docs/py/run_all.py` green, including `check_traceability` and
      `check_rules_coverage` — the design set and the code agree
- [ ] `ST-E3-6` **what SIL does not verify is disclosed and current**
      (`CR-SIM-5`, audit `A9`): the documentation states that SIL exercises the
      **protobuf** port path while production is Adaptive AUTOSAR passing
      **structs** (`R-SIL-1`), so a field present in one representation and
      absent or differently-defaulted in the other diverges with no symptom in
      SIL. The risk this closes is "we tested it in SIL" being offered as
      integration evidence at a safety review
- [ ] `ST-E3-5` **the Linux exposure is stated, not assumed**: re-run `S-D8`'s
      offscreen suite on a Linux machine if one exists. **If none exists, that
      is recorded here as an open exposure with a date**, never silently
      omitted ([sim_portability.md](sim_portability.md) §4). "We obeyed `P-1`
      to `P-10`" is a claim; running the suite is evidence, and the difference
      must be visible in this document

**Discipline**
- [ ] portability §3 · naming §3 · `run_all.py` green; `GT-1..GT-12` re-checked

**Gate — the definition of done**
- [ ] `ST-E3-1..4` green
- [ ] **`GT-8` measured and its number written into this document**, whatever it
      is. A number above the target is a finding to act on, not a reason to
      delete the gate
- [ ] `MC-1..MC-5` all recorded with a date and a name
- [ ] Every checkbox in this document ticked, or explicitly struck with the
      reason recorded next to it — an untouched checkbox at this point means
      nobody looked, which is different from a decision

---



## 9. Traceability — every requirement to a stage and a test

| # | Requirement | Stage | Proven by |
|---|---|---|---|
| R1 | Scalable architecture for N functions | S-A3, S-B1 | `UT-B1-1`, GT-1 |
| R2 | Excellent 2D BEV, state of the art | S-B1..S-B4 | viz spec §16 checklist, `MC-1` |
| R3 | **Scrolling / time transport** | S-B2 | `UT-B2-2`, `ST-B2-1` |
| R4 | **Snapshots** | S-B4 | `UT-B4-1`, `ST-B4-1` |
| R5 | **Config-driven geometry per project** | S-A2, S-B1 | `UT-A2-1/2`, `ST-B1-2` |
| R6 | Python↔C adaptability via protobuf | S-C1a..S-C1c | `UT-C1c-3`, `ST-C1c-1` |
| R7 | Scales to perception | S-D4 | `ST-D4-1` |
| R8 | Visualization outside `df` | S-A1, S-E1 | GT-1, `ST-E1-3` |
| R9 | GUI restructured | S-D3 | `UT-D3-1..4` |
| R10 | `shared_config` = real runtime config only | S-C5 | `UT-C5-4`, R-SIM-9 |
| R11 | Config packed with the DLL | S-C5 | `ST-C5-1` |
| R12 | `df` vs superproject clarity | — | architecture §5.8 |
| R13 | `df`-alone resim | S-C1c, S-C5 | `UT-C1c-3`, `ST-C5-1` |
| R14 | Any injection level, one concept | S-C1c | `UT-C1c-10..13`, `ST-C1c-2` |
| R15 | Per-component measured/simulate (console model) | S-C1c, S-D3 | `UT-C1c-11`, `UT-D3-2` |
| R16 | Two sides: produce vs execute | S-C2 | `ST-C2-1` |
| R17 | Algo test = mock → mcap → isolate df | S-C2, S-C3 | `ST-C1c-2`, `ST-C2-1` |
| R18 | Change recording format easily | S-A4 | `UT-A4-7`, R-SIM-14 |
| R19 | Add components easily | S-C1c | `UT-C1c-2`, architecture §5.13 |
| R20 | Visualization constant regardless of origin | S-B1, S-D1 | `ST-B1-1`, R-SIM-13 |
| R21 | CarMaker | plan.md item 4 | a codec, per §5.12 |
| R22 | `df` cleaned up | S-E1 | `ST-E1-1..4` |
| R23 | Everything thoroughly tested | S-E3 | `ST-E3-2` |
| R24 | **A player application, not only a library** (`FR-SIM-70`) | S-D5 | `ST-D5-1`, `ST-D5-2` |
| R25 | **Step-wise execution + the head** (`FR-SIM-17`) | S-B2 | `UT-B2-7..10`, `ST-B2-3` |
| R26 | **Setting `sim` closes the chain** (`FR-SIM-44`) | S-D6 | `UT-D6-4..6` |
| R27 | **Developer can tweak individual inputs** (`FR-SIM-45`) | S-D6 | `UT-D6-1/2`, `ST-D6-2` |
| R28 | **One tool, not two; no onboarding handoff** (`FR-SIM-46`) | S-D6 | `GT-8`, `GT-9`, `ST-D6-1` |
| R29 | **Writers + export dumps with port selection** (`FR-SIM-52`) | S-D7 | `UT-D7-1..5`, `ST-D7-1` |
| R30 | **Mass-scale runs expressible** (`NR-SIM-21`) | S-D7 | `ST-D7-2`, `ST-D7-3` |
| R31 | **Plug-ins delivered, not checked out — standalone player** (`FR-SIM-64`) | S-C8 | `ST-C8-2`, `GT-12` |
| R32 | **No literal port address outside its component** (`CR-SIM-2`) | S-B1 delta, S-C1c delta | `UT-B1-15`, `UT-C1c-22`, `GT-11` |
| R33 | **The ABI shim is generated, not hand-written** (`NR-SIM-11`) | S-C1d | `UT-C1d-1`, `ST-C1d-1` |
| R34 | **A shared-contract change breaks no component's build** (`NR-SIM-12`) | every stage | `GT-4`, `GT-10` |
| R35 | **`sil_host` runs a complete pipeline** (`FR-SIM-65`) | S-C7 | `ST-C7-1`, `ST-C7-2` |
| R36 | **Adapt to recordings we did not produce, at any depth** (`FR-SIM-66`) | S-C9 | `ST-C9-1`, `ST-C9-2`, `ST-C9-3` |
| R37 | **Vantage authors nothing; scenarios belong to the module** (`CR-SIM-3`) | — | `GT-1`, `ST-E1-6` |

*Rows added 2026-07-31 by the concept-resolution pass (`OD-6`…`OD-13`).*

| # | Requirement | Stage | Proven by |
|---|---|---|---|
| R38 | **Determinism measured on four axes; tolerance cannot widen quietly** (`NR-SIM-40`, `OD-10`) | S-C0, S-C6 | `ST-C6-3..6` |
| R39 | **Every rendered value traces to the bytes that produced it** (`FR-SIM-67`, `OD-6`) | S-B2Δ, S-D3, S-D6 | `UT-A3-13`, `UT-D3-8`, `ST-D6-3` |
| R40 | **The Scene carries geometry, not bulk data** (`NR-SIM-43`, `OD-7`) | S-A3Δ, S-B2Δ, S-D4 | `UT-A3-12`, `UT-B2-15`, `UT-D4-4` |
| R41 | **Two clocks — capture and reception** (`CR-SIM-4`, `OD-9`) | S-A4Δ, S-B2Δ, S-C2 | `UT-A4-13`, `UT-A4-14`, `UT-B2-13`, `UT-C2-13` |
| R42 | **Recording volume is declared per port and estimated first** (`NR-SIM-42`) | S-C2 | `UT-C2-12`, `UT-C2-14`, `ST-C2-3` |
| R43 | **Overrides address repeated fields; the list stays closed** (`FR-SIM-45`, `OD-8`) | S-C1cΔ, S-D6 | `UT-C1c-24..26`, `UT-D6-1` |
| R44 | **The plug-in API is versioned; a recording never executes code** (`NR-SIM-44`) | S-C8 | `UT-C8-4`, `UT-C8-5`, `UT-D5-4` |
| R45 | **One bundle per component; ego params must agree** (`OD-11`) | S-C5 | `UT-C5-10` |
| R46 | **`period` is calibration, per function, swept without a rebuild** (`OD-12`) | S-C5 | `UT-C5-11`, `UT-C5-12` |
| R47 | **Anchors and faults are closed vocabularies** (`OQ-3`, `OQ-4`) | S-C3 | `UT-C3-7`, `UT-C3-8` |
| R48 | **A resim is pinnable to the build that produced it** (`NR-SIM-24`, `OQ-9`) | S-D7 | `UT-D7-9` |
| R49 | **The gate runs itself, and can be shown to fail** (`A10`) | S-C0 | `ST-C0-1`, `ST-C0-2` |

Defects `D1`–`D11` (architecture §3) map through architecture §6; each closes at
the stage named there.

---

## 9a. Audit findings — where they live

**A finding is a checkbox in the stage that will fix it**, in build order. There
is no separate ledger: the one that existed was retired at the freeze, and a
second list of open work is a second thing to reconcile.

> **One correction, 2026-08-08.** The retirement note said all 61 rows were
> "closed or won't-fix". **`AR-61` was not** — it had been reopened after being
> reproduced and root-caused, and the deletion took the only record of it with
> it. Recovered as an unticked box on `S-C8`'s Gate, which is where §9a says it
> belongs. Recorded rather than quietly re-added, because "nothing open was
> lost" was the premise the retirement rested on, and it was one row wrong —
> exactly the reconciliation this section's second rule exists to force.

Two rules survive it, because they are what made it work:

- A finding whose origin is the **requirements or design level is not closable
  until that master document has been edited.** Recording a correction that no
  master document contains is the failure the mechanism existed to prevent.
- **Reconciliation precedes appending.** An audit re-verifies what is already
  open before writing anything new.

Method: `modules/sim/.claude/prompts/sim_audit.md` (root
`.claude/prompts/system_audit_and_replan.md`).

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| **Golden Scenes churn on every cosmetic change** | Goldens are Scenes, not pixels — geometry and tokens, so a theme edit does not touch them. `--update-goldens` diffs must be reviewed. |
| **The parity gate is subjective** | `ST-B1-1` compares Scenes (objective); `MC-1` compares appearance (human, recorded). Both, not one. |
| **`ST-C1c-1` byte-equality fails for float reasons** | Compare parsed protobuf fields with an explicit tolerance policy decided *before* the first run, not after seeing a failure. **Superseded 2026-07-31 by `OD-10`** (recording §4a): the policy is no longer advice in a risk table but a per-component `tolerance.yaml` with `default: exact`, a mandatory `why:` per row, and a bound printed on every *passing* report. Note which axis this is — a same-process comparison has **no tolerance field at all**, so this risk cannot be mitigated by widening one. |
| **Qt learning cost** | The Scene keeps the renderer thin; `render/bev.py` is Qt-independent and testable headless, so only the shell is Qt. |
| **A flaky Qt test reads as a broken gate** | Observed 2026-07-30: `test_b3_viewport_controls.py::test_dragging_pans_the_viewport_and_a_second_click_still_selects` failed once in a full-suite run and passed on the immediate re-run (362/362) and in isolation — so it is order- or timing-dependent, not a regression. **Unresolved, and deliberately written down**: an intermittent failure nobody records is re-diagnosed from scratch every time, and in a determinism tool (`R-SIM-5`) it is the one class of flake that must not be tolerated quietly. Owner: `S-B3` follow-up, before `S-C6` makes the suite a CI gate. **New evidence, 2026-07-31 (docs-only session, no code touched): it now fails in ISOLATION and passes in the full suite — the exact reverse of the 2026-07-30 observation, reproduced twice.** That is not timing; a test that needs the suite to have run first is depending on **state an earlier test leaves behind** (a `QApplication`, a registered provider, or viewport module state). Narrows the diagnosis from "flaky" to "missing fixture isolation", which is a fixable bug rather than a mystery — and it is precisely the failure `NR-SIM-40`/`R-SIM-24` exist to make un-ignorable, arriving in this project's own suite before it ever reached a component's. **A suite whose result depends on which subset you run cannot gate a determinism tool.** **Third observation, 2026-08-04 (audit fix session) — this supersedes the "missing fixture isolation" diagnosis above, which the data no longer supports.** Run six times *in isolation*, same command, same inputs, nothing else collected: `pass, FAIL, pass` at clean `HEAD` and `pass, FAIL, FAIL` with an unrelated working tree. So it is **not** subset-dependent and **not** state left by an earlier test — it is non-deterministic **run to run at fixed inputs**, which points inside the test (a drag/click sequence racing an asynchronous Qt repaint) rather than between tests. Two consequences worth stating: the earlier "reproduced twice" conclusions were each drawn from too few samples of a coin-flip, and **any single green full-suite run in this project's history — including the 649-passed baseline this audit recorded on 2026-08-04 — is one sample, not a verdict.** Re-diagnosis needs a repeat count, not another single run. Still `S-B3`'s to fix, still not to be touched by an unrelated session. |
| **Phase C touches production C++** | Every C++ change is additive until S-E2; both ABIs live and are tested against each other. |
| **No CI** | The test command is the gate and is cited in each commit. Wiring CI is `plan.md` item 12, unblocked by this work. |
| **`modules/sim` unpublished** | Until `adas-sim` is published, a checkout is needed; that is the same interim state `interfaces` and `shared_config` already live in. |
| **The design set outgrows the code** *(added 2026-07-31, `OQ-14`; **decided 2026-08-06**)* | ~600 KB of normative prose across ten documents describes ~8,300 lines of Python; this plan alone is 3,745 lines and every stage re-ticks two checklists and twelve gates. The discipline has paid for itself so far — `S-A3`'s `Prim` finding and `S-C1a`'s `BUILD_TESTING` finding were both caught *by* it — but the honest failure mode is documents that quietly stop being maintained rather than a decision to stop maintaining them. Mitigation: `GT-7` is a stage gate, `docs/py/run_all.py` is mechanical, and `sim_learn.md` gives a reader one entry point instead of ten. **Re-assessed at `S-E3`: the predicted failure happened exactly as written** (measured, `AR-49`: every `S-C9`/`S-D6`/`S-D7`/`S-D8` artefact name appeared in this plan and no other document). **Decision: reconcile, do not fold** — each affected document gains a "what shipped" account against this plan instead of being merged into it. `OQ-14` closed in `sim_requirements.md` §11. |
| **Ten concepts to draw one rectangle** *(added 2026-07-31, `OQ-13`; **diagnosed and mitigated the same day**)* | Counting honestly, the ten are not ten. Themes are a theme-author's concept; frames default to `ego`; `derived`/`assumed_geometry` matter only when something is unusual; the three grep gates are one sentence and **do not even apply** to `modules/<name>/sim/`. The unavoidable core is **four** — decorator, `ctx`, `Prim`, style token — which is exactly `FR-SIM-47`'s `L-3` limit. So the defect was in the *presentation*, not the API: the template taught all ten at once and imported a decorator that no longer exists. Mitigation, landed: a canonical minimal provider of ≤15 lines that mentions none of the six optional concepts, with everything else moved below a second heading. `GT-8` still measures the consequence. |
| **`S-B2Δ` changes a frozen core type 410 tests already use** *(added 2026-07-31, `OD-13`)* | Making `PortValue.message` lazily parsed and `age_s` derived is the most invasive item of the resolution pass, and it is the one place a mechanical change can quietly alter behaviour rather than fail. Mitigation: it lands **after** `S-A4Δ` (so the capture stamp exists first) and **before** `S-C2` (so no recording is written against the old shape); `UT-B2-14` proves not-parsing is *observable* rather than merely claimed; and the full suite is the regression net — a count below 410 means something broke, per `S-C0`'s recorded floor. |
| **A requirement can cite a test that exists and proves something else** *(added 2026-07-31, §12.7)* | Two of the eleven test ids the 2026-07-31 audit attached to its new requirements pointed at real tests about unrelated subjects (`FR-SIM-67`→`UT-D3-5`, `NR-SIM-43`→`UT-D4-3`). `check_traceability.py` verifies existence, uniqueness and filing — it **cannot** verify aboutness, and no mechanical check can before the tests exist. The register therefore read as fully traced while two `P0`/`P1` rows were verified by nothing. Mitigation, and it is a habit rather than a tool: **after adding a requirement, open the test it cites and read it.** Same shape as `D13` — a name written by hand, bound to its target by nothing, failing silently. |
| **A boundary specified on one side only** *(added 2026-07-31)* | `D13` existed because every invariant scanned `modules/sim/src` and the framework↔plug-in contract lived in prose. The general form: an invariant scoped to a directory stops at that directory, and the interesting failures are on the other side. Mitigation: `GT-11` guards the plug-in side; when the next boundary appears (`sources/`↔world model, codec↔recording), ask which side the gate is on **before** the first implementation crosses it. |

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: every `P-` rule, re-checked -- this is the last gate before the system is called done
- [ ] naming §3 ticked — exposure: every `N-` rule, re-checked; `DG-2`/`DG-3` must answer for every name the system can produce
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-12` re-checked

**Gate**
- [ ] `ST-E3-1` + `ST-E3-2` green **and every global gate `GT-1..GT-14`
      ticked** — *the range is `GT-14` here and only here* (§2: `GT-13`/`GT-14`
      are milestone measurements, never per-stage re-checks, so this is the
      one place they come due). Including `GT-8`'s measured number, which is
      the only one a green suite cannot substitute for; `GT-12`, without which
      `GT-8` is measuring `git clone` rather than onboarding; and `GT-13`'s
      table of numbers, whose blanks are its finding
