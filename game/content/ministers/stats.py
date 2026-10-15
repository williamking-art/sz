# -*- coding: utf-8 -*-
"""北宋官员量化能力五维模型、动态历练成长与全战式特质演进系统。

## 规格与背景（Jev 裁定：JEV-台账-官员量化五维与全战式特质演进系统-2026-10-15）

1. **五维量化能力（1~100 分值排列）**：
   - **政略（governance）**：影响地方治理、知通连署、公事效率、积压消减与抚辑流民；
   - **财计（finance）**：影响赋税入库、度支调度、平抑粮价物价、常平仓与官营放贷盈余；
   - **军略（military）**：影响帅司防区防备、沿边御敌战力、士卒操练上限与城防工事；
   - **谋断（strategy）**：影响朝争话语权、诏令三省会签封驳阻力、言路弹劾与洞察机先；
   - **风望（reputation）**：士大夫声望、清流认同度、抗贪腐侵蚀能力与士绅民心支持。

2. **历练成长机制（Exp & Growth）**：
   - 官员在各部司、地方州府任职，根据其所办政务（督税、治水、抚民、御敌、谏诤）积累对应经验；
   - 经验达标时属性突破提升（受潜质 potential 上限约束）；
   - 官员年老（>68岁）或怠政腐化可能出现部分属性小幅折损。

3. **全战式特质动态演进（Total War Traits Evolution）**：
   - 记录官员在任历练行为计数器（triggers）：
     `fiscal_months`、`governance_months`、`military_border_months`、
     `remonstrance_count`、`appease_count`、`corrupt_acts`、`battle_victories`、`counsel_count`；
   - 达标后动态获得新机制特质（如【理财】、【聚敛】、【刚直】、【忠勇】、【调停】、【才艺】等），
     或者洗去对立特质（如【刚直】冲抵【阿附】，【聚敛】冲抵【清正】）。

4. **全员覆盖杜绝后期白板**：
   - 中枢 43 位历史名臣史实量化配置；
   - 21 路监司与 136 州府亲民官初始化量化；
   - 科举及第进士（状元、榜眼、探花、二甲及第、三甲同进士）由标准生成器构建完备档案。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# 五维中英名称映射
ATTRIBUTE_NAMES: Dict[str, str] = {
    "governance": "政略",
    "finance": "财计",
    "military": "军略",
    "strategy": "谋断",
    "reputation": "风望",
}

# 43 位中枢历史名臣五维考据配置（1~100，潜在上限 1~100）
HISTORICAL_MINISTER_STATS: Dict[str, Dict[str, Any]] = {
    "韩忠彦": {
        "attrs": {"governance": 82, "finance": 70, "military": 45, "strategy": 78, "reputation": 88},
        "potential": {"governance": 88, "finance": 78, "military": 55, "strategy": 84, "reputation": 92},
    },
    "曾布": {
        "attrs": {"governance": 88, "finance": 92, "military": 55, "strategy": 90, "reputation": 72},
        "potential": {"governance": 94, "finance": 98, "military": 65, "strategy": 95, "reputation": 80},
    },
    "蔡京": {
        "attrs": {"governance": 90, "finance": 96, "military": 40, "strategy": 93, "reputation": 32},
        "potential": {"governance": 95, "finance": 99, "military": 50, "strategy": 98, "reputation": 45},
    },
    "李清臣": {
        "attrs": {"governance": 80, "finance": 72, "military": 42, "strategy": 76, "reputation": 84},
        "potential": {"governance": 86, "finance": 78, "military": 50, "strategy": 82, "reputation": 89},
    },
    "赵挺之": {
        "attrs": {"governance": 78, "finance": 68, "military": 38, "strategy": 82, "reputation": 85},
        "potential": {"governance": 85, "finance": 75, "military": 48, "strategy": 88, "reputation": 90},
    },
    "邓洵武": {
        "attrs": {"governance": 84, "finance": 78, "military": 40, "strategy": 86, "reputation": 65},
        "potential": {"governance": 90, "finance": 85, "military": 50, "strategy": 92, "reputation": 75},
    },
    "陈瓘": {
        "attrs": {"governance": 75, "finance": 62, "military": 35, "strategy": 85, "reputation": 92},
        "potential": {"governance": 82, "finance": 70, "military": 45, "strategy": 90, "reputation": 96},
    },
    "陈师锡": {
        "attrs": {"governance": 74, "finance": 65, "military": 36, "strategy": 82, "reputation": 90},
        "potential": {"governance": 80, "finance": 72, "military": 45, "strategy": 88, "reputation": 95},
    },
    "丰稷": {
        "attrs": {"governance": 76, "finance": 68, "military": 35, "strategy": 83, "reputation": 89},
        "potential": {"governance": 84, "finance": 75, "military": 46, "strategy": 88, "reputation": 94},
    },
    "童贯": {
        "attrs": {"governance": 70, "finance": 75, "military": 84, "strategy": 82, "reputation": 45},
        "potential": {"governance": 78, "finance": 82, "military": 90, "strategy": 88, "reputation": 55},
    },
    "种师道": {
        "attrs": {"governance": 72, "finance": 65, "military": 92, "strategy": 84, "reputation": 88},
        "potential": {"governance": 80, "finance": 72, "military": 96, "strategy": 89, "reputation": 94},
    },
    "姚古": {
        "attrs": {"governance": 68, "finance": 60, "military": 86, "strategy": 75, "reputation": 78},
        "potential": {"governance": 75, "finance": 68, "military": 90, "strategy": 80, "reputation": 84},
    },
    "刘延庆": {
        "attrs": {"governance": 55, "finance": 52, "military": 68, "strategy": 58, "reputation": 50},
        "potential": {"governance": 65, "finance": 60, "military": 75, "strategy": 68, "reputation": 60},
    },
    "刘法": {
        "attrs": {"governance": 62, "finance": 55, "military": 90, "strategy": 78, "reputation": 82},
        "potential": {"governance": 70, "finance": 62, "military": 95, "strategy": 84, "reputation": 88},
    },
    "李纲": {
        "attrs": {"governance": 82, "finance": 74, "military": 86, "strategy": 85, "reputation": 92},
        "potential": {"governance": 90, "finance": 82, "military": 92, "strategy": 90, "reputation": 98},
    },
    "宗泽": {
        "attrs": {"governance": 85, "finance": 78, "military": 90, "strategy": 88, "reputation": 94},
        "potential": {"governance": 92, "finance": 85, "military": 95, "strategy": 92, "reputation": 99},
    },
    "张叔夜": {
        "attrs": {"governance": 80, "finance": 72, "military": 84, "strategy": 80, "reputation": 88},
        "potential": {"governance": 88, "finance": 78, "military": 89, "strategy": 86, "reputation": 93},
    },
    "韩世忠": {
        "attrs": {"governance": 65, "finance": 58, "military": 94, "strategy": 80, "reputation": 86},
        "potential": {"governance": 75, "finance": 68, "military": 98, "strategy": 88, "reputation": 92},
    },
    "岳飞": {
        "attrs": {"governance": 72, "finance": 65, "military": 98, "strategy": 88, "reputation": 96},
        "potential": {"governance": 85, "finance": 75, "military": 100, "strategy": 94, "reputation": 100},
    },
    "赵桓": {
        "attrs": {"governance": 45, "finance": 42, "military": 30, "strategy": 48, "reputation": 60},
        "potential": {"governance": 65, "finance": 60, "military": 50, "strategy": 68, "reputation": 72},
    },
    "赵楷": {
        "attrs": {"governance": 70, "finance": 65, "military": 35, "strategy": 75, "reputation": 78},
        "potential": {"governance": 82, "finance": 74, "military": 45, "strategy": 85, "reputation": 88},
    },
    "蒋之奇": {
        "attrs": {"governance": 82, "finance": 88, "military": 78, "strategy": 84, "reputation": 76},
        "potential": {"governance": 88, "finance": 92, "military": 84, "strategy": 89, "reputation": 82},
    },
    "章楶": {
        "attrs": {"governance": 80, "finance": 76, "military": 93, "strategy": 88, "reputation": 86},
        "potential": {"governance": 86, "finance": 82, "military": 97, "strategy": 92, "reputation": 92},
    },
    "陆佃": {
        "attrs": {"governance": 84, "finance": 75, "military": 45, "strategy": 80, "reputation": 88},
        "potential": {"governance": 90, "finance": 82, "military": 55, "strategy": 86, "reputation": 92},
    },
    "温益": {
        "attrs": {"governance": 80, "finance": 75, "military": 38, "strategy": 85, "reputation": 62},
        "potential": {"governance": 86, "finance": 80, "military": 48, "strategy": 90, "reputation": 70},
    },
    "吴居厚": {
        "attrs": {"governance": 82, "finance": 90, "military": 45, "strategy": 80, "reputation": 52},
        "potential": {"governance": 88, "finance": 95, "military": 55, "strategy": 85, "reputation": 62},
    },
    "王古": {
        "attrs": {"governance": 84, "finance": 92, "military": 40, "strategy": 80, "reputation": 82},
        "potential": {"governance": 90, "finance": 96, "military": 50, "strategy": 86, "reputation": 88},
    },
    "江公望": {
        "attrs": {"governance": 78, "finance": 68, "military": 36, "strategy": 85, "reputation": 90},
        "potential": {"governance": 85, "finance": 75, "military": 45, "strategy": 90, "reputation": 95},
    },
    "陈次升": {
        "attrs": {"governance": 80, "finance": 72, "military": 42, "strategy": 84, "reputation": 88},
        "potential": {"governance": 86, "finance": 78, "military": 50, "strategy": 89, "reputation": 93},
    },
    "唐恪": {
        "attrs": {"governance": 82, "finance": 86, "military": 48, "strategy": 78, "reputation": 74},
        "potential": {"governance": 88, "finance": 92, "military": 58, "strategy": 84, "reputation": 80},
    },
    "聂昌": {
        "attrs": {"governance": 80, "finance": 74, "military": 55, "strategy": 80, "reputation": 76},
        "potential": {"governance": 86, "finance": 80, "military": 65, "strategy": 85, "reputation": 82},
    },
    "蔡攸": {
        "attrs": {"governance": 70, "finance": 76, "military": 52, "strategy": 82, "reputation": 40},
        "potential": {"governance": 78, "finance": 82, "military": 60, "strategy": 88, "reputation": 50},
    },
    "何执中": {
        "attrs": {"governance": 78, "finance": 76, "military": 40, "strategy": 80, "reputation": 65},
        "potential": {"governance": 85, "finance": 82, "military": 48, "strategy": 85, "reputation": 72},
    },
    "郑居中": {
        "attrs": {"governance": 76, "finance": 72, "military": 45, "strategy": 78, "reputation": 70},
        "potential": {"governance": 82, "finance": 78, "military": 55, "strategy": 84, "reputation": 78},
    },
    "余深": {
        "attrs": {"governance": 72, "finance": 74, "military": 35, "strategy": 76, "reputation": 55},
        "potential": {"governance": 78, "finance": 80, "military": 45, "strategy": 82, "reputation": 62},
    },
    "王黼": {
        "attrs": {"governance": 82, "finance": 88, "military": 40, "strategy": 86, "reputation": 48},
        "potential": {"governance": 88, "finance": 94, "military": 50, "strategy": 90, "reputation": 58},
    },
    "朱勔": {
        "attrs": {"governance": 68, "finance": 85, "military": 35, "strategy": 78, "reputation": 30},
        "potential": {"governance": 75, "finance": 92, "military": 45, "strategy": 82, "reputation": 40},
    },
    "林摅": {
        "attrs": {"governance": 75, "finance": 70, "military": 38, "strategy": 76, "reputation": 50},
        "potential": {"governance": 82, "finance": 78, "military": 48, "strategy": 82, "reputation": 58},
    },
    "张商英": {
        "attrs": {"governance": 86, "finance": 84, "military": 60, "strategy": 85, "reputation": 80},
        "potential": {"governance": 92, "finance": 90, "military": 70, "strategy": 90, "reputation": 88},
    },
    "梁师成": {
        "attrs": {"governance": 75, "finance": 78, "military": 42, "strategy": 88, "reputation": 42},
        "potential": {"governance": 82, "finance": 85, "military": 50, "strategy": 92, "reputation": 50},
    },
    "杨戬": {
        "attrs": {"governance": 70, "finance": 86, "military": 40, "strategy": 78, "reputation": 35},
        "potential": {"governance": 78, "finance": 92, "military": 48, "strategy": 84, "reputation": 45},
    },
    "高俅": {
        "attrs": {"governance": 65, "finance": 68, "military": 72, "strategy": 76, "reputation": 58},
        "potential": {"governance": 72, "finance": 75, "military": 80, "strategy": 82, "reputation": 65},
    },
    "侯蒙": {
        "attrs": {"governance": 84, "finance": 82, "military": 55, "strategy": 85, "reputation": 88},
        "potential": {"governance": 90, "finance": 88, "military": 65, "strategy": 90, "reputation": 94},
    },
}

# 全战式动态特质演化规则（经历计数器与条件检定）
TRAIT_EVOLUTION_RULES = [
    {
        "trait_id": "理财",
        "condition": lambda r: (
            r["triggers"].get("fiscal_months", 0) >= 12
            and r["attrs"].get("finance", 0) >= 75
            and r["triggers"].get("corrupt_acts", 0) <= 1
        ),
        "gain_msg": "【理财】通晓钱谷度支，善于调度国库仓廪",
        "incompatible": [],
    },
    {
        "trait_id": "聚敛",
        "condition": lambda r: (
            r["triggers"].get("corrupt_acts", 0) >= 3
            or (r["triggers"].get("fiscal_months", 0) >= 6 and r.get("corruption", 0.0) >= 0.60)
        ),
        "gain_msg": "【聚敛】搜括民财以媚上，府库虽盈而民望渐失",
        "incompatible": ["清正"],
    },
    {
        "trait_id": "刚直",
        "condition": lambda r: (
            r["triggers"].get("remonstrance_count", 0) >= 3
            and r["attrs"].get("reputation", 0) >= 70
        ),
        "gain_msg": "【刚直】骨鲠敢谏，犯颜直陈不避权贵",
        "incompatible": ["阿附"],
    },
    {
        "trait_id": "清正",
        "condition": lambda r: (
            r["triggers"].get("governance_months", 0) + r["triggers"].get("fiscal_months", 0) >= 24
            and r.get("corruption", 0.0) <= 0.20
            and r["attrs"].get("reputation", 0) >= 75
        ),
        "gain_msg": "【清正】廉洁奉公，两袖清风，士民称善",
        "incompatible": ["聚敛"],
    },
    {
        "trait_id": "军略",
        "condition": lambda r: (
            r["triggers"].get("battle_victories", 0) >= 2
            or (r["triggers"].get("military_border_months", 0) >= 18 and r["attrs"].get("military", 0) >= 70)
        ),
        "gain_msg": "【军略】深通兵机，号令森严，善御强虏",
        "incompatible": ["怯懦"],
    },
    {
        "trait_id": "忠勇",
        "condition": lambda r: (
            r["triggers"].get("battle_victories", 0) >= 1
            and r["triggers"].get("battle_defeats", 0) == 0
            and r.get("loyalty", 0.0) >= 0.70
        ),
        "gain_msg": "【忠勇】临难死节，身先士卒，赤心报国",
        "incompatible": ["怯懦"],
    },
    {
        "trait_id": "怯懦",
        "condition": lambda r: (
            r["triggers"].get("battle_defeats", 0) >= 2
            or (r["triggers"].get("battle_defeats", 0) >= 1 and r.get("loyalty", 0.0) <= 0.40)
        ),
        "gain_msg": "【怯懦】临阵自保，畏刀避箭，望敌先溃",
        "incompatible": ["忠勇", "刚直"],
    },
    {
        "trait_id": "权谋",
        "condition": lambda r: (
            r["triggers"].get("counsel_count", 0) >= 10
            and r["attrs"].get("strategy", 0) >= 80
        ),
        "gain_msg": "【权谋】巧弄机变，深谋机杼，纵横朝堂",
        "incompatible": [],
    },
    {
        "trait_id": "阿附",
        "condition": lambda r: (
            r["triggers"].get("counsel_count", 0) >= 4
            and r["attrs"].get("reputation", 0) <= 58
            and r.get("loyalty", 0.0) >= 0.70
        ),
        "gain_msg": "【阿附】揣摩上意，附势逢迎以固禄位",
        "incompatible": ["刚直"],
    },
    {
        "trait_id": "调停",
        "condition": lambda r: (
            r["triggers"].get("appease_count", 0) >= 3
            and r["attrs"].get("governance", 0) >= 72
        ),
        "gain_msg": "【调停】持平守中，调和两党争执，使公事得行",
        "incompatible": [],
    },
    {
        "trait_id": "才艺",
        "condition": lambda r: (
            r["triggers"].get("literary_works", 0) >= 5
            and (r["attrs"].get("reputation", 0) >= 70 or r["attrs"].get("strategy", 0) >= 70)
        ),
        "gain_msg": "【才艺】翰墨风流，词采清发，文动禁省",
        "incompatible": [],
    },
]


def format_official_stats(stats: Dict[str, Any]) -> str:
    """三国志风格数字排列文本格式化。
    
    输出示例：
    政略 88 | 财计 94 | 军略 42 | 谋断 85 | 风望 76
    """
    attrs = stats.get("attrs", {}) if isinstance(stats, dict) else {}
    parts = []
    for k, cn in ATTRIBUTE_NAMES.items():
        v = int(attrs.get(k, 50))
        parts.append(f"{cn} {v:2d}")
    return " | ".join(parts)


def init_official_profile(name: str, rank: str = "", faction: str = "中立派",
                          traits: Optional[List[str]] = None,
                          custom_attrs: Optional[Dict[str, int]] = None,
                          loyalty: float = 0.55, corruption: float = 0.25) -> Dict[str, Any]:
    """生成一位标准官员的量化档案。"""
    # 默认属性按品阶/历史档案智能派生
    if custom_attrs:
        base_attrs = dict(custom_attrs)
    elif name in HISTORICAL_MINISTER_STATS:
        base_attrs = dict(HISTORICAL_MINISTER_STATS[name]["attrs"])
    else:
        # 通用官员按官衔品级赋予基线（七品 55~65，五品 65~75，三品 75~85）
        base_val = 60
        if any(k in rank for k in ("一品", "二品", "三品", "尚书", "枢密", "宰相")):
            base_val = 78
        elif any(k in rank for k in ("四品", "五品", "知府", "知州", "侍郎")):
            base_val = 68
        elif any(k in rank for k in ("六品", "七品", "通判", "知县")):
            base_val = 58

        rnd = random.Random(sum(ord(c) for c in name))
        base_attrs = {
            "governance": max(30, min(95, base_val + rnd.randint(-6, 8))),
            "finance": max(30, min(95, base_val + rnd.randint(-8, 6))),
            "military": max(25, min(95, base_val - 10 + rnd.randint(-10, 10))),
            "strategy": max(30, min(95, base_val + rnd.randint(-5, 7))),
            "reputation": max(30, min(95, base_val + rnd.randint(-7, 7))),
        }

    # 潜质上限（资质）
    potential = {}
    if name in HISTORICAL_MINISTER_STATS:
        potential = dict(HISTORICAL_MINISTER_STATS[name]["potential"])
    else:
        for k, v in base_attrs.items():
            potential[k] = min(100, v + random.Random(sum(ord(c) for c in name + k)).randint(5, 15))

    return {
        "name": name,
        "rank": rank,
        "faction": faction,
        "attrs": base_attrs,
        "potential": potential,
        "exp": {k: 0 for k in ATTRIBUTE_NAMES},
        "traits": list(traits or []),
        "triggers": {
            "fiscal_months": 0,
            "governance_months": 0,
            "military_border_months": 0,
            "remonstrance_count": 0,
            "appease_count": 0,
            "corrupt_acts": 0,
            "battle_victories": 0,
            "battle_defeats": 0,
            "counsel_count": 0,
            "literary_works": 0,
        },
        "loyalty": float(loyalty),
        "corruption": float(corruption),
    }


def get_or_create_official_stats(state: Any, official_name: str, fallback_rank: str = "") -> Dict[str, Any]:
    """统一官员注册访问接口：查询或为任意官员生成量化能力与经历档案。"""
    store = getattr(state, "official_stats", None)
    if not isinstance(store, dict):
        store = {}
        state.official_stats = store

    if official_name in store:
        return store[official_name]

    # 从 MINISTERS 考据档案构建
    from content.ministers.data import MINISTERS
    if official_name in MINISTERS:
        fig = MINISTERS[official_name]
        profile = init_official_profile(
            name=official_name,
            rank=fig.get("rank") or fallback_rank,
            faction=fig.get("faction", "中立派"),
            traits=list(fig.get("trait_ids", [])),
            loyalty=float(fig.get("loyalty", 0.55)),
            corruption=float(fig.get("corruption", 0.25)),
        )
        store[official_name] = profile
        return profile

    # 通用官员兜底构建
    profile = init_official_profile(name=official_name, rank=fallback_rank)
    store[official_name] = profile
    return profile


def add_official_experience(state: Any, official_name: str, dim: str, amount: int = 20) -> Dict[str, Any]:
    """为官员增加某项能力经验，满 100 点突破成长 +1 属性。"""
    prof = get_or_create_official_stats(state, official_name)
    if dim not in ATTRIBUTE_NAMES:
        return prof

    cur_exp = prof["exp"].get(dim, 0) + amount
    cur_val = prof["attrs"].get(dim, 50)
    pot_val = prof["potential"].get(dim, 90)

    gained_levels = cur_exp // 100
    rem_exp = cur_exp % 100

    if gained_levels > 0 and cur_val < pot_val and cur_val < 100:
        actual_gain = min(gained_levels, pot_val - cur_val)
        prof["attrs"][dim] = cur_val + actual_gain

    prof["exp"][dim] = rem_exp
    return prof


def record_official_action(state: Any, official_name: str, action_type: str,
                           amount: int = 1, exp_dim: Optional[str] = None) -> List[str]:
    """记录官员在任历练行为，累加计数器，并检定是否触发全战式特质演化。"""
    prof = get_or_create_official_stats(state, official_name)
    triggers = prof.setdefault("triggers", {})

    if action_type in triggers:
        triggers[action_type] = triggers.get(action_type, 0) + amount

    if exp_dim and exp_dim in ATTRIBUTE_NAMES:
        add_official_experience(state, official_name, exp_dim, amount=15 * amount)

    # 检定特质演进
    evolved = check_and_evolve_traits(state, official_name)
    return evolved


def check_and_evolve_traits(state: Any, official_name: str) -> List[str]:
    """根据历练经历计数器检定官员特质演化（全战将领特性系统）。"""
    prof = get_or_create_official_stats(state, official_name)
    current_traits = prof.setdefault("traits", [])
    new_evolved = []

    for rule in TRAIT_EVOLUTION_RULES:
        tid = rule["trait_id"]
        if tid in current_traits:
            continue

        try:
            matched = rule["condition"](prof)
        except Exception:
            matched = False

        if matched:
            current_traits.append(tid)
            new_evolved.append(tid)

            # 剔除对立互斥特质（如刚直冲抵阿附）
            for incomp in rule.get("incompatible", []):
                if incomp in current_traits:
                    current_traits.remove(incomp)

            # 记录进政务日志
            log_text = f"🌟【特性演变】官员【{official_name}】历练有成，演进出特性：{rule['gain_msg']}！"
            if hasattr(state, "short_term_log"):
                state.short_term_log.append({
                    "turn": getattr(state, "turn", 0),
                    "kind": "personnel",
                    "title": f"官员特性演进：{official_name}获得【{tid}】",
                    "note": log_text,
                    "year": getattr(state, "year", 1101),
                    "month": getattr(state, "month", 1),
                })

            # 记忆图谱有机沉淀
            mg = getattr(state, "memory_graph", None)
            if mg is not None and hasattr(mg, "add_memory"):
                try:
                    mg.add_memory(
                        actor=official_name,
                        target=official_name,
                        action="特性演化",
                        content=f"经年理政演化出【{tid}】特性",
                        impact=0.1,
                    )
                except Exception:
                    pass

    return new_evolved


def generate_jinshi_official(name: str, exam_rank_type: str = "二甲",
                             curriculum: str = "经律兼治",
                             origin_circuit: str = "开封府",
                             examiner_faction: str = "中立派") -> Dict[str, Any]:
    """科举新进士标准生成器：根据科甲等第与考卷取向，生成绝非白板的完整官员量化档案。
    
    参数：
    - exam_rank_type: "一甲"（状元/榜眼/探花）、"二甲"（进士及第）、"三甲"（同进士出身）
    - curriculum: "策论经义"（政/财偏高）、"诗赋词章"（风望/才艺偏高）、"经律兼治"（均衡）
    """
    seed_val = sum(ord(c) for c in name + exam_rank_type + curriculum)
    rnd = random.Random(seed_val)

    if exam_rank_type == "一甲":
        base_range = (78, 88)
        pot_range = (90, 99)
        num_traits = rnd.randint(1, 2)
    elif exam_rank_type == "二甲":
        base_range = (66, 78)
        pot_range = (82, 92)
        num_traits = 1
    else:  # 三甲
        base_range = (56, 68)
        pot_range = (72, 84)
        num_traits = 0 if rnd.random() < 0.5 else 1

    attrs = {
        "governance": rnd.randint(*base_range),
        "finance": rnd.randint(*base_range),
        "military": rnd.randint(max(25, base_range[0] - 15), base_range[1] - 5),
        "strategy": rnd.randint(*base_range),
        "reputation": rnd.randint(*base_range),
    }

    # 命题取向加成
    if curriculum == "策论经义":
        attrs["governance"] = min(98, attrs["governance"] + rnd.randint(6, 12))
        attrs["finance"] = min(98, attrs["finance"] + rnd.randint(6, 10))
    elif curriculum == "诗赋词章":
        attrs["reputation"] = min(98, attrs["reputation"] + rnd.randint(8, 14))
        attrs["strategy"] = min(98, attrs["strategy"] + rnd.randint(4, 8))
    else:
        for k in attrs:
            attrs[k] = min(98, attrs[k] + rnd.randint(2, 6))

    potentials = {
        k: min(100, max(attrs[k] + 5, rnd.randint(*pot_range)))
        for k in attrs
    }

    # 初始特质赋予
    candidate_traits = ["理财", "清正", "刚直", "才艺", "调停"]
    if curriculum == "诗赋词章":
        candidate_traits.append("才艺")
    elif curriculum == "策论经义":
        candidate_traits.append("理财")

    initial_traits = []
    if num_traits > 0:
        chosen = rnd.sample(candidate_traits, min(num_traits, len(candidate_traits)))
        initial_traits.extend(chosen)

    return {
        "name": name,
        "role": "知县",
        "rank": "从八品",
        "origin": f"{origin_circuit}科举进士（{exam_rank_type}）",
        "faction": examiner_faction if examiner_faction != "无" else "中立派",
        "attrs": attrs,
        "potential": potentials,
        "exp": {k: 0 for k in ATTRIBUTE_NAMES},
        "traits": initial_traits,
        "triggers": {
            "fiscal_months": 0,
            "governance_months": 0,
            "military_border_months": 0,
            "remonstrance_count": 0,
            "appease_count": 0,
            "corrupt_acts": 0,
            "battle_victories": 0,
            "battle_defeats": 0,
            "counsel_count": 0,
            "literary_works": 1 if curriculum == "诗赋词章" else 0,
        },
        "costume_tier": "lv",
        "loyalty": round(rnd.uniform(0.55, 0.75), 2),
        "corruption": round(rnd.uniform(0.05, 0.20), 2),
    }
