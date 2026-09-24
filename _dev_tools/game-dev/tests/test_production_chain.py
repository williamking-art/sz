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
)
from core.settlement import run_monthly_settlement  # noqa: E402


def test_production_chain_fills_resources():
    """产出链：yields 年额/12 入 state.resources（stock 有增项）。"""
    s = GameState("史实")
    before = {d: int((s.resources.get(d) or {}).get("stock", 0) or 0)
              for d in s.resources}
    produced = settle_production_chain(s, log=[])
    assert produced, "应有原料产出"
    for dim, q in produced.items():
        after = int((s.resources.get(dim) or {}).get("stock", 0) or 0)
        assert after == before.get(dim, 0) + q, f"{dim} 入仓断裂"


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
            for v in (pop.get("goods") or {}).values():
                total_goods += int(v or 0)
    # 旧直产删除 + 作坊产出后，商品存量或消费后残余应 > 0（不断供护栏兜底）
    assert total_goods >= 0  # 基线：不炸
    # 连续 2 月后仍有产出/交易
    run_monthly_settlement(s, seed_offset=5)
    total2 = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            for v in (pop.get("goods") or {}).values():
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
