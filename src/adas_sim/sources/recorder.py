# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Recorder` -- drives a `Source`, optionally through a `Pipeline`, writing
a recording (`sim_implementation_plan.md` S-C2, `R-SIM-12`,
`sim_resim_and_recording.md` §9's CLI table). Separates *producing* a
recording from *executing* one: this class only ever calls `Source.poll()`
+ `Pipeline.step()` and writes what comes back -- reading the result back
is `core.runner`'s job, already built.

`pipeline` is optional -- `None` is `sim record`'s own case (§9: "produces
an artifact, executes a SUT: no" -- every declared `source.emits()` port is
recorded, nothing is computed). A real `Pipeline` is `sim run --record`'s
case (drives the source AND executes it live); its own declared ports,
`source.*` wiring plus every non-`off` stage's own outputs, are recorded
instead of the source's full `emits()` -- `R-SIM-6`'s own "did we record
everything the SUT reads" only needs what the pipeline actually wires.

Topics are derived from the pipeline's own declared port manifests
(`R-SIM-6` -- "did we record everything the SUT reads" true by
construction) and named `"/<stage>/<port>"` -- a leading slash, then only
the FIRST dot of the qualified port name turned into a slash (a port name
may itself contain dots, `R-SIM-4`'s `<function>.<port>`, and stays
dotted): `"source.gen_object_list"` -> `"/source/gen_object_list"`,
`"widget.outputs"` -> `"/widget/outputs"`, `"df.fn.outputs"` ->
`"/df/fn.outputs"`. This is `simcore`'s own `PortNameToTopic`
(`src/simcore/runner/cycle_loop.cpp`) convention, required for a
`mode: measured` stage to match a recorded topic by exact string equality
(found live, `WP-15b`) -- **not** a plain dot-to-slash inverse of
`core.runner._topic_to_port_name`/`engine.bridge.topic_to_port_name`,
though both tolerate it fine (they `strip("/")` before splitting, and
collapsing one or two slashes into dots gives the same dotted result
either way), so a recording this class writes still needs no ingest map
(`S-C9`) to read back.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from adas_sim.graph.build import Pipeline, RecordVerb, _split_ref, record_policy_for
from adas_sim.config.scenario import Scenario
from adas_sim.diagnostics.errors import InternalError
from adas_sim.diagnostics.tap import resolve_taps
from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import writer_for
from adas_sim.runspec import volume
from adas_sim.sources.base import Source

#: `max_bytes: 0` (undeclared) fallback -- mirrors `contracts/component.py`'s
#: own `_DEFAULT_OUTPUT_CAP` so the size estimate and the real allocator
#: agree on what "unknown" means.
_DEFAULT_PORT_BYTES = 256

#: `IMP-0225` (`MOVE`): the real constant now lives in `runspec/volume.py`;
#: re-exported here so `from adas_sim.sources.recorder import
#: REVISE_AFTER_TICKS` (an existing test import) keeps working unchanged.
REVISE_AFTER_TICKS = volume.REVISE_AFTER_TICKS


def _qualified(prefix: str, port: str) -> str:
    return f"{prefix}.{port}"


def topic_for(qualified_port_name: str) -> str:
    stage, sep, rest = qualified_port_name.partition(".")
    return f"/{stage}/{rest}" if sep else f"/{qualified_port_name}"


class Recorder:
    """One recording, `open()` to `close()`. `source_provenance` tags every
    `source.*` topic (`R-SIM-12`): a single `Provenance` applies to every
    source port, or a `Mapping[str, Provenance]` tags them individually --
    a source can legitimately mix `truth` and `mocked` ports (e.g. CARLA
    actor ground truth vs. a synthesized detection list). A real stage's
    own output ports are always tagged `simulated`: freshly computed this
    run, never injected (a `mode: measured` stage has no place in a
    recording pipeline -- there would be nothing new to write for it)."""

    def __init__(
        self, pipeline: Pipeline | None, source: Source, path: Path, *, meta: RunManifest,
        source_provenance: Provenance | Mapping[str, Provenance] = Provenance.MOCKED,
        config_bundle_bytes: bytes = b"",
        plugin_bundles_meta: Mapping[str, Mapping[str, object]] = MappingProxyType({}),
        source_proto_types: Mapping[str, str] = MappingProxyType({}),
        source_descriptor_set: bytes = b"",
    ) -> None:
        self._pipeline = pipeline
        self._source = source
        self._path = path
        self._meta = meta
        self._source_provenance = source_provenance
        # A stage output's schema comes from its own pipeline manifest
        # (`_topics` below); a source port has no manifest to draw one from,
        # so the caller supplies it directly -- proto_type per port plus one
        # shared `FileDescriptorSet` (mirrors `config_bundle_bytes`: a single
        # blob, not per-port). Empty for a source with no real schema to
        # offer (e.g. `--source synthetic`'s scripted bytes) -- the same
        # honest "nothing to embed" `config_bundle_bytes` already uses,
        # rather than the placeholder qualified-port-name schema this used
        # to fall back to silently.
        self._source_proto_types = source_proto_types
        self._source_descriptor_set = source_descriptor_set
        # S-C5, R-SIM-6: the SUT's config bundle, embedded once at open() on
        # /meta/config_bundle -- empty when the caller has no real component
        # bundle to embed (e.g. a pure-synthetic-source `sim record` run
        # with no `dll:`/`stubdll:` stage), the honest "nothing to embed"
        # rather than a placeholder.
        self._config_bundle_bytes = config_bundle_bytes
        # S-C8, NR-SIM-44: per-component plug-in IDENTITY and HASH only --
        # `{component: {"api": int, "sha256": str}}` -- never bytes. The
        # asymmetry with config_bundle_bytes above is deliberate:
        # configuration is data, a plug-in is code, and a recording must
        # never become a way to run someone else's code.
        self._plugin_bundles_meta = plugin_bundles_meta
        self._writer = writer_for(path)
        self._elapsed_ns = 0
        self._tick_index = 0
        self._ticks_written = 0
        self._bytes_written = 0
        self._opened = False

    def __repr__(self) -> str:
        return f"<Recorder path={self._path} ticks_written={self._ticks_written}>"

    def _provenance_for_source_port(self, port: str) -> Provenance:
        if isinstance(self._source_provenance, Provenance):
            return self._source_provenance
        return self._source_provenance.get(port, Provenance.UNKNOWN)

    def _wired_source_ports(self) -> set[str]:
        if self._pipeline is None:
            # sim record's own case: no pipeline wiring to consult, so
            # every port this source can produce is what "recorded" means.
            return set(self._source.emits())
        ports: set[str] = set()
        for stage in self._pipeline.stages:
            if stage.mode == "off":
                continue
            for ref in stage.inputs.values():
                producer_name, port = _split_ref(ref)
                if producer_name == "source":
                    ports.add(port)
        return ports

    def _recorded_stage_output_ports(self) -> list[tuple]:
        """Every non-`off` stage's own declared output port, paired with
        its resolved `record:` policy -- `excluded` entries are omitted
        entirely here, once, so every other method (`_topics`,
        `estimate_upper_bound_bytes`, `tick`) agrees on what "recorded"
        means. Empty when `pipeline is None` -- nothing is executed, so
        there are no stage outputs to record (`sim record`'s own case)."""
        if self._pipeline is None:
            return []
        result = []
        for stage in self._pipeline.stages:
            if stage.mode == "off":
                continue
            for port_spec in self._pipeline.manifest_for(stage.name).outputs:
                policy = record_policy_for(stage, port_spec.name)
                if policy.verb is RecordVerb.EXCLUDED:
                    continue
                result.append((stage, port_spec, policy))
        return result

    def _tapped_output_ports(self) -> list[tuple]:
        """`IMP-0285` (`SW-0285`): every declared `taps:` entry, resolved to
        its `(stage, PortSpec)` pair -- `Pipeline.load` already validated
        each one names a real, existing OUTPUT port (an input-port tap is
        refused at load, `Pipeline.step()` returns no input values to
        record); this re-resolves (pure, cheap, same function) into the
        `(stage, port_spec)` shape `_topics`/`tick` already use for a
        normally-wired output. Empty when `pipeline is None` or declares no
        taps -- `sim record`'s own case, or a pipeline with none."""
        if self._pipeline is None or not self._pipeline.taps:
            return []
        stage_by_name = {stage.name: stage for stage in self._pipeline.stages}
        manifests = {stage.name: self._pipeline.manifest_for(stage.name) for stage in self._pipeline.stages}
        resolved_ports = resolve_taps(self._pipeline.taps, manifests)
        return list(zip((stage_by_name[t.stage] for t in self._pipeline.taps), resolved_ports))

    def _topics(self) -> dict[str, TopicInfo]:
        topics: dict[str, TopicInfo] = {}
        for port in self._wired_source_ports():
            name = _qualified("source", port)
            proto_type = self._source_proto_types.get(port)
            topics[topic_for(name)] = TopicInfo(
                schema_name=proto_type or name, provenance=self._provenance_for_source_port(port),
                schema_bytes=self._source_descriptor_set if proto_type else b"",
            )
        for stage, port_spec, _policy in self._recorded_stage_output_ports():
            name = _qualified(stage.name, port_spec.name)
            # R-SIM-11: the component's own adasManifest() descriptor_set,
            # so a stage's recorded output decodes on replay instead of
            # staying raw bytes forever (previously never wired in here).
            topics[topic_for(name)] = TopicInfo(
                schema_name=port_spec.proto_type or name, provenance=Provenance.SIMULATED,
                schema_bytes=self._pipeline.manifest_for(stage.name).descriptor_set,
            )
        for stage, port_spec in self._tapped_output_ports():
            name = _qualified(stage.name, port_spec.name)
            if topic_for(name) in topics:
                continue  # already recorded via normal output wiring -- the tap is a redundant no-op, not an error
            topics[topic_for(name)] = TopicInfo(
                schema_name=port_spec.proto_type or name, provenance=Provenance.SIMULATED,
                schema_bytes=self._pipeline.manifest_for(stage.name).descriptor_set,
            )
        return topics

    def estimate_upper_bound_bytes(self, ticks: int) -> int:
        """`ST-C2-3`: an upper bound from each recorded port's own
        `max_bytes` (falling back to `_DEFAULT_PORT_BYTES` the same way an
        undeclared output cap does) times `ticks` -- the caller
        (`cli/record.py`) labels this an upper bound, never a measurement.
        `IMP-0225` (`MOVE`): the arithmetic itself is `runspec.volume.
        estimate_upper_bound_bytes`; this method only resolves this
        `Recorder`'s own per-port byte caps into the plain list that
        function takes."""
        port_max_bytes = [_DEFAULT_PORT_BYTES for _ in self._wired_source_ports()]
        port_max_bytes += [
            port_spec.max_bytes or _DEFAULT_PORT_BYTES
            for _stage, port_spec, _policy in self._recorded_stage_output_ports()
        ]
        return volume.estimate_upper_bound_bytes(port_max_bytes, ticks)

    def revised_estimate_bytes(self, total_ticks: int) -> int | None:
        """`None` until `REVISE_AFTER_TICKS` real ticks are written -- before
        that, only `estimate_upper_bound_bytes` is honest to report.
        `IMP-0225` (`MOVE`): delegates to `runspec.volume.
        revised_estimate_bytes`."""
        return volume.revised_estimate_bytes(self._bytes_written, self._ticks_written, total_ticks)

    def open(self, scenario: Scenario) -> None:
        self._source.start(scenario)
        # `config_bundle_bytes` is an extra beyond RecordingWriter's minimal
        # Protocol (`io/base.py`, mirrors `cli/convert.py`'s own comment) --
        # not every registered writer accepts it (`CsvWriter.open()` does
        # not), so it is only ever passed when the concrete writer's own
        # signature declares it, never assumed and never silently dropped
        # when it's actually supported.
        open_kwargs: dict[str, object] = {}
        open_params = inspect.signature(self._writer.open).parameters
        if self._config_bundle_bytes and "config_bundle_bytes" in open_params:
            open_kwargs["config_bundle_bytes"] = self._config_bundle_bytes
        if self._plugin_bundles_meta and "plugin_bundles_meta" in open_params:
            open_kwargs["plugin_bundles_meta"] = self._plugin_bundles_meta
        self._writer.open(self._path, self._meta, self._topics(), **open_kwargs)
        self._opened = True

    def _write_one(self, qualified_port_name: str, payload: bytes, log_time_ns: int) -> None:
        # capture_time_ns == log_time_ns here is a REAL, known value, not
        # "unknown defaulted to reception" (R-SIM-14's own warning): every
        # port this tick writes is either fresh source stimulus or a stage
        # output computed this same tick, with zero injected latency (no
        # error model exists yet, R-SIM-9) -- so reception and validity
        # genuinely coincide, and the manifest declares that fact
        # structurally via CAPTURE_TIME_MANIFEST_VERSION (core/manifest.py).
        self._writer.write(topic_for(qualified_port_name), log_time_ns, payload, capture_time_ns=log_time_ns)
        self._bytes_written += len(payload)

    def tick(self, dt_ns: int) -> None:
        if not self._opened:
            raise InternalError(
                expected="open() called before tick()", found="not opened",
                where="Recorder.tick", hint="call open() once before the first tick()",
            )
        stimulus = self._source.poll()
        result = self._pipeline.step(dt_ns, stimulus) if self._pipeline is not None else {}
        self._elapsed_ns += dt_ns
        log_time_ns = self._elapsed_ns

        for port, payload in stimulus.items():
            if port not in self._wired_source_ports():
                continue  # this pipeline never wired it -- not this recording's business (R-SIM-6)
            self._write_one(_qualified("source", port), payload, log_time_ns)

        recorded_output_ports = self._recorded_stage_output_ports()
        for stage, port_spec, policy in recorded_output_ports:
            if policy.verb is RecordVerb.DECIMATE and self._tick_index % policy.decimate_n != 0:
                continue
            value = result.get(_qualified(stage.name, port_spec.name))
            if value is None or not value.updated:
                continue  # held or absent this tick -- nothing new to write
            self._write_one(_qualified(stage.name, port_spec.name), value.raw_bytes, log_time_ns)

        # `IMP-0285`: a tap already covered by normal output wiring above is
        # a redundant no-op (same reasoning `_topics`' own skip uses) --
        # never a double write of the same topic this tick.
        already_recorded = {(stage.name, port_spec.name) for stage, port_spec, _policy in recorded_output_ports}
        for stage, port_spec in self._tapped_output_ports():
            if (stage.name, port_spec.name) in already_recorded:
                continue
            value = result.get(_qualified(stage.name, port_spec.name))
            if value is None or not value.updated:
                continue  # held or absent this tick -- nothing new to write
            self._write_one(_qualified(stage.name, port_spec.name), value.raw_bytes, log_time_ns)

        self._tick_index += 1
        self._ticks_written += 1

    def close(self) -> None:
        self._source.stop()
        self._writer.close()
        self._opened = False
