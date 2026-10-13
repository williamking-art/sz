# -*- coding: utf-8 -*-
"""M82 P1 试点链条**原因链归因**（为何未运到）—— 定向回归。

锁定：① 每条归因**必须带证据数字**；② 证据不足 ⇒ 只报 `undefined_data`（**不臆造**）；
③ 判定优先级：`undefined_data` → `no_workshop` → `raw_shortage` → `capacity_shortage`
→ `demand_far_exceeds_supply` → `ok`；④ 只读。
"""

import copy
import types

from core.domains.economy import p1_pilot_chain as pc


def _mk(monkeypatch, *, raw, per, shops, cap, out, demand):
    """用 monkeypatch 直接给出链条各段（避免构造整局）。"""
    monkeypatch.setattr(pc, "chain_of_route", lambda state, route: {
        "route": route, "pilot": dict(pc.PILOT),
        "raw_input": raw,
        "workshops": {"count": shops, "active": shops, "owners": {}, "rows": [],
                      "per_round_input": per},
        "theoretical_output_cap_per_round": cap,
        "finished_output": out, "demand": demand,
        "gap": None if (demand is None or out is None) else max(0, demand - out),
        "undefined_fields": [], "note": ""})
    return types.SimpleNamespace()


def test_no_workshop_is_primary(monkeypatch):
    st = _mk(monkeypatch, raw=1e9, per=10000, shops=0, cap=None, out=0, demand=1000)
    rep = pc.diagnose_route(st, "路A")
    assert rep["verdict"] == "no_workshop"
    assert rep["reasons"][0]["evidence"] == {"workshops": 0}


def test_raw_shortage_has_evidence(monkeypatch):
    st = _mk(monkeypatch, raw=5000, per=10000, shops=1, cap=8000, out=0, demand=100)
    rep = pc.diagnose_route(st, "路A")
    assert rep["verdict"] == "raw_shortage"
    ev = next(r for r in rep["reasons"] if r["code"] == "raw_shortage")["evidence"]
    assert ev["rounds_supported"] == 0.5 and ev["per_round_input"] == 10000


def test_capacity_and_demand_reasons_carry_numbers(monkeypatch):
    st = _mk(monkeypatch, raw=1e9, per=10000, shops=1, cap=8000, out=100, demand=100000)
    rep = pc.diagnose_route(st, "路A")
    codes = [r["code"] for r in rep["reasons"]]
    assert "capacity_shortage" in codes and "demand_far_exceeds_supply" in codes
    cap_ev = next(r for r in rep["reasons"] if r["code"] == "capacity_shortage")["evidence"]
    assert cap_ev["cap_per_round_total"] == 8000 and cap_ev["demand"] == 100000
    dem_ev = next(r for r in rep["reasons"] if r["code"] == "demand_far_exceeds_supply")["evidence"]
    assert dem_ev["coverage_by_output"] == 0.001
    # 优先级：capacity 先于 demand
    assert rep["verdict"] == "capacity_shortage"


def test_undefined_data_when_evidence_missing(monkeypatch):
    st = _mk(monkeypatch, raw=None, per=None, shops=1, cap=None, out=None, demand=None)
    rep = pc.diagnose_route(st, "路A")
    assert rep["verdict"] == "undefined_data"
    assert "缺失≠0" in rep["reasons"][0]["note"]


def test_ok_when_no_structural_shortage(monkeypatch):
    st = _mk(monkeypatch, raw=1e9, per=10000, shops=3, cap=90000, out=50000, demand=60000)
    rep = pc.diagnose_route(st, "路A")
    assert rep["verdict"] == "ok" and "coverage_by_output" in rep


def test_real_game_survey_diagnosis_and_readonly():
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    rep = pc.survey_diagnosis(s)
    assert isinstance(rep["verdicts"], dict) and rep["pilot"]["output_dim"] == "绸"
    for r in rep["routes"]:
        for reason in r["reasons"]:
            assert reason["evidence"] or reason["code"] == "ok"   # **每条都带证据**
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
