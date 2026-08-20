# -*- coding: utf-8 -*-
"""军队实体模型回归测试（每路禁/厢/乡各一支）：军籍差按率 / 多兵种 ArmyUnit / 军粮军饷按兵种 / 存档往返 / 旧档迁移 / 装备人均。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import branch_std, ARMY_UNIT_INIT  # noqa: E402
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_branch_std_tier_difference():
    """同名兵种不同军籍标准不同（按率 BRANCH_BASE × ARMY_RATE）：禁军轻步兵 grain/pay > 厢军 > 乡兵。"""
    j = branch_std("禁军", "轻步兵")
    x = branch_std("厢军", "轻步兵")
    m = branch_std("乡兵", "轻步兵")
    assert j["grain"] > x["grain"] > m["grain"]
    assert j["pay"] > x["pay"] > m["pay"]
    # 按率验证：禁军轻步 = 1.5×1.0；厢军 = 1.5×0.55；乡兵 = 1.5×0.35；装备 = EQUIP_STD × EQUIP_RATE
    assert abs(j["grain"] - 1.5) < 1e-9
    assert abs(x["grain"] - 1.5 * 0.55) < 1e-9
    assert abs(m["grain"] - 1.5 * 0.35) < 1e-9
    assert abs(j["equip"]["枪刀"] - 1.0) < 1e-9
    assert abs(x["equip"]["枪刀"] - 1.0 * 0.6) < 1e-9
    assert abs(m["equip"]["枪刀"] - 1.0 * 0.4) < 1e-9


def test_army_units_per_tier():
    """每路禁/厢/乡各一支：陕西路 3 支（各军籍单一），branches 键 = 兵种名，Σ 兵额 == ARMY_UNIT_INIT。"""
    s = _new_state()
    units = [u for u in s.army_units if u.station == "陕西路"]
    tiers = sorted(u.tier for u in units)
    assert tiers == ["乡兵", "厢军", "禁军"], f"陕西路应禁/厢/乡各一支：{tiers}"
    for u in units:
        assert not any(":" in k for k in u.branches), "branches 键应为兵种名（军籍由 tier 定）"
    jin = next(u for u in units if u.tier == "禁军")
    assert jin.branches.get("重骑兵") == 66000
    assert jin.troops == 220000
    xiang = next(u for u in units if u.tier == "厢军")
    assert xiang.troops == 20000
    xb = next(u for u in units if u.tier == "乡兵")
    assert xb.troops == 20000
    # 东京乡兵=0 → 该路 2 支；全军 = 2 + 11×3 = 35 支
    assert len([u for u in s.army_units if u.station == "东京开封府"]) == 2
    assert len(s.army_units) == 35
    total = sum(t for ts in ARMY_UNIT_INIT.values() for t in ts.values())
    assert sum(u.troops for u in s.army_units) == total


def test_army_grain_pay_by_branch():
    """军粮/军饷 = Σ(branches[兵种] 人数 × branch_std(u.tier, 兵种).grain/pay)。"""
    s = _new_state()
    grain, _ = s.calc_army_grain()
    cash, _ = s.calc_army_cash()
    expect_g = expect_c = 0.0
    for u in s.army_units:
        for b, n in u.branches.items():
            std = branch_std(u.tier, b)
            expect_g += n * std["grain"]
            expect_c += n * std["pay"]
    assert abs(grain - expect_g) < 1, f"军粮偏离：{grain} vs {expect_g}"
    assert abs(cash - expect_c) < 1, f"军饷偏离：{cash} vs {expect_c}"


def test_army_issue_xiangbing_self_provided():
    """兵口粮联动：实发口径（for_issue=True）不含乡兵军队（乡兵粮饷自备，太仓不造粮/钱）。"""
    s = _new_state()
    g_full, _ = s.calc_army_grain()
    g_issue, _ = s.calc_army_grain(for_issue=True)
    c_full, _ = s.calc_army_cash()
    c_issue, _ = s.calc_army_cash(for_issue=True)
    assert g_full > g_issue, "实发军粮应小于全口径（乡兵自备）"
    assert c_full > c_issue, "实发军饷应小于全口径（乡兵无饷）"
    xb = sum(u.troops for u in s.army_units if u.tier == "乡兵")
    assert xb > 0 and g_full - g_issue > 0


def test_army_branches_roundtrip():
    """存档往返 branches 不丢（兵种名真账）。"""
    s = _new_state()
    from core.save_load import save_game, load_game, _slot_path
    assert save_game(s, slot=7)
    s2 = load_game(7)
    assert s2 is not None
    assert len(s2.army_units) == len(s.army_units)
    for u1, u2 in zip(s.army_units, s2.army_units):
        assert u1.branches == u2.branches
        assert u1.troops == u2.troops
    if os.path.exists(_slot_path(7)):
        os.remove(_slot_path(7))


def test_old_format_migration():
    """旧档（branch/troops 单兵种）加载迁移：branches 兵种名键（军籍由 tier 定）。"""
    from ui.panels_military import ArmyUnit
    old = {"unit_id": "u0001", "name": "test", "tier": "禁军", "branch": "重骑兵",
           "troops": 9000, "morale": 70, "training": 65, "station": "陕西路",
           "defense_line": "北线_陕西", "equip": {}}
    d = dict(old)
    d["branches"] = {d.pop("branch"): int(d.pop("troops"))}
    u = ArmyUnit(**d)
    assert u.branches == {"重骑兵": 9000}
    assert u.troops == 9000


def test_mixed_save_migration_split():
    """混合版存档（branches 键「军籍:兵种」复合键）迁移：拆分到对应军籍军队，兵额守恒。"""
    from ui.panels_military import ArmyUnit
    d = {"unit_id": "u0001", "name": "test", "tier": "禁军",
         "branches": {"禁军:重骑兵": 9000, "厢军:轻步兵": 3000, "乡兵:弓弩兵": 1000},
         "morale": 70, "training": 65, "station": "陕西路",
         "defense_line": "北线_陕西", "equip": {}}
    # 模拟 save_load 拆分逻辑（先建桶再取，避免 RHS 先求值 KeyError）
    by_tier = {}
    for k, n in d["branches"].items():
        t, b = k.split(":", 1)
        bucket = by_tier.setdefault(t, {})
        bucket[b] = bucket.get(b, 0) + n
    units = []
    for t, brs in by_tier.items():
        nd = dict(d)
        nd["tier"] = t
        nd["branches"] = brs
        units.append(ArmyUnit(**nd))
    assert sorted(u.tier for u in units) == ["乡兵", "厢军", "禁军"]
    assert sum(u.troops for u in units) == 13000  # 兵额守恒（9000+3000+1000）


def test_equip_per_capita():
    """装备人均配给口径：军队级 equip = Σ(人数 × 人均标准)；人均 = EQUIP_STD × EQUIP_RATE。"""
    from content.data import EQUIP_STD, EQUIP_RATE
    s = _new_state()
    u = next(x for x in s.army_units if x.station == "陕西路" and x.tier == "禁军")
    n_qibing = u.branches.get("重骑兵", 0)
    assert n_qibing == 66000
    assert u.equip["枪刀"] >= int(n_qibing * EQUIP_STD["重骑兵"]["枪刀"] * EQUIP_RATE["禁军"])
    assert u.equip["战马"] >= int(n_qibing * EQUIP_STD["重骑兵"]["战马"] * EQUIP_RATE["禁军"])
    # 厢军军队轻步兵人均枪刀 = 1.0 × EQUIP_RATE["厢军"]（0.6）——同名兵种不同军籍人均不同
    xu = next(x for x in s.army_units if x.station == "陕西路" and x.tier == "厢军")
    n_xiang = xu.branches.get("轻步兵", 0)
    assert n_xiang == 8000
    per_xiang = EQUIP_STD["轻步兵"]["枪刀"] * EQUIP_RATE["厢军"]
    assert abs(per_xiang - 0.6) < 1e-9
    assert xu.equip["枪刀"] >= int(n_xiang * per_xiang)
    assert u.equip_rate() >= 0.99
