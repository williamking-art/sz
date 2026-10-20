# -*- coding: utf-8 -*-
"""R-N-3：回合初运力重置 + 队列续发（Jev A 0.866）。

修前 `transport_reset_month` / `transport_flush_queue` 零调用方：
- `transport_used` 跨月累积 ⇒ 历史占用永久吃掉运力；
- 超限队列永不续发。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_monthly_settlement_resets_transport_and_flushes_queue():
    from core.commands import new_game
    from core.settlement import run_monthly_settlement

    s = new_game("史实")
    # 给陆运载具/夫役（new_game 默认 0 ⇒ 运力 0，无法验证续发）
    s.carriage = {"official": {"cart": 100}, "private": {}}
    s.transport_labor = {"official": {"hired_porter": 1000}, "private": {}}
    # 人为把上月运力占满 + 放一条超限队列记录
    s.transport_used = {"goods": {"overland": 10 ** 9}, "passenger": {}}
    s.transport_queue = [{"mode": "overland", "qty": 1.0, "kind": "goods",
                          "payload": {"dim": "米", "partner": "金", "direction": "import",
                                      "month": 1}}]
    before = float(s.statistics.get("transport_queue_flushed", 0) or 0)
    run_monthly_settlement(s)
    # 重置后不再保留上月 10 亿占用（若没重置，剩余运力为 0，flush 不可能发出）
    assert float((s.transport_used.get("goods") or {}).get("overland", 0) or 0) < 10 ** 9
    # 队列被续发（运力足够时应清空或至少记录已发）
    flushed = float(s.statistics.get("transport_queue_flushed", 0) or 0) - before
    assert flushed >= 1.0, (flushed, s.transport_queue)
    # 我们放的那条（overland / 米）已被续发；结算过程中贸易新入队的（maritime 等）可保留
    assert not [it for it in s.transport_queue
                if it.get("mode") == "overland" and (it.get("payload") or {}).get("dim") == "米"]
