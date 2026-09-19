# -*- coding: utf-8 -*-
"""公式常量**单点回收**的防回退测试（2026-09-19 代码质量全检）。

背景：`content/data.py` 一度定义了整组公式常量（`S_*` / `E_*` / `ARRIVAL_*` / `PRESTIGE_*`），
但 `calc_decree_execution_rate` / `calc_arrival_rate` / `change_prestige` 内部**硬编码同值**
→ 常量定义了却无人引用，**改常量不生效**（配置漂移）。本文件锁定"实现必须引用常量"：

  ① 源码中不得再出现那些字面量；
  ② 改常量必须真的改变行为（monkeypatch 常量 → 输出随之变化）。
"""
import inspect
import os
import re
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.game_state_econ import GameStateEconMixin  # noqa: E402


def _src(obj) -> str:
    return inspect.getsource(obj)


def _code_only(obj) -> str:
    """剔除注释与 docstring 后的**代码行**（注释里可保留历史值说明，不算硬编码）。"""
    body = inspect.getsource(obj)
    body = re.sub(r'""".*?"""', "", body, flags=re.S)
    return "\n".join(line.split("#")[0] for line in body.splitlines())


def test_decree_execution_rate_has_no_hardcoded_constants():
    code = _code_only(GameState.calc_decree_execution_rate)
    # 这些字面量此前硬编码在公式里；现应全部改为引用 content/data 常量
    for lit in ("0.45", "0.08", "0.15", "0.30", "0.7", "0.10", "0.05", "0.95", "0.04"):
        assert lit not in code, f"执行率公式仍出现硬编码 {lit}（应引用 S_*/E_* 常量）"
    src = _src(GameState.calc_decree_execution_rate)
    for name in ("S_BASE", "S_SUPPORT_WEIGHT", "S_CONFLICT_WEIGHT", "S_SECRET_BASE",
                 "S_SECRET_LOYALTY_WEIGHT", "S_DIRECT_BONUS",
                 "S_ZHONGZHI_SUPPORT_WEIGHT", "E_MIN", "E_MAX"):
        assert name in src, f"执行率公式未引用常量 {name}"


def test_arrival_rate_has_no_hardcoded_constants():
    code = _code_only(GameStateEconMixin.calc_arrival_rate)
    for lit in ("0.30", "0.15", "0.25", "0.05", "0.95"):
        assert lit not in code, f"到账率公式仍出现硬编码 {lit}（应引用 ARRIVAL_* 常量）"
    src = _src(GameStateEconMixin.calc_arrival_rate)
    for name in ("ARRIVAL_AUDIT_WEIGHT", "ARRIVAL_AUTHORITY_WEIGHT",
                 "ARRIVAL_DIVERSION_WEIGHT", "ARRIVAL_MIN", "ARRIVAL_MAX"):
        assert name in src, f"到账率公式未引用常量 {name}"


def test_prestige_clamp_uses_named_constants():
    src = _src(GameState.change_prestige)
    for name in ("PRESTIGE_MAX", "PRESTIGE_MIN", "PRESTIGE_MONTHLY_CAP",
                 "PRESTIGE_MAJOR_EVENT_CAP"):
        assert name in src, f"皇威钳位未引用常量 {name}"


def test_constants_actually_drive_behaviour(monkeypatch):
    """**改常量必须生效**（否则"单点"只是装饰）。"""
    import core.game_state as gs

    s = GameState("史实")
    stances = {k: 0 for k in s.factions}
    base = s.calc_decree_execution_rate(stances, is_direct=True)
    monkeypatch.setattr(gs, "S_DIRECT_BONUS", 0.40)      # 原 0.10
    assert s.calc_decree_execution_rate(stances, is_direct=True) > base, \
        "改 S_DIRECT_BONUS 未影响执行率 → 常量未被实现引用"

    monkeypatch.setattr(gs, "E_MAX", 0.5)
    assert s.calc_decree_execution_rate(stances, is_direct=True) <= 0.5, "E_MAX 未生效"

    # 皇威钳位：月上限与上下界
    import core.game_state as gs2
    s2 = GameState("史实")
    monkeypatch.setattr(gs2, "PRESTIGE_MONTHLY_CAP", 2)
    s2.prestige = 50
    s2.change_prestige(99)
    assert s2.prestige == 52, "PRESTIGE_MONTHLY_CAP 未生效"
    monkeypatch.setattr(gs2, "PRESTIGE_MAX", 60)
    s2.change_prestige(99)
    assert s2.prestige <= 60, "PRESTIGE_MAX 未生效"


def test_arrival_constants_actually_drive_behaviour(monkeypatch):
    import core.game_state_econ as ge

    s = GameState("史实")
    base = s.calc_arrival_rate(audit_effort=1.0, diversion=0.0)
    monkeypatch.setattr(ge, "ARRIVAL_MIN", 0.9)
    monkeypatch.setattr(ge, "ARRIVAL_MAX", 0.91)
    assert 0.9 <= s.calc_arrival_rate(audit_effort=1.0, diversion=0.0) <= 0.91, \
        "ARRIVAL_MIN/MAX 未生效"
    assert base != s.calc_arrival_rate(audit_effort=1.0, diversion=0.0)
