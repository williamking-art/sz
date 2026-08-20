# -*- coding: utf-8 -*-
"""对话口谕内帑调拨（商量确认式）回归测试：提议不划账 / 准守恒 / 罢不动 / 不足不记 / 存档往返 / 金额解析。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.commands_decree import (  # noqa: E402
    propose_inner_transfer, confirm_inner_transfer, cancel_inner_transfer,
)


def _new_state():
    return GameState("史实")


def test_propose_confirm_conservation():
    s = _new_state()
    t0, i0 = s.treasury, s.imperial_treasury
    msg = propose_inner_transfer(s, 500000)
    assert "待准" in msg
    assert s.pending_inner_transfer == {"amount": 500000, "turn": s.turn}
    # 提议不划账
    assert s.treasury == t0 and s.imperial_treasury == i0
    msg2 = confirm_inner_transfer(s)
    assert "准" in msg2
    # 守恒移库：国库 +X == 内帑 -X
    assert s.treasury == t0 + 500000
    assert s.imperial_treasury == i0 - 500000
    assert (s.treasury - t0) == (i0 - s.imperial_treasury) == 500000
    assert s.pending_inner_transfer is None


def test_cancel_no_movement():
    s = _new_state()
    t0, i0 = s.treasury, s.imperial_treasury
    propose_inner_transfer(s, 300000)
    msg = cancel_inner_transfer(s)
    assert "罢" in msg
    assert s.treasury == t0 and s.imperial_treasury == i0
    assert s.pending_inner_transfer is None


def test_insufficient_no_record():
    s = _new_state()
    s.imperial_treasury = 100000
    msg = propose_inner_transfer(s, 999999)
    assert "内帑不足" in msg
    assert s.pending_inner_transfer is None


def test_pending_roundtrip():
    s = _new_state()
    propose_inner_transfer(s, 420000)
    from core.save_load import save_game, load_game, _slot_path
    assert save_game(s, slot=6)
    s2 = load_game(6)
    assert s2 is not None
    assert s2.pending_inner_transfer == {"amount": 420000, "turn": s.turn}
    if os.path.exists(_slot_path(6)):
        os.remove(_slot_path(6))


def test_parse_amount():
    from ui.panels_govern import _parse_inner_amount
    assert _parse_inner_amount("发内帑 50 万入国库") == 500000
    assert _parse_inner_amount("拨内帑 500000") == 500000
    assert _parse_inner_amount("发内帑五十万") == 500000
    assert _parse_inner_amount("发内帑十二万") == 120000
    assert _parse_inner_amount("朕不动内帑") is None
