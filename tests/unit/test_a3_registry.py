# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 `scene/registry.py` tests: UT-A3-6, UT-A3-7
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.scene.registry import layer_provider, registered_providers


def test_duplicate_layer_id_raises_naming_both_providers():
    """UT-A3-6."""

    @layer_provider("sim.test.registry.dup")
    def _first(ctx):
        return ()

    with pytest.raises(AuthoringError) as excinfo:
        @layer_provider("sim.test.registry.dup")
        def _second(ctx):
            return ()

    err = excinfo.value
    assert "_first" in err.expected
    assert "_second" in err.found


def test_registry_discovery_finds_a_provider_added_by_import_alone():
    """UT-A3-7: a component adds a layer by existing -- decorating a
    function at module import time is what registers it, with no separate
    registration call."""

    @layer_provider("sim.test.registry.discovered")
    def _provider(ctx):
        return ()

    assert "sim.test.registry.discovered" in registered_providers()
    assert registered_providers()["sim.test.registry.discovered"].func is _provider
