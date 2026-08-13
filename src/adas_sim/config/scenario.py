# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Scenario schema v2 + the v1 upgrader (`sim_scenarios_and_expectations.md`
SS3, `S-C3`, `R-SIM-8`). Four sections plus a version: `scenario:` (world-model
agnostic content), `sensor_model:`, `run:` (end condition, faults) and `sut:`
(a pipeline reference, never a path) -- plus `markers:` (anchor provenance)
and `expect:` (left as raw data here; `check/expect.py` owns the predicate
vocabulary, a later slice of this same stage). No live world model exists
(`DD-12`); every input is a recording, so there is no `world:` section.

**Framework, not content** (`R-SIM-1`): this module knows the shape of a
scenario, never what is being tested. It carries no function name, and the
18 real cases stay in `modules/df/tests/` (`sim_scenarios_and_expectations.md`
SS0) -- this module's own tests exercise fixture scenarios under
`tests/fixtures/scenarios/` instead of the real ones.

**Back-compat is a load-time upgrade, not two readers.** A file without
`schema: 2` is v1: `_upgrade_v1` maps it onto the v2 shape in memory (the
same technique `lead:` sugar already used), and `_parse_v2` is the only
place that ever builds a `Scenario`. Every v1 file keeps running unchanged;
migrating a case to `schema: 2` is then a mechanical, reviewable pass, not a
flag day (SS3.2, SS7).
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from adas_sim.config.fault import Fault, parse_fault
from adas_sim.diagnostics.errors import AuthoringError

#: The only two shapes this reader understands: an implicit/explicit `1`
#: (upgraded in memory) or the current `2`. Neither is `CURRENT_..._VERSION`
#: alone, the way `pipeline.py`'s single-shape constant is -- v1 stays real
#: input as long as any scenario on disk has not been migrated (SS3.2).
CURRENT_SCENARIO_VERSION = 2
_SUPPORTED_SCHEMAS = frozenset({1, CURRENT_SCENARIO_VERSION})


@dataclass(frozen=True, slots=True)
class LateralPhase:
    """One phase of a `lateral_profile` (SS1): a constant lateral rate held
    for a duration. `rate_mps` is signed in the project convention (`+y` =
    left, `R-COORD-1`) -- deliberately not inferred from a
    converge/diverge label, which breaks for a left-side target. `shape`
    (`const`/`raised_cosine`, SS1) moves across unchanged -- a constant-rate
    slide produces no yaw rate, which is why a spurious-warp case needs the
    other shape to test anything at all."""

    name: str
    rate_mps: float
    duration_s: float
    shape: str = "const"


@dataclass(frozen=True, slots=True)
class Actor:
    """One `scenario.actors[]` entry. `classification` was `class:` on the
    wire (SS3.2's rename table) -- Python has no such reserved-word
    collision on an attribute name, so the field keeps the clearer name."""

    name: str
    classification: str
    long_offset_m: float
    lateral_offset_m: float
    speed_mps: float
    lateral_profile: tuple[LateralPhase, ...] = ()


@dataclass(frozen=True, slots=True)
class RoadHint:
    """`scenario.road` (SS3): what the scenario NEEDS, stated so a different
    map or simulator has a requirement to satisfy rather than a magic
    spawn-point index to copy. Absent for every v1 file -- the requirement
    was previously only in a comment, and the upgrader does not invent one
    from prose (that would be exactly the ad-hoc inference `R-SIM-15`
    refuses one layer up)."""

    hint: str | None = None
    min_straight_m: float | None = None
    lanes_right_of_ego: int | None = None


@dataclass(frozen=True, slots=True)
class EgoScenario:
    speed_mps: float
    lateral_profile: tuple[LateralPhase, ...] = ()


@dataclass(frozen=True, slots=True)
class ScenarioContent:
    """The `scenario:` section (SS3, concern (1)) -- world-model agnostic."""

    road: RoadHint
    ego: EgoScenario
    actors: tuple[Actor, ...]


@dataclass(frozen=True, slots=True)
class ConstantAnchor:
    """`at: <seconds>` -- an externally derived constant. `source` is the
    wire's `from:` -- a Python keyword, so the attribute is renamed rather
    than shadowed. **Required, never defaulted**: a constant anchor with no
    stated origin is exactly the silent drift `R-SIM-8` exists to stop."""

    seconds: float
    source: str


@dataclass(frozen=True, slots=True)
class BecomesAnchor:
    """`at: {first: <signal>, becomes: <value>}` (SS9.1) -- the first tick
    an existing `expect:` predicate would hold, used as a time reference
    instead of an assertion. Resolved by `check/expect.py`, which reuses
    its own `Becomes` transition logic to do it -- no second mechanism."""

    signal: str
    value: object


@dataclass(frozen=True, slots=True)
class CrossesAnchor:
    """`at: {first: <signal>, crosses: <value>, dir: rising|falling}`
    (SS9.1). One signal address, one literal, one direction -- nothing
    else; the moment an anchor relates two signals it is an expression and
    the answer is a constant with `from:` (`ConstantAnchor` above)."""

    signal: str
    threshold: float
    direction: str  # "rising" | "falling"


AnchorForm = ConstantAnchor | BecomesAnchor | CrossesAnchor


@dataclass(frozen=True, slots=True)
class Marker:
    """One `markers:` entry (SS9.1): `id` + `at`, one of the two closed
    forms above. Superseded the earlier `{name: {value, from}}` mapping
    shape (SS3's original sketch) once SS9.1 resolved `OQ-3` -- `markers:`
    is a LIST on the wire (`id` is itself the addressable name), never a
    name-keyed mapping."""

    id: str
    at: AnchorForm


@dataclass(frozen=True, slots=True)
class SensorModelRef:
    """The `sensor_model:` section (SS3, concern (3)). `preset` names a
    shared document (`modules/<name>/sim/sensor_models/*.yaml`, SS3.1) that
    this module does not resolve -- resolving a preset is the sensor-model
    consumer's job, not the scenario loader's (this module stays framework,
    R-SIM-1)."""

    preset: str | None = None
    object_range_m: float | None = None
    num_object_slots: int | None = None


@dataclass(frozen=True, slots=True)
class RunControl:
    """The `run:` section (SS3, concern (4)). `end_condition` is left as the
    raw mapping (or `None` if the file declares none) -- what an absent one
    defaults to is the driving engine's own concern, not this schema's;
    inventing a default here would put runtime behaviour in a module whose
    whole job is not knowing what is being tested. `faults` is the closed
    five-verb vocabulary (`config/fault.py`, SS9.2)."""

    end_condition: Mapping[str, object] | None = None
    faults: tuple[Fault, ...] = ()


@dataclass(frozen=True, slots=True)
class SutRef:
    """The `sut:` section (SS3, concern (5)) -- a reference, never a path.
    `dll_path`/`config_path` are v1 back-compat only (SS3.2's upgrade
    table): honoured when present, with a `DeprecationWarning` naming the
    file, because the build to run is a run-time choice recorded in the run
    manifest, not scenario data."""

    pipeline: str | None = None
    project: str = "base"
    dll_path: str | None = None
    config_path: str | None = None


@dataclass(frozen=True, slots=True)
class Scenario:
    """One scenario, schema v2, however it was authored on disk."""

    schema: int
    id: str
    doc: str
    scenario: ScenarioContent
    sensor_model: SensorModelRef
    run: RunControl
    sut: SutRef
    markers: Mapping[str, Marker] = field(default_factory=dict)
    expect: tuple[Mapping[str, object], ...] = ()
    path: Path | None = None

    def __repr__(self) -> str:
        return f"<Scenario id={self.id!r} schema={self.schema}>"


def _require(mapping: Mapping[str, object], key: str, *, where: str) -> object:
    value = mapping.get(key)
    if value is None:
        raise AuthoringError(
            expected=f"'{key}:' present", found=f"absent or null, resolving {where}",
            where=where, hint="",
        )
    return value


def _leading_comment_block(text: str) -> str:
    """A v1 file's leading `#` comment block, in full (SS3.2's `doc:`
    upgrade row) -- every consecutive line from the top starting with `#`,
    one leading space stripped per line, stopping at the first non-comment
    line. `--list`/the GUI tooltip today only read the FIRST such line
    (`carla_bridge.py._first_comment_line`); `doc:` keeps the whole block,
    which is what SS3's example shows carrying the full acceptance-criteria
    prose forward unabridged."""
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("#"):
            break
        content = stripped[1:]
        if content.startswith(" "):
            content = content[1:]
        lines.append(content)
    return "\n".join(lines)


_LATERAL_SHAPES = frozenset({"const", "raised_cosine"})


def _parse_lateral_profile(raw: object, *, where: str) -> tuple[LateralPhase, ...]:
    if not raw:
        return ()
    if not isinstance(raw, Sequence):
        raise AuthoringError(
            expected="a list of {name, rate_mps, duration_s} phases", found=repr(raw), where=where, hint="",
        )
    phases = []
    for i, phase in enumerate(raw):
        phase_where = f"{where}[{i}]"
        shape = str(phase.get("shape", "const"))
        if shape not in _LATERAL_SHAPES:
            raise AuthoringError(
                expected=f"shape: one of {sorted(_LATERAL_SHAPES)}", found=repr(shape), where=phase_where, hint="",
            )
        phases.append(LateralPhase(
            name=str(_require(phase, "name", where=phase_where)),
            rate_mps=float(_require(phase, "rate_mps", where=phase_where)),
            duration_s=float(_require(phase, "duration_s", where=phase_where)),
            shape=shape,
        ))
    return tuple(phases)


def _parse_actor(raw: Mapping[str, object], *, where: str) -> Actor:
    name = str(_require(raw, "name", where=where))
    actor_where = f"{where}[{name}]"
    return Actor(
        name=name,
        classification=str(raw.get("class", raw.get("classification", "CAR"))),
        long_offset_m=float(_require(raw, "long_offset_m", where=actor_where)),
        lateral_offset_m=float(raw.get("lateral_offset_m", 0.0)),
        speed_mps=float(_require(raw, "speed_mps", where=actor_where)),
        lateral_profile=_parse_lateral_profile(raw.get("lateral_profile"), where=f"{actor_where}.lateral_profile"),
    )


_ALLOWED_ANCHOR_KEYS = frozenset({"first", "becomes", "crosses", "dir"})


def _parse_marker(raw: Mapping[str, object], *, where: str) -> Marker:
    """One `markers:` list entry (SS9.1): `id` + `at`, either a bare number
    (`ConstantAnchor`, `from:` required) or a mapping (`BecomesAnchor` /
    `CrossesAnchor`) -- never both, never a third shape."""
    marker_id = str(_require(raw, "id", where=where))
    marker_where = f"{where} '{marker_id}'"
    at_raw = _require(raw, "at", where=marker_where)

    if isinstance(at_raw, Mapping):
        extra = set(at_raw) - _ALLOWED_ANCHOR_KEYS
        if extra:
            raise AuthoringError(
                expected=f"only {sorted(_ALLOWED_ANCHOR_KEYS)} in a predicate anchor",
                found=f"also has: {sorted(extra)}", where=marker_where,
                hint="one signal address, one literal, one optional direction -- nothing else (SS9.1)",
            )
        signal = str(_require(at_raw, "first", where=marker_where))
        has_becomes, has_crosses = "becomes" in at_raw, "crosses" in at_raw
        if has_becomes == has_crosses:  # neither, or both -- exactly one required
            raise AuthoringError(
                expected="exactly one of becomes:/crosses: alongside first:",
                found=f"keys: {sorted(at_raw)}", where=marker_where, hint="",
            )
        if has_becomes:
            return Marker(id=marker_id, at=BecomesAnchor(signal=signal, value=at_raw["becomes"]))
        direction = at_raw.get("dir")
        if direction not in ("rising", "falling"):
            raise AuthoringError(
                expected="dir: rising or falling (required alongside crosses:)",
                found=repr(direction), where=marker_where, hint="",
            )
        return Marker(
            id=marker_id,
            at=CrossesAnchor(signal=signal, threshold=float(at_raw["crosses"]), direction=direction),
        )

    source = _require(raw, "from", where=marker_where)
    return Marker(id=marker_id, at=ConstantAnchor(seconds=float(at_raw), source=str(source)))


def _reject_roll_fault(raw: Mapping[str, object]) -> list[object]:
    if "roll_fault" not in raw:
        return []
    raise AuthoringError(
        expected="a run.faults: entry expressible in the closed five-verb vocabulary (contracts/fault.py)",
        found="roll_fault: (pre-vocabulary, hardcoded to one ego-roll signal)", where="scenario (v1) roll_fault",
        hint="rewrite as run.faults: [{verb: corrupt|invalidate, address: <port.field>, "
             "value:, from_s:/to_s: or after_tick:}] by hand -- no automatic mapping exists",
    )


def _upgrade_v1(raw: Mapping[str, object], *, doc: str) -> dict[str, object]:
    """Maps a v1-shaped raw dict onto the v2 shape, in memory (SS3.2's
    table). Every v1 file keeps running through `_parse_v2` unchanged --
    this function's whole job is producing something `_parse_v2` cannot
    tell apart from a freshly authored v2 file."""
    actors_raw = raw.get("actors")
    if actors_raw is None:
        lead_cfg = _require(raw, "lead", where="scenario (v1)")
        actors_raw = [{
            "name": "lead",
            "blueprint": lead_cfg.get("blueprint"),
            "long_offset_m": _require(lead_cfg, "initial_gap_m", where="scenario (v1) lead"),
            "lateral_offset_m": 0.0,
            "speed_mps": _require(lead_cfg, "speed_mps", where="scenario (v1) lead"),
            "classification": "CAR",
            "lateral_profile": None,
        }]

    scenario_actors: list[dict[str, object]] = []
    for cfg in actors_raw:
        name = _require(cfg, "name", where="scenario (v1) actors")
        actor_where = f"scenario (v1) actors[{name}]"
        scenario_actors.append({
            "name": name,
            "class": cfg.get("classification", cfg.get("class", "CAR")),
            "long_offset_m": _require(cfg, "long_offset_m", where=actor_where),
            "lateral_offset_m": cfg.get("lateral_offset_m", 0.0),
            "speed_mps": _require(cfg, "speed_mps", where=actor_where),
            "lateral_profile": cfg.get("lateral_profile"),
        })

    ego_raw: Mapping[str, object] = raw.get("ego") or {}
    df_raw: Mapping[str, object] = raw.get("df") or {}
    sut_raw: dict[str, object] = {"pipeline": None, "project": "base"}
    if df_raw.get("dll_path"):
        sut_raw["dll_path"] = df_raw["dll_path"]
    if df_raw.get("config_path"):
        sut_raw["config_path"] = df_raw["config_path"]

    return {
        "schema": CURRENT_SCENARIO_VERSION,
        "id": raw.get("id"),
        "doc": doc,
        "scenario": {
            "road": {},
            "ego": {"speed_mps": ego_raw.get("speed_mps"), "lateral_profile": ego_raw.get("lateral_profile")},
            "actors": scenario_actors,
        },
        "sensor_model": {
            "object_range_m": raw.get("object_range_m"),
            "num_object_slots": raw.get("num_object_slots"),
        },
        "run": {
            "end_condition": raw.get("end_condition"),
            # `roll_fault:` predates the closed five-verb vocabulary
            # (`contracts/fault.py`, SS9.2) and cannot be upgraded
            # automatically: its shape (`corrupt_after_s`/`invalid_after_s`,
            # hardcoded to one ego-roll signal) carries no `address:`, and
            # inventing one would be exactly the guessed mapping this
            # framework refuses (`R-SIM-9`/`NR-SIM-4`). No scenario among
            # the 18 real cases uses this key today -- raising rather than
            # silently dropping is the honest choice for the day one does.
            "faults": _reject_roll_fault(raw),
        },
        "sut": sut_raw,
        "markers": [],
        "expect": [],
    }


def _parse_v2(raw: Mapping[str, object], *, path: Path) -> Scenario:
    """The one place a `Scenario` is built -- reached identically whether
    `raw` was authored as v2 or produced by `_upgrade_v1` (SS3.2's whole
    point: one reader, not two)."""
    scenario_id = str(raw.get("id") or path.stem)
    doc = str(raw.get("doc", ""))

    scenario_raw: Mapping[str, object] = raw.get("scenario") or {}
    road_raw: Mapping[str, object] = scenario_raw.get("road") or {}
    road = RoadHint(
        hint=road_raw.get("hint"),
        min_straight_m=road_raw.get("min_straight_m"),
        lanes_right_of_ego=road_raw.get("lanes_right_of_ego"),
    )
    ego_raw: Mapping[str, object] = scenario_raw.get("ego") or {}
    ego = EgoScenario(
        speed_mps=float(_require(ego_raw, "speed_mps", where=f"{path} scenario.ego")),
        lateral_profile=_parse_lateral_profile(
            ego_raw.get("lateral_profile"), where=f"{path} scenario.ego.lateral_profile",
        ),
    )
    actors = tuple(
        _parse_actor(a, where=f"{path} scenario.actors") for a in (scenario_raw.get("actors") or [])
    )

    sensor_model_raw: Mapping[str, object] = raw.get("sensor_model") or {}
    sensor_model = SensorModelRef(
        preset=sensor_model_raw.get("preset"),
        object_range_m=sensor_model_raw.get("object_range_m"),
        num_object_slots=sensor_model_raw.get("num_object_slots"),
    )

    run_raw: Mapping[str, object] = raw.get("run") or {}
    run = RunControl(
        end_condition=run_raw.get("end_condition"),
        faults=tuple(
            parse_fault(entry, where=f"{path} run.faults[{i}]")
            for i, entry in enumerate(run_raw.get("faults") or ())
        ),
    )

    sut_raw: Mapping[str, object] = raw.get("sut") or {}
    sut = SutRef(
        pipeline=sut_raw.get("pipeline"),
        project=str(sut_raw.get("project", "base")),
        dll_path=sut_raw.get("dll_path"),
        config_path=sut_raw.get("config_path"),
    )
    if sut.dll_path:
        warnings.warn(
            f"{path}: sut.dll_path is deprecated -- the build to run is a run-time "
            "choice (CLI/GUI/CI), recorded in the run manifest, not scenario data",
            DeprecationWarning, stacklevel=2,
        )

    markers_raw = raw.get("markers") or []
    if isinstance(markers_raw, Mapping):
        raise AuthoringError(
            expected="markers: as a list of {id, at, from?} entries (SS9.1)",
            found="a name-keyed mapping", where=f"{path} markers",
            hint="markers: is a list -- id: is itself the addressable name",
        )
    markers: dict[str, Marker] = {}
    for entry in markers_raw:
        marker = _parse_marker(entry, where=f"{path} markers")
        if marker.id in markers:
            raise AuthoringError(
                expected="unique marker ids", found=f"'{marker.id}' declared more than once",
                where=f"{path} markers", hint="",
            )
        markers[marker.id] = marker

    expect = tuple(raw.get("expect") or ())

    return Scenario(
        schema=CURRENT_SCENARIO_VERSION, id=scenario_id, doc=doc,
        scenario=ScenarioContent(road=road, ego=ego, actors=actors),
        sensor_model=sensor_model, run=run, sut=sut,
        markers=markers, expect=expect, path=path,
    )


def load_scenario(path: Path) -> Scenario:
    """Loads one scenario file, upgrading v1 to v2 in memory first if
    needed (SS3.2). A file with no `schema:` key, or `schema: 1`, is v1; a
    schema this reader does not recognise is a load error naming both
    versions, same discipline as `pipeline.py`'s `_resolve_version`."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    schema = raw.get("schema", 1)
    if schema not in _SUPPORTED_SCHEMAS:
        raise AuthoringError(
            expected=f"schema: one of {sorted(_SUPPORTED_SCHEMAS)}", found=f"schema: {schema!r}",
            where=str(path), hint="this scenario was written by a newer adas-sim; upgrade the framework",
        )
    if schema == 1:
        return _parse_v2(_upgrade_v1(raw, doc=_leading_comment_block(text)), path=path)
    upgraded = dict(raw)
    upgraded.setdefault("doc", raw.get("doc", ""))
    return _parse_v2(upgraded, path=path)
