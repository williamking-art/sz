# -*- coding: utf-8 -*-
"""质量放行门 · 圣旨核销闭环（2026-10-20，用户裁定第二轮）。

用户三条裁定：
1. 皇帝发出的旨意**不存在「未决」**——发出即生效，只会被拖延/搁置；
2. 中旨落地率**不是固定 0.75**，而是 执行系统 × 皇威 曲线（皇威高则文官也不敢拖）；
3. 宦官、武将不适用文官那套：不敢不遵中旨，基础落地率高且对皇威不敏感。

钉住：
1. 执行系统识别（文官/宦官/武将/宗室/地方）；
2. 文官落地随皇威显著上升；宦官几乎不受皇威影响且基础更高；
3. 天道档位可覆盖（低/中/高/极 → 0.70/0.85/1.00/1.10）；
4. 无颁布回合也核销（发出即生效，不再有「未决」）；超期中旨=dragged、普通=failed；
5. 幂等不改写；悬挂核销后归零；落地系数夹在 [0.05, 1.0]。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.decree_confirm import OUTCOME_EXECUTED, exec_ledger_of, record_execution  # noqa: E402
from core.domains.politics.edict_closure import (  # noqa: E402
    AI_LANDING, SYSTEM_BASE, closure_status, executor_system_of, is_zhongzhi,
    landing_effect, sweep_edict_closure)


class _S:
    def __init__(self, decrees, turn=10, prestige=55):
        self.turn = turn
        self.prestige = prestige
        self.pending_decrees = list(decrees)
        self.pending_secret_decrees = []
        self.active_decrees = []
        self.statistics = {}


def test_executor_system_detection():
    assert executor_system_of({"addressees": ["内侍省"]}) == "宦官"
    assert executor_system_of({"title": "禁军整饬", "target_org": "殿前司"}) == "武将"
    assert executor_system_of({"target_org": "户部"}) == "文官"
    assert executor_system_of({"target_org": "转运使司"}) == "地方"


def test_zhongzhi_detection():
    assert is_zhongzhi({"category": "中旨"})
    assert is_zhongzhi({"delivery": "御笔直发"})
    assert not is_zhongzhi({"category": "诏令"})


def test_landing_not_fixed_and_prestige_sensitive_for_civil():
    civil = {"target_org": "户部", "category": "中旨"}
    low = landing_effect(civil, prestige=20)
    high = landing_effect(civil, prestige=95)
    assert high["landed"] > low["landed"], (low, high)
    assert low["system"] == "文官"


def test_eunuch_and_general_barely_follow_prestige():
    eun = {"addressees": ["内侍省"], "category": "中旨"}
    mil = {"target_org": "殿前司", "category": "中旨"}
    e_low, e_high = landing_effect(eun, prestige=10)["landed"], landing_effect(eun, prestige=95)["landed"]
    m_low, m_high = landing_effect(mil, prestige=10)["landed"], landing_effect(mil, prestige=95)["landed"]
    assert e_high - e_low < 0.15, (e_low, e_high)   # 宦官对皇威不敏感
    assert SYSTEM_BASE["宦官"] > SYSTEM_BASE["文官"]
    assert SYSTEM_BASE["武将"] > SYSTEM_BASE["文官"]


def test_ai_tier_overrides():
    s = _S([])
    s._decree_ai = {"landing": {"文官": "低"}}
    got = landing_effect({"target_org": "户部", "category": "中旨"}, s, prestige=55)
    assert got["ai_mult"] == AI_LANDING["低"]
    assert "天道" in got["source"]


def test_undated_decree_is_closed_not_pending():
    s = _S([{"title": "无日期旨"}], turn=10)
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 0 and out["kept_count"] == 1   # 当月不算超期
    assert s.pending_decrees[0].get("turn_issued") == 10         # 发出即生效：补颁布回合
    sweep_edict_closure(s, stale_turns=3, turn=14)
    assert closure_status(s)["dangling_count"] == 0


def test_zhongzhi_overdue_is_dragged_with_system_landing():
    s = _S([{"title": "御笔加赏", "category": "中旨", "target_org": "户部", "turn_issued": 1}])
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 1
    rec = list(exec_ledger_of(s).values())[0]
    assert rec["outcome"] == "dragged"
    assert rec["zhongzhi"] is True and rec["system"] == "文官"
    assert 0.05 <= rec["landed"] <= 1.0


def test_normal_decree_overdue_is_failed():
    s = _S([{"title": "普通诏令", "category": "诏令", "turn_issued": 1}])
    sweep_edict_closure(s, stale_turns=3, turn=10)
    rec = list(exec_ledger_of(s).values())[0]
    assert rec["outcome"] != "dragged" and rec["zhongzhi"] is False


def test_idempotent_and_executed_not_overwritten():
    s = _S([{"title": "旧旨", "decree_id": "d1", "turn_issued": 1},
            {"title": "已办", "decree_id": "d2", "turn_issued": 1}])
    record_execution(s, "d2", outcome=OUTCOME_EXECUTED, turn=2, landed=1.0)
    sweep_edict_closure(s, stale_turns=3, turn=10)
    first = dict(exec_ledger_of(s)["d1"])
    sweep_edict_closure(s, stale_turns=3, turn=11)
    assert exec_ledger_of(s)["d1"]["turn"] == first["turn"]
    assert exec_ledger_of(s)["d2"]["outcome"] == OUTCOME_EXECUTED


def test_bounds():
    got = landing_effect({"target_org": "户部", "category": "中旨"}, prestige=0)
    assert 0.05 <= got["landed"] <= 1.0
    got2 = landing_effect({"target_org": "户部", "category": "中旨"}, prestige=100)
    assert 0.05 <= got2["landed"] <= 1.0

def test_ai_landing_level_overrides_prior():
    """天道/Jev 裁决的落地档优先于程序先验（全办/大部/半数/少半/未办）。"""
    s = _S([])
    s._decree_ai = {"landing_levels": {"d1": "少半"}, "landing_note": "文官阳奉阴违"}
    got = landing_effect({"decree_id": "d1", "category": "中旨", "target_org": "户部"},
                         s, prestige=95)
    assert got["landed"] == 0.25 and got["level"] == "少半"
    assert got["source"] == "天道"
    assert got["prior"] > got["landed"], "先验应高于实际落地，说明档位被采纳"


def test_landing_level_by_system():
    s = _S([])
    s._decree_ai = {"landing_levels": {"文官": "半数"}}
    got = landing_effect({"category": "中旨", "target_org": "户部"}, s, prestige=70)
    assert got["landed"] == 0.50 and got["level"] == "半数"


def test_landing_level_provider_injection():
    from core.domains.politics import edict_closure as ec

    s = _S([])
    ec.register_landing_level_provider(lambda st, d: {"landing_level": "未办", "note": "provider"})
    try:
        got = landing_effect({"decree_id": "x", "category": "中旨"}, s, prestige=90)
        assert got["landed"] == 0.0 and "provider" in got["source"]
    finally:
        ec._LANDING_LEVEL_PROVIDERS.clear()


def test_invalid_landing_level_falls_back_to_prior():
    s = _S([])
    s._decree_ai = {"landing_level": "随便"}
    got = landing_effect({"category": "中旨", "target_org": "户部"}, s, prestige=60)
    assert got["level"] is None and got["source"].startswith("程序先验")


def test_no_sync_http_in_settlement_module():
    """纪律：落地档由**前置步骤/离线批**注入，结算期不做同步网络调用。"""
    import inspect

    from core.domains.politics import edict_closure as ec

    src = inspect.getsource(ec)
    for banned in ("requests.", "httpx.", "urllib.request", "jev_gate"):
        assert banned not in src, banned