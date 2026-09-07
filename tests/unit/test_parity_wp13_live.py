# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-13` tests: `UT-livectl-01`, `UT-livectl-02`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.13). `F-LIVE`: a session already
running, reachable from a script. `F-SRC`: the `modules/sim` source tree
as checked in.
"""

from __future__ import annotations

import pytest

from adas_sim.pyapi.api import Api
from adas_sim.pyapi.live import LiveClient, LiveSession, _operation_table


def test_reachable_without_a_display_ut_livectl_01():
    """UT-livectl-01."""
    session = LiveSession(Api())
    try:
        client = LiveClient(session.address)

        # `verbs()` is one of Api's own zero-argument operations -- reached
        # here purely through the socket, with nothing GUI-shaped involved
        # anywhere in LiveSession/LiveClient (no display to require).
        result = client.call("verbs")
        assert isinstance(result, tuple)  # .c1: the operation completes

        with pytest.raises(LookupError):
            client.call("not_a_real_operation")
    finally:
        session.close()


def test_every_operation_delegates_ut_livectl_02():
    """UT-livectl-02."""
    api = Api()
    table = _operation_table(api)
    assert len(table) > 1  # a real, discovered set -- not one hand-picked name

    exported = {name for name in dir(Api) if not name.startswith("_")}
    for name, target in table.items():
        assert name in exported  # .c1: every target is in the headless interface's exported set
        # .c2: the target IS api's own bound method -- no wrapper body of
        # its own beyond what LiveSession's transport handling does.
        assert target == getattr(api, name)
