# -*- coding: utf-8 -*-
"""生产接线守卫测试：`settle_local` 的 `SONGZUO_POPS_GUARD` 观察型守卫。

证明四件事：
  1. **缺省关闭**：不设环境变量时 `settle_local` 不装守卫，路级 `pops` 保持 plain dict。
  2. **开关打开成对还原**：`SONGZUO_POPS_GUARD=1` 时装守卫，结算后**必须还原 plain dict**
     （不把 `_GuardedPops` 子类残留进 state / 存档）。
     ⚠️ "正常局零违规"**不在本文件断言**（本文件只证装配/还原配对）——零违规由
     `test_quality_gate_pops_guard.py` 逐月断言（N2：docstring 不得替代断言）。
  3. **异常路径也成对**：结算中途抛错，`_restore_state` 用装守卫前的 plain 快照整体
     替换 `prefectures`，守卫子类随之卸除；且回滚后仍可安全重试。
  4. **非空转**：注入一处绕过桥接的路级直写，守卫确实记账（否则「零违规」是假象）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

import pytest

from core.foundation.ledger.pop_bridge import _GuardedPops


def _new_state():
    from core.commands import new_game
    return new_game()


def _pops_types(state):
    return {type(p.get("pops")) for p in state.prefectures.values()}


def test_settle_local_default_does_not_install_guard(monkeypatch):
    """缺省（不设 env）不装守卫：结算后路级 pops 仍是 plain dict、非守卫子类。"""
    monkeypatch.delenv("SONGZUO_POPS_GUARD", raising=False)
    from core.commands import settle_local

    s = _new_state()
    t0 = s.turn
    settle_local(s)
    assert s.turn == t0 + 1, "settle_local 应推进回合"
    assert _GuardedPops not in _pops_types(s), "缺省不应残留守卫子类"


def test_settle_local_guard_restores_plain_dict(monkeypatch):
    """开关打开：结算观察期装守卫、结束后还原 plain dict、正常局零违规。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    from core.commands import settle_local

    s = _new_state()
    t0 = s.turn
    settle_local(s)
    assert s.turn == t0 + 1
    # 关键：成对还原——不留守卫子类残留进 state（否则污染存档 / 后续玩家命令）。
    assert _pops_types(s) == {dict}, "结算后路级 pops 必须还原为 plain dict"


def test_settle_local_guard_restores_on_exception(monkeypatch):
    """结算中途抛错：装守卫 → 回滚 → 守卫子类随 plain 快照一并卸除，且可安全重试。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    import core.commands as cmds

    s = _new_state()
    t0 = s.turn

    # 让结算第 1 次抛错、第 2 次正常——验证「回滚后可安全重试」不因守卫接线而破坏。
    calls = {"n": 0}
    real_rms = cmds.run_monthly_settlement

    def _boom(state, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("注入结算异常（验证守卫成对还原）")
        return real_rms(state, *a, **k)

    monkeypatch.setattr(cmds, "run_monthly_settlement", _boom)

    with pytest.raises(RuntimeError):
        cmds.settle_local(s)
    assert s.turn == t0, "结算失败不得推进回合"
    assert _GuardedPops not in _pops_types(s), "异常回滚后不得残留守卫子类"

    # 还原真实函数后重试：应成功且仍不残留守卫子类。
    monkeypatch.setattr(cmds, "run_monthly_settlement", real_rms)
    cmds.settle_local(s)
    assert s.turn == t0 + 1
    assert _pops_types(s) == {dict}, "重试结算后路级 pops 必须还原为 plain dict"


def test_settle_local_guard_records_direct_write(monkeypatch, caplog):
    """非空转：注入一处绕过桥接的路级直写 → 守卫记账并落 WARNING 日志。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    import logging
    import core.commands as cmds
    from core.foundation.ledger.pop_bridge import pops_guard_violations

    s = _new_state()
    t0 = s.turn

    seen = {"n": 0}

    real_rms = cmds.run_monthly_settlement

    def _inject(state, *a, **k):
        # 在结算第一步执行前，先制造一处**绕过桥接**的路级直写（守卫应记账）。
        if seen["n"] == 0:
            seen["n"] += 1
            rt = next(iter(state.prefectures))
            state.prefectures[rt]["pops"]["农"]["size"] = 999999
        return real_rms(state, *a, **k)

    monkeypatch.setattr(cmds, "run_monthly_settlement", _inject)
    with caplog.at_level(logging.WARNING, logger="settle_local"):
        cmds.settle_local(s)

    assert s.turn == t0 + 1, "守卫是记录型，不得阻断结算 / 推进回合"
    # 结算结束后守卫已卸、_VIOLATIONS 被清（reset 在下次装时）——故断言落在日志。
    assert any("只读守卫" in r.message or "直写" in r.message for r in caplog.records), \
        "注入直写后 settle_local 应落守卫告警日志"
