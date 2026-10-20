# -*- coding: utf-8 -*-
"""A 补记：铸钱无收款 POP 时不得耗铜料/登记 external（修前漏账造成残差）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self):
        self.price_level = 1.0
        self.coin = {"melted_pool": 100}
        self.resources = {"iron": {"stock": 1000, "cap": 100000}}
        self.prefectures = {"路": {"pops": {"工匠": {"size": 0, "wealth": 0},
                                            "商人": {"size": 0, "wealth": 0}}}}
        self.statistics = {}


def test_mint_without_recipients_fails_without_consuming_metal():
    from core.domains.economy.settlement_econ_helpers import _settle_mint

    s = _S()
    ok, msg = _settle_mint(s, [], amount=100)
    assert ok is False and "无工匠" in msg
    assert s.coin["melted_pool"] == 100, "失败不得消耗熔铜池"
    assert s.resources["iron"]["stock"] == 1000, "失败不得消耗铜料"
    assert s.statistics.get("minted", 0) == 0
