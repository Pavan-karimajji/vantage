# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SensorModel` -- parses `<PREFIX>_SENSOR_<i>_<FIELD>` **by key shape**,
never by a hardcoded domain prefix (GT-1, sim_api_reference.md §6). Real
sensor poses/FOV/ranges are already runtime calibration owned by the
component that declares them (R-SIM-9); this module
only ever sees whatever `Mapping` the caller hands it -- it never reads a
file or knows a component's name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from adas_sim.core.errors import AuthoringError

# Case-sensitive by construction (P-3): a differently-cased key is a
# different key and must not resolve.
_SENSOR_FIELD_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9]*)_SENSOR_(\d+)_([A-Za-z0-9_]+)$")
_SENSOR_COUNT_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9]*)_SENSOR_COUNT$")


@dataclass(frozen=True, slots=True)
class SensorModel:
    """One sensor's calibration, keyed by whatever fields its own domain
    declared (pose/FOV/range/side are the common shape; nothing here assumes
    a fixed field set beyond that)."""

    sensor_id: str
    fields: Mapping[str, object] = field(default_factory=dict)

    def get(self, name: str, default: object = None) -> object:
        return self.fields.get(name, default)

    def __repr__(self) -> str:
        return f"<SensorModel {self.sensor_id!r} fields={sorted(self.fields)}>"


def parse_sensors(data: Mapping[str, object]) -> tuple[SensorModel, ...]:
    """Discover every `<PREFIX>_SENSOR_<i>_<FIELD>` key in `data`, grouped by
    index, sorted by index. If a `<PREFIX>_SENSOR_COUNT` key is present, the
    discovered count must match it -- a silent short count is exactly the
    kind of "50 objects at the origin" defect R-SIM-3 exists to prevent.
    """
    by_index: dict[str, dict[str, object]] = {}
    for key, value in data.items():
        match = _SENSOR_FIELD_KEY.match(key)
        if match is None:
            continue
        _prefix, index, field_name = match.groups()
        # field_name keeps the source key's exact case (P-3): folding it here
        # would let "SIDE" and "Side" silently collide into one field.
        by_index.setdefault(index, {})[field_name] = value

    declared_count = None
    declared_key = None
    for key, value in data.items():
        if _SENSOR_COUNT_KEY.match(key):
            declared_count = int(value)
            declared_key = key
            break

    if declared_count is not None and declared_count != len(by_index):
        raise AuthoringError(
            expected=f"{declared_count} sensors ({declared_key})",
            found=f"{len(by_index)} sensor indices with fields: {sorted(by_index)}",
            where="the calibration mapping passed to parse_sensors",
            hint="every declared sensor index must carry at least one field",
        )

    return tuple(
        SensorModel(sensor_id=index, fields=dict(fields))
        for index, fields in sorted(by_index.items(), key=lambda kv: int(kv[0]))
    )
