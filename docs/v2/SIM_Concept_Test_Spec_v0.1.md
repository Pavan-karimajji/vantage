# SIM — Replay & Simulation Engine
## Concept Test Specification — v0.1

**Owner:** SIM Team (tool supplier)
**Derived from:** `SIM_Concept_Document_v0.3.1.md` §4 (design principles) and `SIM_System_Requirements_v0.1.md` §4 (operational scenarios).
**Status:** Draft for review. Not baselined.
**Scope:** **Validation only** — *does the tool solve the problem it was built for?* The verification level (`SYT-*`, `ANL-*`, `INSP-*`) is `SIM_System_Test_Spec_v0.1.md`; the software level (`UT-*`, `IT-*`) is `SIM_Software_Test_Spec_v0.1.md`.

> **The master is `SIM_Concept_Document_v0.3.1.md`.** Where anything here appears to disagree with it, the concept wins and this document is wrong.

---

## 0. How to read this document

### 0.1 What validation means here, and why it is a separate document

`CN-0380` fixes this document's mandate:

> *The principles in section 4 become acceptance criteria for the tool **as a whole**, not individual requirements.*

That sentence is why a fifteenth `SYS-` requirement was not written for each
principle. *"Deterministic by default"* is not a boundary behaviour — it is a
property of every boundary behaviour at once, and decomposing it into system
requirements loses exactly the claim it makes. The same is true of every row in
§2.

So this document holds the two things that can only be asserted about the
finished product:

| | Asks | Fails when |
|---|---|---|
| **`CT-nn`** — principles as acceptance criteria | *Is this principle true of the tool?* | The tool is correct requirement by requirement and still violates the principle in aggregate |
| **`E2E-nn`** — operational scenarios | *Can a user complete this job?* | Every step works and the sequence does not |

**A `CT` row is passed by the product, not by a component.** A `CT` that could
be satisfied by one module in isolation was written at the wrong level and
belongs in the System Test Specification.

### 0.2 Where `E2E-*` lives, and the one namespace change in this issue

`SIM_System_Requirements_v0.1.md` §0.5 reserved `E2E-nn` inside the *system*
test namespace, and §4 defines all twelve scenarios there. **This document takes
them**, on the ground that an end-to-end operational scenario asks *"can the
user do their job"* — validation — and not *"does the boundary behave as
specified"* — verification.

The identifiers are **unchanged**: `E2E-01`…`E2E-12`, exactly as SYS §4 and
`SYS-0266` already cite them. Nothing renumbers; only the document that
specifies them moves. SYS §0.5's table is corrected in the same pass.

**Three `E2E` identifiers are cited from `Verify` clauses** — `E2E-07`
(`SYS-0112`), `E2E-08` (`SYS-0124`, `SYS-0130`, `SYS-0197`) and `E2E-10`
(`SYS-0266`); the other nine are cited only by §4's own scenario list. Those
five requirements are therefore verified by a test specified here, which is
intended: their `Accept` clauses read *"`E2E-nn` completes…"* literally, because
their acceptance genuinely is a whole scenario rather than a boundary
observation.

### 0.3 Anatomy

```
`CT-nn` · asserts `CN-nnnn` · fixture `V-<NAME>`
Steps: <imperative sequence, no expected values>
  .c1  PASS <falsifiable condition>  ·  FAIL <the observable that contradicts it>
```

Expected values are the asserted requirement's own text, **cited rather than
paraphrased** (`R-REQ-4`). A row that reworded a principle would create a second
copy free to drift from the first — `CN-0287` at test granularity.

**Every case states its FAIL side.** A pass criterion with no stated
contradiction is where falsifiability leaks back out: at execution time the
operator decides what *"didn't really fail"* means, and the case becomes
unfalsifiable in practice while still looking rigorous on the page.

**There is no status column** (`R-REQ-6`, `CN-0382`). Status lives in
`SIM_Test_Execution_<date>.md`.

**Both ends of every link are checked** (`R-REQ-11`). A `CT` row's `Asserts`
column must name a live `CN` UID, **every design principle in Concept §4 must be
asserted by some `CT`**, and an `E2E` row's `Exercises` column must name live
`SYS` requirements. `trace_check.py` fails on any of the three. This caught a
real defect in this document's own first draft: `CT-15` cited *"`SYS` §1.3"* — a
section, not a UID — leaving the product's headline success measure with no
traceable parent. Its actual parent is `CN-0016`.

### 0.4 Method

Validation is `D` — **demonstration** — far more often than verification is, and
that is a property of the level rather than a weakness. *"An engineer completes
the onboarding path unaided"* has no automated form. `R-REQ-8` binds what `D`
costs: scripted, executed, observed, and evidence attached. **`D` never means
"we tried it".**

Where a principle *does* have a mechanical form, it is `A` and is stated as
one — `CT-13` and `CT-14` are greps, not opinions.

### 0.5 Thresholds not yet supplied — `⊘`

`⊘` means the harness is specified and buildable but the bound is the
customer's (`R-REQ-10`). **A requirement nobody can fail is a requirement that
will be declared satisfied.**

| Marked | Waiting on |
|---|---|
| ~~`CT-15.c1`~~ | **Resolved 2026-08-13** (`OQ-14`, `OQ-16`). Two halves, answered differently: the **structural** half is failable today — each step must be completable in configuration, touching exactly its declared file set, with no rebuild — and the **wall-clock** half is seeded from the first recorded session, per `SYS-0265`, rather than guessed |
| `CT-08.c2` | The "pay only for what you use" ratio — no measured baseline exists yet |
| `E2E-07.c2` | The iteration-speedup factor; depends on a real perception module's cost |

---

## 1. Fixture catalogue

Validation fixtures are **situations**, not files — that is the level. Where a
situation reduces to an artifact, the artifact is named.

| Fixture | What it is | Used by |
|---|---|---|
| **`V-FOREIGN`** | A recording from an external producer, no ingest map, no prior contact with the tool. **The recording nobody has taught the tool to read.** | `E2E-01`, `CT-03` |
| **`V-LIBDIR`** | A deployed library directory — binary + `config/` bundle + `sim/` plug-ins + `bundle.sha256` — with **no source checkout and no compiler reachable**. | `E2E-08`, `CT-02`, `CT-07` |
| **`V-CHAIN`** | A four-stage graph `vdy → perception → fusion → aeb`, every mode combination reachable, including the concept's own broken case `simulate → measured → measured → simulate`. | `E2E-02`…`E2E-04`, `CT-05` |
| **`V-TWOHOST`** | Two machines, one Windows and one Ubuntu, different CPUs, both with the same declared toolchain. | `E2E-12`, `CT-04`, `CT-09` |
| **`V-CAMPAIGN`** | One run configuration, N recordings, a CI runner. Includes one module that segfaults and one that hangs. | `E2E-06`, `CT-07` |
| **`V-DAMAGED`** | A raw recording of unknown quality: truncated tail, a counter gap, one bad checksum, one non-monotonic timestamp run. | `E2E-09`, `CT-05` |
| **`V-NEWTEAM`** | A module team holding a library, with no prior SIM-team contact and no permission to edit any framework file. **Two of them** — `SYS-0266` is passed by the *second*. | `E2E-10`, `CT-03` |
| **`V-DEFECT`** | A run configuration that reproduces a known defect, on both platforms. | `E2E-05`, `CT-12` |
| **`V-DIVERGE`** | A run in which a simulated function commands an actuation the recorded vehicle did not perform. | `E2E-11`, `CT-06` |
| **`V-PROJECTS`** | Two projects with different calibration, both using one installed package, neither with a branch of the tool. | `CT-02` |
| **`V-TREE`** | A source checkout, for the static checks. | `CT-13`, `CT-14` |

---

## 2. `CT-nn` — design principles as acceptance criteria

One row per principle in `SIM_Concept_Document_v0.3.1.md` §4, plus `CT-15` for
`CN-0016` — *"the main measure of success"*, which sits in §2.2 rather than §4
but is an acceptance criterion for the product as a whole by exactly `CN-0380`'s
argument. **Each row asks whether the claim survives in the assembled product**,
which is the question no individual requirement asks.

**Coverage of §4 is complete and mechanically checked** — `trace_check.py` reads
the principles table and fails on any principle no `CT` asserts, so a principle
added to the concept in a later revision cannot land without a validation row.

| ID | Asserts | Method | Fixture | Steps | Cases |
|---|---|---|---|---|---|
| `CT-01` | `CN-0035` Configuration over code | D | `V-CHAIN` | Set up, then materially change, a simulation — different modules, different cut, different source — touching configuration files only. Record every file edited. | `.c1` PASS no file edited is source, and no user-authored loop, callable or expression exists in any of them · FAIL any edit outside the declared configuration kinds, or any construct requiring a programmer to author |
| `CT-02` | `CN-0036` One package, many projects | A | `V-PROJECTS`, `V-LIBDIR` | Run both projects against one installed package. Diff the installed tree between them. Search the organisation's repositories for a fork or a project branch of the tool. | `.c1` PASS the installed tree is byte-identical across both projects · FAIL any per-project file inside the package<br>`.c2` PASS no project branch of the tool exists · FAIL one does |
| `CT-03` | `CN-0037` Declarative modules | D | `V-FOREIGN`, `V-NEWTEAM` | Add a module the engine has never seen, by manifest alone. Inspect the engine for any chain, module name or port list compiled into it. | `.c1` PASS the module runs with no engine edit · FAIL any framework file changed<br>`.c2` PASS no module name appears in engine source · FAIL a grep for the module tokens hits |
| `CT-04` | `CN-0038` Deterministic by default | T | `V-TWOHOST` | The full `E2E-12` procedure. This row is the *principle-level* claim; `E2E-12` is the scenario and `SYS-0239`…`SYS-0246` are the requirements. | `.c1` PASS same-process and fresh-process re-runs are exact on port values · FAIL any difference<br>`.c2` PASS rebuilt-binary and different-machine axes report within the declared tolerance, with headroom printed · FAIL a divergence outside tolerance, or a pass that does not print headroom |
| `CT-05` | `CN-0039` Fail loud, fail early | T | `V-CHAIN`, `V-DAMAGED` | For every entry in the error catalogue, construct the condition and attempt a run. | `.c1` PASS every invalid setup is rejected **before execution begins** · FAIL any that is detected mid-run or not at all<br>`.c2` PASS every message names what to change, verified by test not review (`SYS-0264`) · FAIL a message that states only what is wrong<br>`.c3` PASS no invalid setup produces a result · FAIL any run that completes and yields output |
| `CT-06` | `CN-0040` Provenance everywhere | T | `V-CHAIN`, `V-DIVERGE` | Sample values across every port kind, mode and origin. For each, ask the tool for its provenance. | `.c1` PASS every sampled value answers module, mode, source and original timestamp · FAIL any that cannot<br>`.c2` PASS a field the tool cannot fill reads `unknown` · FAIL any plausible-looking default in a provenance answer |
| `CT-07` | `CN-0041` Headless first | A | `V-CAMPAIGN`, `V-LIBDIR` | Run the full campaign on a machine with no display and no GUI toolkit installed. Dump the engine's link dependencies. | `.c1` PASS the campaign completes · FAIL any capability requires a screen<br>`.c2` PASS no GUI library is linked by the engine · FAIL any is |
| `CT-08` | `CN-0042` Pay only for what you use | A | `V-CHAIN` | Run one configuration, then a second identical but for one module removed from the active graph. Measure bytes read, messages decoded and time spent. | `.c1` PASS nothing belonging solely to the removed module is read or decoded · FAIL any is<br>`.c2` ⊘ PASS cost falls in proportion to the removed work, within a declared factor · FAIL it does not — **threshold not yet supplied** |
| `CT-09` | `CN-0043` Same behaviour on both operating systems | T | `V-TWOHOST` | Run the whole suite on both platforms. Compare results, messages, exit codes and artifact layout. | `.c1` PASS port values agree within the declared tolerance · FAIL any difference is dismissed as a platform quirk — **a difference is a defect, and this case exists to stop it being re-labelled** · `.c2` PASS error messages, exit codes and artifact structure are identical · FAIL any differs |
| `CT-10` | `CN-0044` Open at the edges, closed at the core | A | `V-TREE` | Add one reader, one exporter, one view and one module, each as a plug-in. Then attempt to extend the scheduler, port model and config engine through a published extension point. | `.c1` PASS all four extend with no core file changed · FAIL any requires one<br>`.c2` PASS the three core components expose **no** plug-in surface · FAIL any does — *an extension point in the core is this principle failing in the direction nobody notices* |
| `CT-11` | `CN-0045` Explainable runs | T | `V-CHAIN` | For every capability, invoke its dry-run path. Compare what was printed against what a subsequent real run does. | `.c1` PASS every execution path has a dry-run path (`SYS-0263`) · FAIL any capability executes without one<br>`.c2` PASS the printed plan matches the executed run · FAIL any divergence between predicted and actual graph, schedule or injection boundary |
| `CT-12` | `CN-0046` Debuggable by construction | D | `V-DEFECT` | The full `E2E-05` procedure, on both platforms. | `.c1` PASS a native debugger breaks inside a named module at a named cycle, and steps · FAIL any step of the path requires a tool change, a rebuild, or a workaround<br>`.c2` PASS watchdog and timeouts are inactive under a debugger · FAIL a timeout fires during a stepping session |
| `CT-13` | `CN-0286` Closed vocabularies | A | `V-TREE` | Enumerate every closed vocabulary — override verbs, primitive kinds, error classes, log events, fault kinds, CLI verbs — from source, and diff against its published schema. | `.c1` PASS each set matches its schema in **both** directions · FAIL any difference<br>`.c2` PASS no vocabulary has a runtime registration or extension hook · FAIL any does — *a quiet extension point is how a closed set opens without a decision* |
| `CT-14` | `CN-0287` One implementation per concept | A | `V-TREE` | For each concept named as having exactly one home, search both languages for a second implementation. | `.c1` PASS each named concept has exactly one implementation · FAIL any has two<br>`.c2` PASS the one permitted duplication (the error taxonomy, kept honest by a parity check) is the only one, and its parity check passes · FAIL a second exception exists, or the parity check does not run |
| `CT-15` | `CN-0016` The main measure of success | D | `V-CHAIN`, `V-NEWTEAM` | An algorithm engineer who did not build the tool sets up a simulation, changes its cut, and changes a calibration value — alone, unaided, in configuration. Time it. Record the session. | `.c1` PASS completed alone and in configuration, each step's diff touching exactly its declared file set, within the seeded budget · FAIL SIM-team help was needed, code was edited, a diff reached outside its set, or the session exceeded the seeded budget<br>`.c2` PASS no step required editing source or rebuilding · FAIL any did<br>`.c3` PASS the elapsed times are recorded as observations and carried to the customer team · FAIL not recorded — **`OQ-16`: the wall clock is an observation here, deliberately not a gate** |

> **`CT-09.c1` is worded deliberately.** The principle is *"differences between
> Windows and Linux results are defects"*, so the failure this case must catch is
> not the difference itself — it is the difference being **re-labelled** as a
> platform quirk and left. A case that only compared numbers would be passed by
> a team that had learned which numbers to ignore.

---

## 3. `E2E-nn` — operational scenarios

The twelve sequences from `SIM_System_Requirements_v0.1.md` §4, each the
acceptance vehicle for the requirements it names. **A scenario failing points at
requirements rather than at code**, which is what the `Exercises` column is for.

**Steps are not restated here.** §4 already gives each scenario's *Pre*,
*Steps*, *Post* and *Exercises*, and restating them would create the second copy
`R-REQ-4` forbids. This section adds what §4 does not carry: the **fixture** and
the **cases with explicit PASS/FAIL criteria**.

**Amended 2026-08-20 (`SM-01`) — concept-layer coverage checked in both directions across the player's move to `viz`.** `CT-07`, `E2E-05`, `E2E-08` and `E2E-11` each name a capability ("no GUI library is linked by the engine", "the player answer", "every layer renders", "the player timeline") that is now `viz`'s to provide rather than a Python module inside this repo's own package — none of the four needed rewording, because each describes a capability of the *system*, not of a language or a repo, which is exactly `R-REQ-11`'s point: a validation-layer claim survives a component's internal reorganisation precisely because it was never written at that level of detail. Where a scenario's `Exercises` column names a `SYS` that has since been superseded (`E2E-10`, below), the cell says so rather than leaving a citation that reads live but resolves through a disposition table.

| ID | Scenario | Method | Fixture | Exercises | Cases |
|---|---|---|---|---|---|
| `E2E-01` | Onboard a recording the tool has never seen | D | `V-FOREIGN` | `SYS-0001`…`SYS-0022`, `SYS-0171`, `SYS-0202`, `SYS-0208`, `SYS-0225` | `.c1` PASS the environment report names what is missing **without raising** · FAIL it raises, or omits a missing item<br>`.c2` PASS every ingest-map reference resolves, or the failure names both ends · FAIL a failure naming one end<br>`.c3` PASS the feasible-cut set is known **before any run is attempted** · FAIL it is discovered by a run failing at cycle 0<br>`.c4` PASS `explain` executes nothing · FAIL any module is loaded or any output written |
| `E2E-02` | Tune a driving function against recorded perception | D | `V-CHAIN` | `SYS-0080`…`SYS-0083`, `SYS-0158`…`SYS-0163`, `SYS-0164`…`SYS-0172`, `SYS-0072`, `SYS-0177`, `SYS-0205` | `.c1` PASS the coherence check passes at **selection** time, not at run time · FAIL it is deferred to launch<br>`.c2` PASS the calibration change takes effect with **no rebuild** · FAIL any build step is required<br>`.c3` PASS the comparison reports the first divergence with cycle, port and field · FAIL a bare "runs differ"<br>`.c4` PASS two runs produced two manifests and no code was edited · FAIL any source edit |
| `E2E-03` | Deepen the cut without touching downstream configuration | D | `V-CHAIN` | `SYS-0080`, `SYS-0081`, `SYS-0095`, `SYS-0087`…`SYS-0090` | `.c1` PASS the downstream module's configuration entry is **byte-identical** before and after · FAIL any difference, however cosmetic — *this is the whole claim*<br>`.c2` PASS the downstream module cannot distinguish executed from injected input · FAIL any port-set or metadata difference reveals it<br>`.c3` PASS the tool closes the severed chain by default and **prints exactly what it changed** · FAIL a silent change, or a change not fully enumerated |
| `E2E-04` | Catch and resolve a coherence violation | D | `V-CHAIN` | `SYS-0087`…`SYS-0096` | `.c1` PASS the run is blocked **before execution** · FAIL it starts<br>`.c2` PASS the block names every stale module, the path that made it stale, and the consumer where corruption would land · FAIL any of the three is missing<br>`.c3` PASS three remedies are offered, including the smallest change · FAIL fewer, or none identified as smallest<br>`.c4` PASS a waiver requires a written reason and permanently marks every artifact incoherent · FAIL a waiver without a reason, or an artifact not marked<br>`.c5` PASS neither block nor waiver can occur silently · FAIL either happens without an emitted record |
| `E2E-05` | Interactive debugging down to a native breakpoint | D | `V-DEFECT`, `V-TWOHOST` | `SYS-0153`, `SYS-0154`, `SYS-0165`, `SYS-0166`, `SYS-0212`…`SYS-0217` | `.c1` PASS the player answer and the command-line answer are **identical strings** · FAIL any difference in content or wording — *one producer, two formatters*<br>`.c2` PASS the engine re-launches from the saved Resolved Run Spec with **no Python in the process** · FAIL any interpreter symbol is loaded<br>`.c3` PASS a debugger breaks on entry to the named module at the named cycle and steps · FAIL any part is unreachable<br>`.c4` PASS reproduced on **both** platforms · FAIL either |
| `E2E-06` | Nightly regression campaign | D | `V-CAMPAIGN` | `SYS-0117`, `SYS-0181`…`SYS-0194`, `SYS-0056`, `SYS-0186`, `SYS-0188` | `.c1` PASS the volume estimate is produced before starting, **labelled an upper bound**, and revised from the measured rate · FAIL an unlabelled estimate, or one never revised<br>`.c2` PASS the batch continues past both the segfault and the hang · FAIL either takes the run with it<br>`.c3` PASS aggregate status distinguishes ok, fail, crash and timeout as **four** values · FAIL any two are merged<br>`.c4` PASS each failure names recording, pipeline, last completed cycle, captured stderr and run id · FAIL any of the five missing<br>`.c5` PASS both failures are individually reproducible on a desktop **from their artifacts alone** · FAIL either needs the CI machine |
| `E2E-07` | Reuse an intermediate result | D | `V-CHAIN` | `SYS-0111`, `SYS-0112`, `SYS-0119`, `SYS-0122`, `SYS-0232` | `.c1` PASS the export loads **on its own**, with no other input · FAIL it requires the original recording<br>`.c2` ⊘ PASS iteration wall time drops by at least the measured cost of the perception stage · FAIL it does not — **factor depends on a real module's cost**<br>`.c3` PASS the export declares its own feasible cuts and tags simulated data `simulated` · FAIL any simulated value carries a measured origin tag |
| `E2E-08` | Open a colleague's result on a machine with no build | D | `V-LIBDIR`, `V-TWOHOST` | `SYS-0028`, `SYS-0114`, `SYS-0123`, `SYS-0124`, `SYS-0130`, `SYS-0197`, `SYS-0253`, `SYS-0255` | `.c1` PASS every layer renders, or names precisely which plug-in bundle is missing **and which hash was expected** · FAIL a layer silently absent, or an unnamed hash<br>`.c2` PASS the run reproduces from the manifest alone · FAIL anything from the originating machine is required<br>`.c3` PASS **no code from the artifact executes** · FAIL any plug-in code in the recording is run — *configuration is data, a plug-in is code* |
| `E2E-09` | Prepare a recording for simulation | D | `V-DAMAGED` | `SYS-0220`…`SYS-0229` | `.c1` PASS the integrity check detects all four injected damages · FAIL any is missed<br>`.c2` PASS the damaged recording is **refused before it produces confident nonsense** · FAIL it runs and yields output<br>`.c3` PASS the extracted recording states what it came from, when, and how · FAIL any lineage field missing |
| `E2E-10` | Onboard a new module, with no help from the SIM team | D | `V-NEWTEAM` | `SYS-0037`…`SYS-0042`, `SYS-0053`, `SYS-0149` *(superseded 2026-08-20 → `VIZ:SYS-nnnn`, `SM-01` — `.c2`'s claim now lives with `viz`'s plug-in registry)*, `SYS-0255`, `SYS-0266` | `.c1` PASS the port set is read from the manifest with **no hand-mapping** · FAIL any manual port table is authored<br>`.c2` PASS the plug-in binds ports through the manifest, never by spelled address · FAIL any literal port address appears in it<br>`.c3` PASS **no SIM-team edit, no ticket, no framework file changed** · FAIL any<br>`.c4` PASS a **second** team completes the checklist unaided · FAIL the checklist needed an addition — *and any addition required is recorded as a defect in the checklist, not absorbed silently* |
| `E2E-11` | Open-loop divergence is visible, not hidden | D | `V-DIVERGE` | `SYS-0104`…`SYS-0107` | `.c1` PASS the first divergence point is detected · FAIL it is not<br>`.c2` PASS it appears in **all three** places — run manifest, player timeline, and as a flag on exported data · FAIL any one omits it<br>`.c3` PASS the flag covers the configured grace window past the point · FAIL it stops at the point<br>`.c4` PASS no consumer of the artifact can mistake post-divergence data for valid · FAIL any export path drops the flag |
| `E2E-12` | Determinism, measured | T | `V-TWOHOST` | `SYS-0239`…`SYS-0246` | `.c1` PASS same-process and fresh-process re-runs are **exact** and block · FAIL any difference, or a tolerance field existing on these axes at all<br>`.c2` PASS rebuilt-binary and different-machine axes are measured and reported against a declared tolerance · FAIL an unreported axis<br>`.c3` PASS **headroom consumed is printed even on a pass** · FAIL a bare pass — *the only anti-spiral mechanism that does not depend on someone choosing to look*<br>`.c4` PASS comparison is over port values, not file bytes · FAIL a byte comparison |

---

## 4. Coverage

Bidirectional (`R-REQ-4`, `TV-1`): every principle has ≥1 `CT`, every `CT` and
`E2E` asserts ≥1 concept or system requirement.

**Counts are emitted by the trace checker, not typed here** — a number derivable
from the document is a second stored copy, and a second copy drifts.

```
python docs/py/trace_check.py --counts
python docs/py/trace_check.py --matrix
```

---

## 5. What this document does not contain

- **Expected values** — they are the asserted requirements' own text (§0.3).
- **Scenario steps** — `SIM_System_Requirements_v0.1.md` §4 (§3).
- **Verification status** — `SIM_Test_Execution_<date>.md` (`R-REQ-6`).
- **System-level verification** — `SIM_System_Test_Spec_v0.1.md`. A row here
  that could be satisfied by one module in isolation was written at the wrong
  level and moves there.
