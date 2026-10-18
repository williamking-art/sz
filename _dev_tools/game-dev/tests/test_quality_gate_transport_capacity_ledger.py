# -*- coding: utf-8 -*-
"""质量放行门 · P4 运力账（客货分列 / 排队 / 和雇差雇），2026-10-18。

语义（落地稿 §1.4/§1.5）：运力是**共用同一池**，超额**排队不拒办**；
官运力不足可**和雇**（付钱）或**差雇**（民心代价）。

本门钉住：
1. 货/客分列记账，但**共用容量**（货占则客少）；
2. 旧扁平格式自动迁移为货运用量（向后兼容）；
3. `ship_or_queue`：能运多少运多少，余量入队且不丢；
4. `flush_queue`：回合初续发，容量不足原样留队；回调失败**退回额度**；
5. 和雇扣国库、不足即失败；差雇降民心且封顶；
6. `reset_month` 清两本账但保留队列。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.transport import (  # noqa: E402
    hire_private, impress_private, transport_capacity, transport_consume,
    transport_flush_queue, transport_queue, transport_remaining, transport_reset_month,
    transport_ship_or_queue, transport_used)


def _state():
    from core.commands import new_game

    return new_game()


def test_goods_and_passenger_share_one_pool():
    s = _state()
    cap = transport_capacity(s, "overland")["capacity"]
    transport_consume(s, "overland", 1000, kind="goods")
    assert transport_remaining(s, "overland") == cap - 1000
    transport_consume(s, "overland", 500, kind="passenger")
    assert transport_remaining(s, "overland") == cap - 1500