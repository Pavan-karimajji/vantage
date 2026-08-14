# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Two authoring-time policy checks (`SI-10`):

`check_interpolatable` (`SW-0069`) -- the sampling policy `SW-0068`'s
`Sampling` enum (`simcore`, `latest_at_or_before`/`nearest`/`strict`/
`interpolate`/`all_since_last`) declares per port. `interpolate` is
permitted only on a declared continuous scalar (`TYPE_FLOAT`/`TYPE_DOUBLE`,
never repeated) -- an enumeration, identifier, count or repeated field
interpolated linearly between neighbours produces a value that never
existed (an object id between two ids, a state enum between two states),
which is `SYS-0035` violated inside the framework rather than by a plug-in.
Refused HERE, at config load, because refusing it in the engine would turn
an authoring mistake into a run-time failure.

`read_period_us` (`SW-0163`) reads `<COMPONENT>_<FN>_PERIOD_US` from a
resolved calibration mapping as a plain integer -- microseconds in,
microseconds out, no float anywhere (`R-SIM-18`). `emit_run_spec` (`WP-05`,
`IMP-0001`) is what multiplies this by 1000 into `period_ns`; this module
only owns the READ side.
"""

from __future__ import annotations

from collections.abc import Mapping

from google.protobuf import descriptor_pb2

from adas_sim.diagnostics.errors import AuthoringError

_FT = descriptor_pb2.FieldDescriptorProto

#: The only two protobuf scalar types linear interpolation is meaningful
#: for (`SW-0069`'s Accept clause: "a declared continuous scalar type").
_CONTINUOUS_TYPES = frozenset({_FT.TYPE_FLOAT, _FT.TYPE_DOUBLE})

_TYPE_NAMES = {
    value: name[len("TYPE_"):]
    for name, value in vars(_FT).items()
    if name.startswith("TYPE_") and isinstance(value, int)
}


def check_interpolatable(field_type: int, *, repeated: bool, port_name: str) -> None:
    """`field_type` is a `FieldDescriptorProto.TYPE_*` constant (the same
    system `resolve/component.py`/`scene/codec.py` already build manifests
    with). A repeated field is refused regardless of its scalar type --
    "interpolate" names one value, not a sequence."""
    if not repeated and field_type in _CONTINUOUS_TYPES:
        return
    found = f"repeated {_TYPE_NAMES.get(field_type, field_type)}" if repeated else _TYPE_NAMES.get(field_type, str(field_type))
    raise AuthoringError(
        expected="a continuous scalar type (float or double), not repeated",
        found=found, where=f"port '{port_name}' sampling: interpolate",
        hint="interpolate is refused on an enumeration, identifier, count or repeated field -- "
             "it would produce a value that never existed; use a different sampling policy "
             "(latest_at_or_before/nearest/strict/all_since_last)",
    )


def read_period_us(calibration: Mapping[str, object], *, component: str, function: str) -> int:
    """`<COMPONENT>_<FN>_PERIOD_US` (`R-NAME-3`), read as a plain integer --
    a float value (a YAML `10.0` instead of `10`) is refused rather than
    silently truncated, since a rounded period is exactly the drift
    `R-SIM-18` exists to prevent."""
    key = f"{component.upper()}_{function.upper()}_PERIOD_US"
    if key not in calibration:
        raise AuthoringError(
            expected=f"'{key}' declared in calibration", found="absent",
            where=f"{component}/{function} calibration", hint=f"add {key}: <integer microseconds>",
        )
    value = calibration[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuthoringError(
            expected="an integer number of microseconds", found=repr(value),
            where=f"calibration key '{key}'",
            hint="no float anywhere in the period path (R-SIM-18) -- write a bare integer, e.g. 10000",
        )
    return value


def microseconds_to_nanoseconds(period_us: int) -> int:
    """Integer microseconds in, integer nanoseconds out -- the one
    multiplication `emit_run_spec` (`WP-05`) performs, exposed here so a
    caller never has to write the `* 1000` itself."""
    return period_us * 1000
