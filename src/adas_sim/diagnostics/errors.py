# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The closed error taxonomy (SI-07, DG-5, sim_api_reference.md §9).

Four classes, each with a fixed ``kind`` and exit code so a script can
branch, plus ``ProvenanceWarning`` for the one case that must degrade
rather than fail (R-SIM-3a, R-SIM-6). Every ``SimError`` names what was
expected, what was found, and where it looked (N-8): a message that is
only an identifier is a ``TypeError`` at author time, never a
disappointment at run time.

The C++ half of this taxonomy is ``include/simcore/errors.hpp`` -- the one
permitted cross-language duplication (``SW-0121``), both hand-transcribed
from ``docs/v2/errors.yaml`` and kept in parity by
``scripts/check_error_parity.py`` (``SW-0122``). ``exit_code`` here is each
kind's *default* ``ExitCode`` (``errors.hpp``'s ``DefaultExitCode``) --
``Coherence``/``Input``/``Timeout`` have no ``SimError`` subclass because
they're situational codes a specific call site passes directly (`WP-19`
input refusal, `WP-20` coherence, a future timeout path), never derived
from a raised exception's kind. Renumbered from `docs/v1`'s four-value set
(2/3/4/70) on `WP-03`, 2026-08-13: ``EnvironmentError_`` moved 3->6,
``InternalError`` moved 70->8, freeing 3/5/7 for the situational codes.
"""

from __future__ import annotations

from typing import ClassVar, Mapping


class SimError(Exception):
    """Base of the closed taxonomy. Never raised directly."""

    kind: ClassVar[str]
    exit_code: ClassVar[int]

    def __init__(self, *, expected: str, found: str, where: str, hint: str = "") -> None:
        self.expected = expected
        self.found = found
        self.where = where
        self.hint = hint
        super().__init__(str(self))

    def __str__(self) -> str:
        msg = f"expected {self.expected}; found {self.found}; where {self.where}"
        if self.hint:
            msg += f" -> {self.hint}"
        return msg

    def __repr__(self) -> str:
        return f"<{type(self).__name__} where={self.where!r}>"


class AuthoringError(SimError):
    """The YAML/pipeline/scenario is wrong. Fixed by the person who wrote it."""

    kind = "authoring"
    exit_code = 2


class EnvironmentError_(SimError):
    """A library, bundle or dependency is missing. `sim doctor` says which."""

    kind = "environment"
    exit_code = 6


class ContractError(SimError):
    """An ABI/manifest/version mismatch. Fixed by the component's build."""

    kind = "contract"
    exit_code = 4


class InternalError(SimError):
    """A framework bug. Anything uncaught is this, by definition (DG-5)."""

    kind = "internal"
    exit_code = 8


#: Every ExitCode value (docs/v2/errors.yaml), not only the four Kind
#: defaults above -- Coherence/Input/Timeout are here for a situational
#: caller to look up by name, same source check_error_parity.py compares
#: against errors.hpp's ExitCode enum.
EXIT_CODES: Mapping[str, int] = {
    "ok": 0,
    "config": 2,
    "coherence": 3,
    "module": 4,
    "input": 5,
    "infra": 6,
    "timeout": 7,
    "crash": 8,
}


class ProvenanceWarning(Warning):
    """A project mismatch or unknown-provenance recording (R-SIM-3a, R-SIM-6).

    A WARNING, never a `SimError`: the run degrades visibly and continues.
    Raising here would make the honest path the inconvenient one, which is
    how people start suppressing warnings.
    """
