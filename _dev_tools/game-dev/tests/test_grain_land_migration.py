# -*- coding: utf-8 -*-
"""**G-3 第三片 · 收获分配/本色征粮接入读写桥** 定向回归（2026-10-04）。

改动范围：`settlement_steps._settle_land_local` 的 POP 粮读写（收获分配、本色征粮、种粮）。

关键性质：迁移期 POP 粮**仍在旧载体 `.grain`**（尚未回填 `goods[米]`），
桥接层保证行为与迁移前**完全一致** —— 本组锁的就是这一点。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                    # noqa: E402
from core.grain_ledger import survey_grain                # noqa: E402


def _mk():
    return GameState("史实")


def test_harvest_does_not_create_goods_bucket():
    """收获分配走桥接但载体仍是 legacy ⇒ **不得**凭空建 `goods[米]`。"""
    from core.settlement_steps import _settle_land_local
    s = _mk()
    _settle_land_local(s, [])
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            goods = pop.get("goods") or {}
            assert "米" not in goods and "麦" not in goods, (
                "迁移期不应把粮写进 goods 桶（载体应保持 legacy）")


def test_grain_stays_conserved_after_settlements():
    """多次结算后粮账守恒：粮只在本色征粮入廪/种粮消耗两条出口减少。"""
    from core.settlement_steps import _settle_land_local
    s = _mk()
    before = survey_grain(s)["Σpops[].grain"]
    log = []
    for _ in range(6):
        _settle_land_local(s, log)
    after = survey_grain(s)["Σpops[].grain"]
    assert after <= before, "粮不得凭空增加"
    assert after >= 0, "粮不得为负"
    # 每路 storage 应吸收了被征的粮（本色征粮口径：扣多少入多少）
    assert any(int((p.get("storage") or 0)) > 0 for p in s.prefectures.values()), (
        "本色征粮应把实征粮计入 storage")


def test_bridge_reads_consistent_with_field_after_settle():
    """桥接读值与旧字段一致（迁移期等价性）。"""
    from core.grain_bridge import grain_get
    from core.settlement_steps import _settle_land_local
    s = _mk()
    _settle_land_local(s, [])
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop.get("grain"), (int, float)):
                assert grain_get(pop) == int(pop["grain"]), (
                    "迁移期桥接读值必须等于旧字段")
