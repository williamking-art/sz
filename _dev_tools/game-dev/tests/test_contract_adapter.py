# -*- coding: utf-8 -*-
"""T5 契约统一测试：contract_adapter 映射表（推演类→changes / 叙事类→{changes,narrative}）。

⚠️ **接线状态（2026-09-18 测试体检复核）**：`ai/contract_adapter.py` 在 `core/`、`ai/`、
`engine/`、`backend/`、`content/` 中**没有任何生产调用方**（仅被本文件引用）——
即本文件全部用例测的是**当前未接线的模块**。它们验证的是映射表本身的正确性，
在接线前**不能**作为"AI 契约已在线上生效"的证据。
若要让本文件成为线上行为验证，需先把 `to_unified` 接进 `agent_router` / `state_applier` 链路。
"""
from ai.contract_adapter import (
    CONTRACT_FIELD_MAP, NARRATIVE_FIELD_MAP, to_changes, to_unified,
)


def test_economy_changes_full_fields():
    """economy_decide：13 字段全部映射为 changes（含金融 5 字段，保留既有语义）。"""
    eco = {"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中",
           "窖银": "无", "城市化": "大", "回乡": "微", "科举": "中",
           "jiaozi_trust": "稳", "shortage": "平", "maritime": "兴",
           "bank": "稳", "price_trend": "平"}
    ch = to_changes("economy_decide", eco)
    assert len(ch) == 13
    fields = {c["field"] for c in ch}
    assert fields == set(CONTRACT_FIELD_MAP["economy_decide"])
    by_field = {c["field"]: c["delta_tier"] for c in ch}
    assert by_field["士绅"] == "抛" and by_field["jiaozi_trust"] == "稳"
    assert by_field["price_trend"] == "平"


def test_diplomacy_military_changes():
    """diplomacy/military：档位字段 → changes（表达层，不改落地）。"""
    d = {"attitude": "大", "sui_gong": "订", "alliance": "结"}
    ch = to_changes("diplomacy_decide", d)
    assert ch == [{"field": "attitude", "delta_tier": "大"},
                  {"field": "sui_gong", "delta_tier": "订"},
                  {"field": "alliance", "delta_tier": "结"}]
    m = {"power": "中", "army": "大", "training": "中", "morale": "小", "levy": "中"}
    assert len(to_changes("military_decide", m)) == 5


def test_unknown_contract_fallback():
    """未列契约（finance_decide 等）：顶层标量键全部透传（通用 fallback 全覆盖）。"""
    fin = {"commerce": "中", "tax_fair": "小", "narrative": "度支平稳。"}
    ch = to_changes("finance_decide", fin)
    by = {c["field"] for c in ch}
    assert by == {"commerce", "tax_fair"}     # narrative 为文本，不进 changes


def test_error_passthrough():
    """_error 契约：统一视图透传 _error，不伪造 changes/narrative。"""
    err = {"_error": "AI_NOT_CONFIGURED", "kind": "free_effect"}
    uni = to_unified("economy_decide", err)
    assert uni["_error"] == "AI_NOT_CONFIGURED"
    assert uni["changes"] == [] and uni["narrative"] == ""


def test_narrative_unified():
    """叙事类 → {changes, narrative}：narrative 主、changes 空（叙事不改状态）。"""
    report = {"report": "是岁四海承平。", "scenes": [{"scene": "其一", "text": "禁中"}]}
    uni = to_unified("monthly_report", report)
    assert uni["narrative"] == "是岁四海承平。"
    assert uni["changes"] == []

    dia = {"reply": "臣窃以为不可。", "mood": "小", "intent_hint": "守成"}
    uni2 = to_unified("dialogue", dia)
    assert uni2["narrative"] == "臣窃以为不可。"
    assert uni2["changes"] == []

    cr = {"memo": "工部奏请拨银。", "verdict": "可准"}
    uni3 = to_unified("council_review", cr)
    assert uni3["narrative"] == "工部奏请拨银。"
    assert uni3["changes"] == []


def test_free_effect_unified():
    """free_effect_decide：effects 语义保留在契约自身，adapter 不拍平（narrative 取叙事字段）。"""
    fe = {"mode": "once", "effects": {"govern": "中"}, "cost": {"treasury": 50000},
          "narrative": "老兵治乡，乡里得安。"}
    uni = to_unified("free_effect_decide", fe)
    assert uni["narrative"] == "老兵治乡，乡里得安。"
    assert uni["changes"] == []          # effects/cost 是 dict/list，落地走 free_effect 原链路
