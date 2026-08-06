# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim batch`'s per-recording subprocess entry point (S-D7, `R-SIM-19`).

`core/batch.py` launches ONE of these per recording (`sim batch`/Campaign
isolates at run granularity, never per tick) via `sys.executable -m
adas_sim.core.batch_worker`. This module does exactly one recording's worth
of `Pipeline.load` -> `init_components` -> `resim_pipeline` -> `shutdown_
components` -- the same four calls `cli/resim.py` already makes for one
recording -- and writes its outcome as JSON to `--out-json` before exiting.

The parent process is the one that turns "this subprocess died / hung /
raised" into `crash`/`timeout`/`fail` (`core/batch.py`'s own job): this
module only ever reports `ok` or `fail` for itself, because a REAL crash
(a segfault in a `dll:`/`stubdll:` library) kills this process before it can
write anything -- there is no code path here that could report `crash`
about itself, which is exactly why the parent classifies from the outside
(missing/unreadable JSON + an abnormal exit) rather than trusting a value
this process claims about its own death.

`--checkpoint-json`, if given, is overwritten after every tick
(`resim_pipeline`'s own `on_tick=`, `UT-D7-7`) with the tick count and
`t_ns` reached so far. This is the ONLY record of progress that survives a
real crash -- this process's own in-memory state dies with it, so
`core/batch.py` reads the checkpoint file from the outside, same as it
classifies `crash` itself from the outside.

Two test-only hooks exist, both explicitly named and never reachable from a
real `sim batch` invocation:

- `ADAS_SIM_BATCH_TEST_STUB=crash|hang` (env var, checked before anything
  else, applies to every recording this process is launched for) --
  forces this process to die abnormally or hang forever, with NO pipeline
  involved. Exists so `core/batch.py`'s crash/timeout CLASSIFIER can be
  tested deterministically (`UT-D7-7`/`UT-D7-8`) without a real component
  that can be told to segfault or spin. `ADAS_SIM_BATCH_TEST_STUB_MAP=
  "stemA=crash;stemB=hang"` is the per-recording form (keyed by
  `--recording`'s own `.stem`) -- lets ONE `sim batch` invocation over a
  real recording set make specific recordings crash/hang while the rest
  run for real (`ST-D7-5`'s "one deliberately crashing and one
  deliberately hanging" inside a single batch).
- `--test-stub-echo NAME` (repeatable CLI flag) -- injects a trivial,
  zero-port `InProcessSilComponent` for stage `NAME` via `Pipeline.load`'s
  own `components=` kwarg (the documented mechanism for supplying a stage
  Python cannot resolve from a bare `impl:` string). Exists so `sim batch`'s
  real end-to-end path (`ST-D7-2`/`ST-D7-3`) can be exercised with no
  compiled `dll:`/`stubdll:` component available.
- `ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK=N` (env var) -- unlike the blanket
  `crash` hook above (which dies before any pipeline runs at all), this one
  lets a REAL resim run N ticks for real, then `os._exit(139)` from inside
  `on_tick` -- the one shape the blanket hook cannot produce, and the one
  `UT-D7-7`'s checkpoint claim actually needs: proof that `--checkpoint-json`
  reflects real progress at the moment of death, not just "some value or
  other."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.errors import SimError
from adas_sim.core.resim import resim_pipeline

#: Values `ADAS_SIM_BATCH_TEST_STUB` recognizes -- a closed set, same
#: discipline every other closed vocabulary in this codebase uses, so a typo
#: fails loudly (KeyError) rather than silently running the real pipeline.
_TEST_HOOKS = ("crash", "hang")


def _empty_manifest(name: str) -> ComponentManifest:
    """A manifest with no declared ports -- `--test-stub-echo`'s own stage
    therefore needs no `inputs:` wiring in the test pipeline file, and
    `resim_pipeline` calls `exec()` with an empty input map every tick."""
    return ComponentManifest(
        component=name, version="test", abi_version=1, build_id="test-stub-echo",
        inputs=(), outputs=(), project="", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _echo_component(name: str) -> InProcessSilComponent:
    return InProcessSilComponent(name=name, manifest=_empty_manifest(name), fn=lambda dt_ns, inputs: {})


def _hook_for_recording(recording: Path | None) -> str | None:
    """Two ways to name a hook, both explicit and neither reachable from a
    real `sim batch` invocation:

    - `ADAS_SIM_BATCH_TEST_STUB=crash|hang` -- applies unconditionally,
      regardless of which recording this process was launched for. Simplest
      shape, for a test driving one worker process directly.
    - `ADAS_SIM_BATCH_TEST_STUB_MAP="stemA=crash;stemB=hang"` -- keyed by
      `recording.stem`, so ONE `sim batch` invocation over a real recording
      SET can make specific recordings crash/hang while the rest run for
      real (`ST-D7-5`'s own scenario: "one deliberately crashing and one
      deliberately hanging" inside a single batch of 20).
    """
    blanket = os.environ.get("ADAS_SIM_BATCH_TEST_STUB")
    if blanket is not None:
        return blanket
    mapping = os.environ.get("ADAS_SIM_BATCH_TEST_STUB_MAP")
    if mapping is None or recording is None:
        return None
    for entry in mapping.split(";"):
        stem, _, hook = entry.partition("=")
        if stem == recording.stem:
            return hook
    return None


def _maybe_run_test_hook(recording: Path | None) -> None:
    """`recording` is `None` when called before argument parsing (the
    blanket-only, single-process case); real per-recording dispatch via
    `_TEST_STUB_MAP` needs `args.recording`, so `main()` calls this a
    second time, harmlessly, once parsing has happened."""
    hook = _hook_for_recording(recording)
    if hook is None:
        return
    if hook not in _TEST_HOOKS:
        raise ValueError(f"test stub hook {hook!r} not in {_TEST_HOOKS}")
    if hook == "crash":
        # Dies immediately with no chance to write --out-json -- the exact
        # shape a real segfault leaves for the parent to classify from
        # (UT-D7-7): abnormal exit, no result file.
        os._exit(139)
    # hook == "hang": never returns. The PARENT's subprocess timeout is what
    # ends this (UT-D7-8) -- there is deliberately no in-process timeout
    # here to race against it.
    time.sleep(10_000_000)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adas_sim.core.batch_worker")
    parser.add_argument("--recording", type=Path, required=True)
    parser.add_argument("--pipeline", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--search", type=Path, action="append", default=[])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--test-stub-echo", action="append", default=[], metavar="STAGE_NAME")
    parser.add_argument("--checkpoint-json", type=Path, default=None)
    return parser


def _write_result(out_json: Path, **fields: object) -> None:
    out_json.write_text(json.dumps(fields, sort_keys=True), encoding="utf-8")


def _write_checkpoint(path: Path, *, tick_count: int, last_tick_ns: int) -> None:
    """Overwritten after every tick (`UT-D7-7`) -- written to a sibling
    `.tmp` path and `os.replace`d into place so a reader (`core/batch.py`,
    after this process is already dead) never observes a torn write, same
    discipline `Recorder`/writer code elsewhere in this framework uses for
    any file another process reads concurrently."""
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps({"tick_count": tick_count, "last_tick_ns": last_tick_ns}), encoding="utf-8")
    os.replace(tmp_path, path)


def main(argv: list[str] | None = None) -> int:
    _maybe_run_test_hook(None)  # the blanket-only shortcut, before paying for argparse

    args = _build_parser().parse_args(argv)
    _maybe_run_test_hook(args.recording)  # the per-recording ADAS_SIM_BATCH_TEST_STUB_MAP case
    components = {name: _echo_component(name) for name in args.test_stub_echo} or None

    crash_after_tick = os.environ.get("ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK")
    progress: dict[str, int | None] = {"tick_count": 0, "last_tick_ns": None}

    def _on_tick(tick_count: int, t_ns: int) -> None:
        progress["tick_count"] = tick_count
        progress["last_tick_ns"] = t_ns
        if args.checkpoint_json is not None:
            _write_checkpoint(args.checkpoint_json, tick_count=tick_count, last_tick_ns=t_ns)
        if crash_after_tick is not None and tick_count == int(crash_after_tick):
            os._exit(139)  # see ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK in this module's docstring

    try:
        pipeline = Pipeline.load(args.pipeline, search=tuple(args.search), components=components)
        pipeline.init_components(args.config)
        try:
            outputs = resim_pipeline(pipeline, args.recording, on_tick=_on_tick)
        finally:
            pipeline.shutdown_components()
    except SimError as exc:
        _write_result(
            args.out_json, outcome="fail", error=str(exc),
            tick_count=progress["tick_count"], last_tick_ns=progress["last_tick_ns"],
        )
        return 1
    except Exception as exc:  # noqa: BLE001 -- a framework bug is still a clean "fail" report,
        # never a silent process death; only os._exit (the test hook above) or a real
        # crash inside a C library skips this reporting path entirely.
        _write_result(
            args.out_json, outcome="fail", error=f"{type(exc).__name__}: {exc}",
            tick_count=progress["tick_count"], last_tick_ns=progress["last_tick_ns"],
        )
        return 1

    last_tick_ns = outputs[-1][0] if outputs else None
    _write_result(args.out_json, outcome="ok", tick_count=len(outputs), last_tick_ns=last_tick_ns)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
