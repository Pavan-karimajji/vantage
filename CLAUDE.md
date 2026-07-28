# sim

The simulation & visualization framework (`adas-sim`). Component-agnostic.

## Role

Drives component SIL libraries against live or recorded stimuli, records runs,
and renders them. Consumed by every component; owned by none.

Design docs live here in `docs/`. `docs/sim_requirements.md` is the **master
requirements register** — read it when you need to know what was actually asked
for; `docs/sim_architecture.md` is the master design;
`docs/sim_implementation_plan.md` is the checkbox-tracked build order and is
what an implementation session works from. Normative rules: root
`.claude/rules/sim.md` (`R-SIM-1..14`).

## Local constraints

- **This module must never contain the strings `aeb`/`bsd`/`lca`/`acc`/`ldw`/
  `lka`** (R-SIM-1). A grep is the enforcement. A function's contribution lives
  in that component's own `modules/<name>/sim/`, never here.
- **Layer providers emit geometry, renderers emit pixels** (R-SIM-2) — metres,
  named frames, semantic style tokens. No provider imports a renderer.
- **`io/` holds format codecs; `sources/` holds world-model clients** (R-SIM-14).
  Different abstractions — do not merge them.
- **The viewer's only input is a `Session`** (R-SIM-13). It never talks to a
  world model, a DLL or a file.
- No compiled artifact, so no `CMakeLists.txt`/`build.bat` — same shape as
  `shared_config`. `conanfile.py` uses `package_type = "unknown"`.
- Python file headers per R-STYLE-1; `COMPONENT: SIM` (R-NAME-6).

## AI operational layer — root-canonical

Part of `1v-superproject`. All cross-cutting rules/skills/templates/workflows
live once at the superproject root `.claude/` (spec:
`docs/ai_operational_layer_spec.md`). Load `../../.claude/rules/sim.md` plus the
matching `skills/sim_*`; do not duplicate them here. This file holds only what
is local to `sim`.
