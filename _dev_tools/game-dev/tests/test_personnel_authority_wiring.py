# -*- coding: utf-8 -*-
"""M1b-2：人事入口可选 `executor` 权限门（不传 = 旧行为）。"""
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


def test_circuit_appoint_legal_with_executor():
    s = _state()
    assert _circuit_appoint(s, {"org": "吏部"}) is True
    assert s.circuit_officials["京畿路"]["officials"]["cao"]["name"] == "测试官"


def test_circuit_appoint_illegal_without_mutation():
    s = _state()
    before = copy.deepcopy(getattr(s, "circuit_officials", {}))
    assert _circuit_appoint(s, {"org": "户部"}) is False
    assert getattr(s, "circuit_officials", {}) == before


def test_circuit_dismiss_legal_with_executor():
    s = _state()
    _circuit_appoint(s)  # 先旧行为任命
    old = dismiss_circuit_official(s, "京畿路", "cao", executor="吏部")
    assert isinstance(old, dict) and old.get("name") == "测试官"
    assert s.circuit_officials["京畿路"]["officials"]["cao"].get("vacant") is True


def test_circuit_dismiss_illegal_without_mutation():
    s = _state()
    _circuit_appoint(s)
    before = copy.deepcopy(s.circuit_officials)
    assert dismiss_circuit_official(
        s, "京畿路", "cao", executor={"org": "户部"}
    ) is None
    assert s.circuit_officials == before


def test_prefect_appoint_legal_with_executor():
    s = _state()
    out = appoint_prefect_official(
        s, SEAT, "prefect", _official("知府甲"), executor={"org": "吏部"}
    )
    assert out["ok"] is True
    assert out["name"] == "知府甲"


def test_prefect_appoint_illegal_without_mutation():
    s = _state()
    before = copy.deepcopy(s.prefect_officials)
    out = appoint_prefect_official(
        s, SEAT, "prefect", _official("知府乙"), executor={"org": "户部"}
    )
    assert out["ok"] is False
    assert "事权不合法" in out["msg"]
    assert s.prefect_officials == before


def test_prefect_dismiss_legal_with_executor():
    s = _state()
    appoint_prefect_official(s, SEAT, "prefect", _official("知府丙"))
    out = dismiss_prefect_official(s, SEAT, "prefect", executor="吏部")
    assert out["ok"] is True
    assert out["dismissed"] == "知府丙"


def test_prefect_dismiss_illegal_without_mutation():
    s = _state()
    appoint_prefect_official(s, SEAT, "prefect", _official("知府丁"))
    before = copy.deepcopy(s.prefect_officials)
    out = dismiss_prefect_official(
        s, SEAT, "prefect", executor={"org": "户部"}
    )
    assert out["ok"] is False
    assert s.prefect_officials == before


def test_legacy_calls_without_executor_unchanged():
    s = _state()
    assert _circuit_appoint(s) is True
    out = appoint_prefect_official(s, SEAT, "prefect", _official("知府戊"))
    assert out["ok"] is True
    assert out["name"] == "知府戊"


def test_unknown_executor_rejected():
    s = _state()
    assert _circuit_appoint(s, {"org": "不存在"}) is False
    out = appoint_prefect_official(
        s, SEAT, "prefect", _official("知府己"), executor={"org": "不存在"}
    )
    assert out["ok"] is False

