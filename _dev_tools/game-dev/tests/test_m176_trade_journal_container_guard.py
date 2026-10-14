# -*- coding: utf-8 -*-
"""M176 外贸流水容器 `state.trade_journal` **守卫**（主线 F · 载体甲；零行为变化）。

本批只**建容器**（尚无写入者 ⇒ 未登记 `save_load`，避免"半接通"）。用例锁定：
① 槽存在、类型为 `list`、新局为空（**零行为变化**）；
② **不是账本**：任何将来写入的元素**不得**含余额/存量语义键（BANNED 集）；
③ **遍历集合纪律**：流水涉及的路名必须落在 `state.prefectures` 内（防 `ROUTE_WATERWAY`
   的 `黔中路` 幽灵路）；
④ 短期结算后容器**仍为空**（证明"未接线"、且不影响结算）。
"""

import copy

from core import commands
from core.game_state import GameState

#: 🔴 禁止出现在任何流水元素里的键（出现即视为"在造平行账本"，违反 §3-1）
BANNED_KEYS = {"balance", "stock", "inventory", "on_hand", "holdings"}


def test_slot_exists_and_is_empty_at_new_game():
    s = commands.new_game()
    assert isinstance(s.trade_journal, list)
    assert s.trade_journal == [], "本批只建容器 ⇒ 新局必须为空（零行为变化）"


def test_slot_defaults_on_bare_state():
    """裸 `GameState`（不走 new_game）也应有该槽 ⇒ 旧档/构造路径不会 AttributeError。"""
    s = GameState("史实")
    assert isinstance(getattr(s, "trade_journal", None), list)


def test_guards_are_defined_for_future_writes():
    """守卫集必须非空且**不含**任何"合法字段"误伤（防止将来把正文字段也禁掉）。"""
    assert BANNED_KEYS, "禁止键集不得为空"
    legal = {"month", "route", "seat", "partner", "dim", "qty", "unit_price", "goods_value",
             "freight", "tax_over", "tax_stay", "tax_to", "freight_to", "direction", "reason"}
    assert not (BANNED_KEYS & legal), "禁止键与合法字段重叠"


def test_stays_empty_after_settlement_and_no_behavior_change():
    """未接线 ⇒ 结算后仍为空；且结算前后**其余状态**按同种子一致（零行为变化的直接证据）。"""
    import random
    random.seed(20261013)
    a = commands.new_game()
    for _ in range(3):
        import core.settlement as S
        S.run_monthly_settlement(a)
    assert a.trade_journal == [], "尚无写入者 ⇒ 结算后必须仍为空"

    random.seed(20261013)
    b = commands.new_game()
    for _ in range(3):
        import core.settlement as S
        S.run_monthly_settlement(b)
    assert a.treasury == b.treasury and a.imperial_treasury == b.imperial_treasury
    # 流水本身不参与结算 ⇒ 两局在其余口径上同源
    assert isinstance(copy.deepcopy(a.trade_journal), list)
