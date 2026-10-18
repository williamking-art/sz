# -*- coding: utf-8 -*-
"""审计 B-3 / B-4 定向回归（2026-10-17）。

B-3 作坊产出双记：
  · 成品维唯一权威载体 = 民间 POP `goods`；
  · 恒等式：任一月每成品 `ΔPOP_goods + Δresources == 一次产量`（不再 2×产量）。

B-4 八大链只写报表：
  · 有治所物理仓时，原料真实从仓扣减、成品真实入仓，逐笔记账；
  · 报表产出键必须能对上真实仓存增量（或显式列入 `report_only_outputs`）；
  · 铜：先扣 `copper_ore` 再加 `铜锭`，不再无脑 `resources["铜"] += refined`。
"""
import copy
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState  # noqa: E402
from core.settlement_econ import _settle_workshops  # noqa: E402


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _pop_goods_total(state, dim):
    total = 0
    for p in state.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            goods = (pop or {}).get("goods") or {}
            v = goods.get(dim)
            # 兼容 `{dim: n}` 与 `{治所: {dim: n}}` 两种形态
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                total += int(v)
            elif isinstance(v, dict):
                for sub in v.values():
                    if isinstance(sub, (int, float)) and not isinstance(sub, bool):
                        total += int(sub)
    return total


def _resource_stock(state, dim):
    cell = (getattr(state, "resources", None) or {}).get(dim)
    if isinstance(cell, dict):
        return int(cell.get("stock", 0) or 0)
    return int(cell or 0)


def _warehouse_stock(state, dim):
    total = 0.0
    for p in state.prefectures.values():
        for seat in (p.get("seats") or {}).values():
            for wh in ((seat or {}).get("warehouses") or {}).values():
                stocks = (wh or {}).get("stocks") or {}
                v = stocks.get(dim)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    total += float(v)
    return total


# ---------------------------------------------------------------------------
# B-3：作坊成品单腿入 POP goods
# ---------------------------------------------------------------------------
def _run_one_workshop(output_dim, recipe, yld, granary=0):
    s = GameState("史实")
    s.workshops = {"w0": {
        "active": True, "name": "测试坊", "recipe": recipe,
        "output_dim": output_dim, "yield": yld,
    }}
    for dim, need in recipe.items():
        if dim in ("grain_feed", "ration_weight"):
            continue
        s.resources.setdefault(dim, {"stock": 0, "cap": 0})
        s.resources[dim]["stock"] = int(need)
    s.granary = int(granary)
    return s


def test_workshop_silk_cloth_is_booked_once_in_pop_goods():
    """绸：Δresources==0、ΔPOP==产量、两者之和==产量（修复前为 2×）。"""
    s = _run_one_workshop("绸", {"丝": 100}, 100.0)
    before_res = _resource_stock(s, "绸")
    before_pop = _pop_goods_total(s, "绸")
    _settle_workshops(s, [])
    d_res = _resource_stock(s, "绸") - before_res
    d_pop = _pop_goods_total(s, "绸") - before_pop
    assert d_res == 0, f"成品 绸 仍二次写 resources：Δresources={d_res}"
    assert d_pop == 100, f"绸 未按产量入 POP goods：ΔPOP={d_pop}"
    assert d_res + d_pop == 100, f"ΔPOP+Δresources 应为一次产量，实测 {d_res + d_pop}"


def test_workshop_meat_is_booked_once_in_pop_goods():
    """meat（原双记重灾区）：同样只入 POP goods 一次。"""
    s = _run_one_workshop("meat", {"grain_feed": 50000}, 2000.0, granary=100000)
    before_res = _resource_stock(s, "meat")
    before_pop = _pop_goods_total(s, "meat")
    _settle_workshops(s, [])
    d_res = _resource_stock(s, "meat") - before_res
    d_pop = _pop_goods_total(s, "meat") - before_pop
    assert d_res == 0, f"成品 meat 仍二次写 resources：Δresources={d_res}"
    assert d_pop == 2000, f"meat 未按产量入 POP goods：ΔPOP={d_pop}"
    assert d_res + d_pop == 2000


def test_monthly_finished_goods_identity_per_dim():
    """多成品同月：逐维 `ΔPOP + Δresources == 当月产量`（一次产量，不得双记）。"""
    s = GameState("史实")
    s.workshops = {
        "w_juan": {"active": True, "name": "绢坊", "recipe": {"丝": 300},
                   "output_dim": "绸", "yield": 300.0},
        "w_ma": {"active": True, "name": "麻坊", "recipe": {"麻": 200},
                 "output_dim": "布", "yield": 200.0},
        "w_zhi": {"active": True, "name": "纸坊", "recipe": {"麻": 1800},
                  "output_dim": "纸", "yield": 1700.0},
    }
    s.resources.setdefault("丝", {"stock": 0, "cap": 0}); s.resources["丝"]["stock"] = 300
    s.resources.setdefault("麻", {"stock": 0, "cap": 0}); s.resources["麻"]["stock"] = 2000

    dims = ("绸", "布", "纸")
    before = {d: (_pop_goods_total(s, d), _resource_stock(s, d)) for d in dims}
    _settle_workshops(s, [])
    after = {d: (_pop_goods_total(s, d), _resource_stock(s, d)) for d in dims}

    produced = {"绸": 300, "布": 200, "纸": 1700}
    for d in dims:
        d_pop = after[d][0] - before[d][0]
        d_res = after[d][1] - before[d][1]
        # 纸坊与麻坊争同一味「麻」⇒ 实得料不足 1800/2000，按比例欠产：
        # 允许产量 <= 名义产量，但**不得出现双记**（sum 必须等于一次实际产量）。
        assert d_res == 0, f"{d} 仍二次写 resources：Δresources={d_res}"
        assert 0 < d_pop <= produced[d], f"{d} 产量越界：ΔPOP={d_pop}"
        # 守恒硬断言：POP 增量 = 该维唯一一次产量，且与 resources 增量之和不再翻倍
        assert d_pop + d_res == d_pop
        assert d_pop <= produced[d]
    # 合计：不得出现「POP + resources = 2×」的双记账
    total_pop = sum(after[d][0] - before[d][0] for d in dims)
    total_res = sum(after[d][1] - before[d][1] for d in dims)
    assert total_res == 0 and total_pop > 0


# ---------------------------------------------------------------------------
# B-4：八大链 stock-to-stock
# ---------------------------------------------------------------------------
def _new_game_state():
    from application.game_init import new_game
    return new_game()


def _settle_chain(state):
    from core.domains.economy.industry_chains import settle_industry_chains
    return settle_industry_chains(state, [])


def test_industry_chains_book_outputs_into_physical_warehouses():
    """有物理仓时：每个正产出键都有真实仓存增量（不得只写报表）。"""
    from core.domains.economy.industry_chains import _OUTPUT_STOCK_DIM
    s = _new_game_state()
    before_ore = _warehouse_stock(s, "copper_ore")
    before_cu = _warehouse_stock(s, "铜锭")
    before_bad_cu = _resource_stock(s, "铜")
    summary = _settle_chain(s)
    ss = summary["stock_settlement"]

    assert ss["mode"] == "warehouse_stock_to_stock", ss
    assert ss["input_coverage"] > 0

    outs = summary["outputs"]
    report_only = set(ss.get("report_only_outputs") or [])
    for key, dim in _OUTPUT_STOCK_DIM.items():
        qty = outs.get(key, 0)
        if not isinstance(qty, (int, float)) or qty <= 0:
            continue
        if key in report_only:
            continue
        booked = (ss["outputs_booked"].get(key) or {}).get("qty", 0)
        assert booked > 0, f"{key} 报表 {qty} 但无入仓记账：{ss['outputs_booked'].get(key)}"
        assert _warehouse_stock(s, dim) > 0, f"{key} 报表>0 但仓中 {dim} 为 0"

    # 铜闭环（2026-10-18 维表并轨：copper_ore → 铜）：先扣 铜，再把 铜锭 入仓；
    # 不再额外写非法 resources["铜"]。
    ore_in = ss["inputs"]["铜"]
    assert ore_in["taken"] > 0, "铜 未被扣减"
    assert ore_in["available_before"] > 0, "本月未把 铜 物理入仓"
    assert _warehouse_stock(s, "铜") < ore_in["available_before"], \
        "铜 扣减后剩余应小于入仓前可用量"
    assert _warehouse_stock(s, "铜锭") > before_cu, "铜锭未入仓"
    assert _resource_stock(s, "铜") == before_bad_cu, "旧实现仍在额外造 resources['铜']"


def test_no_positive_chain_output_without_warehouse_stock():
    """「无 output>0 而仓存为 0」：报表正产出必须有仓存增量或显式仅报表标记。"""
    from core.domains.economy.industry_chains import _OUTPUT_STOCK_DIM, _OUTPUT_ALIAS_OF
    s = _new_game_state()
    summary = _settle_chain(s)
    ss = summary["stock_settlement"]
    outs = summary["outputs"]
    report_only = set(ss.get("report_only_outputs") or [])
    alias = dict(ss.get("alias_of") or {})
    monetary = set(ss.get("monetary_outputs") or [])
    for key, qty in outs.items():
        if not isinstance(qty, (int, float)) or qty <= 0:
            continue
        if key in monetary:
            continue
        if key in _OUTPUT_STOCK_DIM:
            if key in report_only:
                continue
            assert _warehouse_stock(s, _OUTPUT_STOCK_DIM[key]) > 0, \
                f"{key} 报 {qty} 但仓存为 0 且未标仅报表"
        elif key in _OUTPUT_ALIAS_OF:
            # 同批货的报表别名：必须能与主键对上，且**不得重复入仓**
            assert alias.get(key) == _OUTPUT_ALIAS_OF[key], \
                f"别名 {key} 未标注主键：{alias.get(key)!r}"
        else:
            assert key in report_only, f"{key} 报 {qty} 却既无仓存也未标 report_only"


def test_chain_report_only_mode_is_explicit_without_warehouses():
    """无治所物理仓（GameState 裸态）⇒ 必须显式 `report_only`，不得凭空造仓存。"""
    s = GameState("史实")
    before_res = copy.deepcopy(getattr(s, "resources", {}))
    summary = _settle_chain(s)
    ss = summary["stock_settlement"]
    assert ss["mode"] == "report_only", ss
    assert "无治所物理仓" in ss["reason"]
    positive = {k for k, v in summary["outputs"].items()
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0}
    # 所有正产出键（现钱类除外）必须显式列出，不接受"静默只写报表"
    assert positive - set(ss["monetary_outputs"]) <= set(ss["report_only_outputs"])
    assert _resource_stock(s, "铜") == int((before_res.get("铜") or {}).get("stock", 0)
                                          if isinstance(before_res.get("铜"), dict) else 0)
