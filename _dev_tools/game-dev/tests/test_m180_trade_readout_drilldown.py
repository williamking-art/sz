# -*- coding: utf-8 -*-
"""M180 外贸读数**真账下钻**（主线 F 已接线）—— 定向回归。

锁定：① 未开市舶 ⇒ `真账_笔数 == 0` 且**如实说明**（不臆造）；② 开市舶并跑月 ⇒ 下钻出
**逐路/逐政权/逐商品**货值与合计，且**合计 ≡ 流水 Σ 货值**（与 `trade_journal` 对账）；
③ 契约不破（值仍为「素材就绪项数」，`display` 规则不变）。
"""

import random

from core import commands
from core.domains.economy import readout_hub as rh


def _months(s, n=1):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(s)
    return s


def test_drill_is_zero_and_explained_when_maritime_closed():
    random.seed(20261013)
    s = commands.new_game()
    try:
        s.maritime["open"] = False
    except Exception:
        pass
    _months(s, 1)
    row = rh.collect(s, keys=["trade_line_status"])["readouts"]["trade_line_status"]
    d = row["drill_down"] or {}
    assert d.get("真账_笔数") == 0
    assert "不臆造" in str(d.get("真账_来源"))
    assert row["value"] is not None            # 素材就绪度仍有值（4）


def test_drill_matches_journal_when_wired():
    random.seed(20261013)
    s = commands.new_game()
    try:
        s.maritime["open"] = True
    except Exception:
        pass
    _months(s, 2)
    assert s.trade_journal, "接线后应产生流水"
    row = rh.collect(s, keys=["trade_line_status"])["readouts"]["trade_line_status"]
    d = row["drill_down"] or {}
    assert d["真账_笔数"] == len(s.trade_journal)
    expect = round(sum(float(x["goods_value"]) for x in s.trade_journal), 2)
    assert abs(float(d["真账_货值合计"]) - expect) < 1e-6
    for key in ("真账_逐路货值", "真账_逐政权货值", "真账_逐商品货值"):
        assert isinstance(d.get(key), dict) and d[key], key
