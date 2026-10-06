# -*- coding: utf-8 -*-
"""回合记忆生命周期（《代码层机制模块化架构方案》§5.2）。

从 `core.commands.finish_turn` 抽出。§5.1 的事实：该函数此前同时承担终局判定、
主记忆库压缩/周期总结/归档、对话记忆周期总结、以及每回合落盘——本模块只接管
**记忆这三步**，终局判定与自动存档留在 `turn_lifecycle`。

边界（§5.2 规则）：不运行月结算、不复制 `state.memory` 数据、失败沿用
「记日志、不阻断主流程」的明确语义（不静默 `pass`）。

⚠️ logger 名保持 `"finish_turn"`：既有 M2 可观测性用例
（`test_error_observability_settle.py`，`caplog.at_level(..., logger="finish_turn")`）
按 logger 名过滤。抽模块改变这个名，等于把一条已登记的对外可见面弄丢。
"""
from __future__ import annotations

import logging

_LOG = logging.getLogger("finish_turn")

# 抽取前的既有阈值，原样带过来（改动会直接改变记忆治理频率，属玩法口径）
COMPRESS_INTERVAL = 6             # 每 6 回合压缩主记忆库
PERIOD_SUMMARY_INTERVAL = 12      # 每 12 回合周期总结 + 归档（对齐 memory_graph._ARCHIVE_INTERVAL）
DIALOGUE_SUMMARY_INTERVAL = 3     # 每 3 回合对话记忆总结去重


def _slot_of(state, mg):
    """记忆槽位取法沿用原实现：优先 `mg._slot`，回落 `state.memory_slot`。"""
    _slot = getattr(mg, "_slot", None)
    if _slot is None:
        _slot = getattr(state, "memory_slot", None)
    return _slot


def compress_memory_if_needed(state) -> dict:
    """主记忆库治理：压缩 → 周期总结 → 归档降权。

    归档这一步是补接线（审查 P1-5）：原实现 `archive()` 零调用方 → 关系/实体只增不减，
    而 `save()` 每回合 DELETE 后全量重写，IO 随历史线性放大。只打 archived 标记、
    不物理删除。顺序固定：先总结（概要已覆盖本轮）再降权。
    """
    out = {"compressed": False, "summarized": False, "archived": False, "error": None}
    try:
        mg = state.memory
        mg.turn = state.turn
        if state.turn > 0 and state.turn % COMPRESS_INTERVAL == 0:
            mg.compress(state.turn)
            out["compressed"] = True
        if state.turn > 0 and state.turn % PERIOD_SUMMARY_INTERVAL == 0:
            mg.summarize_period(state.turn)
            out["summarized"] = True
            _aslot = _slot_of(state, mg)
            if _aslot is not None:
                mg.archive(_aslot)
                out["archived"] = True
    except Exception as e:  # noqa: BLE001 — 记忆治理失败不得阻断结算收尾
        _LOG.warning("记忆库压缩/总结失败（不阻断结算）：%s", e)
        out["error"] = str(e)
    return out


def summarize_dialogue_if_due(state) -> dict:
    """对话记忆库每 3 回合总结去重（防漂移/膨胀；不动旧数据）。

    ⚠️ 既有语义保留：这一支**没有** `turn > 0` 前置条件（`turn=0` 时 `0 % 3 == 0`
    也会触发一次），与上面主库两支不同。抽取时不顺手"修正"它——是否该修属玩法口径。
    """
    out = {"summarized": False, "error": None}
    try:
        from memory.dialogue_memory import get_dialogue_memory
        dm = get_dialogue_memory(state)
        dm.turn = state.turn
        if state.turn % DIALOGUE_SUMMARY_INTERVAL == 0:
            dm.summarize_dialogues(state.turn)
            out["summarized"] = True
    except Exception as e:  # noqa: BLE001
        _LOG.warning("对话总结失败（不阻断结算）：%s", e)
        out["error"] = str(e)
    return out


def persist_memory(state) -> dict:
    """每回合落盘记忆库（防中途崩溃丢失）。

    审查 P1-5/P2-2：失败必须记日志而非静默吞——`save()` 返回 False 同样是失败。
    """
    out = {"attempted": False, "saved": False, "error": None}
    try:
        mg = state.memory
        _slot = _slot_of(state, mg)
        if _slot is not None:
            out["attempted"] = True
            ok = mg.save(_slot)
            out["saved"] = bool(ok)
            if not ok:
                _LOG.warning("记忆库写盘失败（slot=%s），本轮记忆未持久化", _slot)
    except Exception as e:  # noqa: BLE001
        _LOG.warning("记忆库落盘异常（不阻断结算）：%s", e)
        out["error"] = str(e)
    return out


def on_turn_finished(state) -> dict:
    """记忆生命周期三步：主库治理 → 对话记忆 → 落盘。

    顺序沿用抽取前的 `finish_turn`，**不要调换**：主库先总结再落盘，
    落盘覆盖前两步的成果。
    """
    return {
        "memory": compress_memory_if_needed(state),
        "dialogue": summarize_dialogue_if_due(state),
        "persist": persist_memory(state),
    }
