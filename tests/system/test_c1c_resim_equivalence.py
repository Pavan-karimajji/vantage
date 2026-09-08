# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c system test: ST-C1c-1 and ST-C9-1 (docs/sim_implementation_plan.md).

Carries TWO stage gates, which is why the ids are both named here:

  - `ST-C1c-1` -- the generic ABI's correctness gate, proven once against a
    real component before anything depends on it exclusively. This file's
    original and primary claim.
  - `ST-C9-1` -- the asker's workflow end to end (`FR-SIM-66`, P0): every
    existing recording resims through a real `Pipeline` with `df` as the only
    stage and **no per-test topic mapping**, i.e. this file's own hardcoded
    topic constants are gone and the run goes through the declared ingest map
    instead. `S-C9` ticked that gate against this file; until AR-7 the id
    appeared nowhere in the suite, so grepping for `ST-C9-1` found nothing and
    the only thing binding a P0 requirement to its verifier was one sentence
    in a 5,500-line plan.

`ST-C9-1` is a claim about the INGEST MAP; `ST-C1c-1` is a claim about the
ABI. They share a body because the generic path exercises both, not because
they are the same assertion -- if this file is ever split, both ids move with
the half that still proves them.

Resims every existing `df` recording through two independent paths against
the same `df_sil.dll` build and compares every declared output port
byte-for-byte, tick by tick:

  - the GENERIC path: a real `Pipeline` (`S-C9`) built from a `Session`
    (`adas_sim.session.session.Session.open`, itself built through the
    declared `df.carla_legacy` ingest map, `modules/df/sim/ingest/
    carla_legacy.yaml` -- no per-test topic constant). `Pipeline.exec` drives
    `CtypesSilComponent` (`adasInit`/`adasManifest`/`adasExec`), ports
    matched by name, discovered from the manifest (`R-SIM-4`) -- exactly
    what every other `UT-C1c-*` test already drives.
  - the POSITIONAL path: `dfInit`/`dfExec`/`dfShutdown`, the fixed
    nine-parameter pre-S-C1c ABI `modules/df/tools/carla/df_ctypes.py` and
    `replay/df_dll_sim_mcap.py` already drive live resim with today, and
    which stays load-bearing until `S-E1` retires it. Bound directly here
    with `ctypes.CDLL` (not reimported from `df_ctypes.py`, which loads
    through `ctypes.WinDLL` -- an attribute that does not exist outside
    Windows and would make this comparison itself platform-locked; the
    generic path's own `CtypesSilComponent` already proves `CDLL` loads the
    same Windows-built `df_sil.dll` correctly, `sim_portability.md` P-5).

`df_interface_c.cpp`'s own comment records that `adasExec` "dispatches by
port name to the exact same internal helper as dfExec" -- so a divergence
here would mean the generic ABI computed something different from the one
already proven live, not a new algorithm bug.

**`S-C9`.** Before this stage, the GENERIC path read `df/gen_object_list`/
`df/veh_dyn` directly off the mcap file and hand-renamed them to `objects`/
`egoDyn` in a dict literal here -- `S-C9`'s own Gate names this test's own
bridge as the thing to delete. The two paths now diverge only in *what they
bind to* (a real `Pipeline` vs. the fixed positional ABI), never in *how the
bytes reached each one*.

Skips with a named reason if the df_sil.dll build or the recordings
directory is absent (partial clone, or -- as on this Linux checkout, where
`df`'s own conf/build.yml offers no Linux platform for the `sil` target yet
-- simply not built for this platform): `sim` is never required to build
`df` to run its own suite (`sim_sil_contract.md` SS8), and this test needs
both.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

from adas_sim.resolve.component import CtypesSilComponent
from adas_sim.resolve.library import resolve_library
from adas_sim.graph.pipeline import Pipeline, Stage
from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.session.session import Session

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
DF_DEFAULT_PROJECT_YAML = DF_ROOT / "src" / "project" / "base" / "default.yaml"
DF_TESTRUNS = DF_ROOT / "tests" / "carla_testruns"
_DF_SIL_SEARCH_DIRS = [
    DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Debug",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Debug",
]
_SKIP_REASON_NO_DLL = "no built df_sil.dll found under modules/df/build-*-vs2026 (partial clone / not built for this platform)"
_SKIP_REASON_NO_RECORDINGS = "modules/df/tests/carla_testruns is absent (partial clone)"

# Positional buffer name -> the manifest's own named port (df_sil.ports.yaml).
# Fixed and hand-written deliberately: the whole point of "positional" is
# that dfExec carries no port names to discover this mapping from.
_OUTPUT_NAME_MAP = {
    "aebOutputs": "aeb.outputs",
    "aebCompState": "aeb.compState",
    "bsdOutputs": "bsd.outputs",
    "bsdCompState": "bsd.compState",
}

# Generous headroom over the manifest's declared max_bytes (256/512) -- a
# real AebOutputs/BsdOutputs/CompState tick is a handful of scalars, never
# anywhere near this; sized so this harness's own buffers are never the
# thing that goes undersized (that failure mode is `UT-C1c-5`'s, not this
# test's concern).
_OUT_BUF_CAP = 4096


def _real_df_sil_path() -> Path | None:
    try:
        return resolve_library("df_sil", search=_DF_SIL_SEARCH_DIRS)
    except EnvironmentError_:
        return None


def _canonical_recordings() -> list[Path]:
    """Every feature-subfoldered recording -- `exports/` excluded, same
    reasoning `df_dll_sim_mcap.py`'s own `--list`/resolver already use: it is
    flat, timestamped scratch output, not a source recording."""
    if not DF_TESTRUNS.is_dir():
        return []
    return sorted(p for p in DF_TESTRUNS.rglob("*.mcap") if p.parent.name != "exports")


# ---------------------------------------------------------------------------
# The positional (pre-S-C1c) ABI, bound directly -- mirrors
# `modules/df/src/platform/df_sil/df_interface_c.h` field-for-field.
# ---------------------------------------------------------------------------


class _DfReqBuf(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("len", ctypes.c_size_t),
        ("ageS", ctypes.c_double),
        ("valid", ctypes.c_int),
    ]


class _DfProBuf(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("cap", ctypes.c_size_t),
        ("len", ctypes.c_size_t),
        ("updated", ctypes.c_int),
    ]


def _bind_positional(dll: ctypes.CDLL) -> None:
    dll.dfApiVersion.argtypes = []
    dll.dfApiVersion.restype = ctypes.c_int
    dll.dfInit.argtypes = [ctypes.c_char_p]
    dll.dfInit.restype = ctypes.c_void_p
    dll.dfExec.argtypes = [
        ctypes.c_void_p, ctypes.c_double,
        ctypes.POINTER(_DfReqBuf), ctypes.POINTER(_DfReqBuf), ctypes.POINTER(_DfReqBuf),
        ctypes.POINTER(_DfProBuf), ctypes.POINTER(_DfProBuf), ctypes.POINTER(_DfProBuf), ctypes.POINTER(_DfProBuf),
    ]
    dll.dfExec.restype = ctypes.c_int
    dll.dfShutdown.argtypes = [ctypes.c_void_p]
    dll.dfShutdown.restype = None


class _PositionalDfComponent:
    """The pre-S-C1c ABI, called exactly as `df_dll_sim_mcap.py` calls it --
    a second, independent handle over the same DLL, so this and a live
    `CtypesSilComponent` never share state."""

    def __init__(self, path: Path) -> None:
        self._dll = ctypes.CDLL(str(path))
        _bind_positional(self._dll)
        self._handle: int | None = None
        self._out_bufs = {name: (ctypes.c_uint8 * _OUT_BUF_CAP)() for name in _OUTPUT_NAME_MAP}

    def init(self, config_path: Path) -> None:
        handle = self._dll.dfInit(str(config_path).encode("utf-8"))
        if not handle:
            raise RuntimeError(f"dfInit failed for config path {config_path}")
        self._handle = handle

    def shutdown(self) -> None:
        if self._handle is not None:
            self._dll.dfShutdown(self._handle)
            self._handle = None

    def _req(self, payload: bytes, keepalive: list[object]) -> _DfReqBuf:
        buf = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
        keepalive.append(buf)
        return _DfReqBuf(data=ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)), len=len(payload), ageS=0.0, valid=1)

    def exec(self, dt_ns: int, objects_bytes: bytes, veh_dyn_bytes: bytes) -> dict[str, bytes]:
        dt_s = dt_ns / 1_000_000_000.0  # same conversion point CtypesSilComponent.exec uses (P-8)
        keepalive: list[object] = []
        objects_req = self._req(objects_bytes, keepalive)
        veh_dyn_req = self._req(veh_dyn_bytes, keepalive)
        # VehSig was never recorded (sim_resim_and_recording.md SS8) -- both
        # paths get a fresh, all-default VehSig() every tick, which is
        # exactly what b"" deserializes to in proto3 (no generated binding
        # needed to construct it, R-SIM-11).
        veh_sig_req = self._req(b"", keepalive)

        pro_bufs = {
            name: _DfProBuf(
                data=ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)), cap=_OUT_BUF_CAP, len=0, updated=0,
            )
            for name, buf in self._out_bufs.items()
        }
        ok = self._dll.dfExec(
            self._handle, dt_s,
            ctypes.byref(objects_req), ctypes.byref(veh_dyn_req), ctypes.byref(veh_sig_req),
            ctypes.byref(pro_bufs["aebOutputs"]), ctypes.byref(pro_bufs["bsdOutputs"]),
            ctypes.byref(pro_bufs["aebCompState"]), ctypes.byref(pro_bufs["bsdCompState"]),
        )
        if not ok:
            raise RuntimeError("dfExec returned failure (0) for a recorded tick")
        return {name: ctypes.string_at(buf.data, buf.len) for name, buf in pro_bufs.items() if buf.updated}


def test_every_existing_recording_is_byte_identical_between_the_generic_and_positional_paths():
    """ST-C1c-1."""
    dll_path = _real_df_sil_path()
    if dll_path is None:
        pytest.skip(_SKIP_REASON_NO_DLL)
    recordings = _canonical_recordings()
    if not recordings:
        pytest.skip(_SKIP_REASON_NO_RECORDINGS)

    for path in recordings:
        # S-C9: no per-test topic constant -- the recording's own declared
        # ingest map (modules/df/sim/ingest/carla_legacy.yaml) is what
        # resolves df/gen_object_list -> source.gen_object_list etc.
        session = Session.open(path)

        generic = CtypesSilComponent(dll_path)
        generic.init(DF_DEFAULT_PROJECT_YAML)
        positional = _PositionalDfComponent(dll_path)
        positional.init(DF_DEFAULT_PROJECT_YAML)
        declared_outputs = {p.name for p in generic.manifest.outputs}
        pipeline = Pipeline(
            name="df_resim", version=1, components={"df": generic},
            stages=(Stage(
                name="df", mode="simulate", impl=None,
                inputs={"objects": "source.gen_object_list", "egoDyn": "source.veh_dyn", "vehSig": "source.veh_sig"},
            ),),
        )

        try:
            prev_t_ns = 0
            tick_count = 0
            for tick in session.ticks:
                if "source.gen_object_list" not in tick.ports or "source.veh_dyn" not in tick.ports:
                    # An incomplete tick (e.g. only the chase camera arrived
                    # at this log_time): both paths would see the same gap
                    # either way -- skip rather than fabricate a stimulus
                    # (mirrors df_dll_sim_mcap.py's own handling).
                    continue
                dt_ns = tick.t_ns - prev_t_ns
                prev_t_ns = tick.t_ns
                objects_bytes = tick.port("source.gen_object_list").raw_bytes
                veh_dyn_bytes = tick.port("source.veh_dyn").raw_bytes

                # source.veh_sig is declared absent (S-C9) -- both paths get
                # a fresh, all-default VehSig() every tick, which is exactly
                # what b"" deserializes to in proto3 (no generated binding
                # needed to construct it, R-SIM-11).
                generic_out = pipeline.exec(
                    dt_ns, {"gen_object_list": objects_bytes, "veh_dyn": veh_dyn_bytes, "veh_sig": b""}
                )["df"]
                positional_out = positional.exec(dt_ns, objects_bytes, veh_dyn_bytes)

                for positional_name, generic_name in _OUTPUT_NAME_MAP.items():
                    if generic_name not in declared_outputs:
                        continue  # this build's ENABLED_FUNCTIONS doesn't declare it either way
                    assert generic_out.get(generic_name) == positional_out.get(positional_name), (
                        f"{path.name} tick t_ns={tick.t_ns}: port {generic_name!r} diverges "
                        f"between the generic ({generic_out.get(generic_name)!r}) and positional "
                        f"({positional_out.get(positional_name)!r}) paths"
                    )
                tick_count += 1
            assert tick_count > 0, f"{path}: no complete tick (every tick was missing a topic)"
        finally:
            generic.shutdown()
            positional.shutdown()
