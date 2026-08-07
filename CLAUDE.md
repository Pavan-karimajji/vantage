# sim

The simulation & visualization framework (`adas-sim`). Component-agnostic.

## Role

Drives component SIL libraries against live or recorded stimuli, records runs,
and renders them. Consumed by every component; owned by none.

Design docs live here in `docs/`. **`docs/sim_learn.md` is the plain-language
walkthrough** — the same system told as a story, stage by stage; point a
newcomer there before any spec. `docs/sim_player.md` names the application
(**Vantage**, with the **Bench** and **Campaign** workspaces) and specifies its
window; `docs/sim_api_reference.md` fixes the exact symbols to type;
`docs/sim_naming_and_diagnostics.md` holds the naming-for-debugging rules
(`N-1..N-13`) and the diagnostics contract; `docs/sim_portability.md` is the
Windows/Ubuntu contract every stage obeys. `docs/py/` holds frozen design evidence plus the checks that keep the
documents consistent — run `python docs/py/run_all.py` before any docs commit.
`docs/sim_requirements.md` is the **master
requirements register** — read it when you need to know what was actually asked
for; `docs/sim_architecture.md` is the master design;
`docs/sim_implementation_plan.md` is the checkbox-tracked build order and is
what an implementation session works from — **start at its §0a "START HERE",
which names the next stage and the order; do not scan for something that looks
unfinished.** Normative rules: root `.claude/rules/sim.md` (`R-SIM-1..25`).

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
- **`io/` holds format codecs; `sources/` holds world-model clients** (R-SIM-14).
  Different abstractions — do not merge them.
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
(`../../.claude/prompts/system_audit_and_replan.md`) to sim's document triad —
`docs/sim_requirements.md` (master register) → `docs/sim_architecture.md` →
`docs/sim_implementation_plan.md` → code. Findings land in
`docs/sim_audit_log.md` as stable `AR-n` rows, and every actionable fix is a
checkbox in its owning stage. `docs/py/check_audit_ledger.py` enforces that a
requirements- or design-level finding cannot be closed without the master
document actually being edited.

## AI operational layer — root-canonical

Part of `1v-superproject`. All cross-cutting rules/skills/templates/workflows
live once at the superproject root `.claude/` (spec:
`docs/ai_operational_layer_spec.md`). Load `../../.claude/rules/sim.md` plus the
matching `skills/sim_*`; do not duplicate them here. This file holds only what
is local to `sim`.
