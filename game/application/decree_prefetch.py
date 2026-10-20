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
3. Jev 不可用 ⇒ 生产者返回 None ⇒ 不写槽位（缺失≠假装已判）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("decree_prefetch")

__all__ = ["prefetch_decree_slots", "last_result"]

#: 最近一次预取结果（诊断用；不落存档）
_LAST: Optional[dict] = None


def last_result() -> Optional[dict]:
    return dict(_LAST) if isinstance(_LAST, dict) else None


def prefetch_decree_slots(state) -> Optional[dict]:
    """对当前待行诏令跑一次天道裁决（失败返回 None，不抛）。"""
    global _LAST
    got = None
    try:
        from ai.contracts_decree import DecreeContractMixin

        got = DecreeContractMixin().decree_duration_decide(state)
    except Exception:  # noqa: BLE001 — 下旨不得因天道失败而失败
        log.warning("prefetch_decree_slots 失败（不阻断下旨）", exc_info=True)
        got = None
    _LAST = {"ok": bool(got), "slots": dict(got) if isinstance(got, dict) else None}
    return got
