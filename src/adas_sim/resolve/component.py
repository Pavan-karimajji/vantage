# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SilComponent` -- one loaded component, over the generic ABI
(sim_sil_contract.md SS3-4, sim_api_reference.md SS3.1). Two implementations:
`CtypesSilComponent` (a real or `stubdll:` library) and `InProcessSilComponent`
(a Python callable + a manifest, what `impl: stub:` uses) -- every framework
test using the second needs no C++ build at all.

`CtypesSilComponent.exec` is the ONE place integer nanoseconds become the
ABI's float `dtS` (P-8). Port payloads cross this boundary as raw `bytes`
deliberately (R-SIM-11): `SilComponent` never needs a generated protobuf
binding, for its own wire form or for a component's.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

if sys.platform == "win32":
    # A malformed/wrong-architecture PE image (a deliberately-invalid test
    # fixture, or a genuine build mismatch) makes Windows' own WER "close
    # program" dialog pop up and BLOCK -- synchronously, at the OS level,
    # before ctypes.CDLL below ever gets control back to raise the OSError
    # its own except clause already handles. That is a modal dialog on the
    # developer's desktop, not a Python exception, so no try/except here
    # can prevent it -- only SetErrorMode, called once, before the first
    # LoadLibrary this process ever attempts, does. SEM_FAILCRITICALERRORS
    # (0x0001) + SEM_NOGPFAULTERRORBOX (0x0002): the process still gets a
    # real error back (ctypes.CDLL still raises OSError exactly as before),
    # it just never blocks on a human clicking OK first -- interactive and
    # CI/headless runs behave identically either way, which is the actual
    # goal (a `dll:` stage naming an invalid library is a normal, expected
    # authoring/test error, not a crash needing an operator).
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)

from adas_sim.diagnostics.errors import ContractError, EnvironmentError_, InternalError
from adas_sim.diagnostics.logging import Event, log

#: `adas_sil_abi.h`'s `#define ADAS_SIL_ABI_VERSION` -- the framework's own
#: expected generation, never read from the component (two independently
#: wrong libraries could otherwise agree with each other and not with us).
ADAS_SIL_ABI_VERSION = 1

#: `max_bytes` fallback for a port the manifest declares with `max_bytes: 0`
#: (undeclared) -- grow-once-and-retry (SS4.3) corrects a wrong guess.
_DEFAULT_OUTPUT_CAP = 256


@dataclass(frozen=True, slots=True)
class PortSpec:
    """`sim_sil_contract.md` SS3.2's `PortSpec`, one port either direction.

    `period_us` (`OQ-12`/`OD-12`, `S-C1aΔ2`): this port's own function's
    cycle time in integer microseconds, `0` meaning undeclared -- the same
    "no real rate is 0" reasoning `ComponentManifest.period_ns` already
    uses, so a plain `int` needs no presence tracking.

    `fixed_slots` (`OD-8`, `S-C1aΔ2`): `True`/`False` is a real, declared
    answer ("safe to compact" or not); `None` is *undeclared*, and the two
    must never collide (`NR-SIM-4`) -- unlike `period_us` above, `False`
    cannot stand in for "not declared", so this is `bool | None`, not a
    plain `bool` defaulting to `False`.
    """

    name: str
    proto_type: str
    max_bytes: int = 0
    optional: bool = False
    owner_function: str = ""
    doc: str = ""
    period_us: int = 0
    fixed_slots: bool | None = None


@dataclass(frozen=True, slots=True)
class ComponentManifest:
    """`sim_sil_contract.md` SS3.2's `ComponentManifest`, decoded from
    `adasManifest()`'s bytes -- ports discovered, never hardcoded (`R-SIM-4`)."""

    component: str
    version: str
    abi_version: int
    build_id: str
    inputs: tuple[PortSpec, ...]
    outputs: tuple[PortSpec, ...]
    project: str
    config_bundle_sha256: str
    descriptor_set: bytes
    period_ns: int


# ---------------------------------------------------------------------------
# `ComponentManifest`'s own schema, hand-built -- same technique as
# `scene/codec.py`'s `Scene` IR, applied here because the manifest is the
# bootstrap schema that describes every OTHER port's type, so it cannot
# itself be resolved from a `descriptor_set`: there is nothing to bootstrap
# it from. Building it from `google.protobuf.descriptor_pb2` rather than
# importing `interfaces`'s generated binding keeps R-SIM-11 literal: no
# `interfaces` checkout, ever. Field numbers below are byte-identical to
# `interfaces/proto/Adas__Sil/component_manifest.proto` -- the wire format
# doesn't encode package/message names, only field numbers and types, so
# this parses real `adasManifest()` bytes correctly regardless. Lives in its
# own private `DescriptorPool`, so there is no collision even if a real
# generated `adas.sil` binding is also present elsewhere in the process.
# ---------------------------------------------------------------------------


def _build_manifest_schema() -> type:
    from google.protobuf import descriptor_pb2 as dpb
    from google.protobuf import descriptor_pool as dpool
    from google.protobuf import message_factory as mfactory

    ft = dpb.FieldDescriptorProto

    def field(msg, name: str, number: int, ftype: int, *, repeated: bool = False, type_name: str | None = None) -> None:
        f = msg.field.add()
        f.name = name
        f.number = number
        f.type = ftype
        f.label = ft.LABEL_REPEATED if repeated else ft.LABEL_OPTIONAL
        if type_name is not None:
            f.type_name = type_name

    fdp = dpb.FileDescriptorProto()
    fdp.name = "adas_sil_component_manifest.proto"
    fdp.package = "adas.sil"
    fdp.syntax = "proto3"

    port_spec = fdp.message_type.add()
    port_spec.name = "PortSpec"
    field(port_spec, "name", 1, ft.TYPE_STRING)
    field(port_spec, "proto_type", 2, ft.TYPE_STRING)
    field(port_spec, "max_bytes", 3, ft.TYPE_UINT32)
    field(port_spec, "optional", 4, ft.TYPE_BOOL)
    field(port_spec, "owner_function", 5, ft.TYPE_STRING)
    field(port_spec, "doc", 6, ft.TYPE_STRING)
    field(port_spec, "period_us", 7, ft.TYPE_UINT64)
    # `fixed_slots` is proto3 `optional` on the wire (interfaces/proto/
    # Adas__Sil/component_manifest.proto) -- explicit presence, not a plain
    # bool. protoc implements that as a single-field SYNTHETIC oneof named
    # "_<field>" with proto3_optional=true on the field (the FileDescriptorProto
    # shape every proto3-optional field compiles to); reproduced by hand here
    # for the same reason the rest of this schema is hand-built (R-SIM-11's
    # bootstrap problem -- nothing to resolve a descriptor_set FROM yet).
    # Skipping this and declaring a bare bool would silently lose presence:
    # `HasField("fixed_slots")` would raise (no oneof) instead of
    # distinguishing undeclared from explicit False.
    fixed_slots_oneof_index = len(port_spec.oneof_decl)
    port_spec.oneof_decl.add(name="_fixed_slots")
    fixed_slots_field = port_spec.field.add()
    fixed_slots_field.name = "fixed_slots"
    fixed_slots_field.number = 8
    fixed_slots_field.type = ft.TYPE_BOOL
    fixed_slots_field.label = ft.LABEL_OPTIONAL
    fixed_slots_field.oneof_index = fixed_slots_oneof_index
    fixed_slots_field.proto3_optional = True

    manifest = fdp.message_type.add()
    manifest.name = "ComponentManifest"
    field(manifest, "component", 1, ft.TYPE_STRING)
    field(manifest, "version", 2, ft.TYPE_STRING)
    field(manifest, "abi_version", 3, ft.TYPE_INT32)
    field(manifest, "build_id", 4, ft.TYPE_STRING)
    field(manifest, "inputs", 5, ft.TYPE_MESSAGE, repeated=True, type_name=".adas.sil.PortSpec")
    field(manifest, "outputs", 6, ft.TYPE_MESSAGE, repeated=True, type_name=".adas.sil.PortSpec")
    field(manifest, "project", 7, ft.TYPE_STRING)
    field(manifest, "config_bundle_sha256", 8, ft.TYPE_STRING)
    field(manifest, "descriptor_set", 9, ft.TYPE_BYTES)
    field(manifest, "period_ns", 10, ft.TYPE_UINT64)

    pool = dpool.DescriptorPool()
    pool.Add(fdp)
    return mfactory.GetMessageClass(pool.FindMessageTypeByName("adas.sil.ComponentManifest"))


#: Built lazily: importing this module must not pull in protobuf as a side
#: effect (matches `core.runner.decode_message`'s own discipline, UT-A1-2's
#: principle applied here).
_manifest_proto_cls: type | None = None


def _manifest_proto_class() -> type:
    global _manifest_proto_cls
    if _manifest_proto_cls is None:
        _manifest_proto_cls = _build_manifest_schema()
    return _manifest_proto_cls


def parse_manifest(raw: bytes) -> ComponentManifest:
    """Decodes `adasManifest()`'s bytes into a `ComponentManifest` (`UT-C1c-2`)."""
    msg = _manifest_proto_class()()
    msg.ParseFromString(raw)

    def port_spec(p) -> PortSpec:
        return PortSpec(
            name=p.name, proto_type=p.proto_type, max_bytes=p.max_bytes,
            optional=p.optional, owner_function=p.owner_function, doc=p.doc,
            period_us=p.period_us, fixed_slots=p.fixed_slots if p.HasField("fixed_slots") else None,
        )

    return ComponentManifest(
        component=msg.component, version=msg.version, abi_version=msg.abi_version, build_id=msg.build_id,
        inputs=tuple(port_spec(p) for p in msg.inputs),
        outputs=tuple(port_spec(p) for p in msg.outputs),
        project=msg.project, config_bundle_sha256=msg.config_bundle_sha256,
        descriptor_set=msg.descriptor_set, period_ns=msg.period_ns,
    )


def resolve_message_classes(manifest: ComponentManifest) -> Mapping[str, type]:
    """Message classes for every `proto_type` this manifest's ports use,
    built from `descriptor_set` alone (`R-SIM-11`) -- no generated bindings,
    no `interfaces` checkout (`UT-C1c-3`). Keyed by fully-qualified
    `proto_type`. Same dependency-first construction as
    `core.runner.decode_message`."""
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    file_descriptor_set = descriptor_pb2.FileDescriptorSet()
    file_descriptor_set.ParseFromString(manifest.descriptor_set)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in file_descriptor_set.file}
    added: set[str] = set()

    def add(file_proto) -> None:
        if file_proto.name in added:
            return
        added.add(file_proto.name)
        for dependency in file_proto.dependency:
            if dependency in by_name:
                add(by_name[dependency])
        pool.Add(file_proto)

    for file_proto in file_descriptor_set.file:
        add(file_proto)

    classes: dict[str, type] = {}
    for spec in (*manifest.inputs, *manifest.outputs):
        descriptor = pool.FindMessageTypeByName(spec.proto_type)
        classes[spec.proto_type] = message_factory.GetMessageClass(descriptor)
    return classes


@dataclass(frozen=True, slots=True)
class InputMeta:
    """One input port's real `valid`/`age_s` for `_AdasPort` (`R-SIM-9`
    fault injection's own metadata half, `sim_scenarios_and_expectations.md`
    SS9.2). No `updated` field: `df`'s own `ReqPort<T>`
    (`modules/df/src/component/common/framework/ports.hpp`) carries only
    `data`/`ageS`/`valid` on the input side -- `updated` is a *provide*-port
    concept only, so there is nothing on the input ABI for it to drive.
    Defaults reproduce the pre-`S-C3` behaviour (fresh and valid) for a port
    with no entry -- an ordinary stage-to-stage/`source.*` wire that no fault
    or held-value staleness touches."""

    valid: bool = True
    age_s: float = 0.0


class SilComponent(Protocol):
    """A stage that can execute (`sim_api_reference.md` SS3.1)."""

    name: str
    manifest: ComponentManifest

    def init(self, config_path: Path | None = None) -> None: ...
    def exec(
        self, dt_ns: int, inputs: Mapping[str, bytes], input_meta: Mapping[str, InputMeta] | None = None,
    ) -> Mapping[str, bytes]: ...
    def shutdown(self) -> None: ...
    def abi_version(self) -> int: ...


# ---------------------------------------------------------------------------
# `AdasPort`/`AdasPortSet` -- the C ABI's own layout
# (`interfaces/include/adas/adas_sil_abi.h`), mirrored field-for-field.
# ---------------------------------------------------------------------------


class _AdasPort(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("len", ctypes.c_size_t),
        ("cap", ctypes.c_size_t),
        ("ageS", ctypes.c_double),
        ("valid", ctypes.c_int32),
        ("updated", ctypes.c_int32),
    ]


class _AdasPortSet(ctypes.Structure):
    _fields_ = [
        ("ports", ctypes.POINTER(_AdasPort)),
        ("count", ctypes.c_size_t),
    ]


class _OutBuffer:
    """One output port's persistent, per-handle byte buffer (SS4.1, SS4.3):
    allocated once, reused every tick, grown at most once per undersized
    call -- the ~8-allocation-per-tick cost `df_ctypes.py` paid is gone."""

    __slots__ = ("cap", "raw")

    def __init__(self, cap: int) -> None:
        self.cap = max(cap, 1)
        self.raw = (ctypes.c_uint8 * self.cap)()

    def grow(self, new_cap: int) -> None:
        self.cap = new_cap
        self.raw = (ctypes.c_uint8 * new_cap)()


def _bind(dll: ctypes.CDLL) -> None:
    dll.adasAbiVersion.argtypes = []
    dll.adasAbiVersion.restype = ctypes.c_int32
    dll.adasManifest.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
    dll.adasManifest.restype = ctypes.c_size_t
    dll.adasInit.argtypes = [ctypes.c_char_p]
    dll.adasInit.restype = ctypes.c_void_p
    dll.adasExec.argtypes = [
        ctypes.c_void_p, ctypes.c_double, ctypes.POINTER(_AdasPortSet), ctypes.POINTER(_AdasPortSet),
    ]
    dll.adasExec.restype = ctypes.c_int32
    dll.adasShutdown.argtypes = [ctypes.c_void_p]
    dll.adasShutdown.restype = None


def _read_manifest(dll: ctypes.CDLL) -> ComponentManifest:
    """The two-call pattern `adasManifest` documents: probe the required
    size with `cap=0`, then fill a buffer of exactly that size."""
    needed = dll.adasManifest(None, 0)
    buf = (ctypes.c_uint8 * needed)()
    written = dll.adasManifest(ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)), needed)
    return parse_manifest(bytes(buf[:written]))


class CtypesSilComponent:
    """A real (or `stubdll:`) library, loaded over the generic ABI
    (`sim_sil_contract.md` SS4.1). `path` is already resolved --
    `contracts.loader.resolve_library` is the only place a stem becomes a
    path (`P-5`); this class only ever sees the result."""

    def __init__(self, path: Path) -> None:
        try:
            self._dll = ctypes.CDLL(str(path))
        except OSError as exc:
            raise EnvironmentError_(
                expected="a loadable library implementing the generic SIL ABI",
                found=str(exc), where=str(path),
                hint="check the library was built for this platform and its dependencies are resolvable",
            ) from exc
        _bind(self._dll)
        found = self._dll.adasAbiVersion()
        if found != ADAS_SIL_ABI_VERSION:
            raise ContractError(
                expected=f"ABI version {ADAS_SIL_ABI_VERSION}", found=f"ABI version {found}",
                where=f"adasAbiVersion() in {path}",
                hint="rebuild the component or the framework, whichever is behind",
            )
        self.manifest = _read_manifest(self._dll)
        self.name = self.manifest.component
        self._handle: int | None = None
        self._out_buffers: dict[str, _OutBuffer] = {
            spec.name: _OutBuffer(spec.max_bytes or _DEFAULT_OUTPUT_CAP) for spec in self.manifest.outputs
        }

    def __repr__(self) -> str:
        return f"<CtypesSilComponent name={self.name!r} abi={self.manifest.abi_version}>"

    def abi_version(self) -> int:
        return self.manifest.abi_version

    def init(self, config_path: Path | None = None) -> None:
        encoded = str(config_path).encode("utf-8") if config_path is not None else None
        handle = self._dll.adasInit(encoded)
        if not handle:
            raise EnvironmentError_(
                expected="a resolved configuration bundle", found="NULL handle",
                where=f"adasInit for component '{self.name}' (configPath="
                + (f"{config_path})" if config_path is not None else "NULL)"),
                hint="pass an explicit config_path, or build a config/ bundle beside the library (R-SIM-3a)",
            )
        self._handle = handle

    def shutdown(self) -> None:
        if self._handle is not None:
            self._dll.adasShutdown(self._handle)
            self._handle = None

    def exec(
        self, dt_ns: int, inputs: Mapping[str, bytes], input_meta: Mapping[str, InputMeta] | None = None,
    ) -> Mapping[str, bytes]:
        if self._handle is None:
            raise InternalError(
                expected="init() called before exec()", found="no handle",
                where=f"{self.name}.exec", hint="call init() once before the first exec()",
            )
        dt_s = dt_ns / 1_000_000_000.0  # THE ns -> dtS conversion point (P-8)

        keepalive: list[object] = []
        in_set, _in_ports = self._build_in_portset(inputs, keepalive, input_meta)
        out_set, out_ports = self._build_out_portset(keepalive)
        ok = self._dll.adasExec(self._handle, dt_s, ctypes.pointer(in_set), ctypes.pointer(out_set))

        # Undersize is detected from the ports themselves, never from `ok`:
        # the real df_sil.dll still returns success for a tick where one
        # output port was too small (that port is simply left updated=0) --
        # found by this grow path never firing against the real library,
        # not reasoned in advance.
        grown = self._grow_undersized(out_ports)
        if grown:
            log(Event.DEGRADE, run=self.name, stage=self.name,
                msg=f"grew undersized output buffer(s): {', '.join(grown)}")
            out_set, out_ports = self._build_out_portset(keepalive)
            ok = self._dll.adasExec(self._handle, dt_s, ctypes.pointer(in_set), ctypes.pointer(out_set))
            still_undersized = self._find_undersized(out_ports)
            if still_undersized:
                raise ContractError(
                    expected="adasExec() output ports to fit after growing once",
                    found=f"still undersized after growing: {', '.join(still_undersized)}",
                    where=f"{self.name}.exec",
                    hint="the manifest's max_bytes for these ports is chronically wrong",
                )
        elif not ok:
            raise InternalError(
                expected="adasExec() to return success", found="adasExec() returned 0, no port undersized",
                where=f"{self.name}.exec", hint="a component-side failure unrelated to buffer sizing",
            )

        return self._collect_outputs(out_ports)

    def _build_in_portset(
        self, inputs: Mapping[str, bytes], keepalive: list[object], input_meta: Mapping[str, InputMeta] | None = None,
    ) -> tuple[_AdasPortSet, ctypes.Array]:
        input_meta = input_meta or {}
        ports = (_AdasPort * len(inputs))()
        for i, (name, payload) in enumerate(inputs.items()):
            meta = input_meta.get(name, InputMeta())
            buf = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
            keepalive.append(buf)
            ports[i].name = name.encode("utf-8")
            ports[i].data = ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8))
            ports[i].len = len(payload)
            ports[i].cap = 0
            ports[i].ageS = meta.age_s
            ports[i].valid = 1 if meta.valid else 0
            ports[i].updated = 0  # ReqPort<T> has no `updated` -- unused on the input side (see InputMeta)
        port_set = _AdasPortSet(ports=ctypes.cast(ports, ctypes.POINTER(_AdasPort)), count=len(inputs))
        return port_set, ports

    def _build_out_portset(self, keepalive: list[object]) -> tuple[_AdasPortSet, ctypes.Array]:
        names = list(self._out_buffers)
        ports = (_AdasPort * len(names))()
        for i, name in enumerate(names):
            buf = self._out_buffers[name]
            encoded_name = name.encode("utf-8")
            keepalive.append(encoded_name)
            ports[i].name = encoded_name
            ports[i].data = ctypes.cast(buf.raw, ctypes.POINTER(ctypes.c_uint8))
            ports[i].len = 0
            ports[i].cap = buf.cap
            ports[i].ageS = 0.0
            ports[i].valid = 0
            ports[i].updated = 0
        port_set = _AdasPortSet(ports=ctypes.cast(ports, ctypes.POINTER(_AdasPort)), count=len(names))
        return port_set, ports

    def _find_undersized(self, out_ports: ctypes.Array) -> list[str]:
        return [port.name.decode("utf-8") for port in out_ports if port.len > port.cap]

    def _grow_undersized(self, out_ports: ctypes.Array) -> list[str]:
        names = self._find_undersized(out_ports)
        for name in names:
            required = next(port.len for port in out_ports if port.name.decode("utf-8") == name)
            self._out_buffers[name].grow(required)
        return names

    def _collect_outputs(self, out_ports: ctypes.Array) -> Mapping[str, bytes]:
        result: dict[str, bytes] = {}
        for port in out_ports:
            if port.updated:
                result[port.name.decode("utf-8")] = ctypes.string_at(port.data, port.len)
        return result


class InProcessSilComponent:
    """A Python callable + a manifest -- what `impl: stub:` uses
    (`sim_api_reference.md` SS3.1). Every `Pipeline`/wiring test runs against
    this, with zero build dependency."""

    def __init__(
        self, name: str, manifest: ComponentManifest,
        fn: Callable[[int, Mapping[str, bytes]], Mapping[str, bytes]],
    ) -> None:
        self.name = name
        self.manifest = manifest
        self._fn = fn
        self._handle_open = False
        self.last_input_meta: Mapping[str, InputMeta] | None = None

    def __repr__(self) -> str:
        return f"<InProcessSilComponent name={self.name!r}>"

    def abi_version(self) -> int:
        return self.manifest.abi_version

    def init(self, config_path: Path | None = None) -> None:
        del config_path  # a Python stand-in owns no external configuration
        self._handle_open = True

    def exec(
        self, dt_ns: int, inputs: Mapping[str, bytes], input_meta: Mapping[str, InputMeta] | None = None,
    ) -> Mapping[str, bytes]:
        if not self._handle_open:
            raise InternalError(
                expected="init() called before exec()", found="no handle",
                where=f"{self.name}.exec", hint="call init() once before the first exec()",
            )
        # `_fn` stays a plain (dt_ns, inputs) -> outputs callable -- every
        # existing stub across the test suite is that shape, and a Python
        # stand-in has no ABI to feed `valid`/`age_s` into anyway. Recorded
        # for a test to assert on, never consumed here (`CtypesSilComponent`
        # is the one real consumer, `S-C3`).
        self.last_input_meta = input_meta
        return self._fn(dt_ns, inputs)

    def shutdown(self) -> None:
        self._handle_open = False
