# SIM Test Execution — 2026-08-31 — CI descope, `WP-01` closure, board `#25`

**Campaign:** close out hosted CI as an open item (author's decision,
2026-08-31: hosted CI is out of scope). Not a fix, not an abandonment — a
recorded decision.

## What changed

1. **`scripts/ci_gate.py`** — untouched. It remains the real, working local
   gate, run by hand, invoked identically to how `.github/workflows/sim-ci.yml`
   would have invoked it.
2. **`.github/workflows/sim-ci.yml`** — kept, not deleted, with a new header
   stating plainly: hosted CI is out of scope by decision; this file has never
   been observed running through real GH Actions infrastructure and none is
   being sought; nobody is watching it; it is not wired to anything. Reason
   given inline (the commands it would run are already run by hand on every
   platform that matters). Kept only as a written starting point should
   hosting ever be revisited — its presence must never be read as evidence a
   run has passed.
3. **`docs/v2/SIM_Implementation_Plan_v0.1.md`, `WP-01`** — `IMP-0366` (the
   `.github/workflows/` item) closed `[x]`, against the descope decision, not
   against an observed hosted run. Its "Files" bullet and its
   Windows/Linux-comparison "Exit" bullet closed alongside it for the same
   reason (`OQ-15` — which CI system — is resolved: none, by decision). Read
   `CN-0351` ("CI shall be established at the start of the build order") as
   satisfied by the check harness existing and running green from increment
   one, which it has — not by a hosted execution channel this project never
   committed to building. `WP-01`'s `Lands` count moves from 16/18 to 17/18.
   **`IMP-0417` stays open, `[~]`, untouched** — its own closure condition
   (the first `WP` that cites an artifact kind `true` in
   `conf/artifact_kinds.yaml`) is real, unrelated to CI, and scoped to `WP-31`
   content nobody has written yet. `WP-01` therefore does **not** fully close
   this pass; it is not one of the two items this session was asked to
   resolve, and inventing `known_limits.yaml` content to force it closed would
   be exactly the improvised bigger change the session's own instructions
   warn against. `trace_check.py --write-status` regenerated the `Built.`
   lines this implies (`SW-0366`, `SYS-0250`); `trace_check.py` (no args)
   reports `PASS` after.
4. **`scripts/ci_gate_config.yaml`** — `tests/system/test_a1_install.py::
   test_conan_editable_add_resolves_adas_sim` added to `known_flakes`. This
   test was not skipping in this environment as its docstring assumes; it was
   running and failing with `event=unexpected_failure`, turning the whole
   gate red. Root cause, captured directly: `conan graph info` needs to
   authenticate against the `adas-local` remote and this environment has no
   non-interactive credentials for it (`ERROR: EOF when reading a line`) — an
   environment-credential gap, not a code regression, and exactly the kind of
   thing a hosted runner would have had to solve with secrets management
   rather than something this decision left unsolved. Declared **not-doing**,
   per the author's decision, not "pending until `WP-31`" as the Parked table
   used to say.
5. **`misc/START_HERE.md`** — new Decision F (hosted CI out of scope,
   `WP-01`'s two items not-doing). Parked table's two `R-REQ-9`/Conan-editable
   rows removed (they were never really "parked" waiting on `WP-31` — they
   were decided today). Open risk #2 ("`WP-01` cannot close until a real
   GitHub Actions run is observed") removed — the condition it names will now
   never be pursued, so it is a resolved decision, not a standing risk.
6. **`misc/memory.md` §6** — corrected in place (not silently rewritten): the
   original "nothing tells you it is alive" bullets are kept, followed by a
   2026-08-31 correction explaining the two different answers that closed it —
   the *dated test-execution records* (eighteen exist under `docs/v2/` as of
   this edit, this file making the nineteenth) answer "no dated evidence it
   passes"; the *CI descope decision itself*, not a hosted job, answers
   "no CI anywhere" by making the question closed rather than open.
7. **`misc/CONSOLIDATED_REQUIREMENTS.md`**, board `#25` — re-marked 🟡→🟢.
   Headless parity (`GT-9`) is real and already proven; re-read against what
   the row's own sentence actually requires ("a script can do headlessly...
   for CI and for overnight batches") — an engine property, which exists —
   rather than a hosted job watching it, which was only ever evidence for
   that property, now explicitly not being pursued.

## Verification

- `python docs/v2/py/trace_check.py` — **PASS**, chain closes both directions,
  same 3 known-unparented `SW` / 2 known-`SYS`-without-`SW` notes as before
  (`SwReq §32.3`), nothing new introduced.
- `python docs/v2/py/trace_check.py --status` — `WP-01` now 17/18 (was 16/18),
  still listed "in flight" (not closed) because of `IMP-0417` alone; does not
  appear in "finish these first" or "next untouched package" (`WP-17`,
  unaffected).
- `python scripts/ci_gate.py --artifact-dir logs/ci_gate/<run>` — **`status=pass`**
  (was `status=fail` before the `known_flakes` addition, on
  `test_conan_editable_add_resolves_adas_sim`'s `unexpected_failure`).
  `pytest: 1080 collected, 1069 counted toward floor (floor=692)`. Every
  `check_*.py` clean. `sim check`: 18/18 scenarios, 0 unexpected. `check_trace.py`:
  154 `R-REQ-9` violations, informational only (`doc_rc` gates, not the grep
  half — see that script's own `main()`), unchanged by this pass and not
  claimed fixed.

## Not done, and not claimed

- The 154 `R-REQ-9` citations themselves are not fixed — they are v1-era test
  ids cited under a discipline note predating this restructure (see several
  `docs/v2/SIM_Software_Test_Spec_v0.1.md` rows: *"these are `docs/v1`-era
  test identifiers... predating this row's `v2` citation"*). Declaring the
  *test that watches this count* not-doing is not the same as declaring the
  count itself acceptable forever; nothing in this pass licenses ignoring a
  **new** `R-REQ-9` violation introduced by future work — `check_trace.py`
  still runs, still reports the number, still gates on document-chain closure.
  This pass only stops pretending a hosted job was ever going to fix it.
- `WP-01` is not fully closed (`IMP-0417` remains, `WP-31` scope) — see above.
- Board items other than `#25` untouched.
