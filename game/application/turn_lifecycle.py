# -*- coding: utf-8 -*-
"""回合收尾生命周期（《代码层机制模块化架构方案》§5.2 目标接口的实现）。

    finish_turn(state)
      ├── check_terminal_state(state)          → core.workflows.evaluation
      ├── memory_lifecycle.on_turn_finished(state)
      └── auto_save_if_due(state)              → core.save_load

`core.commands.finish_turn` 迁移期保留同名**薄代理**（§5.2 规则），Backend/内部调用方
无需改导入路径。

⚠️ 与 §5.2 草图的一处**有意差异**（不是遗漏）：草图只列了终局判定与记忆三步，
但抽取前的 `finish_turn` 还承担每年正月/终局的自动存档。抽用时把它显式化为
`auto_save_if_due`，而不是悄悄留在 `commands` 里 —— 否则"生命周期已抽出"是假的。

⚠️ logger 名保持 `"finish_turn"`：既有 M2 用例（`test_error_observability_settle.py`）
按 `logger="finish_turn"` 过滤 ERROR，并断言 `state.save_error` 文案。

对外契约不变：本函数**不抛错**；`commands.finish_turn` 仍返回 `None`
（返回值只在应用层用于可观测/单测，不进入既有调用方语义）。
"""
from __future__ import annotations

import logging

from application.memory_lifecycle import on_turn_finished

_LOG = logging.getLogger("finish_turn")


def check_terminal_state(state) -> bool:
    """终局判定：命中则置 `state.game_over`。

    与抽取前一致——**只会把 game_over 置 True，绝不反向覆写**（存档读回的 True
    不能被一次判定冲掉）。依赖 `core.workflows.evaluation`（第二十二包落流程编排层，
    §5.2 指定的归属口径不变），不绕 `core.commands`，避免应用层与命令入口互引成新环。
    """
    from core.workflows.evaluation import check_game_over
    over = bool(check_game_over(state))
    if over:
        state.game_over = True
    return over


def auto_save_if_due(state) -> dict:
    """自动存档：每年正月写槽 0；游戏结束再写一份最终档。

    审查 P2-3 / M2 的既有语义，原样保留：
      · 异常不得 `pass`——ERROR + traceback；
      · `save_game` 返回 `False` 同样是失败（原实现连返回值一起忽略）；
      · 失败/成功都要动 `state.save_error`，供 UI 一次性提示（成功时清陈旧提示）。
    `save_game` 保持**函数内延迟导入**：既有用例是 monkeypatch
    `core.save_load.save_game` 模块属性，顶层绑定会让打桩失效。
    """
    out = {"attempted": False, "saved": False, "error": None}
    if not (getattr(state, "month", 0) == 1 or getattr(state, "game_over", False)):
        return out
    out["attempted"] = True
    try:
        from core.save_load import save_game
        ok = save_game(state, slot=0)
        if not ok:
            _LOG.error("自动存档失败 slot=0（save_game 返回 False，未落盘）")
            state.save_error = "自动存档失败：本年正月的自动档未能写入槽 0（请手动存档）"
        else:
            out["saved"] = True
            state.save_error = ""
    except Exception as e:  # noqa: BLE001 — 不得静默，也不得中断结算收尾
        _LOG.error("自动存档失败 slot=0：%s", e, exc_info=True)
        out["error"] = str(e)
        state.save_error = f"自动存档失败（{type(e).__name__}）：请手动存档"
    return out


def finish_turn(state) -> dict:
    """回合收尾编排。顺序固定：终局判定 → 记忆三步 → 自动存档。

    终局判定必须在自动存档之前——抽取前的实现就是先定 `game_over`
    再按 `month == 1 or game_over` 决定是否写最终档。
    """
    return {
        "game_over": check_terminal_state(state),
        "memory": on_turn_finished(state),
        "save": auto_save_if_due(state),
    }
