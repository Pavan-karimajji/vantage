# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c component tests: UT-C1c-1, UT-C1c-2, UT-C1c-3, UT-C1c-4, UT-C1c-5
(docs/sim_implementation_plan.md).

UT-C1c-1/2/4/5's DLL-backed halves run against the real, already-built
`df_sil.dll` (skip with a named reason if absent -- `df` is not required to
run this suite, `sim_sil_contract.md` SS8). UT-C1c-3 and the manifest
round-trip half of UT-C1c-2 are pure Python: synthetic bytes, no DLL, no
`interfaces` checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.resolve import component as component_mod
from adas_sim.resolve.component import (
    ComponentManifest,
    CtypesSilComponent,
    InputMeta,
    PortSpec,
    parse_manifest,
    resolve_message_classes,
)
from adas_sim.resolve.library import resolve_library
from adas_sim.diagnostics.errors import ContractError, EnvironmentError_

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
DF_DEFAULT_PROJECT_YAML = DF_ROOT / "src" / "project" / "base" / "default.yaml"
_DF_SIL_SEARCH_DIRS = [
    DF_ROOT / "conan_workarea" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "conan_workarea" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Debug",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Release",
    DF_ROOT / "build-gtest-vs2026" / "src" / "platform" / "df_sil" / "Debug",
]
_SKIP_REASON = "no built df_sil.dll found under modules/df/build-*-vs2026 (partial clone / not built)"


def _real_df_sil_path() -> Path | None:
    try:
        return resolve_library("df_sil", search=_DF_SIL_SEARCH_DIRS)
    except EnvironmentError_:
        return None


def _real_df_component() -> CtypesSilComponent:
    """A live `CtypesSilComponent` over the real `df_sil.dll`, initialised
    against `df`'s own default project YAML -- `adasInit` with a non-empty
    path still delegates to the tolerant legacy `dfInit` until `S-C5` packs a
    real bundle (`sim_sil_contract.md` SS3.4)."""
    component = CtypesSilComponent(_real_df_sil_path())
    component.init(DF_DEFAULT_PROJECT_YAML)
    return component


# ---------------------------------------------------------------------------
# UT-C1c-1 -- ABI version mismatch fails loudly at load, naming both versions
# ---------------------------------------------------------------------------


def test_abi_version_mismatch_raises_naming_both_versions(monkeypatch):
    """UT-C1c-1 / UT-D5-1."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    monkeypatch.setattr(component_mod, "ADAS_SIL_ABI_VERSION", 999)
    with pytest.raises(ContractError) as excinfo:
        CtypesSilComponent(path)

    message = str(excinfo.value)
    assert "ABI version 999" in message
    assert "ABI version 1" in message


# ---------------------------------------------------------------------------
# UT-C1c-2 -- manifest parse yields discovered ports; no hardcoded port name
# anywhere in the framework (covered by the existing GT-1 grep, re-run this
# slice via scripts/check_invariants.py -- not duplicated here).
# ---------------------------------------------------------------------------


def test_parse_manifest_round_trips_every_field():
    """UT-C1c-2 (synthetic half, no DLL needed)."""
    schema = component_mod._manifest_proto_class()
    msg = schema(
        component="widget", version="1.2.3", abi_version=1, build_id="deadbeef",
        project="base", config_bundle_sha256="", descriptor_set=b"\x01\x02", period_ns=50_000_000,
    )
    msg.inputs.add(name="objects", proto_type="adas.perception.DfObjList", optional=False)
    msg.outputs.add(
        name="widget.outputs", proto_type="adas.df.WidgetOutputs", max_bytes=256, owner_function="widget",
        period_us=50_000, fixed_slots=True,
    )

    manifest = parse_manifest(msg.SerializeToString())

    assert manifest.component == "widget"
    assert manifest.version == "1.2.3"
    assert manifest.abi_version == 1
    assert manifest.build_id == "deadbeef"
    assert manifest.period_ns == 50_000_000
    assert manifest.inputs == (PortSpec(name="objects", proto_type="adas.perception.DfObjList"),)
    assert manifest.outputs == (
        PortSpec(
            name="widget.outputs", proto_type="adas.df.WidgetOutputs", max_bytes=256, owner_function="widget",
            period_us=50_000, fixed_slots=True,
        ),
    )


def test_parse_manifest_port_period_us_and_fixed_slots_undeclared_defaults():
    """S-C1aΔ2 (UT-C1a-6/7's Python-side counterpart): a port that never sets
    `period_us`/`fixed_slots` decodes as 0/`None` -- undeclared, not a
    guessed value (`NR-SIM-4`). `None`, not `False`: a real declared
    `fixed_slots=False` ("safe to compact") must stay distinguishable from
    "never declared" all the way through `parse_manifest`, the same
    `HasField` distinction `interfaces`' own C++/Python round-trip tests
    check at the wire level."""
    schema = component_mod._manifest_proto_class()
    msg = schema(component="widget")
    msg.outputs.add(name="undeclared_port")
    msg.outputs.add(name="variable_length_port", fixed_slots=False)
    msg.outputs.add(name="fixed_size_port", fixed_slots=True)

    manifest = parse_manifest(msg.SerializeToString())

    assert manifest.outputs[0].period_us == 0
    assert manifest.outputs[0].fixed_slots is None
    assert manifest.outputs[1].fixed_slots is False
    assert manifest.outputs[2].fixed_slots is True


def test_manifest_ports_are_discovered_from_the_real_library_not_hardcoded():
    """UT-C1c-2 (real half): whatever `df` declares is what shows up --
    nothing in `component.py` names 'objects'/'aeb'/'bsd' etc. literally."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    comp = CtypesSilComponent(path)
    assert comp.manifest.component
    assert len(comp.manifest.inputs) > 0
    assert len(comp.manifest.outputs) > 0
    assert all(isinstance(p, PortSpec) and p.name for p in (*comp.manifest.inputs, *comp.manifest.outputs))


# ---------------------------------------------------------------------------
# UT-C1c-3 -- message classes built from descriptor_set alone; no generated
# bindings importable
# ---------------------------------------------------------------------------


def test_resolve_message_classes_needs_no_generated_binding():
    """UT-C1c-3. `Widget`/`adas_sim_test.v1` exist nowhere as a generated
    Python binding on this machine -- there is nothing importable to fall
    back to, so a working message class here proves the descriptor-only
    path, not an accidental import (`R-SIM-11`)."""
    from google.protobuf import descriptor_pb2

    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.name = "adas_sim_test.proto"
    fdp.package = "adas_sim_test.v1"
    fdp.syntax = "proto3"
    widget = fdp.message_type.add()
    widget.name = "Widget"
    f = widget.field.add()
    f.name = "count"
    f.number = 1
    f.type = descriptor_pb2.FieldDescriptorProto.TYPE_INT32
    f.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL

    fds = descriptor_pb2.FileDescriptorSet()
    fds.file.append(fdp)

    manifest = ComponentManifest(
        component="widget", version="1", abi_version=1, build_id="",
        inputs=(),
        outputs=(PortSpec(name="widget.out", proto_type="adas_sim_test.v1.Widget"),),
        project="base", config_bundle_sha256="", descriptor_set=fds.SerializeToString(), period_ns=0,
    )

    classes = resolve_message_classes(manifest)

    widget_cls = classes["adas_sim_test.v1.Widget"]
    instance = widget_cls(count=7)
    round_tripped = widget_cls()
    round_tripped.ParseFromString(instance.SerializeToString())
    assert round_tripped.count == 7


# ---------------------------------------------------------------------------
# UT-C1c-4 -- ports match by name regardless of order
# ---------------------------------------------------------------------------


def test_exec_matches_ports_by_name_regardless_of_input_order():
    """UT-C1c-4."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    comp_a = _real_df_component()
    names = [p.name for p in comp_a.manifest.inputs]
    out_a = comp_a.exec(50_000_000, {name: b"" for name in names})
    comp_a.shutdown()

    comp_b = _real_df_component()
    out_b = comp_b.exec(50_000_000, {name: b"" for name in reversed(names)})
    comp_b.shutdown()

    assert out_a == out_b


def test_build_in_portset_passes_real_valid_and_age_s_from_input_meta():
    """S-C3: `_build_in_portset` used to hardcode every input port's
    `valid`/`ageS` (`valid=1, ageS=0.0`, always), discarding whatever the
    caller actually knew -- the gap `df`'s own `ReqPort` gating
    (`reqPorts_.dfObjects.valid && ageS <= maxAge`,
    `modules/df/src/component/aeb/aeb_function.cpp`) depends on. Verified
    against the real ABI struct directly, naming no port (`R-SIM-1`) --
    only that the field the caller supplied for one port lands there, and
    every other port keeps the documented default."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    comp = _real_df_component()
    names = [p.name for p in comp.manifest.inputs]
    if not names:
        pytest.skip("df_sil declares no input ports")
    target = names[0]

    keepalive: list[object] = []
    input_meta = {target: InputMeta(valid=False, age_s=2.5)}
    _port_set, ports = comp._build_in_portset({name: b"" for name in names}, keepalive, input_meta)
    comp.shutdown()

    by_name = {port.name.decode("utf-8"): port for port in ports}
    assert by_name[target].valid == 0
    assert by_name[target].ageS == pytest.approx(2.5)
    for name in names[1:]:
        assert by_name[name].valid == 1
        assert by_name[name].ageS == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# UT-C1c-5 -- buffer grow-and-retry succeeds once and logs; a second failure
# raises
# ---------------------------------------------------------------------------


def test_exec_grows_an_undersized_output_buffer_once_and_logs(capsys):
    """UT-C1c-5 (success half, against the real library). The target port is
    discovered, not named: whichever declared output actually serialises to
    more than one byte on an all-default tick is the one forced undersize
    (`R-SIM-1` -- this module names no function's port, even in a test)."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    probe = _real_df_component()
    baseline = probe.exec(50_000_000, {p.name: b"" for p in probe.manifest.inputs})
    probe.shutdown()
    candidates = [name for name, payload in baseline.items() if len(payload) > 1]
    if not candidates:
        pytest.skip("no output port serialises to more than 1 byte on an all-default tick")
    target = candidates[0]

    comp = _real_df_component()
    comp._out_buffers[target] = component_mod._OutBuffer(1)  # force undersize

    inputs = {p.name: b"" for p in comp.manifest.inputs}
    result = comp.exec(50_000_000, inputs)
    comp.shutdown()

    assert comp._out_buffers[target].cap > 1
    assert target in result
    log_output = capsys.readouterr().err
    assert "event=degrade" in log_output
    assert target in log_output


def test_exec_raises_when_growing_once_is_not_enough():
    """UT-C1c-5 (failure half): a fake `adasExec` that always reports the
    buffer as undersized, even after growth -- isolates the retry-once-then-
    raise contract from real DLL behaviour, which cannot be coaxed into
    failing twice on demand."""
    path = _real_df_sil_path()
    if path is None:
        pytest.skip(_SKIP_REASON)

    comp = _real_df_component()

    def always_undersized(handle, dt_s, in_ptr, out_ptr):
        del handle, dt_s, in_ptr
        out_set = out_ptr.contents
        for i in range(out_set.count):
            out_set.ports[i].len = out_set.ports[i].cap + 1
            out_set.ports[i].updated = 0
        return 0

    comp._dll.adasExec = always_undersized
    inputs = {p.name: b"" for p in comp.manifest.inputs}
    with pytest.raises(ContractError):
        comp.exec(50_000_000, inputs)
