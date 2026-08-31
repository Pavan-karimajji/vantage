# Simulation Platform — Master Requirements Register (v1, superseded)

**Superseded 2026-08-31 (Step 7 document-set shrink), governed by `R-REQ-2`.**
Full text of the original 77-row, essay-per-row register (2,256 lines,
frozen 2026-07-28): `git show 1e2bb5b:docs/v1/sim_requirements.md`.

**Why this file is not a bare stub.** 49 of its IDs (`FR-SIM-n` /
`NR-SIM-n` / `CR-SIM-n`) are cited by name in live `docs/v2/` `Trace` fields
— `R-REQ-2` makes a retired requirement's disposition mandatory, not
optional, wherever a live trace link would otherwise dangle. This table
gives every ID's disposition so no trace link resolves to nothing.

**The fuller, reasoned crosswalk already exists and is not duplicated here**:
`docs/v2/SIM_System_Requirements_v0.1.md` §25 ("Disposition of the v1
register") did this work independently, as part of building the v2 system
requirements, and carries the *why* for every reworked/cut/process row. This
table is the compact index; that section is where to read the reasoning.

| Disposition | Meaning |
|---|---|
| **→ SYS-nnnn** | Carried forward as-is into the named v2 System Requirement(s). |
| **→ SYS-nnnn (reworked)** | The substance survives in the named requirement(s), but the framing changed — see §25.2 for what and why. |
| **cut** | Out of scope for the v2 system; not carried forward. See §25.3 for the reason. |
| **process** | A development-method obligation, not a system requirement; moved to the development plan. Its one product-visible consequence, if any, is named. |

---

## Architecture & scalability

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-1` | One framework, N functions | → `SYS-0038`, `SYS-0053` |
| `FR-SIM-2` | One framework, N components | → `SYS-0038`, `SYS-0053` |
| `FR-SIM-3` | Scale to perception | → `SYS-0038`, `SYS-0012`, `SYS-0151`, `SYS-0156` |
| `CR-SIM-1` | The framework names no function | → `SYS-0132`, `SYS-0274` |

## Visualization

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-10` | A state-of-the-art 2D BEV, and it is *the* developer view | → `SYS-0141`–`SYS-0148`, `SYS-0151` (reworked — single-privileged-view framing dropped, plots become peers) |
| `FR-SIM-11` | Enumerate the BEV feature set rather than guess | → §11 requirements individually (reworked — enumeration honoured, now requirements rather than a request for an enumeration) |
| `FR-SIM-12` | Time transport ("scrolling") | → `SYS-0135`, `SYS-0139` |
| `FR-SIM-13` | Snapshots | → `SYS-0152` |
| `FR-SIM-14` | Plotting as a first-class, pluggable panel | → `SYS-0151` |
| `FR-SIM-15` | A component ships a default workspace | → `SYS-0145` |
| `FR-SIM-16` | Layers may react to interaction, without becoming stateful | → `SYS-0148` |
| `NR-SIM-1` | Visualization is constant regardless of data origin | → `SYS-0131`, `SYS-0150` |
| `NR-SIM-2` | One picture, many media | → `SYS-0146`, `SYS-0147` |
| `NR-SIM-3` | The Scene IR must evolve without breaking recordings or goldens | → `SYS-0025`, `SYS-0254` (reworked — as port-model and plugin-API versioning; the Scene-specific framing is subsumed) |
| `NR-SIM-4` | One failure policy: fail at load, warn in the HUD, never substitute | → `SYS-0026`, `SYS-0123`, `SYS-0171`, `SYS-0208` |
| `NR-SIM-5` | The viewer stays responsive on a long run | → `SYS-0235` |
| `NR-SIM-7` | The tick model must carry what the specs already promise | → `SYS-0029` |
| `NR-SIM-8` | One signal address space | → `SYS-0023`, `SYS-0151` |
| `FR-SIM-47` | The UI and the concept must be lean, and not frightening | → `SYS-0268` |
| `FR-SIM-49` | Naming conventions must be appropriate for debugging | → `SYS-0267` |
| `FR-SIM-48` | Name the player and its two workspaces | → `OQ-20` (§26, reworked — v2 uses neutral role names; *Vantage*/*Bench*/*Campaign* remain the leading candidates, nothing in the v2 spec depends on the outcome) |
| `FR-SIM-17` | Step-wise execution: play, pause, step, advance-N | → `SYS-0134`, `SYS-0137` |

## Configuration

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-20` | Geometry comes from configuration, per project, at run time | → `SYS-0180` |
| `FR-SIM-21` | Configuration is packed with the build, beside the DLL | → `SYS-0177` |
| `FR-SIM-22` | The config source is overridable and always displayed | → `SYS-0177` |
| `CR-SIM-10` | `shared_config` and the bundle hold real runtime config only | → `SYS-0178`, `SYS-0179` |
| `CR-SIM-11` | World-model specifics live with the tooling | → `SYS-0179`, `SYS-0282` |
| `NR-SIM-6` | Calibration sweeps must not require a rebuild | → `SYS-0072`, `SYS-0177` |

## Interfaces — Python ↔ C

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-30` | A proper architecture for the Python↔C boundary | → `SYS-0165`, `SYS-0269` |
| `NR-SIM-10` | A host must not require generated bindings or a sibling checkout | → `SYS-0028` |

## Simulation modes, levels and sides

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-40` | Correct vocabulary: sim / resim / replay | → `SYS-0109`, `SYS-0122` (reworked — live-world "sim" excluded from system scope, `CN-0282`; the never-call-a-re-execution-a-replay distinction survives whole) |
| `FR-SIM-41` | One concept for every level of simulation | → `SYS-0080`, `SYS-0081` |
| `FR-SIM-42` | Per-component measured vs simulated, from a GUI | → `SYS-0080`, `SYS-0158` |
| `FR-SIM-43` | Two sides: producing a recording vs executing one | → `SYS-0086`, `SYS-0112`, `SYS-0122` |
| `CR-SIM-20` | A mock is not a measurement | → `SYS-0033` |
| `CR-SIM-21` | Which cuts a recording supports is a property of the recording | → `SYS-0022`, `SYS-0163` |
| `FR-SIM-66` | Vantage must adapt to recordings it did not produce, at whatever depth they were cut | → `SYS-0013`…`SYS-0022` |
| `CR-SIM-3` | Vantage authors nothing; scenarios belong to the module | → `SYS-0160` (reworked — survives as "the launcher holds no hidden state"; the scenario-ownership framing follows expectations out of system scope) |
| `CR-SIM-22` | Expectations are data, from one source | **cut** — expectations/predicates/the check runner are out of system scope (`CN-0011`, `SYS-0127`); the mechanism itself was judged good and offered to whoever builds the external automation framework, not deleted from the world |
| `FR-SIM-44` | Setting a stage to `sim` must close the chain automatically | → `SYS-0095` |
| `FR-SIM-45` | A developer must be able to tweak individual inputs | → `SYS-0097`…`SYS-0101` |
| `FR-SIM-46` | One tool, not a developer tool and a project tool | → `SYS-0181`, `SYS-0200` |

## Recording, formats and foreign simulators

| ID | Headline | Disposition |
|---|---|---|
| `NR-SIM-20` | Changing the recording format must be easy | → `SYS-0001`, `SYS-0121` |
| `FR-SIM-50` | CarMaker | → `SYS-0012`, `SYS-0109` (reworked — synthetic-scenario tool support) |
| `FR-SIM-51` | CarMaker closed loop | **cut** — closed loop with a foreign simulator explicitly out of scope (`CN-0010`, `CN-0136`); becomes `SYS-0109`, reading the foreign tool's output as an input only |
| `FR-SIM-52` | Writers and export dumps, with port selection and timestamps | → `SYS-0111`, `SYS-0113`, `SYS-0122` |
| `NR-SIM-21` | Mass-scale runs must be expressible | → `SYS-0181`, `SYS-0189` |

## Repo structure & ownership

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-60` | Move visualization out of `df` | → `SYS-0255`, `SYS-0021` (reworked — principle survives as authoring-home-vs-deployed-form; specific repo layout is a development-plan concern) |
| `FR-SIM-61` | Clarity on what lives in `df` vs the superproject | → `SYS-0255`, `SYS-0021` (reworked, same as above) |
| `FR-SIM-62` | A module's docs live with the module | → `SYS-0255`, `SYS-0021` (reworked, same as above) |
| `FR-SIM-63` | Scenario instances stay with the component that owns their expectations | → `SYS-0255`, `SYS-0021` (reworked, same as above) |
| `FR-SIM-70` | The outcome is a player application, not only a library | → `SYS-0255`, `SYS-0257` |
| `FR-SIM-64` | A component's plug-ins must be delivered, not merely checked out | → `SYS-0021`, `SYS-0255` |
| `CR-SIM-2` | A plug-in never spells a port address; it binds through the manifest | → `SYS-0149` |
| `NR-SIM-11` | The per-component ABI shim is generated, not hand-written | → `SYS-0042` |
| `NR-SIM-12` | A change to a shared contract must be proven not to break any component's build | → `SYS-0258` (reworked — expressed as the compatibility matrix and its enforcement, rather than a build-farm requirement) |
| `FR-SIM-65` | `sil_host` runs a complete pipeline, and that is its whole job | → `SYS-0086` (reworked — sharpened: the host must also never grow its own object generator) |
| `NR-SIM-9` | A shipped player owes an explicit compatibility statement | → `SYS-0258` |

## Delivery & process

| ID | Headline | Disposition |
|---|---|---|
| `NR-SIM-22` | A component that crashes or hangs must not take the run with it | → `SYS-0056`, `SYS-0183`, `SYS-0186`, `SYS-0188` |
| `NR-SIM-23` | Throughput, storage and retention must be sized before the first campaign | → `SYS-0117`, `SYS-0234` |
| `NR-SIM-24` | A resim must be pinnable to a specific component build | → `SYS-0246` |
| `CR-SIM-23` | A pipeline file must carry a schema version | → `SYS-0170` |
| `NR-SIM-25` | Resim must actually run somewhere automatic | → `SYS-0201` |
| `NR-SIM-30` | Nothing is deleted before its replacement is proven | **process** — a migration obligation, not a product property; its product-visible half survives as `SYS-0262` |
| `NR-SIM-31` | Incremental, checkbox-tracked, tested at every step | **process** — development method; its one product-visible consequence (automation exists from the start) is `SYS-0201` |
| `CR-SIM-30` | All work on feature branches | **process** — development method; nothing about the delivered system depends on it |
| `NR-SIM-32` | Promote decisions into the AI operational layer | **process** — development method specific to how this repository is worked |

## Requirements added by the 2026-07-31 adversarial audit

| ID | Headline | Disposition |
|---|---|---|
| `NR-SIM-40` | Determinism must be measured across the axes that break it, and tolerance is declared once | → `SYS-0240`…`SYS-0244` |
| `NR-SIM-41` | Per-tick cost and campaign throughput are budgeted and measured | → `SYS-0234` |
| `NR-SIM-42` | Recording volume is bounded by declared per-port policy, and estimated before it is produced | → `SYS-0116`, `SYS-0117` |
| `FR-SIM-67` | Every rendered value is traceable to the bytes that produced it | → `SYS-0034`, `SYS-0153`, `SYS-0154` |
| `NR-SIM-43` | The Scene carries geometry, not bulk data | → `SYS-0118`, `SYS-0146` |
| `CR-SIM-4` | A message carries capture time and reception time | → `SYS-0030` |
| `NR-SIM-44` | The plug-in API is versioned, and a recording never executes code | → `SYS-0253`, `SYS-0254` |
| `CR-SIM-5` | What SIL does not verify is stated, not assumed | **cut** — a claim about the verification value of SIL testing generally, not about this system; belongs in each component team's own test strategy |
| `NR-SIM-45` | The tool must be survivable by someone who did not build it | → `SYS-0265` |
| `NR-SIM-46` | Build-vs-adopt for the interactive viewer is decided explicitly, before it is paid for | **process/`OQ-21`** — a procurement decision, retained as an open question (§26), not a system requirement |

## Requirements added by the 2026-08-06 audit (run 3)

| ID | Headline | Disposition |
|---|---|---|
| `FR-SIM-71` | A component may be split in two without invalidating recordings, pipelines, plug-ins or expectations | → `SYS-0036` |
| `NR-SIM-47` | A measured claim names the platform and the shell that produced it | → `SYS-0251` |
| `NR-SIM-48` | What a component owes the framework is a checklist, and a second component proves it | → `SYS-0266` |

---

**Not carried forward as separate register rows (recorded for completeness,
`docs/v2/SIM_System_Requirements_v0.1.md` §25.3):** v1's extra themes and
palette validator (concept §21.1) — v2 ships two themes only; v1's third
renderer (concept §21.1) — v2 ships one interactive surface, a decision
rather than an accumulation.
