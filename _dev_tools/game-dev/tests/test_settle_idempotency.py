# -*- coding: utf-8 -*-
"""月度结算**幂等守卫**（`run_monthly_settlement(..., expect_turn=)`，2026-10-22）。

背景（外部审查遗留的唯一硬项）：结算入口末尾 `state.turn += 1` 且**无幂等守卫**，
「结算成功但响应丢失 → 客户端重发」会**再推一个月**（改前行为，本文件第 1 例把它钉住）。

口径：
- `expect_turn=None` ⇒ 行为与改前**完全一致**（老调用方零改动）；
- `== state.turn` ⇒ 正常结算；
- `< state.turn` 且有历史日志 ⇒ **幂等重放**（不结算、不改状态、返回该回合日志副本）；
- `< state.turn` 无历史日志 ⇒ 不结算 + warning；
- `> state.turn` ⇒ 不结算 + warning（客户端超前，跳过一月更危险）。

另钉一个装饰器坑：`_isolated_rng` 用 `functools.wraps` ⇒ `inspect.signature` 跟随
`__wrapped__` 显示真实签名，但 wrapper 若只转固定参数，运行时仍会丢 kwargs
（表现为「签名正确却报 unexpected keyword」，极易误判为缓存问题）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.commands import new_game, settle_local  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402

_FINGERPRINT_FIELDS = ("turn", "year", "month", "treasury", "granary",
                       "imperial_treasury")


def _state(seed=7):
    random.seed(seed)
    return new_game("史实")


def _fp(state):
    """轻量状态指纹（覆盖结算会动的关键标量 + 两个日志长度）。"""
    row = {k: getattr(state, k, None) for k in _FINGERPRINT_FIELDS}
    row["settlement_log_len"] = len(getattr(state, "settlement_log", []) or [])
    row["decision_log_len"] = len(getattr(state, "decision_log", []) or [])
    return row


# ---------------------------------------------------------------- 旧行为（钉住）
def test_without_expect_turn_advances_every_call():
    """无 `expect_turn` ⇒ 与改前一致：每次调用都推一个月（这就是被审查指出的风险面）。"""
    st = _state()
    assert st.turn == 0
    run_monthly_settlement(st)
    assert st.turn == 1
    run_monthly_settlement(st)
    assert st.turn == 2, "无参数的旧调用语义必须保持不变"


# ---------------------------------------------------------------- 幂等重放
def test_retry_same_turn_is_noop_and_replays_log():
    st = _state()
    first = settle_local(st, expect_turn=0)
    assert st.turn == 1 and first
    before = _fp(st)

    second = settle_local(st, expect_turn=0)      # 模拟「响应丢失后重发」
    assert st.turn == 1, "重试不得推进回合"
    assert _fp(st) == before, "重试不得改变任何状态字段/日志长度"
    assert second == first, "重放必须返回同一份日志内容"


def test_replay_returns_a_copy_not_the_stored_list():
    """返回值是副本：调用方改它不能污染存档里的 `settlement_log`。"""
    st = _state()
    log = settle_local(st, expect_turn=0)
    log.append("被调用方篡改")
    stored = st.settlement_log[0]
    assert "被调用方篡改" not in stored
    assert settle_local(st, expect_turn=0) == stored


def test_sequential_turns_still_advance():
    """连续不同回合声明 ⇒ 正常推进（守卫不应妨碍正常玩法）。"""
    st = _state()
    settle_local(st, expect_turn=0)
    settle_local(st, expect_turn=1)
    settle_local(st, expect_turn=2)
    assert st.turn == 3
    # 任意历史回合重放都不改状态
    snap = _fp(st)
    for t in (0, 1, 2):
        assert settle_local(st, expect_turn=t)
        assert _fp(st) == snap


# ---------------------------------------------------------------- 异常输入
def test_ahead_of_state_is_refused():
    """`expect_turn > state.turn`（客户端超前/两端漂移）⇒ 拒绝推进，不跳过一月。"""
    st = _state()
    before = _fp(st)
    assert settle_local(st, expect_turn=99) == []
    assert _fp(st) == before


def test_stale_without_history_is_refused():
    """声明了一个**过去且无历史日志**的回合 ⇒ 不结算（宁可少给，不重复推月）。"""
    st = _state()
    st.settlement_log = []
    st.turn = 3
    before = _fp(st)
    assert run_monthly_settlement(st, expect_turn=0) == []
    assert _fp(st) == before


def test_bad_expect_turn_value_is_ignored_not_crash():
    """不可解析的 `expect_turn` ⇒ 退化为旧行为（不抛异常、不阻断结算）。"""
    st = _state()
    run_monthly_settlement(st, expect_turn="不是数字")
    assert st.turn == 1


# ---------------------------------------------------------------- 装饰器坑
def test_decorator_forwards_new_kwargs():
    """`_isolated_rng` 必须转发 kwargs：否则内省签名正确、运行时却丢参（实测踩过）。"""
    import inspect

    sig = inspect.signature(run_monthly_settlement)
    assert "expect_turn" in sig.parameters
    st = _state()
    run_monthly_settlement(st, expect_turn=0)          # 不抛 TypeError 即通过
    assert st.turn == 1
