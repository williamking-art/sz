# -*- coding: utf-8 -*-
"""外交体系 QA 补全：拒绝式/不伪造、守恒、持久化、联动。

（合并原 game/tests 6 项 + 补全 10 项；权威位置 _dev_tools/game-dev/tests）

覆盖：
  1) 拒绝式：AI 失败 → 「国主未允所请」不达成协议；非法协议类型/档位 → 拒绝（diplomacy_dialogue 契约层）
  2) 守恒：和亲嫁妆内帑−=嫁妆；岁币调整后 _settle_finance sui_gong × mult 正确；榷场收入入国库不重复计税
  3) 持久化：treaties/_at_war/_sui_gong_mult/_trade_income 存档往返；旧档缺字段迁移补默认
  4) 联动：岁币停 → attitude 骤降(−8~−12) + mult=0；盟约 → 关系+；战争 → 边患概率+10%（缺口暴露）
"""
import os
import sys
import json

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.diplomacy_treaty import apply_treaty, TREATY_TYPES  # noqa: E402
from content.data import (  # noqa: E402
    _DIPLO_ATT, DOWRY_BASE, SUI_GONG_MULT, TRADE_INCOME,
    SUI_GONG_ANNUAL, WAR_RISK_BOOST,
)


def _new_state():
    return GameState("史实")


def _mk_client(monkeypatch, raw):
    """构造 AIClient（绕过 __init__）+ monkeypatch _call 返回固定 raw（不触网）。

    _postprocess 经 _extract_json 期望 raw 为 JSON 文本（或 None）；dict 自动转文本。
    """
    from ai.client import AIClient
    client = AIClient.__new__(AIClient)
    client.available = True
    client._prev_texts = []
    holder = {"raw": raw if raw is None or isinstance(raw, str)
              else json.dumps(raw, ensure_ascii=False)}
    monkeypatch.setattr(client, "_call", lambda *a, **k: holder["raw"])
    return client


# ------------------------------------------------------------
# 基础常量与落地（原 6 项）
# ------------------------------------------------------------
def test_constants():
    assert TREATY_TYPES == ("和亲", "岁币", "榷场", "盟约", "纳贡", "战争")
    assert _DIPLO_ATT["和亲"]["中"] == 6
    assert _DIPLO_ATT["战争"]["中"] == -12
    assert DOWRY_BASE["微"] == 50_000 and DOWRY_BASE["极"] == 700_000
    assert SUI_GONG_MULT["增"] == 1.5 and SUI_GONG_MULT["停"] == 0.0
    assert TRADE_INCOME["中"] == 100_000


def test_heqin_conservation():
    """和亲：嫁妆内帑出守恒 + attitude +6（中档）+ treaties 记录。"""
    s = _new_state()
    it0 = s.imperial_treasury
    att0 = s.external["辽"]["attitude"]
    r = apply_treaty(s, "辽", "和亲", {"tier": "中"}, year=1102, month=3)
    assert r["ok"] is True
    assert s.imperial_treasury == it0 - DOWRY_BASE["中"]
    assert s.external["辽"]["attitude"] == min(100, att0 + 6)
    assert s.treaties["辽"][-1]["type"] == "和亲"
    assert s.treaties["辽"][-1]["year"] == 1102


def test_heqin_dowry_reject():
    """嫁妆 > 内帑 → 降档到可支付；内帑全不足 → 拒绝。"""
    s = _new_state()
    s.imperial_treasury = 10_000   # 穷内帑
    r = apply_treaty(s, "辽", "和亲", {"tier": "极"})   # 70 万 > 1 万 → 降档到微 5 万仍不足 → 拒绝
    assert r["ok"] is False and "内帑不足" in r["msg"]
    s.imperial_treasury = 60_000   # 可付微档 5 万
    r2 = apply_treaty(s, "辽", "和亲", {"tier": "极"})
    assert r2["ok"] is True and s.imperial_treasury == 10_000


def test_suigong_and_trade():
    """岁币倍率 + 榷场月入（国库入，不重复计税）。"""
    s = _new_state()
    r = apply_treaty(s, "辽", "岁币", {"tier": "增"})
    assert r["ok"] is True and s._sui_gong_mult["辽"] == 1.5
    t0 = s.treasury
    r2 = apply_treaty(s, "西夏", "榷场", {"tier": "开"})
    assert r2["ok"] is True
    assert s.treasury == t0 + TRADE_INCOME["小"]
    assert s._trade_income["西夏"] == TRADE_INCOME["小"]


def test_war_and_reject():
    """战争标记 + 未知协议/对象拒绝。"""
    s = _new_state()
    att0 = s.external["金"]["attitude"]
    r = apply_treaty(s, "金", "战争", {"tier": "中"})
    assert r["ok"] is True and s._at_war["金"] == 1
    assert s.external["金"]["attitude"] == max(0, att0 - 12)
    assert apply_treaty(s, "辽", "未知协议")["ok"] is False
    assert apply_treaty(s, "高丽", "盟约")["ok"] is False


def test_roundtrip():
    """treaties 存档往返。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    apply_treaty(s, "辽", "榷场", {"tier": "小"})
    assert save_game(s, slot=5)
    s2 = load_game(5)
    assert s2 is not None
    assert s2.treaties.get("辽") and s2.treaties["辽"][-1]["type"] == "榷场"
    if os.path.exists(_slot_path(5)):
        os.remove(_slot_path(5))


# ------------------------------------------------------------
# 组 1：拒绝式 / 不伪造（diplomacy_dialogue 契约层）
# ------------------------------------------------------------
def test_diplomacy_dialogue_ai_failure_rejects(monkeypatch):
    """AI 失败（_call 返回 None）→ fallback 拒绝「国主未允所请」，不伪造协议。"""
    client = _mk_client(monkeypatch, None)
    out = client.diplomacy_dialogue("愿与贵国修好", "辽")
    assert out is not None and out.get("agreement") == "拒绝"
    assert "国主未允所请" in out.get("narrative", "")


def test_diplomacy_dialogue_invalid_rejects(monkeypatch):
    """非法协议类型 / 非法档位 / 非法对象 → 契约校验拒绝（fallback 拒绝，不落地）。"""
    for bad in (
        {"target": "辽", "stance": "友善", "agreement": "抢掠", "terms": {"tier": "中"}, "narrative": ""},
        {"target": "辽", "stance": "友善", "agreement": "岁币", "terms": {"tier": "超大"}, "narrative": ""},
        {"target": "高丽", "stance": "友善", "agreement": "盟约", "terms": {"tier": "中"}, "narrative": ""},
        "这不是 JSON",
    ):
        client = _mk_client(monkeypatch, bad)
        out = client.diplomacy_dialogue("议和", "辽")
        assert out.get("agreement") == "拒绝", f"非法输入应拒绝：{bad}"
        assert "国主未允所请" in out.get("narrative", "")


def test_diplomacy_dialogue_valid_passthrough(monkeypatch):
    """合法协议（岁币/中）→ 契约透传，供 apply_treaty 落地。

    注：diplomacy_dialogue 的 terms.tier 白名单为 5 档（微|小|中|大|极），
    岁币专用档位（增/减/停）与榷场档位（开/扩/停）不在其中——岁币"增 1.5×/停 0×"
    无法经对话表达（会落默认 1.0×），属契约词表对齐缺口，见交付报告。
    """
    raw = {"target": "辽", "stance": "友善", "agreement": "岁币",
           "terms": {"岁币": "增"}, "narrative": "岁币可增。"}
    client = _mk_client(monkeypatch, raw)
    out = client.diplomacy_dialogue("请增岁币", "辽")
    assert out["agreement"] == "岁币" and out["terms"]["tier"] == "增"


# ------------------------------------------------------------
# 组 2：守恒
# ------------------------------------------------------------
def test_suigong_mult_in_finance():
    """岁币调整后 _settle_finance sui_gong × mult 正确（辽 attitude≥60 时）。"""
    from core.settlement_steps import _settle_finance
    # mult=1.5（增）→ 岁币 = 年基准×0.6/12×1.5
    s = _new_state()
    s.external["辽"]["attitude"] = 60
    s._sui_gong_mult["辽"] = 1.5
    log = []
    _settle_finance(s, log)
    sui = [l for l in log if "[岁币]" in l]
    assert sui, "辽 attitude≥60 应产生岁币"
    expected = int(SUI_GONG_ANNUAL * 0.6 / 12 * 1.5)
    assert f"{expected}" in sui[0], f"岁币×mult 不符：{sui[0]} 期望 {expected}"
    # mult=0（停）→ 岁币 0（无岁币日志）
    s2 = _new_state()
    s2.external["辽"]["attitude"] = 60
    s2._sui_gong_mult["辽"] = 0.0
    log2 = []
    _settle_finance(s2, log2)
    assert not any("[岁币]" in l for l in log2), "岁币停（mult=0）不应产生岁币支出"


def test_trade_income_not_in_tax_base():
    """榷场收入不重复计税：TRADE_INCOME 不入工商/市舶/田赋税基（独立税源）。"""
    s = _new_state()
    c0, m0 = s.calc_commerce(), s.calc_maritime_trade()
    t0, _ = s.calc_monthly_tax_income(1.0)
    s._trade_income["西夏"] = TRADE_INCOME["中"]
    s.treasury += TRADE_INCOME["中"]   # 模拟 apply_treaty 入库（仅国库，不进税基）
    assert s.calc_commerce() == c0, "榷场收入不应进工商税基"
    assert s.calc_maritime_trade() == m0, "榷场收入不应进市舶税基"
    t1, _ = s.calc_monthly_tax_income(1.0)
    assert t1 == t0, "榷场收入不应进田赋/二税折色税基"


# ------------------------------------------------------------
# 组 3：持久化
# ------------------------------------------------------------
def test_treaty_fields_roundtrip():
    """外交字段（_at_war/_sui_gong_mult/_trade_income + 多势力协议历史）存档往返。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    apply_treaty(s, "辽", "岁币", {"tier": "增"})
    apply_treaty(s, "金", "战争", {"tier": "小"})
    apply_treaty(s, "西夏", "榷场", {"tier": "开"})
    assert save_game(s, slot=6)
    s2 = load_game(6)
    assert s2 is not None
    assert s2._at_war.get("金") == 1
    assert s2._sui_gong_mult["辽"] == 1.5
    assert s2._trade_income["西夏"] == TRADE_INCOME["小"]
    assert [t["type"] for t in s2.treaties["辽"]] == ["岁币"]
    assert [t["type"] for t in s2.treaties["金"]] == ["战争"]
    assert [t["type"] for t in s2.treaties["西夏"]] == ["榷场"]
    if os.path.exists(_slot_path(6)):
        os.remove(_slot_path(6))


def test_treaty_migration_defaults():
    """旧档缺 _at_war/_sui_gong_mult/_trade_income → load 补默认（不崩溃）。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    assert save_game(s, slot=7)
    p = _slot_path(7)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_at_war", None)
    data.pop("_sui_gong_mult", None)
    data.pop("_trade_income", None)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    s2 = load_game(7)
    assert s2 is not None
    assert s2._at_war == {}
    assert s2._sui_gong_mult == {"辽": 1.0, "金": 1.0, "西夏": 1.0}
    assert s2._trade_income == {}
    if os.path.exists(p):
        os.remove(p)
    from content.data import SAVE_DIR
    _db = os.path.join(SAVE_DIR, "slot_7.db")
    if os.path.exists(_db):
        os.remove(_db)


# ------------------------------------------------------------
# 组 4：联动
# ------------------------------------------------------------
def test_suigong_stop_attitude_plunge():
    """岁币停 → attitude 骤降（−8~−12 内）+ mult=0 + 协议记录。"""
    s = _new_state()
    att0 = s.external["辽"]["attitude"]
    r = apply_treaty(s, "辽", "岁币", {"tier": "停"})
    assert r["ok"] is True
    delta = s.external["辽"]["attitude"] - att0
    assert -12 <= delta <= -8, f"岁币停应 attitude 骤降 −8~−12：Δ={delta}"
    assert s._sui_gong_mult["辽"] == 0.0
    assert s.treaties["辽"][-1]["type"] == "岁币"
    assert s.treaties["辽"][-1]["terms"].get("tier") == "停"


def test_alliance_relation_boost():
    """盟约（结）→ 关系 +6。"""
    s = _new_state()
    att0 = s.external["金"]["attitude"]
    r = apply_treaty(s, "金", "盟约", {"tier": "结"})
    assert r["ok"] is True
    assert s.external["金"]["attitude"] == min(100, att0 + _DIPLO_ATT["盟约"]["结"])
    assert s.treaties["金"][-1]["type"] == "盟约"


def test_war_border_risk_consumed():
    """战争协议 → 边患概率 +10%（WAR_RISK_BOOST）应被消费。

    当前实现缺口：apply_treaty 只写 _at_war 标记，WAR_RISK_BOOST 在 core 无消费点
    （无逻辑提升 invasion_will/边患事件压力）——本断言预期失败，暴露待补联动。
    """
    s = _new_state()
    iw0 = s.external["金"].get("invasion_will", 0)
    ep0 = s.event_pressure.get("金军南侵", 0)
    r = apply_treaty(s, "金", "战争", {"tier": "中"})
    assert r["ok"] is True and s._at_war["金"] == 1, "战争标记应落地"
    # 边患概率 +10%（WAR_RISK_BOOST）应提升可见的战争风险载体
    iw1 = s.external["金"].get("invasion_will", 0)
    ep1 = s.event_pressure.get("金军南侵", 0)
    assert iw1 >= iw0 + 10 or ep1 >= ep0 + 10, \
        f"BUG: 战争协议后边患概率未 +10%（WAR_RISK_BOOST={WAR_RISK_BOOST} 未消费）：" \
        f"invasion_will {iw0}→{iw1}、金军南侵压力 {ep0}→{ep1}"


if __name__ == "__main__":
    test_constants()
    test_heqin_conservation()
    test_heqin_dowry_reject()
    test_suigong_and_trade()
    test_war_and_reject()
    test_suigong_stop_attitude_plunge()
    test_alliance_relation_boost()
    print("DIPLOMACY TREATY QA PASSED")
