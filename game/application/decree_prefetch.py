# -*- coding: utf-8 -*-
"""下旨时预取天道档位（2026-10-20，确定性触发）。

为什么要这层：
- 消费端（decree_duration / edict_closure）只读 state._decree_ai，自己不调 Jev；
- 生产者（ai.contracts_decree.decree_duration_decide）若只靠 agent 唤醒词触发，
  玩家下诏但未命中唤醒词时槽位为空 ⇒ 天道没参与。
- 本模块在**下旨成功之后**调用一次生产者，保证「每道旨发出时都有一次天道裁决」。

纪律：
1. 只在**玩家动作路径**（后端动作分派）调用，**不在结算链内**（结算期禁止同步 HTTP）；
2. 失败一律吞掉并留痕日志：下旨本身不能因为 Jev 不可用而失败；
3. Jev 不可用 ⇒ 生产者返回 None ⇒ 槽位保持**空**（缺失≠假装已判）。

🔴 P0-4（2026-10-20 全审）：**调生产者前先清槽**。
旧实现只在生产者成功时写槽，失败时旧槽原样保留 —— 于是 Jev 不可用/超时后，
新诏会沿用**上一道诏**的时效/态度/落地档（实测 A 旨「长期」后，B 旨 `pay_reform`
仍得 `timing=long, months=12`）。清槽后「未判」就真的是未判，消费端回落程序口径。
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("decree_prefetch")

__all__ = ["prefetch_decree_slots", "last_result", "clear_ai_slot"]

#: 最近一次预取结果（诊断用；不落存档）
_LAST: Optional[dict] = None


def last_result() -> Optional[dict]:
    return dict(_LAST) if isinstance(_LAST, dict) else None


def clear_ai_slot(state, attr: str) -> bool:
    """清空运行时 AI 槽位（存在才删）。

    用 `delattr` 而不是赋 `None`：槽位是**动态属性**，删掉后 `hasattr(state, "_decree_ai")`
    仍为 False（保持"从未判过/未定义"语义，诊断与测试都据此判定），赋 None 会留下
    一个"存在但为 None"的占位，容易被误当成"判过且为空"。
    """
    if state is None or not attr:
        return False
    try:
        if hasattr(state, attr):
            delattr(state, attr)
            return True
    except Exception:  # noqa: BLE001 — 槽位清理失败不得阻断下旨/结算
        log.warning("清理 AI 槽位 %s 失败（按未清处理）", attr, exc_info=True)
    return False


def prefetch_decree_slots(state) -> Optional[dict]:
    """对当前待行诏令跑一次天道裁决（失败返回 None，不抛）。"""
    global _LAST
    got = None
    # P0-4：先清槽 —— 生产者失败时不写槽，旧槽若留着就会被新诏当成本次裁决。
    clear_ai_slot(state, "_decree_ai")
    try:
        from ai.contracts_decree import DecreeContractMixin

        got = DecreeContractMixin().decree_duration_decide(state)
    except Exception:  # noqa: BLE001 — 下旨不得因天道失败而失败
        log.warning("prefetch_decree_slots 失败（不阻断下旨）", exc_info=True)
        got = None
    _LAST = {"ok": bool(got), "slots": dict(got) if isinstance(got, dict) else None}
    return got
