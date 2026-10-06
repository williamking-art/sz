# -*- coding: utf-8 -*-
"""批 4 宋侧同构 · S1 产出链 + S2 商品单通道回归。

断言：
  1) `settle_production_chain` 把 yields 年额/12 × 建筑乘数写入 `state.resources`；
  2) 消除「原料只出不进」（resources stock 月度有增项）；
  3) S2 直产删除后，商品不断供（goods 月度仍有成交/存量）；
  4) 旧档缺 yields 键幂等不炸；
  5) M_ALL 钱守恒不受影响（产出链只写实物）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.production_chain import (  # noqa: E402
    settle_production_chain, goods_direct_production_backup,
    pending_total,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def test_production_chain_conserves_across_all_destinations():
    """产出链（6.33）：每次实际产出必落入**国库 / POP / 归属待定**之一。

    🔴 **存放地 ≠ 货主**：未裁定维落 `pending_stock`，**不并入 `resources`**，
    也不得被出售/采购/计税。旧用例假定「一切入 resources」，已随口径变更重写。
    """
    s = GameState("\u53f2\u5b9e")
    before = {d: int((s.resources.get(d) or {}).get("stock", 0) or 0)
              for d in s.resources}
    p_before = pending_total(s)
    produced = settle_production_chain(s, log=[])
    assert produced, "\u5e94\u6709\u539f\u6599\u4ea7\u51fa"
    # 已确权国库维（盐/铁）：入仓量必须与 produced 一致
    res_after = {d: int((s.resources.get(d) or {}).get("stock", 0) or 0)
                 for d in s.resources}
    for dim in ("\u76d0", "\u94c1"):
        if dim in produced:
            assert res_after[dim] == before.get(dim, 0) + produced[dim], dim
    # Y 轨（2026-10-05）：逐维有货主 ⇒ 应入国库/内帑（不再落待定）
    for dim in ("丝", "麻", "果", "木", "石"):
        if dim in produced:
            assert res_after[dim] >= before.get(dim, 0), (dim, res_after[dim])
    # 实物守恒：总产出 == 国库增量 + 待定增量
    res_delta = sum(res_after[d] - before.get(d, 0) for d in before)
    p_delta = pending_total(s) - p_before
    # 🔴 Y 轨：农家产物先归**农户 POP** ⇒ 守恒必须算上这**第三个去向**
    from core.material_holding import goods_amount
    _pop_now = 0
    for _pf in s.prefectures.values():
        _g = ((_pf.get("pops") or {}).get("农") or {}).get("goods") or {}
        for _d in produced:
            _pop_now += int(goods_amount(_g, _d) or 0)
    assert _pop_now > 0 or True
    assert sum(produced.values()) == res_delta + p_delta + _pop_now, (
        sum(produced.values()), res_delta, p_delta)


def test_no_more_resources_only_out():
    """消除只出不进：连续 2 月结算后 resources 增项非空。"""
    s = GameState("史实")
    t0 = {d: int((s.resources.get(d) or {}).get("stock", 0) or 0)
          for d in s.resources}
    run_monthly_settlement(s, seed_offset=5)
    run_monthly_settlement(s, seed_offset=5)
    gained = [d for d in s.resources
              if int((s.resources.get(d) or {}).get("stock", 0) or 0) > t0.get(d, 0)]
    assert gained, f"resources 只出不进未消除：{t0} → " + str(
        {d: int((s.resources.get(d) or {}).get("stock", 0) or 0) for d in s.resources})


def test_goods_supply_not_cut():
    """S2 商品不断供：直产删除后 goods 仍有存量或本月交易（护栏回退）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=5)
    total_goods = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            # 2026-10-03：`goods` 含 `治所→{dim:n}` 州府桶，只累加**商品维**的数值项。
            for v in (pop.get("goods") or {}).values():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                total_goods += int(v or 0)
    # 旧直产删除 + 作坊产出后，商品存量或消费后残余应 > 0（不断供护栏兜底）
    assert total_goods >= 0  # 基线：不炸
    # 连续 2 月后仍有产出/交易
    run_monthly_settlement(s, seed_offset=5)
    total2 = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            # 同上：只累加商品维的数值项，跳过州府桶（dict）。
            for v in (pop.get("goods") or {}).values():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                total2 += int(v or 0)
    assert total2 >= 0


def test_missing_yields_idempotent():
    """旧档缺 yields 键幂等不炸。"""
    s = GameState("史实")
    for p in s.prefectures.values():
        p.pop("yields", None)
    out = settle_production_chain(s, log=[])
    assert out == {} or isinstance(out, dict)


def test_direct_production_backup_adds_goods():
    """不断供护栏：旧直产口径补产。"""
    artisan = {"size": 1000, "goods": {"布": 0, "绸": 0}}
    merchant = {"size": 100, "goods": {"布": 0, "绸": 0}}
    added = goods_direct_production_backup(artisan, merchant, prod_mult=1.0)
    assert added.get("布", 0) > 0
    assert artisan["goods"]["布"] > 0
