# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The closed error taxonomy (DG-5, sim_api_reference.md §9).

Four classes, each with a fixed exit code so a script can branch, plus
``ProvenanceWarning`` for the one case that must degrade rather than fail
(R-SIM-3a, R-SIM-6). Every ``SimError`` names what was expected, what was
found, and where it looked (N-8): a message that is only an identifier is a
``TypeError`` at author time, never a disappointment at run time.
"""

from __future__ import annotations

from typing import ClassVar


class SimError(Exception):
    """Base of the closed taxonomy. Never raised directly."""

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

    exit_code = 2


class EnvironmentError_(SimError):
    """A library, bundle or dependency is missing. `sim doctor` says which."""

    exit_code = 3


class ContractError(SimError):
    """An ABI/manifest/version mismatch. Fixed by the component's build."""

    exit_code = 4


class InternalError(SimError):
    """A framework bug. Anything uncaught is this, by definition (DG-5)."""

    exit_code = 70


class ProvenanceWarning(Warning):
    """A project mismatch or unknown-provenance recording (R-SIM-3a, R-SIM-6).

    A WARNING, never a `SimError`: the run degrades visibly and continues.
    Raising here would make the honest path the inconvenient one, which is
    how people start suppressing warnings.
    """
