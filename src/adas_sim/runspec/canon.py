# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Canonical serialisation of the Resolved Run Spec (`SW-0004`, `SW-0012`,
design §3.4) -- a stable, hashable, humanly-diffable text form.

**Rules, in force:** UTF-8, `\\n` endings, two-space indent (`json.dumps`'s
own default line-per-scalar shape already gives one JSON value per line);
object keys sorted lexicographically **except the top level**, which is
fixed in the spec's own declared order (`_TOP_LEVEL_ORDER`, design §3.1);
arrays keep semantic order and are never sorted (`order`, `stages`, `ports`
-- reordering `order` *is* a semantic change); floats are forbidden
everywhere except `factor`/`offset`/`operands` (`SW-0046`) -- everything
else that varies over time is an integer nanosecond count. The hash is
computed over the serialisation with `spec_sha256` blanked first, because a
hash cannot cover itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from adas_sim.diagnostics.errors import InternalError
from adas_sim.runspec.sources import SourceSet

#: design §3.1's own field order -- fixed so the file's head is readable at
#: a glance, unlike a lexicographically-sorted top level which would bury
#: `schema`/`run_id` alphabetically among `coherence`/`diagnostics`.
_TOP_LEVEL_ORDER = (
    "schema", "run_id", "spec_sha256", "sources", "stages", "mutations", "outputs",
    "readiness_limit_steps", "fallback_max_gap", "checkpoint", "limits", "coherence_verdict",
)

#: `SW-0046`: the only three keys whose value may be a float. Every other
#: numeric quantity in the spec is an integer (nanoseconds, counts, indices).
_FLOAT_ALLOWED_KEYS = frozenset({"factor", "offset", "operands"})


@dataclass(frozen=True, slots=True)
class RunSpec:
    """A thin wrapper over the spec's own nested-dict shape (design §3.1) --
    `canonical`/`emit_run_spec` operate on `data` directly rather than a
    typed dataclass tree, since the canonical-serialisation rules are
    themselves generic over an arbitrary JSON tree and the spec's real
    complexity lives in its *shape*, not in per-field Python types."""

    data: Mapping[str, object]


def _canon_value(value: object, *, key: str | None) -> object:
    if isinstance(value, Mapping):
        return {k: _canon_value(value[k], key=k) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canon_value(v, key=key) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if key not in _FLOAT_ALLOWED_KEYS:
            raise InternalError(
                expected=f"an integer under key {key!r} (SW-0046 -- floats forbidden outside "
                         f"{sorted(_FLOAT_ALLOWED_KEYS)})",
                found=repr(value), where="adas_sim.runspec.canon.canonical",
                hint="this is an emitter bug, not an authoring mistake -- emit_run_spec produced "
                     "a float where the spec's own rules forbid one",
            )
        return value
    raise InternalError(
        expected="a JSON-representable value (mapping/sequence/str/int/float/bool/None)",
        found=f"{type(value).__name__}: {value!r}", where="adas_sim.runspec.canon.canonical",
        hint="emit_run_spec must build the spec from JSON-safe types only",
    )


def canonical_sources(source_set: SourceSet) -> dict[str, object]:
    """`WP-04` (`SW-0011`, `IMP-0012`): a `SourceSet`'s named recordings and
    per-port assignments, as a JSON-safe block ready to ride `canonical()`'s
    existing path unchanged (`IMP-0013`). Both lists are sorted by their own
    key -- `canonical()` sorts mapping keys but keeps array order exactly as
    given (design §3.1), so without this sort the order `sources`/
    `assignments` happened to be built in would leak straight into the
    emitted bytes, defeating `SW-0011`'s "assembly order does not matter"."""
    return {
        "named": [
            {"name": name, "recording": str(source.recording), "default": source.default}
            for name, source in sorted(source_set.sources.items())
        ],
        "assignments": [
            {"port": port, "source": name}
            for port, name in sorted(source_set.assignments.items())
        ],
    }


def canonical(spec: RunSpec) -> str:
    """The canonical text form -- top-level keys in `_TOP_LEVEL_ORDER`
    (unknown extras appended, sorted, so nothing is silently dropped),
    every other object's keys sorted, every array kept in its own order."""
    data = spec.data
    ordered_keys = [k for k in _TOP_LEVEL_ORDER if k in data]
    ordered_keys += sorted(set(data) - set(_TOP_LEVEL_ORDER))
    top = {k: _canon_value(data[k], key=k) for k in ordered_keys}
    text = json.dumps(top, indent=2, ensure_ascii=False)
    return text.replace("\r\n", "\n") + "\n"


def compute_spec_sha256(spec: RunSpec) -> str:
    """SHA-256 over `canonical()` with `spec_sha256` blanked first -- a hash
    cannot cover itself (design §3.4's own closing rule)."""
    blanked = RunSpec(data={**spec.data, "spec_sha256": ""})
    return hashlib.sha256(canonical(blanked).encode("utf-8")).hexdigest()


def write_run_spec(spec: RunSpec, path: Path) -> str:
    """Computes `spec_sha256`, writes the final canonical form to `path`
    (UTF-8, `\\n` endings, matching `canonical`'s own contract), and
    returns the hash -- the one value the run manifest/`simcore` both need
    to agree the same spec was read."""
    sha256 = compute_spec_sha256(spec)
    final = RunSpec(data={**spec.data, "spec_sha256": sha256})
    text = canonical(final)
    path.write_text(text, encoding="utf-8", newline="\n")
    return sha256


def diff_line_count(a: RunSpec, b: RunSpec) -> int:
    """The number of lines that differ between two specs' canonical forms
    -- `UT-SPC-08`'s own instrument: a one-mode change (`IMP-0012`'s point)
    must produce a small, bounded diff, not a reformatted file."""
    lines_a = canonical(a).splitlines()
    lines_b = canonical(b).splitlines()
    return _line_diff_count(lines_a, lines_b)


def _line_diff_count(a: Sequence[str], b: Sequence[str]) -> int:
    import difflib
    diff = difflib.ndiff(a, b)
    return sum(1 for line in diff if line.startswith(("+ ", "- ")))
