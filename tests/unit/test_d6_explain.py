# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `UT-D6-7` (`docs/sim_implementation_plan.md`): `sim explain` resolves
each of the six accepted name kinds -- run id, topic, layer, style token,
codec name, error code -- and suggests a fuzzy match on an unknown name
rather than failing bare (`DG-2`, `N-8`). `core.explain.explain` covers five
of the six directly; the style-token branch is `cli/explain.py`'s own (see
that module's docstring for why), so `test_style_token_*` below drives it
through `cli.explain._explain_with_style_tokens` instead.
"""

from __future__ import annotations

from adas_sim.cli.explain import _explain_with_style_tokens
from adas_sim.diagnostics.explain import explain
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.scene.registry import layer_provider

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


@layer_provider("test.d6.explain.probe")
def _probe_layer(ctx):  # pragma: no cover -- never actually called, only registered
    return []


def _session() -> Session:
    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={"sim.test.port": PortValue(name="sim.test.port", message=b"\x01", origin="measured")},
        pose=_POSE,
    )
    return Session(run_id="run-123", name="s", ticks=(tick,))


def test_explain_resolves_the_run_id():
    facts = explain("run-123", _session())
    assert facts["kind"] == "run_id"


def test_explain_resolves_a_topic():
    facts = explain("sim.test.port", _session())
    assert facts["kind"] == "topic"
    assert facts["origin"] == "measured"


def test_explain_resolves_a_registered_layer():
    facts = explain("test.d6.explain.probe", _session())
    assert facts["kind"] == "layer"
    assert facts["qualname"] == "_probe_layer"


def test_explain_resolves_a_codec_name_with_or_without_the_dot():
    with_dot = explain(".mcap", _session())
    without_dot = explain("mcap", _session())
    assert with_dot["kind"] == "codec"
    assert without_dot["kind"] == "codec"
    assert with_dot["extension"] == without_dot["extension"] == ".mcap"
    assert with_dot["has_reader"] is True
    assert with_dot["capabilities"] is not None


def test_explain_resolves_a_write_only_codec_naming_it_honestly():
    facts = explain("csv", _session())
    assert facts["kind"] == "codec"
    assert facts["has_reader"] is False
    assert facts["has_writer"] is True


def test_explain_resolves_an_error_code_by_taxonomy_name_class_name_or_exit_code():
    by_taxonomy = explain("contract", _session())
    by_class = explain("ContractError", _session())
    by_exit_code = explain("4", _session())
    for facts in (by_taxonomy, by_class, by_exit_code):
        assert facts["kind"] == "error_code"
        assert facts["taxonomy"] == "contract"
        assert facts["exit_code"] == 4


def test_explain_resolves_environment_error_without_the_builtin_shadowing_underscore():
    facts = explain("EnvironmentError", _session())
    assert facts["kind"] == "error_code"
    assert facts["taxonomy"] == "environment"
    assert facts["exit_code"] == 3


def test_explain_reports_unknown_with_a_fuzzy_suggestion_rather_than_failing_bare():
    facts = explain("sim.test.pory", _session())  # one char off "sim.test.port"
    assert facts["kind"] == "unknown"
    assert "sim.test.port" in facts["did_you_mean"]


def test_explain_reports_unknown_with_no_suggestion_when_nothing_is_close():
    facts = explain("completely-unrelated-garbage-xyz", _session())
    assert facts["kind"] == "unknown"
    assert facts["did_you_mean"] == []


# ---------------------------------------------------------------------------
# style token -- cli/explain.py's own branch, not core.explain.explain's
# ---------------------------------------------------------------------------


def test_style_token_resolves_with_a_colour_per_theme():
    facts = _explain_with_style_tokens("status.warning", _session())
    assert facts["kind"] == "style_token"
    assert set(facts["colors"]) == {"dark", "light", "print", "forced"}
    for color in facts["colors"].values():
        assert color.startswith("#")


def test_style_token_extends_the_fuzzy_suggestion_on_an_unknown_name():
    facts = _explain_with_style_tokens("status.warnin", _session())  # one char short
    assert facts["kind"] == "unknown"
    assert "status.warning" in facts["did_you_mean"]


def test_style_token_check_does_not_shadow_a_real_topic_or_layer():
    """A style token and a topic/layer/codec/error name occupy disjoint
    namespaces in practice, but the check order (token first) must never
    hide a real resolution -- proven directly rather than assumed."""
    facts = _explain_with_style_tokens("sim.test.port", _session())
    assert facts["kind"] == "topic"
