# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `ST-D6-3` (`docs/sim_implementation_plan.md`, `FR-SIM-67`,
`R-SIM-25`): `core.evidence.evidence`'s `Prim.pick_id` -> port join. A
layer provider declares `requires=("self.echo",)` (the same gating
`test_b1_registry_gating.py` exercises), is registered under a
test-scoped id, and renders one `Prim` with a known `pick_id`; a `Session`
carries the matching port plus a `RunManifest` component entry.
`evidence(pick_id, session, tick)` resolves `kind="prim"` with the same
topic/origin/value a direct port lookup would produce, plus `layer_id` and
`derived` -- proving `Layer.id` -> a provider's declared `requires` ->
`contracts.binding.try_resolve_component_ref` is a real, working join, not
just a design sketch."""

from __future__ import annotations

from adas_sim.diagnostics.evidence import evidence, format_evidence
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)
_PORT = "echo_stub_with_output.echo"


def _session_with_port(*, component_build: ComponentBuildInfo | None = None) -> Session:
    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={_PORT: PortValue(name=_PORT, message=b"\xde\xad\xbe\xef", origin="simulated")},
        pose=_POSE,
    )
    meta = RunManifest(components=(component_build,)) if component_build is not None else RunManifest()
    return Session(
        run_id="run-evidence-prim-join", name="s", ticks=(tick,), meta=meta,
        known_ports=frozenset({_PORT}),
    )


@layer_provider("sim.test.evidence_prim_join.echo_layer", requires=("self.echo",))
def _echo_layer(ctx):
    del ctx
    return (
        Layer(
            id="sim.test.evidence_prim_join.echo_layer", group="test",
            prims=(Prim(kind="text", pick_id="echo-prim-1"),),
        ),
    )


def test_evidence_resolves_a_prim_pick_id_to_its_port():
    session = _session_with_port()
    record = evidence("echo-prim-1", session, 0)
    assert record.kind == "prim"
    assert record.topic == _PORT
    assert record.origin == "simulated"
    assert record.layer_id == "sim.test.evidence_prim_join.echo_layer"
    assert record.derived is False


def test_evidence_prim_join_reports_component_build_provenance():
    build = ComponentBuildInfo(
        name="echo_stub_with_output", library_sha256="abc123", build_id="build-7",
        config_bundle_sha256="bundle-sha-9",
    )
    session = _session_with_port(component_build=build)
    record = evidence("echo-prim-1", session, 0)
    assert record.config_bundle_sha256 == "bundle-sha-9"
    assert record.component_build_id == "build-7"
    # Both are carried, each under its own name -- never one standing in for
    # the other (`F-8`).
    assert record.component_library_sha256 == "abc123"


def test_a_library_hash_is_never_reported_as_a_build_id():
    """`F-8`, and the substitution `R-SIM-25`/`NR-SIM-4` forbid.

    Every recording this framework writes fills `library_sha256` and leaves
    `build_id` empty. The library hash must therefore be *shown* -- it is the
    honest answer to "which build produced this" -- but shown under its own
    name, with `component_build_id` still reading unknown, because no build id
    was recorded. Showing the hash under the build-id label would be exactly
    the plausible-looking default the rule exists to prevent.
    """
    build = ComponentBuildInfo(name="echo_stub_with_output", library_sha256="lib-sha-42", build_id="")
    session = _session_with_port(component_build=build)
    record = evidence(_PORT, session, 0)

    assert record.component_library_sha256 == "lib-sha-42"
    assert record.component_build_id is None, "the library hash leaked into the build-id field"

    rendered = dict(format_evidence(record))
    assert rendered["component_library_sha256"] == "lib-sha-42"
    assert rendered["component_build_id"] == "unknown"


def test_a_missing_library_hash_reads_unknown_rather_than_borrowing_the_build_id():
    """The planted violation, mirrored: the substitution must be impossible in
    BOTH directions, or one of them is only accidentally absent."""
    build = ComponentBuildInfo(name="echo_stub_with_output", library_sha256="", build_id="build-7")
    session = _session_with_port(component_build=build)
    record = evidence(_PORT, session, 0)

    assert record.component_build_id == "build-7"
    assert record.component_library_sha256 is None
    assert dict(format_evidence(record))["component_library_sha256"] == "unknown"


def test_evidence_prim_join_matches_direct_port_lookup_provenance():
    """A prim and its resolved port answer the SAME provenance question --
    `ST-D6-3`'s own "config bundle and component build" must not depend on
    which address the caller happened to select."""
    build = ComponentBuildInfo(name="echo_stub_with_output", build_id="build-7", config_bundle_sha256="bundle-sha-9")
    session = _session_with_port(component_build=build)
    via_prim = evidence("echo-prim-1", session, 0)
    via_port = evidence(_PORT, session, 0)
    assert via_prim.config_bundle_sha256 == via_port.config_bundle_sha256
    assert via_prim.component_build_id == via_port.component_build_id
    assert via_prim.value == via_port.value
    assert via_prim.origin == via_port.origin


def test_evidence_unresolvable_pick_id_still_degrades_to_unknown():
    session = _session_with_port()
    record = evidence("no-such-pick-id", session, 0)
    assert record.kind == "unknown"


def test_format_evidence_renders_the_new_prim_fields_never_a_bare_none():
    session = _session_with_port()
    record = evidence("echo-prim-1", session, 0)
    rows = dict(format_evidence(record))
    assert rows["layer_id"] == "sim.test.evidence_prim_join.echo_layer"
    assert rows["derived"] == "False"
    assert "None" not in rows.values()
