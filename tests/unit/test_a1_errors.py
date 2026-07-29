# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 error-taxonomy tests: UT-A1-4, UT-A1-5 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.core.errors import (
    AuthoringError,
    ContractError,
    EnvironmentError_,
    InternalError,
    ProvenanceWarning,
    SimError,
)

EXIT_CODES = {
    AuthoringError: 2,
    EnvironmentError_: 3,
    ContractError: 4,
    InternalError: 70,
}


def test_each_error_class_carries_expected_found_where_and_its_exit_code():
    """UT-A1-4."""
    for cls, code in EXIT_CODES.items():
        err = cls(expected="a manifest field", found="nothing", where="the pipeline file", hint="add it")
        assert err.expected == "a manifest field"
        assert err.found == "nothing"
        assert err.where == "the pipeline file"
        assert err.hint == "add it"
        assert cls.exit_code == code
        assert isinstance(err, SimError)


def test_error_classes_are_distinguishable_by_type():
    """UT-A1-4."""
    err = AuthoringError(expected="a", found="b", where="c")
    assert not isinstance(err, ContractError)
    assert not isinstance(err, EnvironmentError_)
    assert not isinstance(err, InternalError)


def test_constructing_a_sim_error_without_keyword_arguments_raises_type_error():
    """UT-A1-4: a message that is only an identifier is a TypeError at author
    time, not a disappointment at run time (N-8)."""
    with pytest.raises(TypeError):
        AuthoringError("just a message")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        AuthoringError(expected="a")  # found/where missing


def test_provenance_warning_is_a_warning_and_not_a_sim_error():
    """UT-A1-4."""
    assert issubclass(ProvenanceWarning, Warning)
    assert not issubclass(ProvenanceWarning, SimError)
    with pytest.raises(ProvenanceWarning):
        raise ProvenanceWarning("project mismatch")


def test_every_error_reprs_its_own_name_with_no_memory_address():
    """UT-A1-5: the cheapest debugging feature in the system."""
    for cls in EXIT_CODES:
        err = cls(expected="a", found="b", where="c")
        text = repr(err)
        assert "0x" not in text
        assert cls.__name__ in text


def test_provenance_warning_repr_has_no_memory_address():
    """UT-A1-5."""
    assert "0x" not in repr(ProvenanceWarning("mismatch"))
