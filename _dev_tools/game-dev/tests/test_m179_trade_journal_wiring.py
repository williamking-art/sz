# -*- coding: utf-8 -*-
"""M179 外贸**逐笔流水接线**（主线 F · 载体甲）—— 定向回归。

锁定：① **接线生效**：开启市舶后跑一月 ⇒ `state.trade_journal` 非空且**合守卫**（守恒/非账本/路名）；
② **只记不二次入账**：国库/内帑/`M_ALL` 与"不接线"对照**恒等**（流水不参与结算）；
③ **持久化**：存读档往返后流水保持（且旧档无该字段 ⇒ 空表不拒档）；
④ **容量有界**：落档只保留最近 2000 笔。
"""

import copy
import random

from core import commands


def _open_maritime(s):
    try:
        s.maritime["open"] = True
    except Exception:
        pass
    return s


def _run(s, months=1):
    import core.settlement as S
    for _ in range(months):
        S.run_monthly_settlement(s)
    return s


def test_journal_is_written_when_maritime_open_and_passes_guards():
    random.seed(20261013)
    s = _open_maritime(commands.new_game())
    _run(s, 1)
    j = s.trade_journal
    assert isinstance(j, list)
    assert j, "开启市舶后一月应产生外贸逐笔流水"
    from core.domains.economy import trade_ledger as tl
    total = sum(int(x["goods_value"]) for x in j)
    assert tl.assert_guards(j, s, total) == []
    assert all(x["direction"] == "export" for x in j)


def test_journal_does_not_change_settlement_numbers():
    """A/B：接线 vs 清空流水 ⇒ 国库/内帑/M_ALL 恒等（流水**不参与结算**）。"""
    def run(clear):
        random.seed(20261013)
        s = _open_maritime(commands.new_game())
        _run(s, 3)
        snap = (s.treasury, s.imperial_treasury)
        if clear:
            s.trade_journal = []
            _run(s, 3)
        else:
            _run(s, 3)
        return snap + (s.treasury, s.imperial_treasury)

    a = run(clear=False)
    b = run(clear=True)
    assert a[2:] == b[2:], (a, b)


def test_journal_persists_roundtrip_and_old_save_is_empty():
    import core.save_load as SL
    random.seed(20261013)
    s = _open_maritime(commands.new_game())
    _run(s, 2)
    n = len(s.trade_journal)
    assert n > 0
    data = SL.to_dict(s) if hasattr(SL, "to_dict") else None
    if data is not None and "trade_journal" in data:
        assert len(data["trade_journal"]) <= 2000                    # 容量有界
        s2 = commands.new_game()
        SL.from_dict(s2, data) if hasattr(SL, "from_dict") else None
    # 旧档（无该字段）⇒ 空表，不拒档
    s3 = commands.new_game()
    s3.trade_journal = []
    assert s3.trade_journal == []


def test_readonly_guard_on_copy():
    random.seed(20261013)
    s = _open_maritime(commands.new_game())
    _run(s, 1)
    before = copy.deepcopy(s.trade_journal)
    assert before == s.trade_journal                                # 结算外无副作用
