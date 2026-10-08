# -*- coding: utf-8 -*-
"""宋祚 · 新局初始化编排（应用层组合根）。

> **为什么在这里**：2026-10-07 用户裁定（M25）把「隐户入 POP」的初始化职责
> 从 `core/game_state.py` **移出**，避免基础状态模块直接依赖人口业务模块（§6-1 向下依赖）。
>
> **口径**：**直接调用**人口域服务 `ensure_hidden_in_pops`——**不是**函数对象注入，
> **不建**可选回调，**不建**通用注册表。
>
> **失败语义**：fail-fast。初始化失败即抛 `GameInitError`，**不返回半初始化 state**，
> 因为隐户未注入会让「总口 = 在籍 + 隐户」凭空少 2000 万口，而后续月份无从察觉。
"""
from __future__ import annotations


class GameInitError(RuntimeError):
    """新局初始化失败。**带上下文**（站点 + 通道名），便于直接定位。"""

    def __init__(self, site: str, channel: str, cause: BaseException):
        self.site = site
        self.channel = channel
        self.cause = cause
        super().__init__(
            f"新局初始化失败 @ {site} · 通道 {channel}：{type(cause).__name__}: {cause}"
        )


def init_population(state):
    """把隐户口数（`land.hidden_households`）物化进各路 `农.hidden` 子池。

    必须放在 `GameState` 构造**之后**：`state.land`（含 500 万户设计锚）
    在 `GameState._init_extensions()` 里才建立。

    隐户**不计入在籍** `state.population`（不落籍、不纳税）——见 POP 挂载律条 1/4。
    """
    from core.domains.population.settlement_hidden import ensure_hidden_in_pops

    try:
        return ensure_hidden_in_pops(state)
    except Exception as e:                      # noqa: BLE001 — 统一转成带上下文的失败
        raise GameInitError("new_game", "ensure_hidden_in_pops", e) from e


def init_pops_seats(state):
    """把 POP 实体**下沉到州府级**（方案乙）：路级 `pops` → 各治所 `seats`。

    🔴 **为什么新局也必须下沉**：此前只有**读档**触发下沉，导致新局长期停在
    「路级是真账」状态 —— 而桥接层在无 `seats` 时会**回落到旧载体**，
    写法形同虚设。2026-10-08 用户指出「要求的是数据下沉，改描述算什么」。

    ⚠️ **顺序**：必须在 `init_population` **之后**调用 —— `hidden` 属 `SPLIT_FIELDS`，
    先下沉再写路级会让它落进派生镜像而与治所真账**分叉**。
    """
    from core.foundation.persistence.migrations import sink_pops_to_seats

    return sink_pops_to_seats(state)


def new_game(mode: str = "史实"):
    """开局入口：`GameState` 构造 → 人口域初始化 → **POP 下沉州府级**。

    调用方应改用本函数而非直接 `GameState(...)`，否则隐户不会被注入、POP 也不会下沉。
    """
    from core.game_state import GameState

    state = GameState(mode)
    init_population(state)     # 先注隐户（hidden 在 SPLIT_FIELDS 内）
    init_pops_seats(state)      # 再下沉，避免路级写落进派生镜像
    return state
