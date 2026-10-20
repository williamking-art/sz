# -*- coding: utf-8 -*-
"""2026-10-20 复审 O5 · 「读路级镜像余额→扣治所」普查的定向回归。

钉住两处已修点：地方府库读数在**已下沉**路必须取 Σ 治所真账，不得信路级镜像。
（镜像只是派生视图；旧档/直写会让它滞后，据此判余额会错拒/错放，甚至把差额写进治所。）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _sunk_route(mirror=0):
    """构造一条已下沉的路：两个治所真账合计 150，镜像故意写成 0（滞后）。"""
    return {
        "seats": {
            "甲": {"local_treasury": 100},
            "乙": {"local_treasury": 50},
        },
        "local_treasury": mirror,
    }


def test_building_upgrade_reads_seat_truth_not_stale_mirror():
    from core.domains.construction.building_upgrade import _local_treasury_available

    assert _local_treasury_available(_sunk_route()) == 150
    # 未下沉（无 seats）仍回落镜像，行为不变
    assert _local_treasury_available({"local_treasury": 7}) == 7


def test_changping_buy_reads_seat_truth_not_stale_mirror():
    from core.settlement_common import _local_treasury_pool

    assert _local_treasury_pool(_sunk_route()) == 150
    assert _local_treasury_pool({"local_treasury": 7}) == 7
