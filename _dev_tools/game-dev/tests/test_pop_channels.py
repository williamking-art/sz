# -*- coding: utf-8 -*-
"""POP 非经济通道 → 执行度 的回归测试。

覆盖《宋祚局势系统实施规范》新增条款与用户定稿（2026-09）：
1. **兵 POP 的督行系数**（`core/army_models`）：军心/训练/装备/欠饷的方向性与钳位；
2. **AI 权衡文本**（`core/briefing.build_weighing_note`）：只读、含吏治/军政/派系/官制；
3. **集团 ⊆ POP**（`core/faction_basis`）：母集占比自洽、未声明者被拒。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_NAMES, GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST  # noqa: E402
from core.army_models import (  # noqa: E402
    ENFORCE_FLOOR, military_channels, unit_enforcement_mult, unit_monthly_pay,
)
from core.briefing import build_weighing_note  # noqa: E402
from core.faction_basis import (  # noqa: E402
    POP_CLASS_NAMES, basis_readout, build_faction_channels, validate_faction_basis,
)
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ---------------------------------------------------------------
# ① 兵 POP 的督行系数
# ---------------------------------------------------------------
def test_unit_enforcement_mult_directions_and_clamp():
    s = _state()
    u = next(u for u in s.army_units if u.troops > 0)
    base = unit_enforcement_mult(u)
    assert ENFORCE_FLOOR <= base <= 1.0

    u.morale = 0
    low_morale = unit_enforcement_mult(u)
    assert low_morale < base, "军心崩 → 督行系数必须下降"

    u.morale = 100
    u.training = 100
    best = unit_enforcement_mult(u)
    assert best >= low_morale
    assert best <= 1.0

    u.arrears = int(unit_monthly_pay(u) * 100)      # 欠饷百倍月饷
    assert unit_enforcement_mult(u) >= ENFORCE_FLOOR, "欠饷折扣不得击穿下限"
    assert unit_enforcement_mult(u) < best


def test_troopless_unit_is_zero_and_missing_route_is_none():
    s = _state()
    # 逐路校验：有驻军 ↔ 有通道读数（无驻军的路必须是 None，而不是伪造 0）
    for route in PREFECTURE_LIST:
        row = military_channels(s, route)
        has = any(u.station == route and u.troops > 0 for u in s.army_units)
        assert (row is not None) == has, route
    # 空军队
    u = next(u for u in s.army_units if u.troops > 0)
    u.branches = {}
    assert unit_enforcement_mult(u) == 0.0
    assert unit_monthly_pay(u) == 0.0


def test_unit_monthly_pay_follows_branch_std_and_tier_rate():
    """月饷与 `calc_army_cash` 同源（`branch_std`），且军籍系数生效。"""
    from content.data import branch_std
    s = _state()
    u = next(u for u in s.army_units if u.troops > 0)
    manual = 0.0
    for key, n in u.branches.items():
        tier, branch = u._split_key(key)
        manual += n * branch_std(tier, branch)["pay"]
    assert unit_monthly_pay(u) == pytest.approx(manual)

    def per_capita(tier):
        us = [x for x in s.army_units if x.tier == tier and x.troops > 0]
        if not us:
            return None
        return sum(unit_monthly_pay(x) for x in us) / sum(x.troops for x in us)

    jin, xiang, xiangbing = per_capita("禁军"), per_capita("厢军"), per_capita("乡兵")
    assert jin is not None
    if xiang is not None:
        assert jin >= xiang
    if xiangbing is not None:
        assert (xiang if xiang is not None else jin) >= xiangbing


def test_military_channels_is_readonly():
    s = _state()
    before = json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str)
    military_channels(s)
    for route in PREFECTURE_LIST:
        military_channels(s, route)
    after = json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str)
    assert before == after


# ---------------------------------------------------------------
# ② AI 权衡文本（AI 只权衡，数值由程序算）
# ---------------------------------------------------------------
def test_weighing_note_is_readonly_and_mentions_channels():
    s = _state()
    snap = (json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
            json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str),
            json.dumps(getattr(s, "factions", {}), sort_keys=True, ensure_ascii=False, default=str),
            s.treasury, s.prestige)
    note = build_weighing_note(s)
    assert note and "权衡变数" in note
    # 口径（2026-09-19 定稿）：吏治是唯一强关联；军队只是军政类的条件加成
    assert "吏治" in note and "强关联" in note
    assert "官场配合度代理" in note, "会签执行率的盘面代理必须标注为代理"
    assert "军队" in note and "不参与" in note, "民政口径下军队不得参与"
    after = (json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
             json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str),
             json.dumps(getattr(s, "factions", {}), sort_keys=True, ensure_ascii=False, default=str),
             s.treasury, s.prestige)
    assert snap == after, "权衡文本必须只读"


def test_weighing_note_does_not_fabricate_numbers():
    """删掉吏治/军政读数后不得编造——缺失项应缺席，而不是写 0/满分。"""
    s = _state()
    s.army_units = []
    s.factions = {}
    note = build_weighing_note(s)
    assert "督行" not in note, "无军队时不得编造督行系数"
    assert "派系满意度" not in note, "无派系时不得编造满意度"


# ---------------------------------------------------------------
# ③ 集团 ⊆ POP：母集占比自洽
# ---------------------------------------------------------------
def test_basis_readout_share_is_self_consistent():
    s = _state()
    fc = build_faction_channels(s)
    assert set(fc["factions"]) >= set(FACTION_NAMES)
    for name, row in fc["factions"].items():
        b = row["basis_readout"]
        assert b is not None, name
        assert b["subset_of"], name
        assert set(b["subset_of"]) <= set(POP_CLASS_NAMES), name
        assert b["pop_size"] <= b["parent_pop_size"], f"{name}: 子集人口不得超过母集"
        if b["share"] is not None:
            assert 0 < b["share"] <= 1, name
        # 子池口径：子集子池 ≤ 全国母集子池
        assert b["pool_size"] <= b["parent_total"], name
        assert "⊆" in b["subset_note"]


def test_every_pop_class_has_at_least_one_faction_or_channel():
    """六类 POP 每类都要有非经济通道；且至少有集团或通道覆盖它（不得留空类）。"""
    from core.situation_metrics import POP_SENTIMENT_CHANNELS
    assert set(POP_SENTIMENT_CHANNELS) == set(GRAIN_CONSUME_PER_CAPITA)
    covered = set()
    for row in build_faction_channels(_state())["factions"].values():
        spec = row["basis_readout"]
        if spec:
            covered |= set(spec["subset_of"])
    for cls in ("官僚", "士绅", "兵"):
        assert cls in covered, f"{cls} 应至少有一个集团以其为基本盘"


def test_validate_rejects_faction_without_pop_basis():
    assert validate_faction_basis("无名党", None)
    assert validate_faction_basis("无名党", {"pop_classes": ["官僚"], "subset_of": ["官僚"]})
    assert not validate_faction_basis(
        "新政党", {"pop_classes": ["官僚"], "subset_of": ["官僚"],
                   "subset_kind": "pool", "pool": "officials", "routes": None})


def test_subset_kind_must_match_fields():
    """`subset_kind` 必须与实际字段一致（2026-09-19 测试项审查补缺口）。

    否则会出现"声明为 pool 子集却没有 pool"的**语义空洞**：展示时无法判定它究竟取了
    哪一部分，等于把"子集"退化回"整个阶级"（正是本轮要修的旧毛病）。
    """
    base = {"pop_classes": ["士绅"], "subset_of": ["士绅"]}
    # 声明与字段不符 → 必须报错
    assert validate_faction_basis("x", {**base, "subset_kind": "pool"}), "pool 子集须有 pool"
    assert validate_faction_basis("x", {**base, "subset_kind": "route"}), "route 子集须有 routes"
    assert validate_faction_basis("x", {**base, "subset_kind": "pool+route", "pool": "clan"})
    assert validate_faction_basis("x", {**base, "subset_kind": "national", "pool": "clan"})
    assert validate_faction_basis("x", {**base, "subset_kind": "national",
                                         "routes": ["两浙路"]})
    # 声明与字段一致 → 通过
    assert not validate_faction_basis("x", {**base, "subset_kind": "national"})
    assert not validate_faction_basis("x", {**base, "subset_kind": "pool", "pool": "clan"})
    assert not validate_faction_basis("x", {**base, "subset_kind": "route",
                                             "routes": ["两浙路"]})
    assert not validate_faction_basis("x", {**base, "subset_kind": "pool+route",
                                             "pool": "clan", "routes": ["两浙路"]})
    # 现网 6 派与 5 个催生集团的声明都必须自洽
    from content.data import FACTION_NAMES, FACTION_POP_BASIS, REFORM_POP_BASIS
    for name in FACTION_NAMES:
        assert not validate_faction_basis(name, FACTION_POP_BASIS[name]), name
    for spec in REFORM_POP_BASIS.values():
        for f in spec.get("emergent") or []:
            basis = {k: v for k, v in f.items() if k not in ("name", "desc")}
            assert not validate_faction_basis(str(f.get("name")), basis), f.get("name")
