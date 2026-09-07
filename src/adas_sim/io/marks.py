# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-11`, `marks` item (`SW-0036`..`SW-0038`): two closed kinds of
recording mark -- a free-text `Annotation` and a categorical
`Classification` -- each in its own store, each carrying who made it and
when (`SYS-0040`), never inferred from the file that happens to hold it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


def _stamp(*, author: str, clock: datetime | None = None) -> tuple[str, int]:
    """`WP-11` (`SW-0037`): author and creation time, fixed once here, at
    construction -- never re-derived later from a file's own mtime (a
    reopened recording's timestamp changing must never move either field)."""
    when = clock if clock is not None else datetime.now(timezone.utc)
    return author, int(when.timestamp() * 1_000_000_000)


@dataclass(frozen=True, slots=True)
class Annotation:
    """`WP-11` (`SW-0036`): a free-text note. Carries no `value:` field --
    that is `Classification`'s own, and the two are never interchangeable."""

    text: str
    author: str
    created_ns: int

    @classmethod
    def create(cls, text: str, *, author: str, clock: datetime | None = None) -> Annotation:
        stamped_author, created_ns = _stamp(author=author, clock=clock)
        return cls(text=text, author=stamped_author, created_ns=created_ns)


@dataclass(frozen=True, slots=True)
class Classification:
    """`WP-11` (`SW-0036`): a categorical tag. Carries no `text:` field --
    that is `Annotation`'s own."""

    value: str
    author: str
    created_ns: int

    @classmethod
    def create(cls, value: str, *, author: str, clock: datetime | None = None) -> Classification:
        stamped_author, created_ns = _stamp(author=author, clock=clock)
        return cls(value=value, author=stamped_author, created_ns=created_ns)


class MarkStore(Protocol):
    """`WP-11`'s own `F-STORE` contract: annotations and classifications
    travel in SEPARATE meta blocks (`SW-0036`'s "distinct stores"), so a
    caller reading one kind never has to filter out the other's entries."""

    def write_annotations(self, annotations: Sequence[Mapping[str, object]]) -> None: ...

    def read_annotations(self) -> Sequence[Mapping[str, object]]: ...

    def write_classifications(self, classifications: Sequence[Mapping[str, object]]) -> None: ...

    def read_classifications(self) -> Sequence[Mapping[str, object]]: ...


def write_annotations(store: MarkStore, annotations: Sequence[Annotation]) -> None:
    store.write_annotations([
        {"text": a.text, "author": a.author, "created_ns": a.created_ns} for a in annotations
    ])


def read_annotations(store: MarkStore) -> tuple[Annotation, ...]:
    return tuple(
        Annotation(text=str(d["text"]), author=str(d["author"]), created_ns=int(d["created_ns"]))
        for d in store.read_annotations()
    )


def write_classifications(store: MarkStore, classifications: Sequence[Classification]) -> None:
    store.write_classifications([
        {"value": c.value, "author": c.author, "created_ns": c.created_ns} for c in classifications
    ])


def read_classifications(store: MarkStore) -> tuple[Classification, ...]:
    return tuple(
        Classification(value=str(d["value"]), author=str(d["author"]), created_ns=int(d["created_ns"]))
        for d in store.read_classifications()
    )


def select(recordings: Mapping[str, Sequence[Classification]], value: str) -> tuple[str, ...]:
    """`WP-11` (`SW-0038`): every recording name carrying `value` among its
    stored classifications -- exact match on the stored value only, no
    fuzzy or prefix matching to explain later (`IMP-0039`)."""
    return tuple(
        name for name, classifications in recordings.items()
        if any(c.value == value for c in classifications)
    )
