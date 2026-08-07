# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Ties the scenario schema (`contracts/scenario.py`), the resim engine
(`core/resim.py`) and the expectation evaluator (`check/expect.py`)
together into what `sim check` runs (`sim_scenarios_and_expectations.md`
SS3.0a, SS6): resolve a scenario's recording + pipeline, resim it, evaluate
`expect:` against the result. `cli/check.py` -- argument parsing only,
`GT-9` -- calls this module; it never contains the logic itself.

**Recording discovery**: the documented, still-current sibling-folder
convention (SS8) -- `carla_scenarios/<feature>/<id>.yaml` pairs with a
`carla_testruns/<feature>/<id>.<ext>` of some registered recording format.
Renamed in one `git mv` when a second simulator lands (`OD-3`), not before
-- this module reads the convention that exists today, with an explicit
override for when it does not apply. `check/` names no format itself
(`R-SIM-14`, `UT-A4-11`): the extension is discovered by globbing the stem,
never assumed, and the actual read goes through `io.registry.reader_for`
(via `core.resim.resim_pipeline`), which is the one place a suffix is
resolved to a codec.

**Pipeline discovery**: `scenario.sut.pipeline` is a bare name
(`sim_scenarios_and_expectations.md` SS3's "a reference, never a path");
resolved by scanning `modules/*/sim/pipelines/*.yaml` under the
superproject root, the same interim convention `io/ingest.py` already
documents for ingest maps -- no plug-in path exists yet (`S-C8`), so this
is loaded from the checkout, not a component's deployed `sim/` directory.

A scenario with no `sut.pipeline` (every v1-upgraded scenario today, since
none of the 18 real cases have been migrated with a named pipeline yet) or
a missing recording is **skipped, never failed** (`ST-C3-3`): recordings
need a live world server to produce and are not always present in a
partial clone, and a scenario not yet wired to a pipeline has nothing to
resim against.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from adas_sim.check.expect import ExpectationResult, evaluate_scenario
from adas_sim.contracts.component import ComponentManifest, resolve_message_classes
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.contracts.scenario import load_scenario
from adas_sim.core.errors import AuthoringError
from adas_sim.core.resim import resim_pipeline
from adas_sim.core.tick import Pose2D, PortValue, Tick

#: check/runner.py -> check -> adas_sim -> src -> sim -> modules -> superproject root.
_SUPERPROJECT_ROOT = Path(__file__).resolve().parents[5]

_SCENARIOS_DIR_NAME = "carla_scenarios"
_RECORDINGS_DIR_NAME = "carla_testruns"


def discover_pipelines(superproject_root: Path = _SUPERPROJECT_ROOT) -> dict[str, Path]:
    """Every `modules/*/sim/pipelines/*.yaml`, keyed by file stem."""
    pipelines: dict[str, Path] = {}
    for pipeline_dir in sorted(superproject_root.glob("modules/*/sim/pipelines")):
        for path in sorted(pipeline_dir.glob("*.yaml")):
            pipelines[path.stem] = path
    return pipelines


def default_recording_stem_for(scenario_path: Path) -> Path:
    """`.../carla_scenarios/<feature>/<id>.yaml` -> `.../carla_testruns/
    <feature>/<id>` -- deliberately **no extension**: which codec produced
    this scenario's recording is a fact about the file on disk, not
    something this module assumes (`R-SIM-14`). Raises naming the scenario
    path if it does not contain the expected directory segment -- callers
    outside that convention pass `recording_path=` explicitly instead."""
    parts = list(scenario_path.parts)
    if _SCENARIOS_DIR_NAME not in parts:
        raise AuthoringError(
            expected=f"a scenario path containing a {_SCENARIOS_DIR_NAME!r} directory segment",
            found=str(scenario_path), where="check.runner.default_recording_stem_for",
            hint="pass recording_path= explicitly for a scenario outside that folder convention",
        )
    parts[parts.index(_SCENARIOS_DIR_NAME)] = _RECORDINGS_DIR_NAME
    return Path(*parts).with_suffix("")


def _find_recording(stem: Path) -> Path | None:
    """The one file in `stem`'s directory sharing its name, whatever
    extension a registered codec gave it -- `None` if none exists yet
    (`ST-C3-3`'s skip case) or `AuthoringError` if more than one matches
    (an ambiguous convention is worse than a missing file)."""
    if not stem.parent.is_dir():
        return None
    matches = sorted(p for p in stem.parent.glob(stem.name + ".*") if p.is_file())
    if len(matches) > 1:
        raise AuthoringError(
            expected=f"at most one recording named {stem.name!r} in {stem.parent}",
            found=f"{len(matches)}: {[m.name for m in matches]}", where=str(stem),
            hint="remove the stale/duplicate recording",
        )
    return matches[0] if matches else None


@dataclass(frozen=True, slots=True)
class ScenarioCheckResult:
    """One scenario's outcome -- either evaluated (`results` populated) or
    skipped (`skip_reason` set, `ST-C3-3`: a missing recording or an
    unmigrated `sut.pipeline` is a skip, never a failure)."""

    scenario_id: str
    scenario_path: Path
    skipped: bool
    skip_reason: str = ""
    results: tuple[ExpectationResult, ...] = ()

    @property
    def passed(self) -> bool:
        """A skipped scenario does not fail the suite -- it was never
        evaluated, which is a different fact than "evaluated and failed"
        (`ST-C3-3`)."""
        return self.skipped or all(r.passed for r in self.results)

    def __repr__(self) -> str:
        state = "skipped" if self.skipped else ("pass" if self.passed else "fail")
        return f"<ScenarioCheckResult {self.scenario_id!r} {state}>"


def _decode_tick_ports(
    pipeline: Pipeline, outputs_by_stage: Mapping[str, Mapping[str, bytes]],
    classes_by_stage: Mapping[str, Mapping[str, type]], t_ns: int,
) -> dict[str, PortValue]:
    ports: dict[str, PortValue] = {}
    for stage in pipeline.stages:
        manifest = pipeline.manifest_for(stage.name)
        classes = classes_by_stage[stage.name]
        produced = outputs_by_stage.get(stage.name, {})
        origin = "measured" if stage.mode == "measured" else "simulated"
        for port_spec in manifest.outputs:
            qualified = f"{stage.name}.{port_spec.name}"
            payload = produced.get(port_spec.name)
            if payload is None:
                ports[qualified] = PortValue(
                    name=qualified, message=None, origin="unknown", valid=False, updated=False, t_ns=t_ns,
                )
                continue
            message = classes[port_spec.proto_type]()
            message.ParseFromString(payload)
            ports[qualified] = PortValue(name=qualified, message=message, origin=origin, valid=True, updated=True, t_ns=t_ns)
    return ports


def _ticks_from_resim(pipeline: Pipeline, outputs: Sequence[tuple[int, dict]]) -> tuple[Tick, ...]:
    """Decodes `core.resim.resim_pipeline`'s raw-bytes-per-stage output into
    `Tick`s the evaluator can address by `<stage>.<port>.<field>`
    (`core/signals.py`'s one address space). Eager decode -- unlike a
    recording's own lazy `PortValue.message` (`S-B2Δ`) -- since every
    stage's message classes are resolved once, up front, from its own
    manifest, and a resim's whole point is examining every tick's output."""
    classes_by_stage = {
        stage.name: resolve_message_classes(pipeline.manifest_for(stage.name)) for stage in pipeline.stages
    }
    ticks = []
    previous_t_ns: int | None = None
    for index, (t_ns, outputs_by_stage) in enumerate(outputs):
        dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
        previous_t_ns = t_ns
        ports = _decode_tick_ports(pipeline, outputs_by_stage, classes_by_stage, t_ns)
        ticks.append(Tick(index=index, t_ns=t_ns, dt_ns=dt_ns, ports=ports, pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)))
    return tuple(ticks)


def check_scenario(
    scenario_path: Path, *, recording_path: Path | None = None, pipeline_path: Path | None = None,
    search: Sequence[Path] = (), pipelines: Mapping[str, Path] | None = None,
    components: Mapping[str, object] | None = None, config_path: Path | None = None,
) -> ScenarioCheckResult:
    """One scenario, end to end. `pipelines=` lets a caller checking a
    whole set (`check_scenarios`) discover the pipeline directory once and
    share it, rather than every scenario re-scanning the checkout.
    `components=` forwards to `Pipeline.load` (`impl: stub:` has no
    registry yet, `S-C2`) -- a real run always uses `dll:`/`stubdll:`
    stages, so this is exercised only by tests injecting an
    `InProcessSilComponent`, the same pattern `test_c1c_pipeline.py` and
    `test_c2_record_resim.py` already use. `config_path=` is forwarded to
    `Pipeline.init_components` -- resolving a project name to its config
    (`src/project/<p>/default.yaml`, say) is a component-specific
    convention this framework does not invent (`adasInit(NULL)`'s own
    packed-bundle resolution is `S-C5`, not yet built); the caller supplies
    it explicitly until then."""
    scenario = load_scenario(scenario_path)

    if recording_path is not None:
        resolved_recording: Path | None = recording_path if recording_path.exists() else None
        not_found_detail = str(recording_path)
    else:
        try:
            stem = default_recording_stem_for(scenario_path)
        except AuthoringError as exc:
            # A scenario outside the sibling-folder convention is not an
            # authoring mistake worth stopping a whole batch run over
            # (`ST-C3-3`'s own "skip, don't fail" reasoning extended to
            # "cannot even guess where the recording would be").
            return ScenarioCheckResult(
                scenario_id=scenario.id, scenario_path=scenario_path, skipped=True, skip_reason=str(exc),
            )
        resolved_recording = _find_recording(stem)
        not_found_detail = f"{stem}.*"
    if resolved_recording is None:
        return ScenarioCheckResult(
            scenario_id=scenario.id, scenario_path=scenario_path, skipped=True,
            skip_reason=f"recording not found: {not_found_detail}",
        )

    if pipeline_path is not None:
        resolved_pipeline_path = pipeline_path
    else:
        if not scenario.sut.pipeline:
            return ScenarioCheckResult(
                scenario_id=scenario.id, scenario_path=scenario_path, skipped=True,
                skip_reason="scenario declares no sut.pipeline (not yet migrated to a named pipeline)",
            )
        available = pipelines if pipelines is not None else discover_pipelines()
        if scenario.sut.pipeline not in available:
            raise AuthoringError(
                expected=f"a pipeline named {scenario.sut.pipeline!r} under modules/*/sim/pipelines/",
                found=f"known pipelines: {sorted(available)}", where=str(scenario_path),
                hint="add modules/<name>/sim/pipelines/<name>.yaml, or pass pipeline_path= explicitly",
            )
        resolved_pipeline_path = available[scenario.sut.pipeline]

    pipeline = Pipeline.load(
        resolved_pipeline_path, search=search, components=components, faults=scenario.run.faults,
    )
    pipeline.init_components(config_path)
    try:
        outputs = resim_pipeline(pipeline, resolved_recording)
    finally:
        pipeline.shutdown_components()
    ticks = _ticks_from_resim(pipeline, outputs)
    sut = _sole_simulate_stage(pipeline)
    results = evaluate_scenario(scenario, ticks, sut=sut)
    return ScenarioCheckResult(scenario_id=scenario.id, scenario_path=scenario_path, skipped=False, results=results)


def _sole_simulate_stage(pipeline: Pipeline) -> tuple[str, ComponentManifest] | None:
    """`(stage_name, manifest)` for `pipeline`'s own single `mode: simulate`
    stage -- what a `self.<port>` signal resolves against (`S-C1cΔ`,
    `ST-C1c-2`'s own canonical algo-test shape). `None` for zero or more
    than one `simulate` stage -- "self" is then genuinely undefined, and
    `check.expect._resolve_self_address` raises naming that only if a
    scenario's `expect:` block actually uses `self.` (never eagerly, since
    most scenarios never do)."""
    simulate_stages = [stage.name for stage in pipeline.stages if stage.mode == "simulate"]
    if len(simulate_stages) != 1:
        return None
    name = simulate_stages[0]
    return name, pipeline.manifest_for(name)


def discover_scenarios(scenario_set: Path) -> tuple[Path, ...]:
    """`<scenario-set>` (`sim_api_reference.md` SS10): a single scenario
    file, or every `*.yaml` under a directory, recursively."""
    if scenario_set.is_file():
        return (scenario_set,)
    return tuple(sorted(scenario_set.rglob("*.yaml")))


def check_scenarios(
    scenario_set: Path, *, search: Sequence[Path] = (), config_path: Path | None = None,
) -> tuple[ScenarioCheckResult, ...]:
    """Every scenario under `scenario_set`, checked -- pipelines discovered
    once, up front, shared across the whole set."""
    pipelines = discover_pipelines()
    return tuple(
        check_scenario(path, search=search, pipelines=pipelines, config_path=config_path)
        for path in discover_scenarios(scenario_set)
    )
