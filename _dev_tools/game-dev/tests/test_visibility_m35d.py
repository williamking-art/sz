# -*- coding: utf-8 -*-
"""M35-D《财政信息差 · rumor 档位化》契约回归。

裁决：rumor **档位化**（0 无异常／1 钱粮迟滞／2 吏胥鼓噪／3 州县积欠／4 地方失控风险），
但**不**直接告诉 AI"发生腐败事件"——只提供**观察结果**；保持三层
（real 内部真账／official 官府账／rumor 民间传闻），玩家·官员·巡按·中央之间**继续存在信息差**。
给 AI 的读取接口：`identity_pressures()`／`arrears_months_summary()`／`fiscal_visibility_view()`／
`arrears_recovery_capacity()` —— **只输出状态，不自动生成剧情**。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FIN_ANOMALY_OVERSIGHT_LINE, RUMOR_LABELS  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.settlement_finance import _settle_local_expenditure  # noqa: E402


def _drive(s, rk, times):
    for _ in range(times):
        s.prefectures[rk]["local_treasury"] = 0
        _settle_local_expenditure(s, [])


def test_rumor_tier_zero_when_quiet():
    """静好之局：档位＝0（无异常），且标签与常量表一致。"""
    s = new_game()
    rt = s.rumor_tier()
    assert rt["tier"] == 0 and rt["label"] == RUMOR_LABELS[0]
    assert rt["signals"]["routes_tier_ge1"] == 0
    assert s.rumor_tier() == s.rumor_tier(), "同一状态重复读取应一致（纯派生）"


def test_rumor_tier_rises_with_arrears_months():
    """欠给越久 ⇒ 档位越高（1 月 → ≥1；≥3 月 → ≥3），且**不**声明"已查实腐败"。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 1)
    t1 = s.rumor_tier()["by_route"][rk]["tier"]
    assert t1 >= 1, "存在欠给即至少'钱粮迟滞'"
    _drive(s, rk, 3)
    row = s.rumor_tier()["by_route"][rk]
    assert row["tier"] >= 3, "欠给 ≥3 月应升到'州县积欠'"
    assert row["label"] in RUMOR_LABELS.values()
    # 档位只是"观察结果"：不得出现"腐败/查实"等判定词
    assert "腐败" not in str(row) and "查实" not in str(row)
    assert s.rumor_tier()["tier"] == row["tier"], "全国档位＝逐路最高"


def test_rumor_tier_does_not_generate_events():
    """**只输出状态**：读 rumor/可见度不得生成事件、案卷或风闻（无写入）。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 3)
    before_events = copy.deepcopy(getattr(s, "active_events", []))
    before_cases = copy.deepcopy(getattr(s, "audit_cases", {}))
    before_susp = copy.deepcopy(getattr(s, "discovery_suspicions", []))
    s.rumor_tier()
    s.fiscal_visibility()
    s.fiscal_visibility_view("player")
    s.fiscal_visibility_view("court")
    s.identity_pressures()
    s.arrears_months_summary()
    s.arrears_recovery_capacity()
    assert getattr(s, "active_events", []) == before_events, "读数不得生成事件"
    assert getattr(s, "audit_cases", {}) == before_cases, "读数不得生成案卷"
    assert getattr(s, "discovery_suspicions", []) == before_susp, "读数不得生成风闻"


def test_info_gap_between_viewers():
    """信息差：玩家/官员/中央**看不到 real**；中央只见汇总；巡按需'查得实情'才见真账。"""
    s = new_game()
    _drive(s, min(s.prefectures), 2)
    player = s.fiscal_visibility_view("player")
    official = s.fiscal_visibility_view("official")
    court = s.fiscal_visibility_view("court")
    for out in (player, official, court):
        assert "real" not in out, "非监察视角不得直读真账"
        assert "official" in out and "rumor" in out
    assert court["granularity"] == "national"
    assert "by_route" not in court["rumor"], "中央只见汇总（无逐路明细）"
    assert "by_route" in player["rumor"], "玩家/地方官可见逐路档位"
    # 巡按：默认不真账，查得实情（监察足额/密查）才给
    assert "real" not in s.fiscal_visibility_view("inspector", oversight=0.0)
    assert "real" in s.fiscal_visibility_view("inspector",
                                             oversight=FIN_ANOMALY_OVERSIGHT_LINE + 0.1)
    assert "real" in s.fiscal_visibility_view("audit", secret=True)
    assert set(s.fiscal_visibility_view("ai")) >= {"real", "official", "rumor"}


def test_readout_exposes_ai_state_interfaces():
    """AI 读取接口齐备（只输出状态）：pressure／months／visibility／recovery capacity。"""
    s = new_game()
    _drive(s, min(s.prefectures), 2)
    out = s.finance_readout()
    for k in ("rumor_tier", "rumor", "identity_pressures", "local_arrears_months",
              "fiscal_visibility", "arrears_recovery_capacity",
              "local_arrears_by_identity", "population_breakdown"):
        assert k in out, f"finance_readout 缺 AI 接口字段 {k}"
    assert isinstance(out["rumor_tier"], int) and 0 <= out["rumor_tier"] <= 4
    assert "real" not in out["fiscal_visibility"], "读数（玩家视角）不得含真账"
    # `rumor` 层保留 P3 发现链原文（供巡按/调查消费）
    assert "discovery" in s.fiscal_visibility()["rumor"]
