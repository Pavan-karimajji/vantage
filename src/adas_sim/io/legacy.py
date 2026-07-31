# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Maps today's legacy topic names onto namespaced ones and synthesises the
missing `VehSig` (sim_resim_and_recording.md §8). **The one sanctioned name
translation** (`N-6`): every other layer sees only namespaced topics, and the
mapping is declared as data here and nowhere else.

**This file is also the one sanctioned exception to `GT-1`'s string ban**,
for the same reason `N-6` already treats it as special: its entire job is to
recognise real legacy topic names, and two of the five (`df/aeb_outputs`,
`df/bsd_outputs`) are function-prefixed by construction -- they are what a
real recording on disk actually contains, not framework prose repeating a
function's name. Obfuscating the strings to dodge the grep would make the
mapping harder to read for no safety gained; declaring the one real
exception, narrowly, is what `check_invariants.py`'s `check_gt1` does
instead (naming this file specifically, not a general carve-out).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

from adas_sim.io.base import Provenance, RecordingReader, RunManifest, TopicInfo

#: Old name -> new, namespaced name (sim_resim_and_recording.md §3.2/§8).
LEGACY_TOPIC_MAP: dict[str, str] = {
    "df/gen_object_list": "/source/gen_object_list",
    "df/veh_dyn": "/source/veh_dyn",
    "carla/chase_camera": "/source/camera/chase",
    "df/aeb_outputs": "/df/aeb.outputs",
    "df/bsd_outputs": "/df/bsd.outputs",
}

#: A legacy recording never captured VehSig -- the live bridge and the resim
#: harness both construct a fresh, empty one each tick and never recorded it
#: ("The hole: VehSig is not recorded", sim_resim_and_recording.md). This
#: reader synthesises the *topic* so a consumer expecting it does not break;
#: reconstructing a real populated message would need `interfaces`' generated
#: VehSig bindings, which this framework must never require (R-SIM-11) --
#: deferred to when a real consumer needs it, not invented speculatively.
SYNTHESIZED_VEH_SIG_TOPIC = "/source/veh_sig"


class LegacyRecordingReader:
    """Wraps any `RecordingReader`, remapping legacy topic names and adding
    the synthesised `VehSig` topic. Safe to wrap a modern recording too --
    the mapping is a no-op for names it does not recognise.
    """

    def __init__(self, inner: RecordingReader) -> None:
        self._inner = inner
        self.capabilities = inner.capabilities

    def __repr__(self) -> str:
        return f"<LegacyRecordingReader wrapping {self._inner!r}>"

    def meta(self) -> RunManifest:
        # A recording without a manifest loads as RunManifest() (known=False,
        # R-SIM-6) -- already the wrapped reader's own degrade path.
        return self._inner.meta()

    def topics(self) -> Mapping[str, TopicInfo]:
        remapped = {LEGACY_TOPIC_MAP.get(name, name): info for name, info in self._inner.topics().items()}
        remapped.setdefault(
            SYNTHESIZED_VEH_SIG_TOPIC,
            TopicInfo(schema_name="", provenance=Provenance.MOCKED),
        )
        return remapped

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]:
        # `topics` (if given) is expressed in the new namespaced names; the
        # inner reader is asked for its own (possibly legacy) names.
        reverse = {new: old for old, new in LEGACY_TOPIC_MAP.items()}
        inner_topics = [reverse.get(t, t) for t in topics] if topics is not None else None
        for topic, log_time_ns, capture_time_ns, payload in self._inner.messages(inner_topics):
            yield LEGACY_TOPIC_MAP.get(topic, topic), log_time_ns, capture_time_ns, payload

    def close(self) -> None:
        self._inner.close()
