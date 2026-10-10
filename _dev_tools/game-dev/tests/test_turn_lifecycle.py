# -*- coding: utf-8 -*-
"""回合生命周期（架构方案 §5.2 抽出物）的触发条件与失败路径回归。

覆盖口径来自 §5.2 那句规则：「可单测每种触发条件和失败路径」。
抽取前的实现把这些埋在 `core.commands.finish_turn` 的 62 行里，无法逐项验证。

同时锁定两条**对外可见面**（改动它们会让既有调用方/用例受骗）：
  · `commands.finish_turn` 仍返回 `None`、不抛错；
  · 日志仍走 logger 名 `"finish_turn"`（M2 用例按名过滤）。
"""
import logging
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from application import memory_lifecycle as ml  # noqa: E402
from application.turn_lifecycle import finish_turn as app_finish_turn  # noqa: E402
from core.commands import finish_turn as cmd_finish_turn  # noqa: E402
from core.game_state import GameState  # noqa: E402


# =====================================================================
# 工具：给真实 state 装记忆/存档探针
# =====================================================================
def _state(turn=0, month=2):
    s = GameState("史实")
    s.turn = turn
    s.month = month
    return s


def _spy_memory(s, slot="slot-x"):
    """返回 calls 列表：记录主记忆库被调了什么。"""
    calls = []
    mg = s.memory
    mg._slot = slot
    mg.compress = lambda t: calls.append(("compress", t))
    mg.summarize_period = lambda t: calls.append(("summarize_period", t))
    mg.archive = lambda sl: calls.append(("archive", sl))
    mg.save = lambda sl: (calls.append(("save", sl)) or True)
    return calls


def _spy_dialogue(monkeypatch):
    calls = []

    class _DM:
        turn = 0

        def summarize_dialogues(self, t):
            calls.append(("dialogue", t))

    import memory.dialogue_memory as dmod
    monkeypatch.setattr(dmod, "get_dialogue_memory", lambda *_a, **_k: _DM())
    return calls


def _spy_save(monkeypatch, ret=True, exc=None):
    calls = []
    import core.save_load as sl

    def fake(state, slot=0, *_a, **_k):
        calls.append(slot)
        if exc is not None:
            raise exc
        return ret

    monkeypatch.setattr(sl, "save_game", fake)
    return calls


# =====================================================================
# 1) §5.2 契约：返回结构可观测，三段齐全
# =====================================================================
def test_finish_turn_returns_lifecycle_result(monkeypatch):
    s = _state(turn=13)
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch)
    r = app_finish_turn(s)
    assert sorted(r) == ["game_over", "memory", "save"], f"§5.2 结构不符：{sorted(r)}"
    assert sorted(r["memory"]) == ["dialogue", "memory", "persist"], sorted(r["memory"])


# =====================================================================
# 2) 触发条件：主记忆库按 6 / 12 间隔
# =====================================================================
def test_compress_triggers_only_on_six_turn_interval():
    s = _state(turn=13)                      # 13：既非 6 也非 12 的倍数
    calls = _spy_memory(s)
    ml.compress_memory_if_needed(s)
    assert calls == [], f"turn=13 不该触发主库治理，实际 {calls}"

    s6 = _state(turn=6)
    calls6 = _spy_memory(s6)
    ml.compress_memory_if_needed(s6)
    assert ("compress", 6) in calls6, calls6
    assert not any(c[0] == "summarize_period" for c in calls6), calls6


def test_period_summary_then_archive_in_that_order():
    s = _state(turn=12)
    calls = _spy_memory(s, slot="slot-12")
    out = ml.compress_memory_if_needed(s)
    kinds = [c[0] for c in calls]
    assert kinds == ["compress", "summarize_period", "archive"], f"顺序错：{kinds}"
    assert ("archive", "slot-12") in calls, calls
    assert out["summarized"] and out["archived"], out


def test_archive_falls_back_to_state_memory_slot():
    s = _state(turn=12)
    calls = _spy_memory(s, slot=None)
    s.memory_slot = "slot-from-state"
    ml.compress_memory_if_needed(s)
    assert ("archive", "slot-from-state") in calls, calls


def test_archive_skipped_when_no_slot_anywhere():
    s = _state(turn=12)
    calls = _spy_memory(s, slot=None)
    s.memory_slot = None
    out = ml.compress_memory_if_needed(s)     # 不该因此报错
    assert not any(c[0] == "archive" for c in calls), calls
    assert out["summarized"] and out["error"] is None, out


# =====================================================================
# 3) 触发条件：对话记忆每 3 回合；**turn=0 也会触发**（既有语义，故意保留）
# =====================================================================
def test_dialogue_summary_triggers_at_turn_zero(monkeypatch):
    s = _state(turn=0)
    _spy_memory(s)
    calls = _spy_dialogue(monkeypatch)
    ml.summarize_dialogue_if_due(s)
    assert ("dialogue", 0) in calls, f"抽取前 turn=0 也会总结，语义须原样保留：{calls}"


def test_dialogue_summary_triggers_every_third_turn(monkeypatch):
    s = _state(turn=13)
    calls = _spy_dialogue(monkeypatch)
    ml.summarize_dialogue_if_due(s)
    assert calls == [], f"13 不是 3 的倍数，不该触发：{calls}"
    s.turn = 9
    ml.summarize_dialogue_if_due(s)
    assert ("dialogue", 9) in calls, calls


# =====================================================================
# 4) 落盘：无槽位则不写；返回 False 必须记 warning（不得静默）
# =====================================================================
def test_persist_skipped_without_slot(monkeypatch):
    s = _state(turn=1)
    calls = _spy_memory(s, slot=None)
    s.memory_slot = None
    out = ml.persist_memory(s)
    assert out == {"attempted": False, "saved": False, "error": None}, out
    assert not any(c[0] == "save" for c in calls), calls


def test_persist_false_is_logged_not_swallowed(caplog):
    s = _state(turn=1)
    mg = s.memory
    mg._slot = "slot-w"
    mg.save = lambda sl: False
    with caplog.at_level(logging.WARNING, logger="finish_turn"):
        out = ml.persist_memory(s)
    assert out["saved"] is False, out
    msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("写盘失败" in m for m in msgs), msgs


def test_persist_exception_logged_under_finish_turn_logger(caplog):
    s = _state(turn=1)
    mg = s.memory
    mg._slot = "slot-w"

    def _boom(sl):
        raise RuntimeError("落盘炸了")
    mg.save = _boom
    with caplog.at_level(logging.WARNING, logger="finish_turn"):
        out = ml.persist_memory(s)                      # 不得抛
    assert out["error"] and "落盘炸了" in out["error"], out
    assert [r for r in caplog.records if r.name == "finish_turn"], \
        "logger 名必须是 finish_turn（M2 用例按名过滤）"


def test_memory_governance_failure_does_not_raise(caplog):
    s = _state(turn=12)
    mg = s.memory
    mg._slot = "slot-x"

    def _boom(t):
        raise RuntimeError("压缩炸了")
    mg.compress = _boom
    with caplog.at_level(logging.WARNING, logger="finish_turn"):
        out = ml.compress_memory_if_needed(s)           # 不得抛
    assert "压缩炸了" in out["error"], out
    assert any("记忆库压缩/总结失败" in r.getMessage() for r in caplog.records)


# =====================================================================
# 5) 自动存档触发条件与 M2 失败语义
# =====================================================================
def test_autosave_not_attempted_outside_january_or_game_over(monkeypatch):
    s = _state(turn=1, month=2)
    s.game_over = False
    _spy_memory(s)
    calls = _spy_save(monkeypatch)
    out = app_finish_turn(s)["save"]
    assert out["attempted"] is False, out
    assert calls == [], f"不该写盘，实际写了 {calls}"


def test_autosave_attempted_on_january_and_on_game_over(monkeypatch):
    s = _state(turn=1, month=1)
    _spy_memory(s)
    calls = _spy_save(monkeypatch)
    assert app_finish_turn(s)["save"]["attempted"] is True
    assert calls == [0], f"自动槽必须是 0：{calls}"

    s2 = _state(turn=1, month=7)
    s2.game_over = True
    calls2 = _spy_save(monkeypatch)
    _spy_memory(s2)
    assert app_finish_turn(s2)["save"]["attempted"] is True
    assert calls2 == [0], calls2


def test_terminal_check_never_unsets_game_over(monkeypatch):
    # 🔴 第二十二包（2026-10-09）：实现已迁 `core.workflows.evaluation`，消费者按新路径
    # 延迟导入 ⇒ **打桩目标必须同步随迁**。若仍打旧桩 `core.evaluation`，patch 会静默失效
    # （桩只转发名字，改它不影响消费者），本用例就变成空跑——所以这里加 `fired` 断言，
    # 让"桩没接上"当场红，而不是继续绿着什么都没测。常驻扫描见
    # `test_workflows_evaluation_b22.py::test_no_test_patches_the_old_evaluation_stub`。
    import core.workflows.evaluation as ev
    s = _state(turn=1, month=2)
    s.game_over = True
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch)
    fired = []
    monkeypatch.setattr(ev, "check_game_over", lambda _s: fired.append(1) or False)
    app_finish_turn(s)
    assert fired, "桩没被调用 ⇒ 消费者的导入与打桩目标不同家（本用例会退化成空跑）"
    assert s.game_over is True, "只允许把 game_over 置 True，不得反向冲掉"


def test_autosave_failure_sets_save_error_and_logs_error(monkeypatch, caplog):
    s = _state(turn=1, month=1)
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch, exc=RuntimeError("磁盘炸了"))
    with caplog.at_level(logging.ERROR, logger="finish_turn"):
        out = app_finish_turn(s)                        # 不得抛
    assert s.save_error and "磁盘炸了" not in s.save_error, s.save_error  # 文案含类型名，不回显原始异常串
    assert "RuntimeError" in s.save_error, s.save_error
    assert out["save"]["error"], out["save"]
    assert [r for r in caplog.records
            if r.levelno >= logging.ERROR and "自动存档失败" in r.getMessage()], \
        "M2：自动存档失败必须有 ERROR"


def test_autosave_success_clears_stale_error(monkeypatch):
    s = _state(turn=1, month=1)
    s.save_error = "上一回合的陈旧错误"
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch, ret=True)
    out = app_finish_turn(s)
    assert out["save"]["saved"] is True, out["save"]
    assert s.save_error == "", f"成功一次必须清掉陈旧提示：{s.save_error!r}"


def test_autosave_returning_false_is_failure(monkeypatch, caplog):
    s = _state(turn=1, month=1)
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch, ret=False)
    with caplog.at_level(logging.ERROR, logger="finish_turn"):
        out = app_finish_turn(s)
    assert out["save"]["saved"] is False, out["save"]
    assert s.save_error, "save_game 返回 False 同样是失败"
    assert [r for r in caplog.records if r.levelno >= logging.ERROR], "False 也必须记 error"


# =====================================================================
# 6) 薄代理契约：同名入口行为与抽取前一致
# =====================================================================
def test_commands_proxy_returns_none_and_delegates(monkeypatch):
    s = _state(turn=13, month=2)
    _spy_memory(s)
    _spy_dialogue(monkeypatch)
    save_calls = _spy_save(monkeypatch)
    seen = []
    import application.turn_lifecycle as tl
    real = tl.finish_turn

    def spy(state):
        seen.append(state)
        return real(state)
    monkeypatch.setattr(tl, "finish_turn", spy)

    assert cmd_finish_turn(s) is None, "对外契约：代理必须返回 None"
    assert seen == [s], "必须真的委派到应用层，而不是就地还有一份实现"


def test_two_successor_paths_are_same_implementation(monkeypatch):
    """命令层代理与应用层入口对同一 state 产生同样的记忆调用。"""
    s1 = _state(turn=12, month=2)
    c1 = _spy_memory(s1)
    _spy_dialogue(monkeypatch)
    _spy_save(monkeypatch)
    cmd_finish_turn(s1)

    s2 = _state(turn=12, month=2)
    c2 = _spy_memory(s2)
    app_finish_turn(s2)
    assert c1 == c2, f"两条路径调用序列不一致：{c1} != {c2}"
