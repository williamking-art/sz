# -*- coding: utf-8 -*-
"""皇帝个人行动矩阵（契约 v2）测试：矩阵白名单/时代门槛/月度限/旅程/守恒/风险/效果/契约/存档。

覆盖 T4a 落地清单：
  1) location×mode 行动矩阵白名单（跨格子非法）
  2) state.imperial_action 存档字段（替代单值 personal_action）+ 旧档迁移
  3) 时间消耗：公开出京准备期 1-2 月（pending_imperial_trip 月度推进）/ 微服他地距离核算 / 出京带宽仅 -1
  4) 微服京城每月 1 次（程序按回合计数）
  5) 资源通道守恒：公开→国库 / 微服→内帑（程序基础开销，AI 不写数值）
  6) 风险事件：risk 档概率（低2%/中8%/高20%）+ 时代门槛 + 三标签（史实锚/合理推演）
  7) 效果落地：effects 档位 → prestige/population_satisfaction/emperor_health/art/taoism/pleasure/factions
  8) 契约 v2 validate（拒绝式：跨格子/键越界 → 整单失败）
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)
sys.path.insert(0, os.path.join(_GAME_ROOT, "tests"))

from core.game_state import GameState  # noqa: E402
from content.data import (  # noqa: E402
    IMPERIAL_ACTION_MATRIX, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
    IMPERIAL_RISK_PROB, imperial_distance, imperial_prep_months,
)
from core.commands import choose_imperial_action, do_personal_action  # noqa: E402
from core.settlement_steps import _settle_emperor_personal  # noqa: E402
from core.events import get_imperial_risk_event, IMPERIAL_RISK_EVENTS  # noqa: E402


def _new_state():
    return GameState("史实")


# ------------------------------------------------------------
# 1) 矩阵白名单（跨格子非法）
# ------------------------------------------------------------
def test_matrix_legal_cell():
    s = _new_state()
    msg = choose_imperial_action(s, "宫里", "公开", "临朝")
    assert "临朝" in msg
    assert s.imperial_action["location"] == "宫里"
    assert s.imperial_action["mode"] == "公开"
    assert s.imperial_action["action"] == "临朝"
    assert s.imperial_action["pending_months"] == 0


def test_matrix_cross_cell_illegal():
    s = _new_state()
    # 宫里·微服 空格（无任何行动）
    assert "非法" in choose_imperial_action(s, "宫里", "微服", "临朝")
    assert not s.imperial_action
    # 微行市井 只在 京城·微服 格内
    assert "非法" in choose_imperial_action(s, "京城", "公开", "微行市井")
    assert not s.imperial_action
    # 幸艮岳 只在 京城·公开 格内
    assert "非法" in choose_imperial_action(s, "出京", "微服", "幸艮岳")
    assert not s.imperial_action
    # 合法格照常
    assert "微行市井" in choose_imperial_action(s, "京城", "微服", "微行市井")


def test_matrix_data_shape():
    """矩阵结构与三标签/风险档/时代门槛字段齐全（单一权威源 data.py）。"""
    assert IMPERIAL_LOCATIONS == ("宫里", "京城", "出京")
    assert IMPERIAL_MODES == ("公开", "微服")
    for loc in IMPERIAL_LOCATIONS:
        for mode in IMPERIAL_MODES:
            for action, cell in IMPERIAL_ACTION_MATRIX[loc][mode].items():
                assert cell.get("label"), f"{loc}.{mode}.{action} 缺三标签"
                assert "base_cost" in cell and "fund" in cell
                assert cell["fund"] in ("treasury", "imperial_treasury")
                assert cell.get("risk") in IMPERIAL_RISK_PROB


# ------------------------------------------------------------
# 2) 旧通道兼容（do_personal_action → 宫里·公开）
# ------------------------------------------------------------
def test_legacy_do_personal_action():
    s = _new_state()
    assert "临朝" in do_personal_action(s, "勤政")
    assert s.imperial_action["location"] == "宫里"
    assert s.imperial_action["action"] == "临朝"
    assert do_personal_action(s, "不存在的行动") == "无此行动。"


# ------------------------------------------------------------
# 3) 时代门槛（艮岳 1117 / 延福宫 1113 / 上清宝箓宫 1117 / 东幸镇江 1126）
# ------------------------------------------------------------
def test_era_gates():
    s = _new_state()   # 1101
    assert "未至该时代" in choose_imperial_action(s, "京城", "公开", "幸艮岳")
    assert "未至该时代" in choose_imperial_action(s, "京城", "公开", "延福宫宴游")
    assert "未至该时代" in choose_imperial_action(s, "京城", "公开", "上清宝箓宫")
    assert "未至该时代" in choose_imperial_action(s, "出京", "公开", "东幸镇江")
    assert not s.imperial_action
    s.year = 1113
    assert "延福宫宴游" in choose_imperial_action(s, "京城", "公开", "延福宫宴游")
    s.year = 1117
    assert "幸艮岳" in choose_imperial_action(s, "京城", "公开", "幸艮岳")
    assert "上清宝箓宫" in choose_imperial_action(s, "京城", "公开", "上清宝箓宫")
    s.year = 1126
    assert "东幸镇江" in choose_imperial_action(s, "出京", "公开", "东幸镇江")


# ------------------------------------------------------------
# 4) 微服京城每月 1 次（程序按回合计数）
# ------------------------------------------------------------
def test_micro_once_per_month(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.99)   # 禁风险
    s = _new_state()
    assert "微行市井" in choose_imperial_action(s, "京城", "微服", "微行市井")
    assert s.imperial_micro_count == 1
    # 同月第二次微服（另一行动）→ 拒绝
    assert "只可一次" in choose_imperial_action(s, "京城", "微服", "微行大臣府第")
    # 结算月末归零 → 可再行
    _settle_emperor_personal(s, [])
    assert s.imperial_micro_count == 0
    assert "微行市井" in choose_imperial_action(s, "京城", "微服", "微行市井")


# ------------------------------------------------------------
# 3) 时间消耗：准备期 / 距离核算
# ------------------------------------------------------------
def test_travel_prep_months():
    # 公开出京：未准备 2 月 / 已准备 1 月（准备期 1-2 月）
    assert imperial_prep_months("出京", "公开", "巡幸东南", prepared=False) == 2
    assert imperial_prep_months("出京", "公开", "巡幸东南", prepared=True) == 1
    # 微服他地：按目标路距离档（近=当月来回 / 中=装备1月 / 远=装备2月）
    assert imperial_distance("开封府") == "近"
    assert imperial_distance("河北路") == "中"
    assert imperial_distance("两浙路") == "远"
    assert imperial_prep_months("出京", "微服", "微服他地", target="开封府") == 0
    assert imperial_prep_months("出京", "微服", "微服他地", target="河北路") == 1
    assert imperial_prep_months("出京", "微服", "微服他地", target="两浙路") == 2
    # 宫里/京城：当月生效
    assert imperial_prep_months("宫里", "公开", "临朝") == 0
    assert imperial_prep_months("京城", "微服", "微行市井") == 0


def test_pending_trip_progression(monkeypatch):
    """公开出京准备期月度推进：准备中不落地开销/效果；成行当月落地。"""
    monkeypatch.setattr("random.random", lambda: 0.99)   # 禁风险
    s = _new_state()
    msg = choose_imperial_action(s, "出京", "公开", "巡幸东南", prepared=False)
    assert "准备 2 月" in msg
    assert s.pending_imperial_trip is not None
    assert s.imperial_action["pending_months"] == 2
    t0, b0 = s.treasury, s.decree_bandwidth
    # 准备中不可另定行动
    assert "准备中" in choose_imperial_action(s, "宫里", "公开", "临朝")
    # 第 1 月：推进（尚余 1 月），不落地开销/效果；出京带宽 -1（远程批奏）
    log = []
    _settle_emperor_personal(s, log)
    assert s.imperial_action["pending_months"] == 1
    assert s.treasury == t0
    assert s.decree_bandwidth == max(5, b0 - 3)   # 回调 -2 + 出京 -1
    assert any("准备中" in x for x in log)
    # 第 2 月：成行，落地基础开销（巡幸东南 50 万贯国库）
    log2 = []
    _settle_emperor_personal(s, log2)
    assert s.treasury == t0 - 500_000
    assert s.imperial_action == {} and s.pending_imperial_trip is None


# ------------------------------------------------------------
# 5) 资源通道守恒：公开→国库 / 微服→内帑
# ------------------------------------------------------------
def test_resource_channels(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.99)   # 禁风险
    # 公开大驾 → 国库
    s = _new_state()
    t0 = s.treasury
    choose_imperial_action(s, "宫里", "公开", "崇道修醮")   # base_cost 5 万
    _settle_emperor_personal(s, [])
    assert s.treasury == t0 - 50_000
    # 微服便服 → 内帑（不动国库）
    s2 = _new_state()
    t02, it0 = s2.treasury, s2.imperial_treasury
    choose_imperial_action(s2, "京城", "微服", "微行市井")   # base_cost 2 万
    _settle_emperor_personal(s2, [])
    assert s2.imperial_treasury == it0 - 20_000
    assert s2.treasury == t02


def test_resource_shortfall(monkeypatch):
    """府库不足 → 扣至 0 + 日志明示缺口（不凭空扣负）。"""
    monkeypatch.setattr("random.random", lambda: 0.99)
    s = _new_state()
    s.imperial_treasury = 5_000
    choose_imperial_action(s, "京城", "微服", "微行市井")   # cost 2 万
    log = []
    _settle_emperor_personal(s, log)
    assert s.imperial_treasury == 0
    assert any("不足" in x for x in log)


# ------------------------------------------------------------
# 7) 效果落地（state_applier 白名单 path）
# ------------------------------------------------------------
def test_effects_landing(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.99)
    # 临朝：皇威 +3 / 带宽 +2 / 龙体 -2（1101 无自然衰减）
    s = _new_state()
    p0, b0, h0 = s.prestige, s.decree_bandwidth, s.emperor_health
    choose_imperial_action(s, "宫里", "公开", "临朝")
    _settle_emperor_personal(s, [])
    assert s.prestige == min(100, p0 + 3)
    assert s.decree_bandwidth == min(10, max(6, b0 - 2) + 2)
    assert s.emperor_health == h0 - 2
    # 书画翰墨：艺术造诣 +3
    s2 = _new_state()
    a0 = s2.art_mastery
    choose_imperial_action(s2, "宫里", "公开", "书画翰墨")
    _settle_emperor_personal(s2, [])
    assert s2.art_mastery == min(100, a0 + 3)
    # 崇道修醮：道心 +4 / 新党满意度 +3
    s3 = _new_state()
    ta0 = s3.taoism_leaning
    fa0 = s3.factions["新党"]["satisfaction"]
    choose_imperial_action(s3, "宫里", "公开", "崇道修醮")
    _settle_emperor_personal(s3, [])
    assert s3.taoism_leaning == min(100, ta0 + 4)
    assert s3.factions["新党"]["satisfaction"] == min(100, fa0 + 3)


def test_ai_effects_override(monkeypatch):
    """AI 契约 v2 档位词覆盖 base 核心 4 键（混沌）；base 其它键（带宽）保留。"""
    monkeypatch.setattr("random.random", lambda: 0.99)
    s = _new_state()
    choose_imperial_action(s, "宫里", "公开", "临朝")
    s._emperor_ai = {
        "location": "宫里", "mode": "公开", "action": "临朝",
        "prepared": False, "risk": "低",
        "effects": {"威望": "中", "健康": "-大"}, "narrative": "临朝决事。",
    }
    p0, b0, h0 = s.prestige, s.decree_bandwidth, s.emperor_health
    _settle_emperor_personal(s, [])
    # 威望：AI 中档（tier_to_value prestige 中 = 4）覆盖 base +3；带宽仍 +2；健康 -大 → -4
    assert s.prestige == min(100, p0 + 4)
    assert s.decree_bandwidth == min(10, max(6, b0 - 2) + 2)
    assert s.emperor_health == h0 - 4


# ------------------------------------------------------------
# 6) 风险事件（概率 / 时代门槛 / 三标签）
# ------------------------------------------------------------
def test_risk_triggered(monkeypatch):
    """risk 高（20%）强制命中 → 风险事件入 event_history + active_events，带三标签。"""
    monkeypatch.setattr("random.random", lambda: 0.0)   # 必命中
    s = _new_state()
    s.imperial_treasury = 10_000_000
    choose_imperial_action(s, "京城", "微服", "微行市井")   # risk 高
    log = []
    _settle_emperor_personal(s, log)
    assert any("[风险" in x for x in log)
    assert s.event_history, "风险事件应入 event_history"
    ev = s.event_history[-1]
    assert ev.get("label") in ("史实锚", "史实方向", "合理推演"), "风险事件须带三标签"
    assert any(a.get("title") == ev["title"] for a in s.active_events)


def test_risk_miss(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.99)   # 必不命中
    s = _new_state()
    s.imperial_treasury = 10_000_000
    choose_imperial_action(s, "京城", "微服", "微行市井")
    _settle_emperor_personal(s, [])
    assert not s.event_history


def test_risk_pool_gates_and_labels():
    """风险事件池：时代门槛与三标签（花石纲 1105 / 遇刺=合理推演）。"""
    by_id = {ev["id"]: ev for ev in IMPERIAL_RISK_EVENTS}
    assert by_id["imp_huashigang_minyuan"]["era_gate"] == 1105
    assert by_id["imp_difang_yinfeng"]["era_gate"] == 1105
    assert by_id["imp_yuci_rumor"]["label"] == "合理推演"
    assert by_id["imp_huashigang_minyuan"]["label"] == "史实锚"
    # 1101 年（<1105）公开方式：花石纲/应奉 不可命中
    s = _new_state()
    got = get_imperial_risk_event(s, {"mode": "公开", "action": "巡幸东南"})
    assert got is None or got["id"] not in ("imp_huashigang_minyuan", "imp_difang_yinfeng")


# ------------------------------------------------------------
# 8) 契约 v2 validate（拒绝式）
# ------------------------------------------------------------
def test_contract_v2_valid():
    from ai.client import AIClient

    class _Stub(AIClient):
        def __init__(self, resp):
            super().__init__()
            self._resp = resp

        def _call(self, system_prompt, user_prompt="", **kw):
            return self._resp

    stub = _Stub(json.dumps({
        "location": "京城", "mode": "微服", "action": "微行市井",
        "prepared": True, "risk": "高",
        "effects": {"威望": "-小", "民心": "中"},
        "narrative": "微行市井，得闻民瘼。",
    }, ensure_ascii=False))
    r = stub.emperor_personal_decide("朝局")
    assert r["location"] == "京城" and r["action"] == "微行市井"
    assert r["mode"] == "微服" and r["prepared"] is True
    assert r["risk"] == "高"
    assert r["effects"] == {"威望": "-小", "民心": "中"}
    assert r["narrative"]


def test_contract_v2_rejected():
    """拒绝式：跨格子 action / effects 键越界 → 整单 _error。"""
    from ai.client import AIClient

    class _Stub(AIClient):
        def __init__(self, resp):
            super().__init__()
            self._resp = resp

        def _call(self, system_prompt, user_prompt="", **kw):
            return self._resp

    # 临朝 不在 京城·微服 格（跨格子非法）
    stub = _Stub(json.dumps({
        "location": "京城", "mode": "微服", "action": "临朝",
        "prepared": False, "risk": "低", "effects": {}, "narrative": "",
    }, ensure_ascii=False))
    r = stub.emperor_personal_decide("朝局")
    assert isinstance(r, dict) and r.get("_error")
    # effects 键越界（文采 不在 4 键白名单）
    stub2 = _Stub(json.dumps({
        "location": "宫里", "mode": "公开", "action": "临朝",
        "prepared": False, "risk": "低",
        "effects": {"文采": "中"}, "narrative": "",
    }, ensure_ascii=False))
    r2 = stub2.emperor_personal_decide("朝局")
    assert isinstance(r2, dict) and r2.get("_error")
    # risk 非法
    stub3 = _Stub(json.dumps({
        "location": "宫里", "mode": "公开", "action": "临朝",
        "prepared": False, "risk": "极高", "effects": {}, "narrative": "",
    }, ensure_ascii=False))
    r3 = stub3.emperor_personal_decide("朝局")
    assert isinstance(r3, dict) and r3.get("_error")


# ------------------------------------------------------------
# AI 接线：_ai_prelude 注入 _emperor_ai（契约 v2 结果）
# ------------------------------------------------------------
def test_ai_prelude_wiring():
    from fake_ai_backend import FakeAIClient

    class _Fake(FakeAIClient):
        def __init__(self):
            super().__init__()
            self.called = False

        def emperor_personal_decide(self, posture, state=None):
            self.called = True
            return {"location": "宫里", "mode": "公开", "action": "临朝",
                    "prepared": False, "risk": "低",
                    "effects": {"威望": "小"}, "narrative": "勤政。"}

    from core.commands import _ai_prelude
    s = _new_state()
    choose_imperial_action(s, "宫里", "公开", "临朝")
    fake = _Fake()
    _ai_prelude(s, fake)
    assert fake.called
    assert s._emperor_ai["effects"] == {"威望": "小"}


# ------------------------------------------------------------
# 存档：imperial_action 往返 + 旧 personal_action 迁移
# ------------------------------------------------------------
def _patch_save_dir(tmp_path, monkeypatch):
    from core import save_load
    monkeypatch.setattr(save_load, "SAVE_DIR", str(tmp_path))
    monkeypatch.setattr("memory.memory_graph.SAVE_DIR", str(tmp_path))


def test_save_load_roundtrip(tmp_path, monkeypatch):
    from core import save_load
    _patch_save_dir(tmp_path, monkeypatch)
    s = _new_state()
    choose_imperial_action(s, "京城", "微服", "微行市井")
    s.imperial_micro_count = 1
    assert save_load.save_game(s, slot=7)
    s2 = save_load.load_game(7)
    assert s2 is not None
    assert s2.imperial_action["action"] == "微行市井"
    assert s2.imperial_micro_count == 1


def test_legacy_personal_action_migration(tmp_path, monkeypatch):
    """旧档（仅 personal_action 单值）→ 加载迁移为 宫里·公开 矩阵行动。"""
    from core import save_load
    _patch_save_dir(tmp_path, monkeypatch)
    s = _new_state()
    assert save_load.save_game(s, slot=6)
    path = os.path.join(str(tmp_path), "slot_6.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("imperial_action", None)
    data["personal_action"] = "勤政"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    s2 = save_load.load_game(6)
    assert s2 is not None
    assert s2.imperial_action["location"] == "宫里"
    assert s2.imperial_action["mode"] == "公开"
    assert s2.imperial_action["action"] == "临朝"
