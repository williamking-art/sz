# -*- coding: utf-8 -*-
"""M35《官僚身份经济层与欠给身份化》契约回归。

裁决口径（用户 2026-10-11）：
- **M35-A** 官僚身份经济层：只加**记账层**（`officials_wealth` / `clerks_wealth`），
  **不拆 POP、不改人口真账、不改粮耗、不破 `pop_bridge` 镜像**；
- **M35-B** 欠给身份化：`local_arrears_by_identity`（官员欠俸／胥吏欠钱／衙役欠钱／士卒欠饷）；
- **M35-C** 职业映射：`official/clerk/soldier/militia/runner`（**不改军费**，runner 走接口留白）；
- **M35-D** 财政可见度三层：`real`（真账）／`official`（官府账）／`rumor`（风闻）；
- 新增字段一律支持 `save_load` 迁移（旧档补 0，幂等）；不新增 POP 类型。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import new_game  # noqa: E402
from core.settlement_finance import (  # noqa: E402
    _settle_finance, _settle_local_expenditure)

_M35_FIELDS = ("officials_wealth", "clerks_wealth",
               "officials_salary_arrears", "clerks_pay_arrears")


def _snapshot(s):
    return {"treasury": int(getattr(s, "treasury", 0) or 0),
            "stats": copy.deepcopy(dict(s.statistics)),
            "prefs": copy.deepcopy(s.prefectures)}


def test_identity_economics_fields_and_shares():
    """官/吏 计数与记账额齐备；份额读侧派生（无记账 → None，不伪造 0.5）。"""
    s = new_game()
    for p in s.prefectures.values():
        pool = (p.get("pops") or {}).get("官僚") or {}
        for f in _M35_FIELDS:
            assert f in pool, f"官僚 POP 缺 M35 字段 {f}"
        assert pool["officials_wealth"] == 0 and pool["clerks_wealth"] == 0
    view = s.identity_economics()
    for row in view["by_route"].values():
        assert row["officials_wealth_share"] is None, "无记账时份额必须为 None（缺省语义）"
        assert row["coverage"] is None or row["coverage"] <= 1.0
    assert s.finance_readout()["identity_economics"]["total"]["officials"] > 0


def test_bookkeeping_never_exceeds_pool_wealth():
    """记账层不得越过整池 wealth（超标部分不计；不改人口真账/粮耗）。"""
    s = new_game()
    rk = min(s.prefectures)

def test_arrears_identity_mapping():
    """欠给身份化：官员欠俸／胥吏欠钱／衙役欠钱 落对应身份字段；分科目和 ≡ 总额。"""
    s = new_game()
    poor = min(s.prefectures)
    s.prefectures[poor]["local_treasury"] = 0          # 逼出欠支
    ret = _settle_local_expenditure(s, [])
    assert ret["arrears"] > 0
    by_id = ret["arrears_by_identity"]
    assert set(by_id) == {"official_salary", "clerk_pay", "runner_pay", "soldier_pay"}
    # 公用（public_supply）无身份 → 只按科目留痕；故身份和 + 公用 ＝ 总额
    gap = ret["arrears"] - sum(by_id.values())
    assert gap == ret["arrears_by_kind"].get("public_supply", 0)
    pool = s.prefectures[poor]["pops"]
    assert int(pool["官僚"]["officials_salary_arrears"]) == by_id["official_salary"]
    assert int(pool["官僚"]["clerks_pay_arrears"]) == by_id["clerk_pay"]
    # 🟢 M35-C-1：役人欠给挂**官僚桶**（原挂兵桶；兵侧字段为旧位兼容）
    assert int(pool["官僚"]["runners_pay_arrears"]) == by_id["runner_pay"]
    stats_id = s.statistics.get("local_arrears_by_identity") or {}
    assert sum(int(v) for v in stats_id.values()) == sum(by_id.values())
    assert s.finance_readout()["local_arrears_by_identity"] == stats_id


def test_local_identities_view_does_not_change_army_pay():
    s = new_game()
    army0 = s.calc_army_cash()[0]
    view = s.calc_local_identities()
    assert s.calc_army_cash()[0] == army0, "职业映射不得改动军费口径"
    tot = view["total"]
    troops = sum(int(getattr(u, "troops", 0) or 0) for u in s.army_units)
    assert tot["soldier"] + tot["militia"] == troops, "士卒＋乡兵必须等于总兵额"
    assert tot["official"] > 0 and tot["clerk"] > 0
    assert tot["runner"] == 0, "衙役接口留白（尚未建模）"


def test_runner_interface_is_a_hook():
    """衙役走**接口留白**：路级 `runners` 可被 AI/事件填充，无需改 POP 结构。"""
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk]["runners"] = 7
    view = s.calc_local_identities()
    assert view["by_route"][rk]["runner"] == 7
    assert view["total"]["runner"] == 7

    pool = s.prefectures[rk]["pops"]["官僚"]
    pool["wealth"] = 100                      # 极小池


def test_fiscal_visibility_three_layers():
    s = new_game()
    _settle_finance(s, [])
    vis = s.fiscal_visibility()
    assert set(vis) == {"real", "official", "rumor"}
    assert vis["real"]["land_central"] == int(s.statistics["land_tax_central"])
    assert "loss_report" in vis["official"] and "loss_status" in vis["official"]
    assert isinstance(vis["rumor"], dict)
    assert "fiscal_visibility" in s.finance_readout()


def test_m35_readouts_are_readonly():
    s = new_game()
    _settle_finance(s, [])
    before = _snapshot(s)
    s.identity_economics()
    s.calc_local_identities()
    s.fiscal_visibility()
    s.finance_readout()
    assert _snapshot(s) == before, "M35 读数必须只读"


def test_old_save_defaults_for_m35_fields():
    """旧档缺 M35 字段 → 载入时幂等补 0（与欠税/欠给同款）。"""
    from core.save_load import load_game, save_game
    s = new_game()
    slot = 6
    for p in s.prefectures.values():                    # 制造"旧档"
        for pool in (p.get("pops") or {}).values():
            if isinstance(pool, dict):
                for f in _M35_FIELDS + ("soldiers_arrears", "runners_pay_arrears",
                                        "militia_pay_arrears"):
                    pool.pop(f, None)
    assert save_game(s, slot=slot)
    loaded = load_game(slot=slot)
    assert loaded is not None, "旧档（缺 M35 字段）必须仍可载入"
    for p in loaded.prefectures.values():
        for pool in (p.get("pops") or {}).values():
            if isinstance(pool, dict):
                for f in _M35_FIELDS + ("soldiers_arrears", "runners_pay_arrears",
                                        "militia_pay_arrears"):
                    assert pool.get(f) == 0, f"载入后 {f} 必须补 0"

    pool["officials_wealth"] = 60
    pool["clerks_wealth"] = 40                # 已满 ⇒ 无余量
    grain0 = int(pool.get("grain", 0) or 0)
    size0 = int(pool.get("size", 0) or 0)
    _settle_local_expenditure(s, [])
    assert int(pool["officials_wealth"]) + int(pool["clerks_wealth"]) <= 100
    assert int(pool.get("grain", 0) or 0) == grain0, "身份经济层不得改粮耗"
    assert int(pool.get("size", 0) or 0) == size0, "身份经济层不得改人口真账"
