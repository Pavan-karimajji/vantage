# SIM Test Execution — 2026-08-31 — `simcore/io/codecs/mcap.cpp`'s `capture_time_ns` gap closed

**Campaign:** `mcap.cpp:25`'s own top-of-file note named an unresolved gap —
this codec's reader trusted `publishTime` as a real `capture_time_ns`
unconditionally, never replicating `io/mcap.py`'s `manifest_version >=
CAPTURE_TIME_MANIFEST_VERSION` gate (`R-SIM-14`), because `simcore` has no
structured `RunManifest` C++ type to read that field from. Read, resolved,
proven with a test — not the full `RunManifest` port the note said was
needed, since the fix only needs one integer, not the type.

## Root cause, confirmed by reading

`io/mcap.py::RecordingReader.messages` computes `capture_aware =
self.meta().manifest_version >= CAPTURE_TIME_MANIFEST_VERSION` **once per
file** and yields `capture_time_ns = message.publish_time if capture_aware
else None` — `manifest_version` defaults to `0` when no manifest exists at
all, so "no manifest" and "pre-two-clock manifest" are both, correctly,
*not capture-time-aware*. `simcore/io/codecs/mcap.cpp`'s `Pull()` had no
equivalent: `msg.capture_time_ns = static_cast<std::int64_t>(mv.message.
publishTime);`, unconditional, every file.

**A second, dormant bug found while tracing this, fixed alongside it:**
`simcore::io::ToString(MetaKind::kRunManifest)` returned `"run_manifest"` —
not the string Python's writer actually uses (`io/mcap.py::_MANIFEST_META =
"manifest"`). Nothing in the C++ tree called `GetMeta`/`WriteMeta` with this
enum value before this fix, so the mismatch never manifested as a failure —
but it would have silently defeated this very fix (`GetMeta("run_manifest")`
would never find the block Python/`overwrite_manifest_meta` write under
`"manifest"`). Corrected to `"manifest"` (`src/simcore/io/meta.cpp`).

## The fix

`src/simcore/io/codecs/mcap.cpp`:
- `kCaptureTimeManifestVersion = 2` — a second, named copy of `io/base.py
  ::CAPTURE_TIME_MANIFEST_VERSION`; no shared header exists between the
  Python and C++ sides to avoid the duplication, stated so nobody "fixes"
  it quietly out of sync.
- `ParseManifestVersion(bytes)` — a narrow, targeted scalar read of one
  `manifest_version:` line out of the opaque meta-block bytes. **Not a YAML
  parser and not the `RunManifest` type** the file's own top note said
  was missing — safe because the producer side is controlled
  (`manifest_to_dict` + `yaml.safe_dump(sort_keys=True)` always emits a
  bare, unquoted top-level integer).
- `McapReader::DetermineCaptureTimeAwareness()` — called once per `Open()`
  (mirroring Python's once-per-file computation), sets `capture_time_aware_`
  from `GetMeta(ToString(MetaKind::kRunManifest))` + the scalar above. No
  manifest block → `false` (never defaulted to "aware").
- `Pull()` — `capture_time_ns` is now `capture_time_aware_ ? publishTime :
  std::nullopt`, never the unconditional value it was.

This is the "explicit capability degradation, not a filled-in value" the
task's own framing asked for: the codec's declared `capabilities.capture_time
= true` stays true (the codec genuinely supports it, and its own writer is
always capture-time-aware by construction) — the degradation happens **per
file, per read**, exactly where `R-SIM-14` says it must: `capture_time_ns`
reads `nullopt` for a file nobody certified, never a plausible-looking
default.

## Test

Three cases added to `tests/unit/test_ut_io_mcap_roundtrip.cpp`'s existing
`UtIo22McapRoundtrip` suite (no new `UT-IO-nn` id allocated — `UT-IO-23`
through `UT-IO-29` are already spoken for by other, unrelated `SW`
requirements per `SIM_Software_Test_Spec_v0.1.md` §5.1; this is regression
coverage for a named defect, the same "no new requirement" shape
`test_ut_io_erg_negative.cpp`'s own top note already uses):

- `CaptureTimeReadsUnknownWithNoManifestBlock` — a message with an explicit
  `capture_time_ns` set (so `publishTime` really is deliberate), no manifest
  block written at all → reads back `nullopt`.
- `CaptureTimeReadsRealValueWhenManifestIsCaptureTimeAware` — a manifest
  block with `manifest_version: 2` → reads back the real value.
- `CaptureTimeReadsUnknownWhenManifestPredatesTwoClockModel` (planted
  violation, `R-REQ-9`) — a manifest block with `manifest_version: 1` (old)
  → still reads back `nullopt`, proving the gate actually discriminates on
  the version rather than merely on presence/absence of a block.

## Verification

- `cmake --build build-gtest-vs2026 --config Release --target simcore_tests`
  — clean rebuild of `simcore`/`simcore_tests`, no new warnings from this
  change (pre-existing `LNK4217` import-library warnings, unrelated).
- `simcore_tests.exe --gtest_filter=UtIo22McapRoundtrip.*` — **6/6 pass**
  (3 pre-existing + 3 new).
- Full `simcore_tests.exe` — **215 passed, 2 skipped, 1 failed** (218 total).
  The one failure, `UtEdg08Reproducer.WritesARealPackageWithEveryDeclaredPiece`
  (`%TEMP%\ut_edg_08_out` file-lock exception), is the **same pre-existing
  Windows temp-dir flake verified on 2026-08-28**
  (`docs/v2/SIM_Test_Execution_2026-08-28.md` line 44,
  `..._ingest.md` line 135) — confirmed unrelated here too: fails identically
  in isolation, before and after clearing the stale temp directory by hand,
  and touches none of `io/codecs`, `io/meta.cpp` or this fix's own files.
- `scripts/check_invariants.py` — clean.

## Not done, and not claimed

- `simcore` still has no structured `RunManifest` C++ type. This fix reads
  exactly the one field the capture-time gate needs and nothing more — a
  consumer needing any *other* manifest field (project, scenario, component
  list) still has no C++ way to get it. Named, not built; out of this item's
  scope.
- `ParseManifestVersion` is explicitly not a general YAML reader (stated in
  its own comment) — it must not be reused for another field without
  reconsidering whether a real parser is owed at that point instead.
