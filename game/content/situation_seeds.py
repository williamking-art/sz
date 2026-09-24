# -*- coding: utf-8 -*-
"""局势系统 v1 · 开局种子（批 2 · 成败条件全公开）。

依据《改进方案_合并版》A1 与《明末经验》§2.1：
  每项局势 = 结构化长期任务，**成败条件明文全公开** + 持续代价 + bar 进度 + phase/severity。

本模块只定义**开局三条局势**（花石纲民怨 / 东南财政亏空 / 辽事边备），
用 `core.situations.make_record` 落成合法记录；不改结算推进逻辑
（推进仍走既有 `situation_settle` / `situation_metrics`）。

结构约束（`core.situations.validate_record` 强制）：
  - `origin_kind` 首批仅 `"event_pool"`（幂等键 `event_pool:<ref>`）；
  - `resolve_condition` / `fail_condition` 必须是条件 DSL dict
    （`{all|any: [...], streak?}` 或叶子 `{metric, arg?, op, value}`）；
  - `ongoing_cost` 必须是 dict 或 None（禁止用字符串顶替）；
  - `effect_on_resolve` / `effect_on_fail` 路径必须在 `SITUATION_EFFECT_PATHS` 白名单。

验收（对应方案批 2）：玩家打开面板 3 秒答出「怎么算赢 / 怎么算崩 / 不动会怎样」。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.situations import make_record

__all__ = ["INITIAL_SITUATIONS", "seed_initial_situations"]


# 开局三条局势（宋名，语义对齐明末「户部亏空 / 陕西流寇 / 宁锦防线」三件套）
# 条件用 metric DSL（describe_condition 可渲染为中文）；* 为玩家可读原文。
INITIAL_SITUATIONS: List[Dict[str, Any]] = [
    {
        "title": "花石纲民怨",
        "origin_kind": "event_pool",
        "origin_ref": "huashigang_minyuan",
        "region_hint": "东南",
        "faction_hint": None,
        "progress_mode": "bar",
        "bar_value": 25,
        # 达成：两浙路（花石纲主产地）民心 ≥55 且动乱 ≤30，连续 2 月
        "resolve_condition": {
            "all": [
                {"metric": "region.public_support", "arg": "两浙路", "op": ">=", "value": 55},
                {"metric": "region.unrest", "arg": "两浙路", "op": "<=", "value": 30},
                {"metric": "region.public_support", "arg": "江南东路", "op": ">=", "value": 55},
                {"metric": "region.unrest", "arg": "江南东路", "op": "<=", "value": 30},
            ],
            "streak": 2,
        },
        "resolve_text": "看【花石纲抽分】：两浙路与江南东路民心 ≥55 且动乱 ≤30，连续 2 月 → 解除",
        # 失败：任一主产地动乱 ≥85 且民心 ≤30（民变破州县的数值代理）
        "fail_condition": {
            "any": [
                {
                    "all": [
                        {"metric": "region.unrest", "arg": "两浙路", "op": ">=", "value": 85},
                        {"metric": "region.public_support", "arg": "两浙路", "op": "<=", "value": 30},
                    ],
                },
                {
                    "all": [
                        {"metric": "region.unrest", "arg": "江南东路", "op": ">=", "value": 85},
                        {"metric": "region.public_support", "arg": "江南东路", "op": "<=", "value": 30},
                    ],
                },
            ],
        },
        "fail_text": "两浙路或江南东路动乱 ≥85 且民心 ≤30，或激起民变破州县 → 立即失败",
        "ongoing_cost": {"treasury": -50000, "population_satisfaction": -2},
        "ongoing_text": "国库 −5 万/月（应奉局靡费）、东南民心 −2/月",
        "bar_good_meaning": "民怨渐平",
        "bar_bad_meaning": "东南鼎沸",
        "effect_on_resolve": {"population_satisfaction": 5, "prestige": 2},
        "effect_on_fail": {"population_satisfaction": -15, "prestige": -10},
    },
    {
        "title": "东南财政亏空",
        "origin_kind": "event_pool",
        "origin_ref": "dongnan_caikui",
        "region_hint": None,
        "faction_hint": None,
        "progress_mode": "bar",
        "bar_value": 30,
        # 达成：国库 ≥0（上月结余代理），连续 3 月
        "resolve_condition": {
            "all": [
                {"metric": "treasury", "op": ">=", "value": 0},
            ],
            "streak": 3,
        },
        "resolve_text": "看【国库上月实绩】：结余 ≥0 则 +10/月；连续 3 月盈余 → 解除",
        # 失败：国库见底（≤0）致刚性支出违约
        "fail_condition": {
            "all": [
                {"metric": "treasury", "op": "<=", "value": 0},
            ],
        },
        "fail_text": "国库见底致刚性支出违约（欠饷哗变/官俸断发/宗禄拖欠）→ 立即失败",
        "ongoing_cost": {"treasury": -100000, "population_satisfaction": -1},
        "ongoing_text": "国库 −10 万/月（亏空利息）、民心 −1/月",
        "bar_good_meaning": "财用渐丰",
        "bar_bad_meaning": "太仓见底",
        "effect_on_resolve": {"treasury": 500000, "prestige": 3},
        "effect_on_fail": {"treasury": -1000000, "prestige": -8},
    },
    {
        "title": "辽事边备",
        "origin_kind": "event_pool",
        "origin_ref": "liaoshi_bianbei",
        "region_hint": "河北",
        "faction_hint": None,
        "progress_mode": "bar",
        "bar_value": 20,
        # 达成：北线（河北路+河东路）军心 ≥50 且欠饷 ≤10 万贯，连续 2 月
        # （城防无独立 metric，用军心/欠饷作边备代理）
        "resolve_condition": {
            "all": [
                {"metric": "army.morale", "arg": "河北路", "op": ">=", "value": 50},
                {"metric": "army.arrears", "arg": "河北路", "op": "<=", "value": 100000},
                {"metric": "army.morale", "arg": "河东路", "op": ">=", "value": 50},
                {"metric": "army.arrears", "arg": "河东路", "op": "<=", "value": 100000},
            ],
            "streak": 2,
        },
        "resolve_text": "看【北线城防与欠饷】：河北路与河东路军心 ≥50 且欠饷 ≤10 万贯，连续 2 月 → 解除",
        # 失败：北线军心 <30 或欠饷激成兵变（欠饷 ≥30 万贯）
        "fail_condition": {
            "any": [
                {"metric": "army.morale", "arg": "河北路", "op": "<", "value": 30},
                {"metric": "army.morale", "arg": "河东路", "op": "<", "value": 30},
                {"metric": "army.arrears", "arg": "河北路", "op": ">=", "value": 300000},
                {"metric": "army.arrears", "arg": "河东路", "op": ">=", "value": 300000},
            ],
        },
        "fail_text": "北线军心 <30 或欠饷 ≥30 万贯激成兵变，或燕云失守 → 立即失败",
        "ongoing_cost": {"treasury": -80000, "army_morale": -1},
        "ongoing_text": "国库 −8 万/月（边饷）、军心 −1/月",
        "bar_good_meaning": "边备渐修",
        "bar_bad_meaning": "烽火告警",
        # defense_bonus 不在 SITUATION_EFFECT_PATHS 白名单 → 用 prestige/民生表达
        "effect_on_resolve": {"prestige": 4, "population_satisfaction": 2},
        "effect_on_fail": {"prestige": -12, "population_satisfaction": -5},
    },
]


def seed_initial_situations(state, turn: int = 0) -> List[dict]:
    """把开局三条局势写入 state.situations（幂等：按 situation_key 去重）。

    返回新建的记录列表；已存在同 key 的局势则跳过（不覆盖玩家进度）。
    """
    from core.situations import find_duplicate

    existing = state.situations if isinstance(getattr(state, "situations", None), list) else []
    created: List[dict] = []
    for spec in INITIAL_SITUATIONS:
        spec = dict(spec)
        title = spec.pop("title")
        origin_kind = spec.pop("origin_kind")
        origin_ref = spec.pop("origin_ref")
        # 展示字段（* _text / *_meaning）不进 make_record 校验体，随 overrides 落盘
        if find_duplicate(existing, origin_kind, origin_ref):
            continue
        rec = make_record(
            title=title,
            origin_kind=origin_kind,
            origin_ref=origin_ref,
            origin_turn=turn,
            **spec,
        )
        existing.append(rec)
        created.append(rec)
    state.situations = existing
    return created
