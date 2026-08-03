# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`PortValue`, `Tick` (sim_api_reference.md §2.2). Frozen at S-B2, moved
ahead of `S-B1` in the actual build order (`sim_implementation_plan.md`'s own
finding: `S-B1`'s tests need `Tick`/`LayerCtx`, which are S-B2 deliverables,
and S-B2 has no dependency back on S-B1 -- confirmed with the user before
writing code).

**Note on precedence.** `sim_architecture.md` §5.3's own `Tick` sketch splits
ports into three separate mappings (`stimulus`/`observation`/`truth`); this
stage's own checklist line says "api reference §2.2" explicitly, so the
unified `ports: Mapping[str, PortValue]` + `.port(name)` shape below is what
is implemented -- and it does not lose information, because `PortValue.origin`
already carries the measured/truth/mocked/simulated/overridden tag the
three-way split existed to express (R-SIM-12).

**`S-B2Δ`** (`OD-9`, `OD-13`) changed `PortValue` in two ways:

- `message` is **lazily parsed and memoised over retained bytes** rather than
  eagerly decoded at construction. A `Session` is then bounded by the
  recording's own size, not by parsed-message count (`NR-SIM-41`'s
  escalation step 1 -- "stop deserializing what nobody reads"). A caller
  that already has a decoded object (a test, or `contracts/pipeline.py`'s
  live SIL execution) still passes it as `message=`; only a caller passing
  raw bytes plus `schema_bytes`/`schema_name` gets the deferred parse.
- `age_s` **stops being a plain stored field and becomes derived**:
  `(t_ns - capture_ns)/1e9` when the recording's own capture stamp is known
  (`capture_ns`, from `S-A4Δ`), else whatever `hold_age_s` the caller already
  computed from its own schedule (`R-SIM-18` -- `contracts/pipeline.py`'s
  own multi-rate hold tracking). The two sources are **distinguishable**
  (`capture_ns is not None` says which one fired), which is the ambiguity
  today's bare stored float could not express (`UT-B2-13`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from adas_sim.core.errors import AuthoringError

#: Extended with "unknown" beyond api reference §2.2's literal five values,
#: mirroring `io.base.Provenance` (R-SIM-6): a Tick built from a no-meta
#: recording has ports whose origin is honestly unknown, not fabricated.
Origin = Literal["measured", "truth", "mocked", "simulated", "overridden", "unknown"]

#: Marks `PortValue._parsed` as not-yet-computed -- distinct from any real
#: decoded value (including `None`, itself a legitimate "invalid" message).
_UNPARSED = object()


@dataclass(frozen=True, slots=True)
class Pose2D:
    """Ego pose in the world frame (R-COORD-1)."""

    x_m: float
    y_m: float
    yaw_rad: float

    def __repr__(self) -> str:
        return f"<Pose2D x_m={self.x_m:.2f} y_m={self.y_m:.2f} yaw_rad={self.yaw_rad:.3f}>"


def decode_message(schema_bytes: bytes, schema_name: str, payload: bytes) -> Any:
    """Builds the message class from an embedded `FileDescriptorSet` at run
    time (R-SIM-11: no generated bindings required) and parses `payload`.
    Returns `payload` unchanged if no schema is available to decode with --
    degrading, never raising, so a recording predating a component's
    embedded-schema support still replays (R-SIM-6). Moved here from
    `core/runner.py` at `S-B2Δ`: `PortValue.message`'s own lazy parse is the
    only caller that matters now, and both modules stay import-cycle-free
    this way (`core/runner.py` re-uses this one, never a second copy).
    """
    if not schema_bytes:
        return payload
    # Deferred: importing adas_sim.core must not pull in protobuf as a side
    # effect (UT-A1-2) -- only decoding an actual schema needs it.
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    file_descriptor_set = descriptor_pb2.FileDescriptorSet()
    file_descriptor_set.ParseFromString(schema_bytes)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in file_descriptor_set.file}
    added: set[str] = set()

    def add(file_proto: descriptor_pb2.FileDescriptorProto) -> None:
        if file_proto.name in added:
            return
        added.add(file_proto.name)
        for dependency in file_proto.dependency:
            if dependency in by_name:
                add(by_name[dependency])
        pool.Add(file_proto)

    for file_proto in file_descriptor_set.file:
        add(file_proto)

    descriptor = pool.FindMessageTypeByName(schema_name)
    message_cls = message_factory.GetMessageClass(descriptor)
    message = message_cls()
    message.ParseFromString(payload)
    return message


@dataclass(frozen=True, slots=True, init=False)
class PortValue:
    """One port's value for one tick. `message` is `Any` -- a decoded
    protobuf message, raw bytes if no schema, an already-decoded object a
    caller handed in directly, or `None` when invalid -- resolved lazily and
    memoised (`S-B2Δ`, `UT-B2-14`): nothing is parsed until `.message` is
    actually read.
    """

    name: str  # fully qualified, N-2: "<component>.<port>"
    origin: Origin
    valid: bool
    updated: bool  # False when held from an earlier tick (multi-rate)
    #: The recording's own second stamp (`S-A4Δ`), when known -- drives the
    #: capture-derived half of `age_s`.
    capture_ns: int | None
    #: Set instead of `capture_ns` when age comes from multi-rate holding
    #: (`R-SIM-18`), e.g. `contracts/pipeline.Pipeline.step()`'s own
    #: schedule tracking -- never both at once for one `PortValue`.
    hold_age_s: float | None
    #: This `PortValue`'s own tick time -- `age_s`'s other half of
    #: `(t_ns - capture_ns)/1e9`.
    t_ns: int
    schema_bytes: bytes = field(repr=False)
    schema_name: str = field(repr=False)
    _raw: Any = field(repr=False)
    _parsed: Any = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        name: str,
        origin: Origin,
        message: Any = None,
        valid: bool = True,
        updated: bool = True,
        capture_ns: int | None = None,
        hold_age_s: float | None = None,
        t_ns: int = 0,
        schema_bytes: bytes = b"",
        schema_name: str = "",
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "updated", updated)
        object.__setattr__(self, "capture_ns", capture_ns)
        object.__setattr__(self, "hold_age_s", hold_age_s)
        object.__setattr__(self, "t_ns", t_ns)
        object.__setattr__(self, "schema_bytes", schema_bytes)
        object.__setattr__(self, "schema_name", schema_name)
        object.__setattr__(self, "_raw", message)
        object.__setattr__(self, "_parsed", _UNPARSED)

    @property
    def message(self) -> Any:
        if not self.schema_name:
            return self._raw  # nothing declared to parse with -- raw bytes or an already-decoded object, as-is
        if self._parsed is _UNPARSED:
            object.__setattr__(self, "_parsed", decode_message(self.schema_bytes, self.schema_name, self._raw))
        return self._parsed

    @property
    def raw_bytes(self) -> bytes:
        """The undecoded wire bytes this `PortValue` was built from --
        independent of whether `.message` has since parsed them (`S-C9`):
        what a resim harness feeds `contracts.pipeline.Pipeline.exec`'s
        byte-only `stimulus`/`measured`. Raises if this `PortValue` was
        built from an already-decoded object instead of bytes (a synthetic
        test tick) -- there is nothing to hand back."""
        if not isinstance(self._raw, (bytes, bytearray)):
            raise AuthoringError(
                expected="a PortValue built from raw bytes", found=type(self._raw).__name__,
                where="adas_sim.core.tick.PortValue.raw_bytes",
                hint="this PortValue was constructed from an already-decoded object, not recorded bytes",
            )
        return bytes(self._raw)

    @property
    def age_s(self) -> float:
        if self.capture_ns is not None:
            return (self.t_ns - self.capture_ns) / 1e9
        if self.hold_age_s is not None:
            return self.hold_age_s
        return 0.0  # updated this tick, no schedule to hold against

    def __repr__(self) -> str:
        return f"<PortValue {self.name!r} origin={self.origin} valid={self.valid} age_s={self.age_s:.3f}>"


@dataclass(frozen=True, slots=True)
class Tick:
    index: int
    t_ns: int  # integer, accumulated from dt_ns -- never a float sum
    dt_ns: int
    ports: Mapping[str, PortValue]  # keyed by fully qualified name
    pose: Pose2D  # ego pose in the world frame

    def __post_init__(self) -> None:
        # A MappingProxyType, not a plain dict: freezing the Tick dataclass
        # only blocks `tick.ports = ...`, not `tick.ports["x"] = y` -- the
        # in-place mutation UT-B2-11 requires to raise (Session immutability).
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))

    @property
    def t_s(self) -> float:
        return self.t_ns / 1e9  # derived, never fed back

    def port(self, name: str) -> PortValue:
        try:
            return self.ports[name]
        except KeyError:
            raise AuthoringError(
                expected=f"a port named {name!r}",
                found=f"available ports: {sorted(self.ports)}",
                where="adas_sim.core.tick.Tick.port",
                hint="check the port name against the component's manifest",
            ) from None

    def __repr__(self) -> str:
        return f"<Tick index={self.index} t_ns={self.t_ns} ports={len(self.ports)}>"
