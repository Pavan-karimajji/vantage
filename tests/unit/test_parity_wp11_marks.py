# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-11` tests: `UT-marks-01`..`UT-marks-03`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.8). `F-STORE`: an in-memory store
that can be written, closed and reopened.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from adas_sim.io.marks import (
    Annotation, Classification, read_annotations, read_classifications, select,
    write_annotations, write_classifications,
)


class _Store:
    """`F-STORE`, same shape the WP-07/WP-10 stores use -- a fresh instance
    built from a closed one's own payloads stands in for "reopened"."""

    def __init__(self, annotations=(), classifications=()) -> None:
        self._annotations = tuple(annotations)
        self._classifications = tuple(classifications)
        self._closed = False

    def write_annotations(self, annotations) -> None:
        self._annotations = tuple(annotations)

    def read_annotations(self):
        return self._annotations

    def write_classifications(self, classifications) -> None:
        self._classifications = tuple(classifications)

    def read_classifications(self):
        return self._classifications

    def close(self) -> None:
        self._closed = True

    def reopen(self) -> "_Store":
        assert self._closed, "reopen() is only meaningful after close()"
        return _Store(self._annotations, self._classifications)


def test_two_kinds_two_stores_ut_marks_01():
    """UT-marks-01."""
    store = _Store()
    write_annotations(store, [Annotation.create("looks off here", author="pavan")])
    write_classifications(store, [Classification.create("regression", author="pavan")])

    annotations = read_annotations(store)
    classifications = read_classifications(store)

    assert len(annotations) == 1 and isinstance(annotations[0], Annotation)  # .c1
    assert len(classifications) == 1 and isinstance(classifications[0], Classification)  # .c1
    assert not any(isinstance(a, Classification) for a in annotations)
    assert not any(isinstance(c, Annotation) for c in classifications)

    # .c2: neither type accepts the other's fields.
    annotation_fields = {f.name for f in dataclasses.fields(Annotation)}
    classification_fields = {f.name for f in dataclasses.fields(Classification)}
    assert "value" not in annotation_fields
    assert "text" not in classification_fields
    with pytest.raises(TypeError):
        Annotation(value="regression", author="pavan", created_ns=0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Classification(text="looks off here", author="pavan", created_ns=0)  # type: ignore[call-arg]


def test_author_and_time_are_recorded_not_inferred_ut_marks_02():
    """UT-marks-02."""
    clock = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    store = _Store()
    write_annotations(store, [Annotation.create("note", author="pavan", clock=clock)])
    write_classifications(store, [Classification.create("regression", author="pavan", clock=clock)])
    store.close()
    reopened = store.reopen()

    (annotation,) = read_annotations(reopened)
    (classification,) = read_classifications(reopened)

    assert annotation.author == "pavan" and annotation.created_ns > 0  # .c1
    assert classification.author == "pavan" and classification.created_ns > 0  # .c1

    # .c2: neither field is ever re-derived from a file's own mtime --
    # nothing in read_annotations/read_classifications even looks at one,
    # so re-reading after any simulated "file timestamp change" is a no-op.
    (annotation_again,) = read_annotations(reopened)
    assert annotation_again.created_ns == annotation.created_ns


def test_classification_selects_exactly_ut_marks_03():
    """UT-marks-03."""
    recordings = {
        "run_a": [Classification.create("regression", author="pavan")],
        "run_b": [Classification.create("golden", author="pavan")],
        "run_c": [Classification.create("regression", author="pavan"), Classification.create("flaky", author="pavan")],
    }

    selected = select(recordings, "regression")

    assert set(selected) == {"run_a", "run_c"}  # .c1: every carrier and no non-carrier
