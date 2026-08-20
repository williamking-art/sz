# -*- coding: utf-8 -*-
"""AI 契约回归测试：档位换算 / 效果字典 / 白名单。"""
import json

from ai.client_utils import (
    tier_to_value, effects_to_dict, _EFFECT_WHITELIST, _normalize_decree_effects,
)


def test_tier_to_value_basic():
    """档位 × 基准 × 皇威乘数（7 档：大 1.5、巨 2.0、极 2.5）。"""
    assert tier_to_value("prestige", "中", 1.0) == 4      # 4×1.0×1.0
    assert tier_to_value("prestige", "大", 1.0) == 6      # 4×1.5=6
    assert tier_to_value("prestige", "巨", 1.0) == 8      # 4×2.0=8
    assert tier_to_value("prestige", "微", 1.0) == 1      # 4×0.25=1.0
    # 丰富表达归一
    assert tier_to_value("prestige", "些许", 1.0) == 1   # 些许→微
    assert tier_to_value("prestige", "海啸", 1.0) == 10  # 海啸→极 4×2.5=10


def test_tier_to_value_cap():
    """单项封顶。"""
    assert tier_to_value("treasury", "大", 2.0) == 2_400_000   # 800000×1.5×2=240 万
    assert tier_to_value("treasury", "大", 3.0) == 3_000_000   # 360 万 → 封顶 300 万


def test_tier_to_value_commerce_tax():
    """工商征率是设定值（档位→税率），非增量（7 档：大 0.25、巨 0.30、极 0.35）。"""
    assert tier_to_value("commerce_tax", "中", 1.0) == 0.20
    assert tier_to_value("commerce_tax", "大", 1.0) == 0.25
    assert tier_to_value("commerce_tax", "无", 1.0) == 0.05


def test_tier_to_value_unknown_dim():
    """未知维度返回 0，不抛异常。"""
    assert tier_to_value("nonexistent", "中", 1.0) == 0


def test_effects_to_dict_basic():
    eff = [{"dim": "prestige", "tier": "中"}]
    assert effects_to_dict(eff, 1.0) == {"prestige": 4}


def test_effects_to_dict_faction_change():
    """faction_change 用 prestige 档位换算各派系数值。"""
    eff = [{"dim": "faction_change", "value": {"旧党": "中", "新党": "小"}}]
    out = effects_to_dict(eff, 1.0)
    assert out["faction_change"]["旧党"] == 4   # 中档
    assert out["faction_change"]["新党"] == 2   # 小档 4×0.5


def test_effects_to_dict_commerce_tax_precise():
    """commerce_tax 优先用精确 value，无 value 回退档位。"""
    eff = [{"dim": "commerce_tax", "value": 0.18}]
    assert effects_to_dict(eff, 1.0)["commerce_tax"] == 0.18
    eff2 = [{"dim": "commerce_tax", "tier": "大"}]
    assert effects_to_dict(eff2, 1.0)["commerce_tax"] == 0.25


def test_effect_whitelist_17_keys():
    """白名单与 _TIER_BASE 对齐（17 维度）。"""
    assert len(_EFFECT_WHITELIST) == 17
    for k in ("prestige", "treasury", "land_survey", "hoard", "commerce_tax", "reform"):
        assert k in _EFFECT_WHITELIST


def test_normalize_decree_effects():
    """归一化：只留白名单键 + 强制数值类型，非法键/非法值丢弃。"""
    out = _normalize_decree_effects({"prestige": "4", "bad_key": "999", "treasury": "abc"})
    assert out == {"prestige": 4.0}


def test_economy_decide_vault_tier_contract(monkeypatch):
    """economy_decide 契约：窖银 白名单 无|微|小|中|大，缺失/非法兜底「无」，失败兜底 None。

    假后端：monkeypatch AIClient._call 返回固定 raw，不触网、不携带任何 api_key。
    """
    from ai.client import AIClient

    client = AIClient.__new__(AIClient)   # 绕过 __init__，无需真实密钥
    client.available = True
    client._prev_texts = []
    holder = {}
    monkeypatch.setattr(client, "_call", lambda *a, **k: holder.get("raw"))

    def decide(raw, posture="国库紧张，粮价高企。"):
        holder["raw"] = raw
        return client.economy_decide(posture)

    # 合法档位透传（既有字段不受影响；金融 5 字段三态词）
    out = decide(json.dumps({"景气": "中", "士绅": "抛", "士绅力度": "小",
                             "生产": "中", "窖银": "大",
                             "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                             "bank": "稳", "price_trend": "平"}, ensure_ascii=False))
    assert out["窖银"] == "大"
    assert (out["景气"], out["士绅"], out["士绅力度"], out["生产"]) == ("中", "抛", "小", "中")

    # 非法档位 → 兜底「无」（不开窖冻结）
    out = decide(json.dumps({"景气": "中", "士绅": "抛", "士绅力度": "小",
                             "生产": "中", "窖银": "倾巢出动",
                             "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                             "bank": "稳", "price_trend": "平"}, ensure_ascii=False))
    assert out["窖银"] == "无"

    # 缺失字段 → 默认「无」
    out = decide(json.dumps({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中",
                             "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                             "bank": "稳", "price_trend": "平"}, ensure_ascii=False))
    assert out["窖银"] == "无"

    # 整体失败（非 JSON）→ None，调用方按「无 AI」处理（窖银冻结不动用）
    assert decide("这不是 JSON") is None


def test_economy_decide_mobility_tier_contract(monkeypatch):
    """economy_decide 契约：城市化/回乡/科举 白名单 无|微|小|中|大（与窖银同构）。

    假后端：monkeypatch AIClient._call 返回固定 raw，不触网、不携带任何 api_key。
    """
    from ai.client import AIClient

    client = AIClient.__new__(AIClient)   # 绕过 __init__，无需真实密钥
    client.available = True
    client._prev_texts = []
    holder = {}
    monkeypatch.setattr(client, "_call", lambda *a, **k: holder.get("raw"))

    def decide(raw, posture="景气萧条，米贵。"):
        holder["raw"] = raw
        return client.economy_decide(posture)

    base = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中", "窖银": "无",
            "jiaozi_trust": "稳", "shortage": "平", "maritime": "平", "bank": "稳",
            "price_trend": "平"}

    # 合法档位透传（既有字段不受影响）
    out = decide(json.dumps(dict(base, 城市化="大", 回乡="微", 科举="中"), ensure_ascii=False))
    assert (out["城市化"], out["回乡"], out["科举"]) == ("大", "微", "中")
    assert out["窖银"] == "无" and out["景气"] == "中"

    # 非法档位 → 兜底「无」（动向不发生）
    out = decide(json.dumps(dict(base, 城市化="蜂拥", 回乡="返乡潮", 科举="扩招"),
                            ensure_ascii=False))
    assert (out["城市化"], out["回乡"], out["科举"]) == ("无", "无", "无")

    # 缺失字段 → 默认「无」
    out = decide(json.dumps(base, ensure_ascii=False))
    assert (out["城市化"], out["回乡"], out["科举"]) == ("无", "无", "无")

    # 整体失败（非 JSON）→ None，调用方按「无 AI」处理（各动向默认关闭）
    assert decide("这不是 JSON") is None
