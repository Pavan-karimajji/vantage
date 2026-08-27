# sim

The simulation & visualization framework (`adas-sim`). Component-agnostic.

## Role

Drives component SIL libraries against live or recorded stimuli, records runs,
and renders them. Consumed by every component; owned by none.

> ### ▶ An implementation session starts here
>
> **`misc/START_HERE.md` — first, before anything else.** One screen. It carries
> what no tool can derive: which movement is in progress, the single next action,
> the decisions in force, what is parked and what unparks it, and the open risks.
> A **specification freeze** is in force and is stated there.
>
> Then `docs/v2/SIM_Implementation_Plan_v0.1.md` §0.1, and:
>
> ```
> python docs/v2/py/trace_check.py --status
> ```
>
> It prints the overall position first, then progress at every layer, the
> in-flight packages closest to done, and the next untouched package — with,
> where a package lands them, which `IMP` boxes remain. That is the resume
> pointer.
>
> **It was wrong until 2026-08-27** and said `WP-01` from 20% to 79% complete;
> if you remember that answer, it is fixed. See `misc/memory.md` §1.
>
> **Division of labour, so the two never drift:** `trace_check.py` is the
> authority for *what is built* — every count is computed from the plan's
> checkboxes. `misc/START_HERE.md` is the authority for *what we are doing and
> why*, and **contains no counts at all**. Never put a progress list in
> `START_HERE.md`; that is a second copy of the plan's state and it will drift
> from it, which is the defect the 2026-08-27 reset exists to undo.
>
> **`docs/v1/` is not the build order.** It is the *previous* effort's plan,
> 632 of 740 boxes ticked, and it looks convincingly resumable. Resuming it is
> the single most expensive mistake available in this module.

**The v2 document set (`docs/v2/`) is the V-model requirement baseline** and is
where requirement and implementation work happens. **`docs/v1/` is evidence
about a codebase, never an authority** — it holds the superseded design set
(`sim_architecture.md`, `sim_requirements.md`, `sim_player.md`,
`sim_learn.md`, `sim_api_reference.md`, `sim_portability.md`,
`sim_naming_and_diagnostics.md`, `sim_implementation_plan.md`). Read it for
*why* something was designed a certain way; never for what to build next.

`docs/py/` holds frozen design evidence plus checks over the **v1** set.
**Known-red since the v1/v2 restructure:** its checks still scan the old
top-level `docs/sim_*.md` paths, so `run_all.py` fails 5/5 on stale paths rather
than on anything you did. It reads nothing under `docs/v2/`. The gate that means
something for v2 work is `trace_check.py` — repointing or retiring the v1 checks
is a `WP-01` item.

Governed by root `.claude/rules/requirements.md` (`R-REQ-1..11`, and `R-REQ-6a`
for progress marks), with `skills/requirements_management.md` as the procedure:

| Layer | Requirements | Test requirements |
|---|---|---|
| Concept | `SIM_Concept_Document_v0.3.1.md` — `CN-nnnn` | `SIM_Concept_Test_Spec_v0.1.md` — `CT-nn`, `E2E-nn` |
| System | `SIM_System_Requirements_v0.1.md` — `SYS-nnnn` | `SIM_System_Test_Spec_v0.1.md` — `SYT-<area>-nn`, `ANL-nn`, `INSP-nn` |
| Software | `SIM_Software_Requirements_v0.1.md` — `SW-nnnn` | `SIM_Software_Test_Spec_v0.1.md` — `UT-<item>-nn`, `IT-nn` |
| Design | `SIM_Implementation_Design_v0.1.md` — `IMP-nnnn` → `WP-nn` | analysis checks + build gates |
| Build order | `SIM_Implementation_Plan_v0.1.md` — `WP-nn`, 32 packages, 416 per-`IMP` boxes | the checkboxes, and §0.1 START HERE |

**Run `python docs/v2/py/trace_check.py` before any `docs/v2/` commit.** It
closes `CN → SYS → SW → IMP → WP → test` in both directions, **fails on a
duplicate test identifier** (`R-REQ-2`), and **verifies every generated
`Built.` line against the plan's checkboxes**, failing on drift.

### Tracking progress

| Command | Answers |
|---|---|
| `trace_check.py --status` | *Where did I stop?* Overall position, per-layer done/started/open, in-flight packages, next untouched package |
| `trace_check.py --write-status` | Regenerates the `**Built.**` lines after ticking boxes. Idempotent |
| `trace_check.py --exec-rows all` | Test Execution Record skeleton, all `Not Run` |

**Two different questions, two different artifacts, and they do not substitute
for each other** (`R-REQ-6`, `R-REQ-6a`):

- **`Built.`** — *has the work been done?* Generated into `SYS` and `SW`
  from the plan's per-`IMP` checkboxes, which are the **only** hand-maintained
  progress state in the set. Never typed; verified on every run.
- **`SIM_Test_Execution_<date>.md`** — *has it been verified?* Pass/fail, dated,
  per campaign. **First campaign run 2026-08-27: FAIL** — 1499 passed, 12 failed,
  plus header/time-unit/trace violations and 3 scenario failures. A later campaign
  is a **new file**, never an edit to an existing one (`R-REQ-6`).

**Tick discipline.** `[x]` only when the named test passes. `[~]` for part-done
work and it **must** say `closed by <command or condition>` — a bare `[~]` is a
finding, because the state's whole value is telling the next session where to
resume. `SwReq`'s `**Now.**` field is **not** progress: it is a frozen
2026-08-10 reuse snapshot that is never updated and is deleted at `WP-31`.

Normative rules: root `.claude/rules/sim.md` (`R-SIM-1..25`).

## Local constraints

- **This module's `src/` must never contain the strings `aeb`/`bsd`/`lca`/
  `acc`/`ldw`/`lka`** (R-SIM-1). A grep is the enforcement (`GT-1`, mechanised
  in `scripts/check_invariants.py`, scoped to `src/adas_sim/**`). A function's
  contribution lives in that component's own `modules/<name>/sim/`, never here.
  **`tests/` is deliberately outside the grep** — a parity/golden test must name
  the component it achieves parity with (see R-SIM-1 for why widening it would
  delete real coverage).
- **Layer providers emit geometry, renderers emit pixels** (R-SIM-2) — metres,
  named frames, semantic style tokens. No provider imports a renderer.
- **`io/` holds format codecs; `sources/` holds the scripted stimulus source
  and its recorder** (R-SIM-14) — the live world-model client is removed
  (`DD-12`, `WP-02`). Different abstractions — do not merge them.
- **The viewer's only input is a `Session`** (R-SIM-13). It never talks to a
  world model, a DLL or a file.
- **A plug-in never spells a port address** (R-SIM-21). `self.<port>`, resolved
  against `LayerCtx.known_ports` (`ctx.port(...)`/`requires=`, `S-B1Δ`). An
  *ambiguous* match (more than one known port fits) is an `AuthoringError`,
  never a guess; a *zero*-match `requires=` entry returns a placeholder layer
  — named, carrying no prims, badged `unavailable` in the layer list (`AR-53`,
  2026-08-07) — never a value nobody published, and never silently absent
  either: manifests are live (`S-C1d`), so "this port does not exist" and
  "this run never wired that component" no longer need to be indistinguishable
  the way they were before that stage landed. A resolved reference simply not
  yet present *this tick* still stays a silent empty result (transient, will
  populate). This is the boundary `GT-1` does *not* guard — it scans `src/`
  and stops exactly where a component's plug-in begins (arch `D13`); `GT-11`
  (`scripts/check_invariants.py`) is the mechanised check over
  `modules/*/sim/**`.
- **Authoring home ≠ deployed form** (R-SIM-20). Plug-ins are authored in
  `modules/<name>/sim/` and *copied* beside the library at build time, like the
  config bundle. "The player is standalone" and "the picture lives with the
  component" are both true; only the copy step joins them.
- **A recording carries data, never code** (R-SIM-20, `NR-SIM-44`). The config
  bundle's *bytes* are embedded; a plug-in's *hash and identity* are. Opening a
  colleague's file must never run their code. The asymmetry is deliberate —
  configuration is data, a plug-in is code — so do not "fix" it.
- **Closed lists stay closed.** Six override verbs (`const`/`hold`/`offset`/
  `scale`/`select`/`drop`, R-SIM-15), five faults, an index grammar of `[i]` and
  `[*]` with no predicate, and no expression language anywhere. Each has a
  written reason; reopening one is a design change, never an implementation
  choice. The governing line: **an override may destroy or attenuate
  information, never create an entity.**
- **A field the tool cannot fill reads `unknown`** (R-SIM-25, `NR-SIM-4`) — never
  a plausible-looking default. Applies hardest to the evidence panel and
  `sim explain`, whose entire purpose is being believed.
- **Two clocks per message** (R-SIM-14): `log_time_ns` is reception and drives
  scheduling; `capture_time_ns` is validity and is `None` when unknown. Never
  default capture to reception — equality manufactures an `age_s` of `0.0`
  indistinguishable from a true one.
- No compiled artifact, so no `CMakeLists.txt`/`build.bat` — same shape as
  `shared_config`. `conanfile.py` uses `package_type = "unknown"`.
- Python file headers per R-STYLE-1; `COMPONENT: SIM` (R-NAME-6).

## Auditing this module

`\.claude/prompts/sim_audit.md` (here, in this module) is the entry point for a
full-scope audit. It binds the root method
(`../../.claude/prompts/system_audit_and_replan.md`) to sim's **v1** document
triad — `docs/v1/sim_requirements.md` (master register) →
`docs/v1/sim_architecture.md` → `docs/v1/sim_implementation_plan.md` → code.
**This triad predates the v1/v2 restructure and is not the current build
order** — see this file's own `▶ An implementation session starts here`
note above; `sim_audit.md` itself has not yet been repointed at the v2 set
and is not authoritative until it is. **A finding is a checkbox in the
stage that will fix it** — there is no separate ledger. A requirements- or
design-level finding is not closable until that master document has been
edited; see the plan's §9a.

## AI operational layer — root-canonical

Part of `1v-superproject`. All cross-cutting rules/skills/templates/workflows
live once at the superproject root `.claude/` (spec:
`docs/ai_operational_layer_spec.md`). Load `../../.claude/rules/sim.md` plus the
matching `skills/sim_*`; do not duplicate them here. This file holds only what
is local to `sim`.
