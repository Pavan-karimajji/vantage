# adas-sim

The **simulation & visualization framework** — component-agnostic. Drives
component SIL libraries against live or recorded stimuli, records runs, and
renders them (2D bird's-eye view, print figures, shareable scenes).

Status: **design frozen 2026-07-27, no code yet.** Tracked as `plan.md` item 25
in the superproject. Today's working equivalent still lives at
`modules/df/tools/carla/` and is what this module replaces.

## The one rule

**Framework here, content in the component.** This module must never contain
the strings `aeb`, `bsd`, `lca`, `acc`, `ldw` or `lka` — a grep is the
enforcement (`R-SIM-1`). A component contributes plug-ins under its own
`modules/<name>/sim/`: layer providers, port manifest, pipelines, viewpoints,
sensor models.

## Design documents

**What was actually asked for?**
[`docs/sim_requirements.md`](docs/sim_requirements.md) — the master requirements
register: every requirement, question and constraint from the design sessions,
numbered, with the verbatim phrasing, what answers it and what proves it. When
the design docs and the plan disagree, that file says what was asked.

**Implementing?** Start at
[`docs/sim_implementation_plan.md`](docs/sim_implementation_plan.md) — the
normative, checkbox-tracked stage list with per-stage unit and system tests.

**Understanding the design?** Read
[`docs/sim_architecture.md`](docs/sim_architecture.md) first — it is the master,
and §5.8 answers "where does this file go?".

| Doc | Owns |
|---|---|
| **[sim_requirements.md](docs/sim_requirements.md)** | **the source** — 40 numbered requirements (`FR-`/`NR-`/`CR-SIM-n`), the decisions register, what is parked and why, open questions |
| [sim_architecture.md](docs/sim_architecture.md) | vocabulary, the defect analysis, layers, the Scene IR, placement map, config bundle, pipeline depth, extension points |
| [sim_sil_contract.md](docs/sim_sil_contract.md) | the Python↔C boundary: named port sets, component manifests, pipelines |
| [sim_visualization_spec.md](docs/sim_visualization_spec.md) | the viewer: Scene primitives, BEV feature set, renderers, themes |
| [sim_resim_and_recording.md](docs/sim_resim_and_recording.md) | sim / resim / replay, run manifests, determinism, recording model & codecs |
| [sim_scenarios_and_expectations.md](docs/sim_scenarios_and_expectations.md) | scenario schema, sensor model, expectations-as-data, headless CI |
| **[sim_implementation_plan.md](docs/sim_implementation_plan.md)** | **the executable plan** — 20 stages, checkboxes, unit + system tests, the `df` retirement inventory, traceability |

Normative rules: superproject `.claude/rules/sim.md` (`R-SIM-1..14`).

## Planned layout

```
src/adas_sim/
  core/       clock · runner · session · manifest
  contracts/  sil_abi · component · pipeline · ports
  model/      project · ego · objects · sensors · cameras
  io/         mcap · (rosbag · mdf4 · carmaker…)    ← format codecs
  sources/    carla · carmaker · synthetic          ← world-model clients
  sinks/      console · image · video
  scene/      types · registry · builder · frames
  render/     theme · viewer · matplotlib · foxglove
  view/       viewport · transport · layers · inspector · timeline · measure
  check/      expect · report
  app/        cli · gui
tests/
```

No `CMakeLists.txt` and no `build.bat` — this module produces no compiled
artifact, the same shape `shared_config` uses. It **does** get a `conanfile.py`
(`adas-sim`, `package_type = "unknown"`) so a component can resolve it without
needing this module checked out (`sim_architecture.md` §5.9).

## Not yet done

Everything except the design. Stage **S-A1** in the implementation plan is the
first thing to build: `pyproject.toml`, `conanfile.py`, the package skeleton and
the test harness.
