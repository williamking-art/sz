# -*- coding: utf-8 -*-
"""M1b-3：旧调用自动解析承办主体 + 严格/非严格迁移边界。"""
import copy

from core import commands
from core.domains.administration.circuit_officials import (
    appoint_circuit_official,
    dismiss_circuit_official,
)
from core.domains.administration.prefect_officials import (
    appoint_prefect_official,
    dismiss_prefect_official,
)

SEAT = "京畿路|开封府"


def _state():
    return commands.new_game()


def _official(name="测试官"):
    return {"name": name, "faction": "中立派"}


def _circuit_appoint(s, executor=None):
    return appoint_circuit_official(
        s, "京畿路", "cao", _official(), executor=executor
    )


def _counters(s):
    stats = s.statistics
    return (
        int(stats.get("authority_auto_resolved_personnel", 0) or 0),
        int(stats.get("legacy_unchecked_personnel", 0) or 0),
    )


def test_legacy_circuit_appoint_auto_resolves_libu():
    s = _state()
    before_auto, before_legacy = _counters(s)
    assert _circuit_appoint(s) is True
    after_auto, after_legacy = _counters(s)
    assert after_auto == before_auto + 1
    assert after_legacy == before_legacy


def test_strict_mode_rejects_when_no_executor_can_be_resolved():
    s = _state()
    s.central_orgs["吏部"]["abolished"] = True
    s.authority_strict = True
    before = copy.deepcopy(s.circuit_officials)
    assert _circuit_appoint(s) is False
    assert s.circuit_officials == before


def test_non_strict_mode_keeps_legacy_and_counts_unchecked():
    s = _state()
    s.central_orgs["吏部"]["abolished"] = True
    s.authority_strict = False
    before_auto, before_legacy = _counters(s)
    assert _circuit_appoint(s) is True
    after_auto, after_legacy = _counters(s)
    assert after_auto == before_auto
    assert after_legacy == before_legacy + 1


def test_strict_mode_rejects_prefect_appoint_without_executor():
    s = _state()
    s.central_orgs["吏部"]["abolished"] = True
    s.authority_strict = True
    before = copy.deepcopy(s.prefect_officials)
    out = appoint_prefect_official(s, SEAT, "prefect", _official("知府甲"))
    assert out["ok"] is False
    assert s.prefect_officials == before


def test_non_strict_mode_prefect_appoint_legacy():
    s = _state()
    s.central_orgs["吏部"]["abolished"] = True
    s.authority_strict = False
    before_auto, before_legacy = _counters(s)
    out = appoint_prefect_official(s, SEAT, "prefect", _official("知府乙"))
    assert out["ok"] is True
    after_auto, after_legacy = _counters(s)
    assert after_auto == before_auto
    assert after_legacy == before_legacy + 1


def test_explicit_executor_does_not_touch_counters():
    s = _state()
    before_auto, before_legacy = _counters(s)
    assert _circuit_appoint(s, {"org": "吏部"}) is True
    after_auto, after_legacy = _counters(s)
    assert after_auto == before_auto
    assert after_legacy == before_legacy


def test_explicit_wrong_executor_still_rejected():
    s = _state()
    assert _circuit_appoint(s, {"org": "户部"}) is False


def test_legacy_dismiss_circuit_auto_resolves():
    s = _state()
    _circuit_appoint(s)  # auto
    before_auto, _ = _counters(s)
    old = dismiss_circuit_official(s, "京畿路", "cao")
    assert isinstance(old, dict) and old.get("name") == "测试官"
    after_auto, _ = _counters(s)
    assert after_auto == before_auto + 1


def test_legacy_dismiss_prefect_auto_resolves():
    s = _state()
    appoint_prefect_official(s, SEAT, "prefect", _official("知府丙"))
    before_auto, _ = _counters(s)
    out = dismiss_prefect_official(s, SEAT, "prefect")
    assert out["ok"] is True
    after_auto, _ = _counters(s)
    assert after_auto == before_auto + 1


def test_legacy_circuit_appoint_result_unchanged():
    s = _state()
    assert _circuit_appoint(s) is True
    assert s.circuit_officials["京畿路"]["officials"]["cao"]["name"] == "测试官"

