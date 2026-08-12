# SIM v2 — Plan Review

**Reviewer pass:** 2026-08-12
**Scope reviewed:** all seven `docs/v2/*.md`, the v1 document set (`docs/v1/`), the live implementation (`modules/sim/src/**`, 115 modules / 20,008 lines; `modules/sil_host/**`, 9 sources / ~1,943 lines incl. headers), and the root rules `.claude/rules/sim.md`.
**Status:** Findings only. **Nothing has been edited.** Each finding names the document to change and the smallest change that closes it. Approve per finding, or per severity band.

---

## 0. Verdict in one paragraph

The v2 chain is sound and I would build from it. The concept correctly identifies the one defect that made v1 not work on real data (cycle-by-timestamp-equality), the language boundary is drawn in a place that can actually be enforced, and the `CN → SYS → SW → IMP → WP → test` chain is closed in both directions. **I checked the five claimed code defects against the code: all five are real.** What the chain is missing is not structure but *four decisions it never made and does not know it skipped* — the ones in §1 below. Each is invisible while you read one document at a time and becomes unbuildable at exactly the work package that needs it. Everything in §2 is mechanical and cheap, but two of those rows would silently disarm six of the analysis checks that the whole migration's safety rests on.

**Recommended order:** close §1 (four items) → apply §2 (eleven rows, one pass) → decide §3's answers → then baseline and start `WP-01`.

---

## 1. Blocking findings — decisions the chain never made

These are not errors in what was written. They are gaps between documents, each of which only becomes visible when you hold two documents open at once.

---

### `RV-01` · **BLOCKING** · Three trigger authorities, no stated precedence — and `t_sim` is never defined

**What.** Three documents each declare what makes a module run, and no document says which wins.

| Authority | Where | Says |
|---|---|---|
| Data arrival | `CN-0143` → `SYS-0064` → `SW-0065` | *"The **default** trigger is the arrival of new data on the key input"* |
| The grid | `CN-0145` → `SYS-0066` → `SW-0064` | *"Due-ness is integer arithmetic over base grid, period and offset"* |
| The recording | `SW-0110` | A `measured` stage *"shall emit its declared outputs **at the recorded rate**"* |

And separately: **no requirement anywhere states how `t_sim` advances.** `SYS-0059` names the three clocks; nothing says whether the engine's clock steps by `grid.step_ns` from a start instant, or is driven forward by the cycle boundaries `SI-02` reconstructs from the recording.

**Evidence.** `grep` for `t_sim` across the SwReq returns three hits, all about *periods and delays* — none about advance. `SW-0109` requires *"exactly one entry point that advances the run"* and never says what one advance is.

**Why it matters — and why it matters here rather than anywhere else.** On a recording *this* framework produced, all three authorities agree by construction: every port was written on the grid. On a foreign recording — the entire reason v2 exists — they cannot agree. A signal arriving at 3.7 ms is either seen at 3.7 ms (data-driven) or at 10 ms with a 6.3 ms error (grid). Two arrivals inside one grid step either both fire the module or one is lost. This is the same class of defect as `CN-0330`: an assumption that is true for self-produced recordings, silently wrong for everyone else's. `MP-1` is named *"fix the clock"* and does not fix this one.

**Smallest fix.** One new `SYS` requirement in §8.3 and its `SW` child, stating in order:

1. `t_sim` advances by exactly `grid.step_ns` per tick, from a declared run start (or: is driven by reconstructed cycle boundaries — but say which);
2. a module declaring a key input fires when that input's freshness key changed **since the previous tick**, evaluated at the tick — so the grid remains the sampling clock and the data-driven trigger is a predicate on top of it, not a second clock;
3. a module with no key input fires on its periodic due-ness;
4. whether a data-driven module contributes its declared period to the GCD (I recommend **yes** — otherwise the grid can be coarser than the data and rule 2 loses arrivals).

**Where.** `SIM_System_Requirements_v0.1.md` §8.3, then `SIM_Software_Requirements_v0.1.md` §7, then a line in `SIM_Concept_Document_v0.3.1.md` §12.3.

---

### `RV-02` · **BLOCKING** · Snapping contradicts `SW-0063` *and* the root rule `R-SIM-18`

**What.** `CN-0147` → `SYS-0068` → `SW-0173` permit a snap tolerance that aligns near-equal periods (19.99 ms → 20 ms), printed. `SW-0063` requires that a period which is not an integer multiple of the grid *"shall never be rounded"*. The superproject's own normative rule says the same thing with the reason attached:

> `R-SIM-18`: *"a period that is not an integer multiple of it is a **load error naming both numbers** — never rounded, because a rounded period accumulates into drift that reads as an algorithm bug."*

**Why it matters.** These are reconcilable only if snapping runs *before* the multiple check, and no document says so. More importantly `R-SIM-18` is not a v2 document — it is the rule that governs the whole superproject, and `SW-0173` overrides it without saying it is doing so. The Implementation Plan §0.1 lists **three** rules that must change (`R-SIM-13`, `R-SIM-14`, `R-SIM-9`) and misses this one. An implementer reading the rule and the requirement gets opposite instructions.

**Smallest fix.** Pick one and write the reason down:
- **(a) Drop snapping.** `SYS-0068` is `P2`; `SW-0173` is `P2`. Removing it costs one requirement and makes `R-SIM-18` unambiguous. **Recommended.**
- **(b) Keep it,** and add to `SW-0173` that snapping is a *pre-check normalisation applied once, before `SW-0063`'s multiple check, bounded by a declared tolerance, and recorded in the run manifest* — plus amend `R-SIM-18` in the same pass and add it to the Plan's §0.1 table.

---

### `RV-03` · **BLOCKING** · `ANL-SW-07` and `ANL-SW-34` forbid the thing `SI-13` is designed to do

**What.** Two analysis checks say `ctypes` may appear only in `pyapi/` and `transport/`, and that `config/`, `graph/`, `ingest/`, `resolve/` and `runspec/` may import neither `io` nor `ctypes`.

But the design requires `resolve/component.py` to call `adasManifest` through `ctypes`:

- `IMP-0279` — *"`diagnostics/probe.py` calls `adasManifest` **through `resolve/component.py`'s probe path**"*
- `SW-0164`'s own `Now.` — *"`contracts/pipeline.py` loads component libraries at load time to read their manifests, **which is legitimate** but must move behind `SI-13`"*
- `SW-0006` needs the manifest's `period_ns` to compute the GCD; `SYS-0072` says that period is read from the component's config bundle and *reported through its manifest*. There is no other way to get it.

**Why it matters.** As written, both checks fail on the design's own target state. `WP-01` builds them on day one, so the migration starts with two red checks that are correct-by-the-letter and wrong-by-intent — and the likely repair under schedule pressure is to weaken the check rather than name the exception. That is precisely how `ANL-SW-05` ("no Python on the per-message path") later gets weakened too, because the precedent exists.

**Smallest fix.** Name `resolve/` as the **third** permitted `ctypes` site, bounded and reasoned, in `SW-0017` and `SW-0164`:

> `resolve/component.py` may open a module binary and call `adasManifest` / `adasAbiVersion` **only**. `adasInit`, `adasExec` and `adasShutdown` are unreachable from the configuration layer, and `ANL-SW-07` asserts that — a symbol-level check, not a directory-level one.

That is a stronger guarantee than the current wording, not a weaker one: it forbids execution by symbol rather than forbidding import by folder.

---

### `RV-04` · **BLOCKING** · Nobody owns the recording's topic index, and the spec cannot be emitted in one pass

**What.** Three obligations need to know what is inside a recording *before* the run:

| Needs the topic index | Item | May it read a recording? |
|---|---|---|
| `IMP-0111` `check_measured_supported` | `SI-11 graph` | No — *"`graph` must not read a message"* (§1.4) |
| `IMP-0185` `feasible_cuts` | `SI-11 graph` | No |
| `ingest/family.py` — which map matches this file | `SI-12 ingest` | No — `ANL-SW-34` |

`DD-04` puts the only codec in C++. So the only paths to a topic index are `io` (forbidden to all three) or `ctypes` into `simcore` (forbidden by `ANL-SW-07`). **No document says who reads it or in what shape it is handed over.**

The same gap has a second face. `§3.3` states the seam's governing rule: *"if the engine has to decide something the configuration layer could have decided, the spec is missing a field."* But three spec fields cannot be filled without opening the recording first — `sources[].ingest[].ladder_floor` (`SW-0051`, depends on what the file actually carries), `sources[].absent[]` (`SW-0190`), and any `measured`-mode validation. **The spec emit is therefore a two-pass operation — probe, then emit — and no document says so.**

**Why it matters.** `WP-20` (`graph/feasible.py`) is 25 `IMP` rows and cannot be written until this is settled, and `WP-05` (the seam, the first real package) silently assumes it.

**Smallest fix.** Two additions, both small:

1. A new `SW` under `SI-16 prep` or `SI-23 pyapi`: **`RecordingIndex`** — a plain data structure (`{topic → {proto_type, count, first_ns, last_ns, origin}}`) produced by exactly one reader call, passed *as an argument* into `graph/` and `ingest/`. Neither imports anything; both receive data. This is the same shape `SI-19 scene` already uses to stay dependency-free, so it is a pattern already in the house.
2. One paragraph in Design §3 making the two-pass emit explicit: **probe → resolve → emit**, with the probe's result hashed into the spec so a spec emitted against a different recording is detectable.

---

## 2. Mechanical findings — cheap, but two of them disarm live safety checks

One editing pass. Listed most-consequential first.

| ID | Finding | Evidence | Fix |
|---|---|---|---|
| `RV-05` | **Six analysis checks scan a directory that will never exist.** `ANL-SW-02`, `-03`, `-04`, `-08`, `-53` and `UT-PLR-01` all scan **`cpp/**`**. `DD-01` explicitly rejects a `cpp/` folder — *"There is no language folder, and that is the point"* — and fixes the tree as `src/simcore/`, `src/simengine/`. A grep over a path that does not exist returns nothing and **passes**. These are the checks that stop the GCD, the reference parser, the YAML reader and the four deleted capabilities from coming back into the engine. `O-1` exists to prevent exactly this. | 7 rows in the Test Spec, 8 mentions in SwReq | Replace `cpp/**` with `src/simcore/** src/simengine/**` everywhere; add one row to `trace_check.py` asserting every path a check names exists in the tree |
| `RV-06` | **`DD-12` cites the wrong check ID.** It says *"`ANL-SW-12` becomes a deletion check, not an import check"* for the world-model name grep. In the Test Spec `ANL-SW-12` is the peak-RSS memory measurement (`SW-0025`); the name grep is `ANL-SW-53`. The Plan's `WP-06` uses `ANL-SW-12` correctly, so the two documents disagree about the same identifier. | Design L228 vs Test Spec L100/L141 | `DD-12` → `ANL-SW-53` |
| `RV-07` | **`t_capture` means the opposite of `capture_time_ns`.** The concept's §7.2 table and §12.2 ladder define `t_capture` as **arrival/reception time** *("arrival time includes transport jitter")*. The superproject rule `R-SIM-14` defines `capture_time_ns` as **validity — the instant the data describes** — and `log_time_ns` as reception. One word, two opposite meanings, in two normative documents an implementer reads together. | Concept §7.2, §12.2 vs `R-SIM-14` | Rename the concept's field to **`t_recv`** throughout the v2 chain (`R-SIM-14`'s meaning matches the wider convention and should not move). ~12 occurrences |
| `RV-08` | **`DD-11` points at the wrong work packages.** It says the header and ladder are *"`WP-05` then `WP-06`, both inside `MP-1`"*. In the Plan they are `WP-07` and `WP-08`; `WP-05` is the seam (`MP-0`) and `WP-06` is `io`. The error is copied forward into the Open Questions register §1.1 (*"`DD-11`'s `WP-05`"*). | Design L199, L201; OQ L28 | `WP-05`→`WP-07`, `WP-06`→`WP-08` in both files |
| `RV-09` | **Design §2.3 sends the `viewer.py` split to the wrong package.** It says *"`WP-22` splits it"*; `WP-22` is the run manifest and the split is `WP-26`. | Design L382 vs Plan §6 | `WP-22` → `WP-26` |
| `RV-10` | **`WP-16`'s deletion ledger quotes line counts that do not survive inspection.** `ingest_map.cpp` is **118 lines total** and contains *both* halves, yet the table lists *"apply half ~80 of 198"* and *"parse half ~118 of 198"* — 198 of 198, i.e. the whole file plus its header, counted twice. `library_loader.cpp` is 112 lines of which `ResolveLibrary` plus its two message helpers is ~70, against a claimed *"resolve half ~102 of 162"*. The ledger reads as measured and is estimated. | Verified by reading both files | Recount from the files, or mark the column `est.` — the ledger is `WP-16`'s only real content, so it should be exact |
| `RV-11` | **The concept's CLI table has no `resim` verb.** §15.3 lists twelve invocations; `resim` is not among them, while `SW-0233`/`DD-14` require it as one of the three mandatory verbs (`convert` / `run` / `resim`). | Concept §15.3 vs `SW-0233` | Add `sim resim <recording> --run …` to §15.3 |
| `RV-12` | **The claim *"the multi-rate scheduler is used never"* is overstated in Python.** `Pipeline.step()` — the multi-rate path — **is** called, by `cli/run.py:75` and `sources/recorder.py:229`, and is unit-tested (`tests/unit/test_c1c_pipeline.py`). It is the *resim* driver that calls the single-rate `exec()`. The finding is real; the wording is not. It matters because it hides `RV-16` below. | `grep -rn "\.step("` | `SW-0056`/`SW-0061`'s `Now.` → *"used by the record path, not by the resim driver"* |
| `RV-13` | **Test counts are typed, not derived.** The Test Spec states 338 `UT` rows; there are 339. `SW-0373` — the document set's own rule — says a derived number is never stored by hand. | `grep -c '^\| \`UT-'` | Let `trace_check.py --counts` emit §0.2's table |
| `RV-14` | **`SW-0060`'s note and `SYS-0068` disagree about what may enter the grid.** `SW-0060` says a static port *"never contributes to the base grid"*, correctly. `SYS-0068`'s snapping and `SW-0006`'s GCD say nothing about excluding static ports, so the exclusion exists only in a `SW`-level note. | `SW-0060` note | State the exclusion in `SW-0006`'s `Shall.`, not in a note under a different item |
| `RV-15` | **`R-SIM-5` has a branch v2 deletes.** It defines *sim* as *"live world model, non-deterministic"*. `DD-12` removes live world models entirely, so that branch names nothing. The Plan's §0.1 rule-change table does not list it. | `R-SIM-5` vs `DD-12` | Add `R-SIM-5` (and `R-SIM-18`, per `RV-02`) to the Plan's §0.1 table — it is currently three rows and should be five |

---

## 3. Plan-level findings — ordering and risk

---

### `RV-16` · **HIGH** · `WP-02` deletes the multi-rate path's only live exercise, seven packages before its replacement

`CN-0360`: *"Nothing is deleted before its replacement is proven."*

The Python multi-rate path (`Pipeline.step`) is reached in production **only** through `cli/run.py --source` and `sources/recorder.py`. `WP-02` deletes the first (`DD-12`) and retires the `record` verb (`DD-14`). The C++ multi-rate scheduler is `WP-09`. Between `WP-02` and `WP-09` — the whole of `MP-0` and most of `MP-1` — the only path that runs a pipeline end-to-end is the **single-rate** one, which `SW-0061` exists to abolish.

**Fix.** Either keep `io/recorder.py` driving `Pipeline.step` until `WP-09` lands (it moves in `WP-02` anyway — do not unwire it), or move the `--source`/`record` removal from `WP-02` into `WP-16`, where every other deletion already lives and `prove_equal.py` already gates. The second is more consistent with `O-5`.

---

### `RV-17` · **HIGH** · `MP-1`'s exit gate cannot be met by `MP-1`

`MP-1` ends when *"a recording the framework did not produce reconstructs into cycles correctly."* Its validating fixture, `F-FOREIGN`, is **crafted** by the SIM team. The two real foreign formats — MDF4 and TDMS — are deferred to `WP-18` in `MP-2` because no sample file exists (`DD-13`, correctly reasoned).

So the phase whose stated purpose is *"make foreign data possible"* ends without ever having met foreign data, and `F-FOREIGN` encodes the same assumptions the ladder does — a fixture written from a guess validates the guess.

**Fix.** State it rather than discovering it: mark `MP-1`'s exit **provisional** until `WP-18`, and add an explicit re-validation box to `WP-18` — *"re-run `UT-BUS-07`…`UT-BUS-13` against a real sample; any rung that behaves differently is a `WP-08` reopening, not a `WP-18` finding."* Ten seconds of real bench capture would retire this risk entirely, which makes `OQ-09` worth more than its position in the register suggests.

---

### `RV-18` · **MEDIUM** · The riskiest gate in the migration has no package of its own

`prove_equal.py` (`IMP-0019`) gates `WP-16`, which deletes ~2,500 lines and retires a module. Risk `R-2` names the failure — *"`WP-16` is started before `prove_equal.py` is clean, because the deletions look obvious"* — and the mitigation is a line inside `WP-16` itself. A gate that lives inside the package it gates is opened by whoever opens the package.

**Fix.** Cut it out as `WP-15a`, prerequisite `WP-10`, exit *"reports zero unexplained failures across all seven rows of Design §28.3"*. `WP-16` then has a **ticked prerequisite**, which is the only mechanism the plan trusts anywhere else.

---

### `RV-19` · **MEDIUM** · `WP-01` cannot distinguish *green* from *green because empty*

`WP-01` builds eight check scripts before the code they govern exists. `ANL-SW-02`/`-03`/`-04`/`-08` scan the C++ engine, which does not exist until `WP-03`; `ANL-SW-05` walks a per-tick call graph that does not exist until `WP-13`. Their planted-violation tests (`TV-3`) prove the *check* works — they do not prove the check is *pointed at anything*.

**Fix.** One line in `WP-01`'s exit: each check reports the **number of files it scanned**, and a check reporting zero is `SKIPPED`, never `PASSED`. This is the same discipline `IFQ-05` already reached for the standalone schema check — *"a check that silently passes on zero inputs dies quietly."* It should be the general rule, not one question's answer.

---

### `RV-20` · **MEDIUM** · `OQ-17` is a row and should be a gate

`OQ-17` (tool qualification / functional-safety constraints) is marked *"answer early"* in three documents and *"potentially everything"* in the System Requirements. If it returns *yes*, it changes requirement style, verification evidence and the size of the document set — **after** 31 packages have been cut against the current style.

**Fix.** Promote it from a register row to a **baselining gate**, beside `OQ-01`/`OQ-11`/`OQ-14`/`OQ-16`, and state the fallback explicitly: *"if unanswered by `WP-05`, the chain is built to the current style and re-styling is accepted as a known, scoped cost."* An unanswered question with a written fallback is manageable; one without is a surprise.

---

## 4. Open Questions — answers I am confident in

The register invited these. Each below is offered as an **answer with its argument**, for you to accept or overturn; the rest of the register I am deliberately not touching, because it is genuinely external.

| ID | Answer | Argument |
|---|---|---|
| `IFQ-01` **µs or ns** | **`timestamp_us`** — confirm the leaning | Not on the "false precision" argument alone, which is weak, but on unit agreement: `SYS-0072` and `R-SIM-18` already fix the period as `<COMPONENT>_<FN>_PERIOD_US` in **integer microseconds**, and `SW-0046` refuses a fractional one. A nanosecond header beside a microsecond period puts two units in adjacent fields of the same contract. Width does not decide it — `uint64` µs is 584,000 years, `uint64` ns is 584 years, both ample. **One thing to write down with it:** the bus stays integer nanoseconds (`SW-0046`), so translation multiplies by 1000 exactly once, at ingest. Say so in `SW-0033`, or `ANL-SW-02`'s ban on unit conversion in the engine will trip on it |
| `IFQ-02` **monotonic?** | **Required; a violation is reported, never clamped** — confirm | Add one consequence the register does not state: a non-monotonic `t_source` invalidates **rung 3** of `SW-0050`'s ladder for that port, so the violation must *demote the port a rung*, not merely warn. Otherwise the ladder claims a quality the data does not have |
| `IFQ-06` **one stamp or two** | **One in the header — but the default is only safe because the *recording* supplies the other**, and that dependency must be written down | `CN-0298` and `SW-0044` require two distinct timestamps and forbid defaulting one to the other. With one header field, `t_recv` must come from the recording envelope. MCAP has one. **If `OQ-09` returns "TDMS carries no per-message reception stamp", `IFQ-06` flips to two fields** — so make `IFQ-06`'s answer explicitly conditional on `OQ-09` rather than independent of it |
| `OQ-13` **same-step default?** | **Close it: yes, and `delay_steps` is in the spec from day one, default 0** | It is already decided by the schema. §3.1 carries `inputs[].delay_steps`; `SW-0073` is `P1·R1`. The field costs nothing to carry and the modelling is then data, not a redesign. The question is answered by the artifact and only the register does not know it |
| `OQ-03` **module instances** | **Close it: declared unbounded, exercised at 2, shipped at 1** | `CN-0092`/`SYS-0043` already require instance renaming, and `SW-0389` makes port identity independent of producer — so N instances cost a name prefix and nothing else. `graph/build.py::instantiate` is already scheduled (`WP-30`). Asking the module teams for a number invites an answer that becomes a limit |
| `OQ-21` **build or adopt the viewer** | **Close it: keep what exists** | `SI-19` is 16-of-17 `DONE` and SwReq §30.2 calls it the strongest area in the codebase. `WP-26` is a *split* of a working 1,990-line Qt surface, not a rewrite. Adopting a third-party surface now would discard the one thing v1 got unambiguously right, to solve a problem nobody has reported |
| `OQ-20` **naming** | **Close it: neutral role names in the requirement documents; `Vantage`/`Bench`/`Campaign` remain the product and UI names** | The register calls it *"nothing technical"*, which is true and is why it should be closed rather than carried. It is blocking in exactly one place: `WP-02(d)` edits `modules/sim/CLAUDE.md`, which still uses the v1 names throughout, and that edit cannot be written while the question is open |
| `OQ-05` **which components are real** | **Narrowed, not closed:** `df` and `vdy` are the two with generated port manifests and real libraries (confirmed against `modules/` and the v1 plan's `S-C1d`) | Still needs the module teams to say which of the remaining nine are functional versus structural — but `E2E-02`/`-03`/`-10` and `IT-22`'s *"a second component completes the checklist unaided"* can both be planned against `df` + `vdy` today rather than waiting |

**Not answered here, correctly external:** `OQ-01`, `OQ-02`, `OQ-04`, `OQ-06`, `OQ-07`, `OQ-09`, `OQ-10`, `OQ-11`, `OQ-12`, `OQ-14`, `OQ-15`, `OQ-16`, `OQ-17`, `OQ-18`, `OQ-19`, `OQ-22`.

---

## 5. Open Questions I would add

The register is a view over the authored documents, so a question nobody wrote down is invisible to it. These eight are not in it.

| Proposed | Question | Marker | Blocks |
|---|---|---|---|
| `OQ-23` | **How does `t_sim` advance** — fixed grid step, or driven by reconstructed cycle boundaries? | `BLOCKS` | `SW-0064`, `SW-0065`, `SW-0109`, `SW-0110` — `RV-01` |
| `OQ-24` | Does a **data-driven module contribute its period to the GCD**? | `BLOCKS` | `SW-0006`, `SW-0062` — `RV-01` |
| `OQ-25` | **Is snapping kept?** If yes, `R-SIM-18` must be amended in the same pass | `DEFAULT` (drop it) | `SW-0063`, `SW-0173`, `SYS-0068` — `RV-02` |
| `OQ-26` | **Who reads the recording's topic index**, and in what shape does `graph/`/`ingest/` receive it? | `BLOCKS` | `WP-20` (25 `IMP` rows) — `RV-04` |
| `OQ-27` | **Is `resolve/` a permitted `ctypes` site**, bounded to `adasManifest`/`adasAbiVersion`? | `DEFAULT` (yes, symbol-bounded) | `ANL-SW-07`, `ANL-SW-34` — `RV-03` |
| `OQ-28` | **Is the spec emitted in one pass or two** (probe → resolve → emit)? | `BLOCKS` | `WP-05`, the first real package — `RV-04` |
| `OQ-29` | **`t_capture` vs `capture_time_ns`** — one word, two opposite meanings. Which survives? | `DEFAULT` (`R-SIM-14`'s wins; rename the concept's to `t_recv`) | Every timing requirement — `RV-07` |
| `OQ-30` | Does **`MP-1` exit provisionally** without a real foreign sample, or is `WP-08` gated on obtaining one? | `EXTERNAL` | `MP-1`'s exit gate — `RV-17` |

---

## 6. What is right, and should not be disturbed

Recorded so that a fix for one of the above does not cost one of these.

| | |
|---|---|
| **The five claimed code defects are all real.** | I checked each against the code: `severed_chains()` (`pipeline.py:1043`) genuinely inspects one hop in each direction; `group_by_log_time` is genuinely called by all three drivers; the whole recording is genuinely materialised three times in Python; the ctypes host is genuinely on the per-tick path. The evidence base is honest, which is rarer than it sounds |
| **The seam is drawn in the right place, and `IT-01` is the right test.** | *"Delete the configuration tree, run from the spec alone, compare port values"* is the only test that can prove a language boundary rather than assert it |
| **The `Now.` field with an expiry date.** | A dated snapshot that is deleted at `MP-6` is the correct answer to *"we need to know where we are"* without creating the second stored status `SW-0373` forbids |
| **Cycle reconstruction assigned to `SI-02`, not `SI-01`.** | SwReq §2.4's reasoning is the sharpest paragraph in the set: putting it in the reader is what made it a per-format decision, and a per-format decision is how one format's assumption became every format's behaviour |
| **Checks before code (`O-1`), tests moving before their code (§2.2), deletion last and alone (`O-5`).** | Three independent mechanisms that all make the migration reversible. `RV-18` and `RV-19` sharpen them; nothing here weakens them |
| **`DD-13`'s honesty about the two missing readers.** | Refusing to write a reader against a specification and no file is the right call, and saying so in the plan rather than discovering it at `WP-18` is why `RV-17` is a small fix rather than a lost phase |

---

## 7. What I would change, per document, on your go-ahead

| Document | Findings | Size |
|---|---|---|
| `SIM_Concept_Document_v0.3.1.md` | `RV-01` (§12.3 precedence line), `RV-02a` (drop `CN-0147`), `RV-07` (`t_capture` → `t_recv`), `RV-11` (add `resim` to §15.3) | ~4 edits, no UID renumbering |
| `SIM_System_Requirements_v0.1.md` | `RV-01` (new `SYS` in §8.3), `RV-02` (`SYS-0068`), `RV-04` (parent for `RecordingIndex`), `RV-07`, `RV-20` (`OQ-17` → gate) | ~5 edits, 1–2 new `SYS` |
| `SIM_Software_Requirements_v0.1.md` | `RV-01`, `RV-02`, `RV-03` (`SW-0017`/`SW-0164`), `RV-04` (new `SW`), `RV-05` (`cpp/**`), `RV-07`, `RV-12`, `RV-14` | ~8 edits, 2 new `SW` |
| `SIM_Implementation_Design_v0.1.md` | `RV-04` (§3 two-pass), `RV-06`, `RV-08`, `RV-09`, `RV-10` (recount §2.2) | ~5 edits |
| `SIM_Implementation_Plan_v0.1.md` | `RV-15` (§0.1 table → 5 rows), `RV-16`, `RV-17`, `RV-18` (new `WP-15a`), `RV-19` | ~5 edits, 1 new `WP` |
| `SIM_Software_Test_Spec_v0.1.md` | `RV-05` (7 rows), `RV-13` | ~8 edits |
| `SIM_Open_Questions_v0.1.md` | §4 answers from §4 above; §5's eight new rows; `RV-08`'s stale `WP-05` | rewrite §1 and §3 |
| `docs/v2/py/trace_check.py` | `RV-05` (assert every scanned path exists), `RV-13` (emit the counts) | ~2 additions |
| `.claude/rules/sim.md` | `R-SIM-18` (`RV-02`), `R-SIM-5` (`RV-15`) — **at `WP-02`, with the code, never before** | 2 rules, deferred |

**Suggested sequence:** decide `RV-01`…`RV-04` and §4's answers first — they are the only ones that change requirement *content*. Everything else is one editing pass that can follow immediately after.
