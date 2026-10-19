# -*- coding: utf-8 -*-
"""质量放行门 · P5.6 占领经济后果（2026-10-19；用户裁定：不冻结）。

用户原话：「怎么会冻结税产呢？占领后会产生财产流失，这个我理解；为什么会冻结呢」
⇒ 模型改为：**一次性财产流失（掠夺/逃户）+ 残破度税基（0.6 起，逐月 +0.10 恢复）+ 按残破征税**。

本门用**独立 fixture**（不依赖 `new_game`），钉住：
1. 占领当刻：人口 −3% / 财富 −15% / 存粮 −15%，掠夺额 = 损失财富 ×50% 入占领方 treasury；
2. `devastation` 初始 0.6，重复调用**幂等**（不二次打残）；
3. `regime_intake` **不冻结**：`tax_output_frozen=False`，`collectable_tax > 0` 且 ≈ 财富×0.6×1%；
4. 月度征税从 POP 财富扣、入政权 treasury（钱不凭空生）；
5. `recover_devastation` 每月 +0.10、封顶 1.0；
6. 归还（owner 改回）后残破**保留**（战争破坏不返还）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.regime_intake import (  # noqa: E402
    DEVASTATION_RECOVERY, DEVASTATION_START, TAX_RATE_ON_WEALTH,
    apply_occupation_damage, collect_occupation_tax, recover_devastation,
    regime_intake)


class _S:
    """最小 state fixture（只含本模块用到的三段）。"""

    def __init__(self):
        self.regions = {
            "p0": {"level": "T2", "name": "省甲", "owner": "辽", "parent": "辽"},
            "p0_a": {"level": "T1", "name": "甲州", "owner": "辽", "owner_at_init": "辽", "parent": "p0",
                     "pop": {"农": {"size": 100000, "wealth": 1000000, "grain": 500000}},
                     "land": 1000},
            "p0_b": {"level": "T1", "name": "乙州", "owner": "辽", "owner_at_init": "辽", "parent": "p0",
                     "pop": {"农": {"size": 50000, "wealth": 500000, "grain": 200000}},
                     "land": 500},
        }
        self.external_regimes = {"辽": {"treasury": 0}, "金": {"treasury": 0, "placeholder": True}}
        self.prefectures = {}


def test_damage_and_loot():
    s = _S()
    out = apply_occupation_damage(s, ["p0_a"], to_regime="金")
    assert out["ok"] and out["touched"] == ["p0_a"]
    pop = s.regions["p0_a"]["pop"]["农"]
    assert pop["size"] == 97000, pop          # −3%
    assert pop["wealth"] == 850000, pop       # −15%
    assert pop["grain"] == 425000, pop        # −15%
    assert s.regions["p0_a"]["devastation"] == DEVASTATION_START
    assert s.external_regimes["金"]["treasury"] == 75000, s.external_regimes["金"]


def test_damage_idempotent():
    s = _S()
    apply_occupation_damage(s, ["p0_a"], to_regime="金")
    treasury = s.external_regimes["金"]["treasury"]
    again = apply_occupation_damage(s, ["p0_a"], to_regime="金")
    assert again["touched"] == [] and again["skipped"] == ["p0_a"]
    assert s.external_regimes["金"]["treasury"] == treasury
    assert s.regions["p0_a"]["pop"]["农"]["wealth"] == 850000


def test_intake_not_frozen_and_tax_backed_by_damage():
    s = _S()
    apply_occupation_damage(s, ["p0_a"], to_regime="金")
    s.regions["p0_a"]["owner"] = "金"
    got = regime_intake(s, "金")
    assert got["tax_output_frozen"] is False
    assert got["devastation_avg"] == DEVASTATION_START
    expect = int(850000 * DEVASTATION_START * TAX_RATE_ON_WEALTH)
    assert got["collectable_tax"] == expect, (got["collectable_tax"], expect)


def test_collect_taxes_backed_by_pop_wealth():
    s = _S()
    apply_occupation_damage(s, ["p0_a"], to_regime="金")
    s.regions["p0_a"]["owner"] = "金"
    before_wealth = s.regions["p0_a"]["pop"]["农"]["wealth"]
    before_treasury = s.external_regimes["金"]["treasury"]
    out = collect_occupation_tax(s)
    assert out["collected"] > 0
    after_wealth = s.regions["p0_a"]["pop"]["农"]["wealth"]
    after_treasury = s.external_regimes["金"]["treasury"]
    assert after_wealth == before_wealth - out["collected"]
    assert after_treasury == before_treasury + out["collected"]


def test_recovery_caps_and_restores():
    s = _S()
    apply_occupation_damage(s, ["p0_a"], to_regime="金")
    for _ in range(3):
        recover_devastation(s)
    assert s.regions["p0_a"]["devastation"] == 0.9
    for _ in range(10):
        recover_devastation(s)
    assert s.regions["p0_a"]["devastation"] == 1.0


def test_devastation_kept_after_return():
    s = _S()
    apply_occupation_damage(s, ["p0_a"], to_regime="金")
    s.regions["p0_a"]["owner"] = "金"
    s.regions["p0_a"]["owner"] = "辽"     # 和议归还
    assert s.regions["p0_a"]["devastation"] == DEVASTATION_START, "战争破坏不返还"