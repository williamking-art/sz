# -*- coding: utf-8 -*-
"""质量放行门 · 长期旨案卷化（2026-10-20，参考外部 UI）。

参考结构：案号/承办人+六维/授权(专款·余额·出库·专断之权)/案卷底册/
阶段+进度/持续影响/推进日志/达成目标/失败代价。

钉住：
1. 字段幂等补齐，缺失保持 None/空（不假装 0）；
2. 授权：**只登记专款额度、不即时扣库**；府库不足 ⇒ 拒批且不动账；重复授权不重复拨款；
3. 逐月自理：每月扣 monthly_cost（**唯一真实扣库点**）；专款耗尽 ⇒ blocked 且**不落持续效果**；
4. 持续效果只认白名单键（prestige/treasury/population_satisfaction），未知键忽略；
5. 阶段映射：0=见底 / <75=推进中 / <100=终前 / 100=达成；达成时落 outcome_effects；
6. 推进日志有上限；readout 字段与参考 UI 对齐。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics.longterm_case import (  # noqa: E402
    CASE_LOG_KEEP, authorize_case, case_readout, ensure_case_fields,
    monthly_case_settle, phase_of)


class _S:
    def __init__(self, treasury=1000000, imperial=100000, prestige=60, sat=55, turn=30):
        self.treasury = treasury
        self.imperial_treasury = imperial
        self.prestige = prestige
        self.population_satisfaction = sat
        self.turn = turn

    def change_treasury(self, d):
        self.treasury += int(d)

    def change_imperial_treasury(self, d):
        self.imperial_treasury += int(d)

    def change_prestige(self, d, reason=""):
        self.prestige += int(d)


def _task():
    return {"id": "ltp1", "task_name": "整饬海防", "minister": "郑芝龙",
            "progress": 0, "monthly_effects": [{"key": "prestige", "amount": -1}],
            "outcome_effects": [{"key": "prestige", "amount": 9}],
            "fail_effects": []}


def test_fields_idempotent_and_none():
    t = _task()
    ensure_case_fields(None, t)
    assert t["case_no"] is None and t["severity"] is None
    assert t["budget"] == {"total": 0, "remaining": 0, "pool": "treasury"}
    ensure_case_fields(None, t)
    assert t["monthly_effects"] == [{"key": "prestige", "amount": -1}]


def test_authorize_registers_quota_and_rejects_insufficient():
    """P0-3（2026-10-20 全审）：授权**只登额度、不即时扣库**；月结才是唯一真实扣款点。"""
    s = _S(treasury=1000000)
    t = _task()
    out = authorize_case(s, t, budget=500000, pool="treasury", discretion=True)
    assert out["ok"] and s.treasury == 1000000, "授权不得即时扣库（否则月结双扣）"
    assert t["budget"]["remaining"] == 500000 and t["discretion"] is True
    assert t["case_no"] and t["opened_turn"] == 30, "授权应补案号/立项回合"
    again = authorize_case(s, t, budget=500000)
    assert again["ok"] is False and s.treasury == 1000000, "重复授权不得重复扣款"
    t2 = _task()
    poor = authorize_case(_S(treasury=100), t2, budget=500000)
    assert poor["ok"] is False and "府库不足" in poor["reason"]


def test_monthly_settle_spends_and_applies_effects():
    s = _S(treasury=1000000, prestige=60)
    t = _task()
    authorize_case(s, t, budget=100000, monthly_cost=20000)
    out = monthly_case_settle(s, t, [], narrative="增烽堠八座", progress=10)
    assert out["ok"] and not out["blocked"]
    assert s.treasury == 1000000 - 20000, "月费只扣一次（授权不预扣）"
    assert t["budget"]["remaining"] == 80000
    assert s.prestige == 59, "皇威 −1 应落账"
    assert out["applied"] == [{"key": "prestige", "amount": -1}]
    assert out["phase"] == "推进中"


def test_budget_exhausted_blocks_effects():
    s = _S(treasury=1000000, prestige=60)
    t = _task()
    authorize_case(s, t, budget=30000, monthly_cost=20000)
    monthly_case_settle(s, t, [], progress=5)
    out = monthly_case_settle(s, t, [], progress=10)
    assert out["blocked"] and "专款耗尽" in out["blocked"]
    assert s.prestige == 59, "受阻月不得落持续效果"
    assert s.treasury == 1000000 - 20000, "受阻月不得再扣库"


def test_pool_short_blocks_without_charging_or_spending_quota():
    """复审补丁（2026-10-20）：额度够但国库不足 ⇒ 本月 blocked，不扣库、不减额度、不落效果。"""
    s = _S(treasury=30000, prestige=60)
    t = _task()
    authorize_case(s, t, budget=30000, monthly_cost=20000)
    s.treasury = 10000                       # 授权后国库被别处花掉
    out = monthly_case_settle(s, t, [], progress=5)
    assert out["blocked"] and "府库不足" in out["blocked"]
    assert s.treasury == 10000, "扣款失败不得动账"
    assert t["budget"]["remaining"] == 30000, "扣款失败不得消耗额度"
    assert s.prestige == 60, "受阻月不得落持续效果"


def test_unknown_effect_key_ignored():
    s = _S(prestige=60)
    t = _task()
    t["monthly_effects"] = [{"key": "乱写", "amount": -5}]
    out = monthly_case_settle(s, t, [])
    assert out["applied"] == [] and s.prestige == 60


def test_phase_mapping_and_outcome_effect():
    assert phase_of(0) == "见底" and phase_of(10) == "推进中"
    assert phase_of(80) == "终前" and phase_of(100) == "达成"
    s = _S(prestige=60)
    t = _task()
    out = monthly_case_settle(s, t, [], progress=100)
    assert out["outcome"] == "达成" and s.prestige == 60 - 1 + 9


def test_log_capped_and_readout_shape():
    s = _S()
    t = _task()
    for i in range(CASE_LOG_KEEP + 5):
        monthly_case_settle(s, t, [], progress=i)
    assert len(t["progress_log"]) == CASE_LOG_KEEP
    r = case_readout(s, t)
    for k in ("case_no", "handler", "authorization", "progress", "monthly_effects",
              "progress_log", "outcome_effects", "fail_effects"):
        assert k in r, k
    # C-4（2026-10-20 全审）：未授权 ⇒ authorization 缺失一律 None（面板显示未授权），
    # 不得回落成 {"budget_total":0,...} 让玩家读到「专款 0 万两」。
    assert r["authorization"] is None
    authorize_case(s, t, budget=100000, monthly_cost=20000)
    r2 = case_readout(s, t)
    assert r2["authorization"]["budget_total"] == 100000
    assert r2["authorization"]["discretion"] in (True, False)
    assert r2["case_no"] == t["case_no"]