# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Provenance record for this directory's fixtures -- **not a generator that
runs from a clean checkout**, unlike `tests/fixtures/make_tiny_mcap.py`'s
purely-synthetic sibling. `SM-05a`'s own exit condition needs a *real*
CarMaker `.erg` sample, not a synthetic one, and a real one cannot be
synthesized -- it requires an actual CarMaker TestRun. This file documents
exactly how these bytes were produced, so a future regeneration (a new
component build, a new scenario) is a repeat of these two steps, not a
re-derivation.

Step 1 -- the `.erg`/`.erg.info` pairs: copied verbatim from a real
`bsd/bsd_tos_left_straight` TestRun (`modules/df/src/platform/cm/SimOutput/`,
gitignored there -- CarMaker run output is transient by design, R-SIM-9's
"world-model bindings ... live with the tooling" logic applied to a
supplier's own output tree). `bsd_tos_left_straight_1row.erg` is a real
152-byte single-tick capture (the smallest real file from that session);
`bsd_tos_left_straight_3000row.erg` is the same TestRun's full 60s/3000-tick
run (`.info` schema identical between the two, `diff`-confirmed at the time
of copy -- only per-run timestamps/RandomSeed differ).

Step 2 -- the `.manifest.pb` sidecars: the real `adas.sil.ComponentManifest`
bytes served by `adasManifest()` on an already-built `df_sil.so`
(`modules/df/build-gtest-ubuntu_gcc/tests/libdf_sil.so` at the time of
capture), dumped via the same two-call size-then-fill pattern
`cm_host.cpp` uses:

    import ctypes
    lib = ctypes.CDLL("<path to a real libdf_sil.so/df_sil.dll>")
    lib.adasManifest.restype = ctypes.c_size_t
    lib.adasManifest.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    needed = lib.adasManifest(None, 0)
    buf = ctypes.create_string_buffer(needed)
    lib.adasManifest(buf, needed)
    open("<stem>.manifest.pb", "wb").write(buf.raw[:needed])

Both `_1row` and `_3000row` share one manifest (same component build) --
duplicated per stem rather than symlinked, since a symlink is not portable
across this repo's Windows/WSL/Linux checkouts.
"""
