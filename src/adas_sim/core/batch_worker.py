# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim batch`'s per-recording subprocess entry point (`S-D7`, `R-SIM-19`).

`core/batch.py` launches one of these per recording -- isolation is at run
granularity, never per tick. This module does one recording's worth of
`Pipeline.load` -> `init_components` -> `resim_pipeline` -> `shutdown_components`
and writes its outcome as JSON to `--out-json`.

**It only ever reports `ok` or `fail` about itself.** A real crash kills this
process before it can write anything, so the parent classifies
`crash`/`timeout`/`fail` from the outside (missing JSON plus an abnormal exit)
rather than trusting a value a dying process claims about its own death.

`--checkpoint-json` is overwritten after every tick, and is the only record of
progress that survives a crash -- in-memory state dies with the process.

Three test-only hooks, never reachable from a real `sim batch`:

- `ADAS_SIM_BATCH_TEST_STUB=crash|hang` -- die or hang with no pipeline
  involved, so the parent's classifier can be tested without a component that
  can be told to segfault. `ADAS_SIM_BATCH_TEST_STUB_MAP="stemA=crash;stemB=hang"`
  is the per-recording form.
- `--test-stub-echo NAME` -- inject a zero-port `InProcessSilComponent` for one
  stage, so the end-to-end path (`ST-D7-2`, `ST-D7-3`) runs with no compiled
  component available.
- `ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK=N` -- run N ticks for real, then exit
  abnormally from inside `on_tick`. The one shape the blanket hook cannot
  produce, and what proves the checkpoint reflects real progress at the moment
  of death.
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
