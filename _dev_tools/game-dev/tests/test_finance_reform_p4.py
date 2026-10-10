# -*- coding: utf-8 -*-
"""P4 治理改革（V1.3 终稿 §9/§13）：route 级 grip（Q12）／改革轴（四率归一）／抄没前置（Q11）。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core.audit_case import confiscate_by_case, resolve_audit
from core.commands import new_game
from core.clerks import route_decree_mult
from core.decree_effect import decree_effect_mult, effect_channels
from core.foundation.ledger.money import m_all
from core.settlement_decree import _apply_decree_effect


def _route(s):
    return next(iter(s.prefectures))


def _set_grip(s, route, v):
    p = s.prefectures[route]
    d = p.get("clerks_detail")
    if not isinstance(d, dict):
        d = {}
        p["clerks_detail"] = d
    d["grip"] = v


# ---------------- Q12：route 级 grip ----------------

def test_route_grip_discount_and_scope():
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.60)
    rm = route_decree_mult(s, r)
    assert rm == pytest.approx(1.0 - 0.35 * 0.60)
    ch = effect_channels(s, org_hint="政府", text="勾校", route=r)
    assert ch["clerks_scope"] == f"按路（{r}）"
    assert ch["clerks_mult"] == pytest.approx(rm)
    ch2 = effect_channels(s, org_hint="政府", text="勾校")
    assert ch2["clerks_scope"] == "全国"           # 无 route → 回落全国
    # clerks_detail 缺失 → None（调用方回落，绝不臆造）
    s.prefectures[r].pop("clerks_detail", None)
    assert route_decree_mult(s, r) is None


def test_route_level_grip_makes_corrupt_route_harder():
    """贪得越狠的路越查不动：按路折扣低于全国折扣。"""
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.90)
    m_route = decree_effect_mult(s, org_hint="政府", text="勾校某路", route=r)
    m_global = decree_effect_mult(s, org_hint="政府", text="勾校某路")
    assert m_route < m_global


# ---------------- 改革轴（四率归一，保护 transfer） ----------------

def test_finance_reform_normalizes_and_protects_transfer():
    s = new_game()
    before = dict(s.finance)
    rf = s.apply_finance_reform({"local_keep_rate": 0.04})       # keep 0.04→0.08
    af = rf["after"]
    assert af["transfer_rate"] + af["local_keep_rate"] + af["diversion_rate"] == pytest.approx(1.0, abs=1e-9)
    assert af["transfer_rate"] == pytest.approx(before["transfer_rate"])   # transfer 最高保护
    assert af["diversion_rate"] <= before["diversion_rate"] + 1e-12        # div 残差吸收
    # 未知键/坏值忽略
    rf2 = s.apply_finance_reform({"nonsense": 1, "transfer_rate": True})
    assert rf2["applied"] == {}
    # 强中央：transfer↑ → div 被挤
    s2 = new_game()
    r2 = s2.apply_finance_reform({"transfer_rate": 0.04})
    assert r2["after"]["transfer_rate"] > 0.94
    assert r2["after"]["diversion_rate"] <= 0.02


def test_finance_reform_decree_effect_wires():
    s = new_game()
    log = []
    _apply_decree_effect(s, {"title": "改定上供", "effects": {"finance_rates": {"diversion_rate": -0.01}}}, log)
    assert any("[改革]" in x for x in log)
    assert s.finance["diversion_rate"] < 0.02 + 1e-12


# ---------------- 抄没前置（Q11） ----------------

def test_confiscation_requires_case_and_conserves_money():
    s = new_game()
    r = _route(s)
    # 无案 → 拒（Q11：财政贪墨须先成案）
    assert confiscate_by_case(s, case_id="nope")["ok"] is False
    # 成案（清廉执行者 + 低把持）→ 抄没守恒（私囊 → 国库）
    _set_grip(s, r, 0.10)
    cid = resolve_audit(s, r, executor="陈瓘")["case"]["id"]
    m0 = m_all(s)
    t0 = s.treasury
    cr = confiscate_by_case(s, case_id=cid)
    assert cr["ok"] and cr["seized"] > 0
    assert s.treasury == t0 + cr["seized"]
    assert abs(m_all(s) - m0) < 1e-9
    assert s.audit_cases[cid]["judgement"]
    assert s.audit_cases[cid]["status"] == "已定案"
    # 二次抄没：案已定案 → 拒
    assert confiscate_by_case(s, case_id=cid)["ok"] is False
    # 皇权事件例外通道（显式）
    s2 = new_game()
    cr2 = confiscate_by_case(s2, route=_route(s2), imperial_exception=True)
    assert cr2["ok"] is True


def test_confiscate_decree_effect_and_refusal_log():
    s = new_game()
    r = _route(s)
    log = []
    # 无案 → 拒并留痕
    _apply_decree_effect(s, {"title": "抄没", "effects": {"confiscate": {"case_id": "nope"}}}, log)
    assert any("[抄没] 未成" in x for x in log)
    # 成案后 → 成功
    _set_grip(s, r, 0.10)
    cid = resolve_audit(s, r, executor="陈瓘")["case"]["id"]
    log2 = []
    _apply_decree_effect(s, {"title": "抄没", "effects": {"confiscate": {"case_id": cid}}}, log2)
    assert any("[抄没]" in x and "未成" not in x for x in log2)
