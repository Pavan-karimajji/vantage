# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SyntheticSource` -- scripted stimuli, no world model
(`sim_implementation_plan.md` S-C2). The one `Source` every framework test
(including this stage's own `ST-C2-1`/`ST-C2-2`) runs against: a fixed
sequence of pre-encoded per-tick byte maps, in order, with no protobuf
dependency of its own (the caller decides what bytes mean).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import yaml

from adas_sim.contracts.scenario import Scenario
from adas_sim.core.errors import AuthoringError, InternalError


class SyntheticSource:
    """`script` is one `Mapping[str, bytes]` per tick, in declaration order.
    `emits()` is the union of every port any tick declares, computed once at
    construction -- so a pipeline's `source.*` wiring is validated at LOAD
    (`Pipeline.load`'s `source=`), before the first `poll()` (`R-SIM-10`)."""

    name: ClassVar[str] = "synthetic"

    def __init__(self, script: Sequence[Mapping[str, bytes]]) -> None:
        self._script: tuple[Mapping[str, bytes], ...] = tuple(dict(tick) for tick in script)
        self._emits = frozenset(port for tick in self._script for port in tick)
        self._index = 0
        self._started = False

    def __repr__(self) -> str:
        return f"<SyntheticSource ticks={len(self._script)} index={self._index}>"

    def __len__(self) -> int:
        return len(self._script)

    @classmethod
    def from_yaml(cls, path: Path) -> SyntheticSource:
        """`cli/record.py`'s own file form: a YAML list, one entry per
        tick, each entry `{port: <hex bytes>}` -- e.g.

            - veh_dyn: "0a0200000a"
              gen_object_list: ""
            - veh_dyn: "0a0200000b"

        Hex, not base64/raw text, because a `.yaml` scenario script is
        edited by hand and hex is what stays unambiguous next to YAML's
        own quoting rules."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise AuthoringError(
                expected="a YAML list, one mapping per tick", found=type(raw).__name__, where=str(path),
                hint='e.g. `- veh_dyn: "0a0b"`',
            )
        script = [{port: bytes.fromhex(value) for port, value in tick.items()} for tick in raw]
        return cls(script)

    def emits(self) -> frozenset[str]:
        return self._emits

    def start(self, scenario: Scenario) -> None:
        # No world model to reset -- the script is fixed at construction,
        # `scenario` is accepted only to satisfy the `Source` Protocol.
        del scenario
        self._index = 0
        self._started = True

    def poll(self) -> Mapping[str, bytes]:
        if not self._started:
            raise InternalError(
                expected="start() called before poll()", found="not started",
                where="SyntheticSource.poll", hint="call start() once before the first poll()",
            )
        if self._index >= len(self._script):
            raise AuthoringError(
                expected=f"poll() called at most {len(self._script)} time(s), this source's own script length",
                found=f"poll() call number {self._index + 1}", where="SyntheticSource.poll",
                hint="the pipeline ran longer than this source's scripted ticks -- extend the script",
            )
        tick = self._script[self._index]
        self._index += 1
        return tick

    def stop(self) -> None:
        self._started = False
