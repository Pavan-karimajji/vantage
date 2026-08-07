# Naming & diagnostics — names that survive a debugging session

Status: **normative for every stage.** Extends the platform's naming rules
(`.claude/rules/naming.md`, `R-NAME-1..6`) with the rules specific to a
simulation platform, where a name's real job is to answer **"where did this
value come from?"** at three in the afternoon, six months from now, in a log
line with no surrounding context.

Companions: [`sim_architecture.md`](sim_architecture.md) (master),
[`sim_api_reference.md`](sim_api_reference.md) (the symbols these rules
constrain), [`sim_portability.md`](sim_portability.md),
[`sim_player.md`](sim_player.md).

---

## 0. The premise

A run passes through seven layers: world model → codec → recording → stage
wiring → SUT → layer provider → renderer. When a number is wrong, **the entire
debugging task is deciding which of the seven lied.**

Every rule here is chosen to make one name answer that question. The test for
any proposed name is:

> **The isolation test.** Paste the name alone into a chat message. Can a
> colleague say what it is, who produced it, and where to look — with no other
> context? If not, the name is wrong.

`objects` fails. `perception-core.gen_object_list` passes.

---

## 1. Naming rules (`N-1` … `N-13`)

### N-1 — One token, every layer

A function or component has exactly **one** token, and that token is byte-identical
everywhere it appears:

| Layer | Form |
|---|---|
| source directory | `src/component/<token>/` |
| build selection | `ENABLED_FUNCTIONS=<token>` |
| port name | `<token>.<port>` |
| recording topic | `/<component>/<token>/<port>` |
| layer group | `<token>` |
| calibration prefix | `<TOKEN>_` (`R-NAME-3`) |
| expectation path | `<component>.<token>.<port>.<field>` |
| test name | `test_<token>_…` |

**The payoff is a single grep.** `grep -rn "<token>" .` returns the complete
vertical slice — algorithm, build wiring, port, drawing, calibration, tests —
and nothing else. That is only true if no layer invents its own spelling, which
is why this is a rule and not a convention.

**Both halves of a port name are governed, not just the first.** A port is
`<token>.<port>`, and the `<port>` half is **byte-identical to the
`ReqPort`/`ProPort` member name** in that function's `<fn>_ports.hpp`:
`aeb.compState`, because the member is `compState`. `snake_case` is the proto
*field* convention (`R-NAME-4`) and stops at the message boundary; a port name
is a C++-side identifier travelling outward, so it takes `R-NAME-2` camelCase.
A port named `aeb.comp_state` breaks the single grep at its first hop and is
worth naming as the failure it is — it shipped that way in `S-C1b` and was
caught in the 2026-07-30 Phase C review, before `S-C1c` could spread it into
topics, signal paths, CSV headers and `expect:` strings, where it would have
been a breaking change to every recorded artefact rather than a rename.

Enforced by two tests, one per half: `UT-C1b-9` compares each port's
`owner_function` against the `ENABLED_FUNCTIONS` list and the
`src/component/` directory names, and `UT-C1b-12` compares each port's
`<port>` segment against the real `ReqPort`/`ProPort` member names. Any
disagreement fails, naming all three sources.

### N-2 — Fully qualified always; bare names never leave their scope

Any name that reaches a log line, an error, a topic, a column header, a report
or a Foxglove entity is **fully qualified from the root**. Local variables may
be short; anything serialized may not.

```
topic          /df/aeb/outputs                  not  /outputs
signal         df.aeb.outputs.brake_request     not  brake_request
layer id       df.aeb.corridor                  not  corridor
style token    zone.entry                       not  entry
run artifact   20260728T143012Z-9f3a1c04        not  run_3
```

The cost is verbosity in exactly the places where verbosity is free (machine-read
text) and never in the places where it hurts (code you type).

### N-3 — No name that grep cannot isolate

Two bans, both about search noise:

**(a) No standalone generic identifier** in framework code — as a module name,
class name, public attribute or port name:

> `data` · `value` · `result` · `info` · `state` · `item` · `obj` · `handler` ·
> `manager` · `helper` · `util` · `common` · `misc` · `temp` · `tmp` · `run`

`_common.py` in `docs/py` predates this and is the boundary case the rule
tolerates: it is a private module in a non-shipping folder. Nothing under
`adas_sim/` may follow it.

**(b) No name that is a substring of an unrelated name.** `port` and `portal`,
`veh` and `vehicle`, `obj` and `object`. Grepping the shorter one finds the
longer one, and a search that returns noise is a search people stop running.
When two names must share a prefix, the shorter gets a disambiguating suffix.

### N-4 — Units in the name, or the name is incomplete

`R-NAME-2` already requires unit suffixes on members (`ttcS`,
`corridorHalfwidthM`). Extended to everything serialized:

| Artefact | Form |
|---|---|
| protobuf field | `brake_request_mps2` |
| signal path | `df.aeb.outputs.ttc_s` |
| export column | `vdy.veh_dyn.vx_mps` |
| plot axis label | derived from the name, never hand-typed |

**Unitless is a unit** and is written: `_ratio`, `_norm`, `_count`, `_flag`,
`_idx`. A bare name means "nobody decided", which in a physics-carrying system
is the defect that produces a plausible wrong answer.

Timestamps carry both quantity and base: `t_ns`, `log_time_ns`,
`scenario_time_s`. `P-8` requires integer nanoseconds; the suffix is what makes
a float creeping in visible at the call site.

### N-5 — A name states origin, not intent

The producer is part of the identity:

```
perception-core.gen_object_list      who made it
source.objects_truth                 ground truth, not perception
measured:/perception-core/gen_object_list   from a recording
```

A stage's *inputs* are wired by producer name, so reading a pipeline file tells
you the data flow without running anything. Combined with the per-topic origin
tag (`measured` / `truth` / `mocked` / `simulated` / `overridden`,
`R-SIM-12`/`R-SIM-15`), a name plus its tag carries both **where from** and
**what evidence grade** — the pair a report must never collapse.

### N-6 — One name, all the way through — no translation tables

The name in Python == the name in the manifest == the topic == the CSV column ==
the signal path == the log line == the label in the viewer.

**No layer may map an internal name to an external one.** A translation table is
how a debugging session becomes archaeology: the log says one thing, the file
says another, and the join lives in someone's head. Where a foreign format
forces a different spelling (a vendor codec, `R-SIM-14`), the mapping lives in
**that codec and only there**, is declared as data, and is printed by
`sim explain` (`DG-4`).

Enforced by `UT-A4-9`: for a round-trip through every registered codec, the set
of names in the model is unchanged.

### N-7 — Every runtime object prints its identity

Every public class defines `__repr__` returning its **name**, not its address:

```python
<SilComponent 'df' impl=dll:df_sil.dll ports=7 abi=1>
<Pipeline 'urban_l1' stages=[rsp:off, perception-core:measured, df:simulate]>
<Session 'urban_003' ticks=1200 head=412 deterministic=True>
<Layer 'df.aeb.corridor' prims=14 frame=ego>
<PortValue 'df.aeb.outputs' origin=simulated age_s=0.0>
```

This is the cheapest debugging feature in the system and the easiest to skip.
A traceback, a `print()`, a debugger watch window and a pytest failure message
all become self-explaining for the cost of one method per class.

Enforced by `UT-A1-5`: every public class's `repr` contains the object's own
name and no memory address (`0x` is banned from `repr` output).

### N-8 — An error names both ends and where it looked

`§5.14`'s contract, restated as a naming obligation because it is where names
earn their keep:

```
BAD   Unknown component.
BAD   Port not found: 3
BAD   File not found.

GOOD  Pipeline 'urban_l1' stage 'df' requires input port
      'perception-core.gen_object_list', which no executing stage produces and
      the recording 'urban_003.mcap' does not contain.
        stages producing ports: rsp(off), perception-core(measured)
        recording topics matching 'perception-core.*': (none)
        did you mean: perception-core.gen_object_list_debug
      -> set perception-core mode to 'simulate', or record its outputs
         (R-SIM-6).
```

Four obligations: name **what was expected**, name **what was found**, name
**where it looked**, and suggest the next action. An identifier alone — an
index, a handle, a bare path — is never a sufficient message.

Enforced by `UT-D8-8`: over a table of induced failures, no message consists
only of an identifier, and every one contains at least two distinct names.

### N-9 — One correlation id joins every artefact of a run

```
run_id = <UTC-compact>-<8 hex>        e.g. 20260728T143012Z-9f3a1c04
```

- **sortable** — lexical order is chronological, so `ls` is a timeline;
- **typable** — short enough to say aloud and paste;
- **unique** — the hex is over (pipeline, recording, project, build hashes,
  overrides, seed), so two identical runs share an id and a differing one does
  not. That equality is itself diagnostic: same id, different result means
  non-determinism, which is a finding rather than a mystery.

It appears in **every** artefact: the recording manifest, every log line, the
report, each snapshot sidecar, every export header, the HUD, and the window
title. Given any one artefact you can find the other five.

Enforced by `UT-B4-4` (a snapshot's sidecar carries the same `run_id` as its
session) and `ST-D7-4` (an export header carries it).

### N-10 — The log line format is fixed, and every field is greppable

One line, key=value after a fixed prefix, never multi-line:

```
2026-07-28T14:30:19.412Z INFO  run=20260728T143012Z-9f3a1c04 tick=412 t_s=20.600
    stage=df port=df.aeb.outputs event=exec_ok dur_us=118
```

| Field | Always present | Purpose when grepping |
|---|---|---|
| `run` | yes | join across artefacts (`N-9`) |
| `tick`, `t_s` | when inside the loop | line up with the timeline and the recording |
| `stage` | when attributable | which of the seven layers |
| `port` | when about one port | which value |
| `event` | yes | a **closed vocabulary**, so `grep event=exec_fail` is exhaustive |
| `dur_us` | on completion events | the cheap performance answer |

`event` values are a closed set declared in one module. A free-text log message
is allowed only *after* these fields, never instead of them.

**Rationale:** the debugging move that actually works is
`grep 'port=df.aeb.outputs' run.log | grep event=` — and it works only if the
fields are positionally stable and the vocabulary is closed.

### N-11 — Approved abbreviations only

Abbreviations defeat `N-1`'s grep. The permitted set is the platform's existing
domain vocabulary (`R-NAME-1`) plus these, and **nothing else**:

> `abi` · `cfg` (config bundle only) · `dt` · `id` · `ns`/`us`/`ms`/`s` ·
> `px` · `req`/`pro` (ports only) · `sha` · `sut` · `ttc` · `vx`/`vy`/`ax`/`ay`

Everything else is spelled out: `manifest`, `pipeline`, `recording`,
`provenance`, `expectation`, `override`, `capability`. A new abbreviation is a
change to this list, in review — which is the point.

### N-12 — Module paths name the layer

A traceback should say which of the seven layers failed, before you read the
code:

```
adas_sim/io/<fmt>.py            a format codec        -- the file lied
adas_sim/sources/<world>.py     a world-model client  -- the world lied
adas_sim/contracts/pipeline.py  stage wiring          -- the wiring lied
adas_sim/contracts/component.py the SUT boundary      -- the DLL lied
adas_sim/scene/…                geometry              -- the provider lied
adas_sim/render/…               pixels                -- the renderer lied
modules/<c>/sim/layers/<x>.py   component content     -- the component lied
```

The directory split is therefore a **diagnostic** device, not only an
architectural one — which is why `io/` and `sources/` stay separate
(`R-SIM-14`) even though both "read data from somewhere".

### N-13 — Test names name the thing, not the number

```
test_pipeline_severed_chain_autocloses_intervening_stage        good
test_export_missing_port_errors_by_default                      good
test_case_17                                                    banned
```

A failing test must name the broken behaviour in the failure line. The
`UT-`/`ST-` id is a *label for traceability*, carried in a docstring or marker,
never the whole function name.

---

## 2. Diagnostics (`DG-1` … `DG-5`)

Naming is half; the other half is being able to *ask*.

### DG-1 — Everything named is discoverable at run time

Because ports come from a manifest (`R-SIM-4`), schemas from the descriptor set
(`R-SIM-11`), layers from the Scene and topics from the recording index, the
tool can always enumerate what exists. **No name is knowable only from source.**

```
sim list ports <lib>          from adasManifest
sim list topics <recording>   from the topic index
sim list layers <session>     from the emitted Scene
sim list signals <session>    ports x fields, the one address space (NR-SIM-8)
```

### DG-2 — `sim explain <name>` — the flagship debugging verb

Give it **any** name in the system; it says everything known about it.

```
$ sim explain df.aeb.outputs.brake_request --session urban_003

df.aeb.outputs.brake_request
  kind        port field
  type        float, unit m/s^2  (from the field name, N-4)
  producer    stage 'df', mode=simulate, impl=dll:df_sil.dll (build 4c1e0a2)
  origin      simulated
  topic       /df/aeb/outputs            present in recording: yes
  schema      Adas.Df.AebOutputs         from the DLL's descriptor set
  drawn by    layer df.aeb.corridor (level 2), style 'warn.active'
  asserted by scenario urban_003 expect: becomes true within_s 1.4
  at tick 412 value 0.0    first non-zero at tick 517 (t=25.85s)
```

Every line comes from something already in the system — none of it is a new
index to maintain. This is the direct payoff of `N-1`/`N-6`: because one name
means one thing everywhere, one lookup can join all of it.

`sim explain` also accepts a **style token**, a **layer id**, a **codec name**,
a **run id** and an **error code**, and for an unknown name it does a
fuzzy match and suggests (`N-8`'s "did you mean").

**Shipped, reconciled 2026-08-06.** `cli/explain.py` (`S-D6`,
follow-up pass 2026-08-06, `UT-D6-7`): all six accepted name kinds now
resolve — port/field/layer/run-id were already there from `S-B2`/`S-C1c`;
codec name and error code were added in this pass, alongside a
`difflib`-based fuzzy "did you mean" on an unresolved name (a real
duplicate-suggestion bug was found and fixed while landing it — see
`sim_implementation_plan.md` `S-D6` for the mechanism). **Scoped
honestly, still true today**: a bare field-path name with no `--at` is
not separately resolved beyond an exact topic match; that richness
(type, producer, schema, value) is exactly what `--at`'s `evidence()`
path already provides, and adding it would need a message class resolved
from the port's own schema bytes — real, separate work, not attempted.

### DG-3 — `sim doctor` — explain the environment before anything runs

The first command to run when something is inexplicable. It answers the
questions that produce the most wasted hours, and each answer names a file:

- which Python, which `adas_sim`, which install mode;
- which libraries resolve for the pipeline's `impl:` stems, and by which
  pattern (`P-5`), listing every directory searched;
- which config bundle each stage would resolve, from where, and its hash —
  plus **whether the viewer and the SUT would agree** (`R-SIM-3a`'s core fear);
- codec capabilities for every registered format;
- for a recording: which cuts it supports (`R-SIM-12`);
- platform, line-ending setting, console encoding (`P-4`).

Exit non-zero on anything that would break a run, so it is usable in CI as a
pre-flight.

**Shipped, reconciled 2026-08-06.** `cli/doctor.py` (`S-D6`,
follow-up pass 2026-08-06, `UT-D6-8`) is the full form above: `--pipeline`/
`--search`/`--config`/`--recording`/`--project` flags, each firing its own
optional check; codec capabilities are always reported (no flag needed).
**A real design gap was found and fixed landing it**: `Pipeline.load`
itself used to raise on the first unresolvable `impl:` stem, which would
have made "which stem is broken" undiagnosable — exactly the condition
this verb exists to report — fixed by a new `Pipeline.parse_stages`
(reads stage declarations with no component resolution) so a broken stem
is reported instead of crashing `sim doctor` before it can say anything.

### DG-4 — Every degrade is announced with its name and its cause

`R-SIM-14` requires explicit degradation. Naming makes it actionable: a degrade
message names **the capability**, **the codec**, and **what will be missing**.

```
codec 'csv' lacks capability 'embedded_schemas'; column types come from the
manifest of 'urban_003.mcap' instead. Affected: 3 columns of enum type, which
export as integers. Use --with-enum-labels to inline them.
```

Silence, or a generic warning, is the failure this prevents.

### DG-5 — The failure taxonomy is closed, and every class has an owner

Four classes, matching `§5.14`, each with a fixed exit code so a script can
branch:

| Class | Exit | Means | Who fixes it |
|---|---|---|---|
| `authoring` | 2 | YAML/pipeline/scenario is wrong | the person who wrote the file |
| `environment` | 3 | a library, bundle or dependency is missing | `sim doctor` says which |
| `contract` | 4 | ABI/manifest/version mismatch | the component's build |
| `internal` | 70 | a framework bug | an issue, with the `run_id` |

Anything unclassified is `internal` by definition — an uncaught exception is a
framework bug even when it was provoked by bad input, because failing to
classify it *is* the bug.

---

## 3. The per-stage checklist

Ticked alongside `sim_portability.md` §3, in the same block:

- [ ] every serialized name is fully qualified (`N-2`)
- [ ] no generic identifier introduced (`N-3a`); no substring collision (`N-3b`)
- [ ] every quantity carries a unit suffix, including `_ratio`/`_count`/`_flag` (`N-4`)
- [ ] every new public class has a `__repr__` naming itself, no `0x` (`N-7`)
- [ ] every new error names expected, found, where it looked, and a next action (`N-8`)
- [ ] every log line carries `run`, and `tick`/`stage`/`port` where applicable (`N-10`)
- [ ] `event=` value added to the closed vocabulary, not free text (`N-10`)
- [ ] no new abbreviation outside `N-11`'s list
- [ ] anything newly nameable is reachable from `sim explain` (`DG-2`)
- [ ] any new degrade path names capability, codec and consequence (`DG-4`)

---

## 4. Traceability

| Requirement / rule | Answered here |
|---|---|
| `R-NAME-1..6` (platform) | extended, not replaced — §1 |
| `R-SIM-4` (ports named and discovered) | `N-1`, `DG-1` |
| `R-SIM-12` (origin tags) | `N-5` |
| `R-SIM-14` (explicit degradation) | `DG-4`, `N-6` |
| `R-SIM-15` (overrides are declared) | `N-5` (`overridden` tag) |
| `FR-SIM-47` (lean, not frightening) | `N-8`, `DG-2`, `DG-3` — a tool that explains itself is smaller than one that needs a manual |
| `§5.14` (fail at load, warn in the HUD) | `N-8`, `DG-5` |
