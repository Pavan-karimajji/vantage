# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The expectation predicate vocabulary + evaluator
(`sim_scenarios_and_expectations.md` SS5, `R-SIM-8`). One resolver serves the
timeline, plot panels, the HUD, `sim check` and the A/B diff (`core/signals`),
so anything you can plot you can assert on.

**Closed, kept deliberately small** (SS5.2): `equals` (+ `always`/`during`/
`whenever`), `becomes` (+ `within_s`/`of`), `never`, `count`, `between`,
`monotonic`, plus `equals` + `at_least_s`/`at_most_s`. Anything needing more
is a Python check registered alongside the scenario -- the fact that one was
needed is itself a signal worth seeing in review, not a reason to widen this
module.

**Markers reuse this module's own transition logic** (SS9.1): a
predicate-form anchor (`BecomesAnchor`/`CrossesAnchor`,
`contracts/scenario.py`) is "an existing `expect:` predicate used as a time
reference instead of an assertion" -- `resolve_marker` below is that reuse,
not a second mechanism.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from adas_sim.contracts.scenario import (
    BecomesAnchor, ConstantAnchor, CrossesAnchor, Marker, Scenario,
)
from adas_sim.core.errors import AuthoringError, InternalError
from adas_sim.core.history import FrameTree, HistoryView, LayerCtx
from adas_sim.core.signals import registered_signals, resolve_tick
from adas_sim.core.tick import Tick
from adas_sim.model.project import ProjectModel

# ---------------------------------------------------------------------------
# Time references -- `of: marker.<id>` and `during: [a, marker.<id>]`
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeRef:
    """`of:`/a `during:` bound naming a declared marker -- an expectation's
    timing anchor is always a marker, never a bare literal (`R-SIM-8`: an
    un-provenanced constant is exactly what `markers:`'s `from:` exists to
    avoid one layer up)."""

    marker_id: str


def _parse_time_ref(raw: object, *, where: str) -> TimeRef:
    if not isinstance(raw, str) or not raw.startswith("marker."):
        raise AuthoringError(
            expected="'marker.<id>'", found=repr(raw), where=where,
            hint="a timing anchor always names a declared marker, never a bare literal",
        )
    return TimeRef(marker_id=raw[len("marker."):])


def _parse_bound(raw: object, *, where: str) -> TimeRef | float:
    if isinstance(raw, str) and raw.startswith("marker."):
        return _parse_time_ref(raw, where=where)
    return float(raw)


def _bound_seconds(bound: TimeRef | float, *, markers: Mapping[str, float], where: str) -> float:
    if isinstance(bound, TimeRef):
        if bound.marker_id not in markers:
            raise AuthoringError(
                expected=f"a declared marker for 'marker.{bound.marker_id}'",
                found=f"known markers: {sorted(markers)}", where=where, hint="",
            )
        return markers[bound.marker_id]
    return bound


# ---------------------------------------------------------------------------
# `whenever: <signal> <op> <value>` -- one closed comparison, not an
# expression language (R-SIM-15's discipline applied here for the same
# reason: SS5.2 kept the predicate list small on purpose).
# ---------------------------------------------------------------------------

_COND_RE = re.compile(r"^(?P<signal>\S+)\s*(?P<op>==|!=|<=|>=|<|>)\s*(?P<value>\S+)$")
_COND_OPS = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
}


@dataclass(frozen=True, slots=True)
class Condition:
    signal: str
    op: str
    value: str  # coerced against the resolved value at eval time, never parsed early


def _parse_condition(raw: object, *, where: str) -> Condition:
    if not isinstance(raw, str):
        raise AuthoringError(expected="a string 'whenever:' condition", found=repr(raw), where=where, hint="")
    match = _COND_RE.match(raw.strip())
    if not match:
        raise AuthoringError(
            expected="'<signal> <op> <value>' with op in ==, !=, <, <=, >, >=",
            found=repr(raw), where=where,
            hint="whenever: is one closed comparison, not an expression language (R-SIM-15's discipline)",
        )
    return Condition(signal=match["signal"], op=match["op"], value=match["value"])


def _coerce_like(token: str, other: object) -> object:
    """`token` (a raw YAML scalar string, e.g. from `whenever:`'s RHS or an
    `equals:`/`becomes:` value already a plain scalar) compared against
    `other`'s own type -- numeric when `other` is numeric, else a bare
    string/enum-name comparison. Never a smarter coercion than that: this
    module has no schema for a port's field types (`R-SIM-11`), only
    whatever `resolve_tick` handed back."""
    if isinstance(other, bool):
        return token in ("true", "True", "1")
    if isinstance(other, (int, float)):
        try:
            return float(token) if not float(token).is_integer() or isinstance(other, float) else int(token)
        except ValueError:
            return token
    return token


# ---------------------------------------------------------------------------
# The closed predicate vocabulary (SS5.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EqualsAlways:
    value: object


@dataclass(frozen=True, slots=True)
class EqualsDuring:
    value: object
    start: TimeRef | float
    end: TimeRef | float


@dataclass(frozen=True, slots=True)
class EqualsWhenever:
    value: object
    condition: Condition


@dataclass(frozen=True, slots=True)
class EqualsAtLeastS:
    value: object
    duration_s: float


@dataclass(frozen=True, slots=True)
class EqualsAtMostS:
    value: object
    duration_s: float


@dataclass(frozen=True, slots=True)
class Becomes:
    value: object
    within_s: float
    of: TimeRef


@dataclass(frozen=True, slots=True)
class Never:
    value: object


@dataclass(frozen=True, slots=True)
class Count:
    value: object
    times: int


@dataclass(frozen=True, slots=True)
class Between:
    lo: float
    hi: float


@dataclass(frozen=True, slots=True)
class Monotonic:
    direction: str  # "increasing" | "decreasing"


Predicate = (
    EqualsAlways | EqualsDuring | EqualsWhenever | EqualsAtLeastS | EqualsAtMostS
    | Becomes | Never | Count | Between | Monotonic
)

_TOP_SHAPE_KEYS = ("becomes", "never", "count", "between", "monotonic", "equals")
_EQUALS_MODIFIER_KEYS = ("always", "during", "whenever", "at_least_s", "at_most_s")


@dataclass(frozen=True, slots=True)
class Expectation:
    """One `expect:` entry, parsed (SS5.1).

    **Authoring trap, worth stating once here:** YAML 1.1 (what `yaml.safe_load`
    implements) reads a bare `off`/`on`/`yes`/`no`/`true`/`false` (any case) as
    a *boolean*, and a bare `null`/`~`/`NONE`/`None` as *null* -- colliding
    with real enum members this framework's own components use verbatim
    (`BsdOutputs.WarningState.OFF`, `BsdOutputs.Scenario.NONE`). An unquoted
    `equals: OFF` silently becomes `equals: false`, comparing against the
    field-path resolver's enum-NAME string (`core/signals.py`'s own
    enum -> name resolution) and never matching. **Quote any enum-name
    literal that could be misread as a YAML keyword** (`equals: "OFF"`,
    `equals: "NONE"`) -- this module cannot detect the mistake after the
    fact, since a real `bool`-typed field legitimately uses bare
    `true`/`false` too.
    """

    id: str
    doc: str
    signal: str
    predicate: Predicate


def parse_expectation(raw: Mapping[str, object], *, where: str) -> Expectation:
    exp_id = str(raw.get("id") or "")
    if not exp_id:
        raise AuthoringError(expected="an 'id:' naming this expectation", found=repr(raw.get("id")), where=where, hint="")
    entry_where = f"{where} '{exp_id}'"
    doc = str(raw.get("doc", ""))
    signal = raw.get("signal")
    if not signal:
        raise AuthoringError(expected="a 'signal:' address", found=repr(signal), where=entry_where, hint="")

    present = [k for k in _TOP_SHAPE_KEYS if k in raw]
    if len(present) != 1:
        raise AuthoringError(
            expected=f"exactly one of {_TOP_SHAPE_KEYS}",
            found=f"has: {sorted(set(raw) & set(_TOP_SHAPE_KEYS))}", where=entry_where,
            hint="the expectation predicate vocabulary is closed (SS5.2)",
        )
    shape = present[0]

    predicate: Predicate
    if shape == "becomes":
        predicate = Becomes(
            value=raw["becomes"],
            within_s=float(raw.get("within_s") if raw.get("within_s") is not None else _missing_within_s(entry_where)),
            of=_parse_time_ref(raw.get("of"), where=entry_where),
        )
    elif shape == "never":
        predicate = Never(value=raw["never"])
    elif shape == "count":
        count_raw = raw["count"]
        if not isinstance(count_raw, Mapping) or "value" not in count_raw or "times" not in count_raw:
            raise AuthoringError(
                expected="count: {value: V, times: n}", found=repr(count_raw), where=entry_where, hint="",
            )
        predicate = Count(value=count_raw["value"], times=int(count_raw["times"]))
    elif shape == "between":
        between_raw = raw["between"]
        if not isinstance(between_raw, Sequence) or len(between_raw) != 2:
            raise AuthoringError(expected="between: [lo, hi]", found=repr(between_raw), where=entry_where, hint="")
        predicate = Between(lo=float(between_raw[0]), hi=float(between_raw[1]))
    elif shape == "monotonic":
        direction = raw["monotonic"]
        if direction not in ("increasing", "decreasing"):
            raise AuthoringError(
                expected="monotonic: increasing or decreasing", found=repr(direction), where=entry_where, hint="",
            )
        predicate = Monotonic(direction=direction)
    else:  # "equals"
        modifiers = [k for k in _EQUALS_MODIFIER_KEYS if k in raw]
        if len(modifiers) != 1:
            raise AuthoringError(
                expected=f"exactly one of {_EQUALS_MODIFIER_KEYS} alongside equals:",
                found=f"has: {modifiers}", where=entry_where, hint="",
            )
        modifier = modifiers[0]
        value = raw["equals"]
        if modifier == "always":
            predicate = EqualsAlways(value=value)
        elif modifier == "during":
            during_raw = raw["during"]
            if not isinstance(during_raw, Sequence) or len(during_raw) != 2:
                raise AuthoringError(expected="during: [start, end]", found=repr(during_raw), where=entry_where, hint="")
            predicate = EqualsDuring(
                value=value,
                start=_parse_bound(during_raw[0], where=entry_where),
                end=_parse_bound(during_raw[1], where=entry_where),
            )
        elif modifier == "whenever":
            predicate = EqualsWhenever(value=value, condition=_parse_condition(raw["whenever"], where=entry_where))
        elif modifier == "at_least_s":
            predicate = EqualsAtLeastS(value=value, duration_s=float(raw["at_least_s"]))
        else:
            predicate = EqualsAtMostS(value=value, duration_s=float(raw["at_most_s"]))

    return Expectation(id=exp_id, doc=doc, signal=str(signal), predicate=predicate)


def _missing_within_s(where: str) -> float:
    raise AuthoringError(
        expected="within_s: on a becomes: predicate",
        found="within_s: absent", where=where,
        hint="every timing predicate carries an explicit within_s -- there is no default tolerance (SS5.2)",
    )


# ---------------------------------------------------------------------------
# Evaluation -- one tick-indexed series per signal, over the one address
# space `core.signals` already resolves for the timeline/plots/HUD.
# ---------------------------------------------------------------------------


def _series(ticks: Sequence[Tick], address: str, *, project: str) -> tuple[tuple[float, object], ...]:
    """`address`'s value at every tick, as `(t_s, value)` pairs -- the same
    resolver `core.signals.resolve_series` uses, indexed by time instead of
    tick position (a predicate reasons in seconds, `within_s`'s own unit)."""
    needs_ctx = address in registered_signals()
    model = ProjectModel.resolve(project=project) if needs_ctx else None
    out: list[tuple[float, object]] = []
    for i, tick in enumerate(ticks):
        ctx = None
        if needs_ctx:
            ctx = LayerCtx(model=model, history=HistoryView(_ticks=tuple(ticks[: i + 1])), frames=FrameTree(tick.pose))
        out.append((tick.t_s, resolve_tick(tick, address, ctx=ctx)))
    return tuple(out)


def _first_transition_into(series: Sequence[tuple[float, object]], value: object) -> tuple[float, object] | None:
    """The first `(t_s, value)` pair whose value equals `value` and whose
    predecessor's did not (or which is the very first sample) -- "becomes"
    (SS5.1) and a `count:` rising edge share this one definition."""
    previous: object = None
    for i, (t_s, v) in enumerate(series):
        if v == value and (i == 0 or previous != value):
            return t_s, v
        previous = v
    return None


def _count_transitions_into(series: Sequence[tuple[float, object]], value: object) -> int:
    count = 0
    previous: object = None
    for i, (_t_s, v) in enumerate(series):
        if v == value and (i == 0 or previous != value):
            count += 1
        previous = v
    return count


@dataclass(frozen=True, slots=True)
class ExpectationResult:
    """One expectation's outcome (SS5.4): the actual value/time next to the
    expected ones, so a report row never needs a second run to explain a
    failure."""

    id: str
    doc: str
    signal: str
    passed: bool
    detail: str
    actual_value: object = None
    actual_time_s: float | None = None
    expected_time_s: float | None = None

    def __repr__(self) -> str:
        return f"<ExpectationResult id={self.id!r} passed={self.passed}>"


def _eval_equals_always(series: Sequence[tuple[float, object]], value: object) -> ExpectationResult:
    for t_s, v in series:
        if v != value:
            return False, t_s, v, f"was {v!r} at t={t_s:.3f}s, expected always {value!r}"
    return True, None, None, f"== {value!r} always"


def _eval_span(series: Sequence[tuple[float, object]], value: object, *, lo: float, hi: float, label: str) -> tuple:
    for t_s, v in series:
        if lo <= t_s <= hi and v != value:
            return False, t_s, v, f"was {v!r} at t={t_s:.3f}s (within {label} [{lo:.3f}, {hi:.3f}]), expected {value!r}"
    return True, None, None, f"== {value!r} over {label} [{lo:.3f}, {hi:.3f}]"


def evaluate_expectation(
    expectation: Expectation, ticks: Sequence[Tick], *, markers: Mapping[str, float], project: str = "base",
) -> ExpectationResult:
    """One expectation's pass/fail (SS5.4) -- the one evaluator the
    timeline, `sim check` and the report all call (never three copies)."""
    predicate = expectation.predicate
    series = _series(ticks, expectation.signal, project=project)

    passed: bool
    actual_time_s: float | None = None
    actual_value: object = None
    detail: str

    if isinstance(predicate, EqualsAlways):
        passed, actual_time_s, actual_value, detail = _eval_equals_always(series, predicate.value)

    elif isinstance(predicate, EqualsDuring):
        lo = _bound_seconds(predicate.start, markers=markers, where=f"expect '{expectation.id}' during[0]")
        hi = _bound_seconds(predicate.end, markers=markers, where=f"expect '{expectation.id}' during[1]")
        passed, actual_time_s, actual_value, detail = _eval_span(series, predicate.value, lo=lo, hi=hi, label="during")

    elif isinstance(predicate, EqualsWhenever):
        cond_series = _series(ticks, predicate.condition.signal, project=project)
        op = _COND_OPS[predicate.condition.op]
        passed = True
        for (t_s, v), (_t2, cond_raw) in zip(series, cond_series):
            cond_value = _coerce_like(predicate.condition.value, cond_raw)
            if op(cond_raw, cond_value) and v != predicate.value:
                passed, actual_time_s, actual_value = False, t_s, v
                break
        detail = (
            f"== {predicate.value!r} whenever {predicate.condition.signal} {predicate.condition.op} "
            f"{predicate.condition.value}"
            if passed else
            f"was {actual_value!r} at t={actual_time_s:.3f}s while "
            f"{predicate.condition.signal} {predicate.condition.op} {predicate.condition.value}, "
            f"expected {predicate.value!r}"
        )

    elif isinstance(predicate, (EqualsAtLeastS, EqualsAtMostS)):
        at_least = isinstance(predicate, EqualsAtLeastS)
        bound_s = predicate.duration_s
        spans: list[tuple[float, float]] = []
        span_start: float | None = None
        last_t = series[-1][0] if series else 0.0
        for t_s, v in series:
            if v == predicate.value and span_start is None:
                span_start = t_s
            elif v != predicate.value and span_start is not None:
                spans.append((span_start, t_s))
                span_start = None
        if span_start is not None:
            spans.append((span_start, last_t))
        passed = True
        for start, end in spans:
            duration = end - start
            if (at_least and duration < bound_s) or (not at_least and duration > bound_s):
                passed, actual_time_s, actual_value = False, start, duration
                break
        verb = "at_least_s" if at_least else "at_most_s"
        detail = (
            f"every {predicate.value!r} span {verb} {bound_s:.3f}s"
            if passed else
            f"a {predicate.value!r} span starting t={actual_time_s:.3f}s lasted {actual_value:.3f}s, "
            f"violating {verb} {bound_s:.3f}s"
        )

    elif isinstance(predicate, Becomes):
        found = _first_transition_into(series, predicate.value)
        expected_t = _bound_seconds(predicate.of, markers=markers, where=f"expect '{expectation.id}' of")
        if found is None:
            passed, detail = False, f"never became {predicate.value!r}"
        else:
            actual_time_s, actual_value = found
            passed = abs(actual_time_s - expected_t) <= predicate.within_s
            detail = (
                f"-> {predicate.value!r} @ {actual_time_s:.3f}s (target {expected_t:.3f} "
                f"+/-{predicate.within_s:.3f})"
            )
        return ExpectationResult(
            id=expectation.id, doc=expectation.doc, signal=expectation.signal, passed=passed, detail=detail,
            actual_value=actual_value, actual_time_s=actual_time_s, expected_time_s=expected_t,
        )

    elif isinstance(predicate, Never):
        found = next(((t_s, v) for t_s, v in series if v == predicate.value), None)
        if found is None:
            passed, detail = True, f"never == {predicate.value!r}"
        else:
            actual_time_s, actual_value = found
            passed, detail = False, f"took {predicate.value!r} at t={actual_time_s:.3f}s"

    elif isinstance(predicate, Count):
        actual_count = _count_transitions_into(series, predicate.value)
        passed = actual_count == predicate.times
        detail = f"{actual_count} transition(s) into {predicate.value!r}, expected {predicate.times}"
        actual_value = actual_count

    elif isinstance(predicate, Between):
        passed = True
        for t_s, v in series:
            if not (predicate.lo <= v <= predicate.hi):
                passed, actual_time_s, actual_value = False, t_s, v
                break
        detail = (
            f"stayed within [{predicate.lo}, {predicate.hi}]"
            if passed else
            f"was {actual_value!r} at t={actual_time_s:.3f}s, outside [{predicate.lo}, {predicate.hi}]"
        )

    elif isinstance(predicate, Monotonic):
        passed = True
        previous_v = None
        for t_s, v in series:
            if previous_v is not None:
                ok = v >= previous_v if predicate.direction == "increasing" else v <= previous_v
                if not ok:
                    passed, actual_time_s, actual_value = False, t_s, v
                    break
            previous_v = v
        detail = (
            f"monotonic {predicate.direction}"
            if passed else
            f"violated monotonic {predicate.direction} at t={actual_time_s:.3f}s (value {actual_value!r} "
            f"after {previous_v!r})"
        )

    else:  # pragma: no cover -- exhaustive over the closed Predicate union
        raise InternalError(
            expected="a recognised Predicate", found=type(predicate).__name__,
            where="adas_sim.check.expect.evaluate_expectation", hint="",
        )

    return ExpectationResult(
        id=expectation.id, doc=expectation.doc, signal=expectation.signal, passed=passed, detail=detail,
        actual_value=actual_value, actual_time_s=actual_time_s,
    )


# ---------------------------------------------------------------------------
# Marker resolution -- reuses this module's own transition logic (SS9.1)
# ---------------------------------------------------------------------------


def resolve_marker(marker: Marker, ticks: Sequence[Tick], *, project: str = "base") -> float:
    """One marker's resolved time, in seconds. `ConstantAnchor` is a
    pass-through; the two predicate forms reuse `_series` +
    `_first_transition_into`/a threshold crossing -- "an anchor is an
    existing predicate used as a time reference" (SS9.1), not a second
    mechanism."""
    anchor = marker.at
    if isinstance(anchor, ConstantAnchor):
        return anchor.seconds

    series = _series(ticks, anchor.signal, project=project)

    if isinstance(anchor, BecomesAnchor):
        found = _first_transition_into(series, anchor.value)
        if found is None:
            raise AuthoringError(
                expected=f"'{anchor.signal}' to become {anchor.value!r} at some tick",
                found="no such tick in this run", where=f"marker '{marker.id}'", hint="",
            )
        return found[0]

    # CrossesAnchor
    previous: float | None = None
    for t_s, raw_v in series:
        v = float(raw_v)
        if previous is not None:
            rising = previous < anchor.threshold <= v
            falling = previous > anchor.threshold >= v
            if (anchor.direction == "rising" and rising) or (anchor.direction == "falling" and falling):
                return t_s
        previous = v
    raise AuthoringError(
        expected=f"'{anchor.signal}' to cross {anchor.threshold} ({anchor.direction}) at some tick",
        found="no such tick in this run", where=f"marker '{marker.id}'", hint="",
    )


def resolve_markers(scenario: Scenario, ticks: Sequence[Tick]) -> dict[str, float]:
    """Every declared marker's resolved time, keyed by id -- what
    `evaluate_scenario` feeds `evaluate_expectation`'s `markers=`."""
    return {marker_id: resolve_marker(marker, ticks, project=scenario.sut.project) for marker_id, marker in scenario.markers.items()}


def evaluate_scenario(scenario: Scenario, ticks: Sequence[Tick]) -> tuple[ExpectationResult, ...]:
    """Every `expect:` entry's result, in declaration order -- markers
    resolved once, up front, and shared across every expectation that
    references one (SS5.4's "one evaluator, three consumers")."""
    markers = resolve_markers(scenario, ticks)
    expectations = [parse_expectation(raw, where=f"{scenario.id} expect") for raw in scenario.expect]
    return tuple(
        evaluate_expectation(expectation, ticks, markers=markers, project=scenario.sut.project)
        for expectation in expectations
    )
