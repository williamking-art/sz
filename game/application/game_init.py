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


def init_local_treasury_seats(state):
    """把**地方府库**（`local_treasury`）下沉到州府级（主线 B 第一片）。

    与 `init_pops_seats` 同型：真账落 `seats[治所]["local_treasury"]`，路级降为 Σ 派生镜像。
    🔴 **不是**中央 `state.treasury`（国库）——本模块只管地方府库（账户 `local:<路>`）。
    **必须在 `init_pops_seats` 之后**——分摊权重取自治所人口。
    幂等：已下沉的路跳过；权重不可得或无 `local_treasury` 数值的路跳过（不臆造归属）。
    """
    from core.foundation.persistence.migrations import sink_local_treasury_to_seats

    return sink_local_treasury_to_seats(state)


def init_buildings_seats(state):
    """把**建筑**（`buildings`）下沉到州府级（主线 B 批次 2 · M38b-2）。

    真账落 `seats[治所]["buildings"]`，路级降为 Σ 派生镜像（**保形态**：字典条目仍字典）。
    **必须在 `init_pops_seats` 之后**——首府（路治）判定取治所人口权重作同级决胜。
    幂等：已下沉的路跳过；无可分配等级或判不出首府的路跳过（不臆造归属）。
    """
    from core.foundation.persistence.migrations import sink_buildings_to_seats

    return sink_buildings_to_seats(state)


def init_building_owners(state):
    """给建筑登记**归属**（P2 第一片 · M91；Jev 甲 0.866）。

    幂等：只填缺失、不覆盖；未登记类型跳过（不臆造）；**保形态**（`buildings` 不动）；**零数值变化**。
    """
    from core.foundation.persistence.migrations import assign_building_owners

    return assign_building_owners(state)


def init_workshop_expansion(state):
    """**丝坊补座**（产能批 · M196）——无条件**幂等**入口，新局与读档共用。

    Jev：旋钮＝**作坊数量**（乙 0.591）· 量级＝**温和 ~10%**（甲 0.450）· 分布＝**按丝产能加权**（丁 0.388）
    ⇒ 丝坊 **7 → 28 座**。只建实例、**不动钱货**、**不改 `yield`**（口径单点）。
    ⚠️ 必须在 `init_workshop_owners` **之前**调用（否则新座无货主）。
    """
    from core.foundation.persistence.migrations import open_workshop_expansion

    return open_workshop_expansion(state)


def init_workshop_owners(state):
    """给作坊登记**货主**（产权落点 · M66；Jev choose A 0.665）。

    幂等：只填缺失、不覆盖；判不出归属者跳过（不臆造）；**不动任何钱**。
    依赖`workshops`已建（`GameState.__init__` 建）与治所（定路）。
    """
    from core.foundation.persistence.migrations import assign_workshop_owners

    return assign_workshop_owners(state)


def init_canal_seats(state):
    """把**漕运淤塞**（`canal_block`）下沉到州府级（交通下沉 M39c-1）。

    原为全国单标量 ⇒ 按路落到**首府**治所（不编造逐治所差异）；路级/全国降为派生镜像。
    **必须在 `init_pops_seats` 之后**——首府判定依赖治所存在。
    幂等：已下沉的路跳过。
    """
    from core.foundation.persistence.migrations import sink_canal_to_seats

    return sink_canal_to_seats(state)


def init_storage_seats(state):
    """把**常平仓**（`changping_stock`）下沉到州府级（批次 4 · M40a）。

    路级存量落**首府**治所（不编造逐治所差异）；路级降为 Σ 派生镜像。
    **必须在 `init_pops_seats` 之后**——首府判定依赖治所存在。幂等。
    """
    from core.foundation.persistence.migrations import sink_changping_to_seats

    return sink_changping_to_seats(state)


def init_prefectural_storage_seats(state):
    """把**州仓**（`storage`）下沉到州府级（批次 4 · M40b）。

    路级存量落**首府**治所（不编造逐治所差异）；路级降为 Σ 派生镜像。
    **必须在 `init_pops_seats` 之后**——首府判定依赖治所存在。幂等。
    """
    from core.foundation.persistence.migrations import sink_prefectural_storage_to_seats

    return sink_prefectural_storage_to_seats(state)


def init_spatial_warehouses_seats(state):
    """把**治所物理四仓位**（`warehouses`）下沉到全域 seats（空间确权底座 · Bundle 1）。

    四大物理仓位：public_granary, public_depot, civilian_depots, private_storage。
    **必须在 `init_pops_seats` 之后**——依赖治所 seats 存在。幂等。
    """
    from core.foundation.persistence.migrations import sink_spatial_warehouses_to_seats

    return sink_spatial_warehouses_to_seats(state)


def init_minister_agents(state):
    """为中枢在任 holders 建立 `minister_agents` 运行态（C-1）。

    正式诏令/密旨的复述与事权门禁经 `confirm_decree -> can_act` 需要
    `state.minister_agents` 中已有该人；新局若不建档，任何“有受命人”的诏令都会
    以 `unknown_actor/unauthorized` 死锁。这里只做**增量初始化**：已存在者原样保留，
    权限只作为 `can_act` 的 >0 门槛，真正的调兵/编制事权仍由
    `resolve_executor`/`check_authority` 按当前官职反查（人不另立权限）。
    """
    import logging
    _log = logging.getLogger("game_init")
    try:
        from core.domains.administration.minister_agent import ensure_actor
    except Exception as e:  # noqa: BLE001
        _log.warning("init_minister_agents 导入失败（不阻断开局）：%s", e)
        return 0
    orgs = getattr(state, "central_orgs", None) or {}
    # name -> posts（同一人可兼多职，actor 只建一次）
    by_name = {}
    for org in orgs.values():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        lead = str(org.get("lead") or "").strip()
        if lead:
            by_name.setdefault(lead, [])
        for post, holder in (org.get("holders") or {}).items():
            name = str(holder or "").strip()
            if not name:
                continue
            posts = by_name.setdefault(name, [])
            if post not in posts:
                posts.append(str(post))
    seeded = 0
    for name, posts in by_name.items():
        try:
            existing = (getattr(state, "minister_agents", None) or {}).get(name)
            if isinstance(existing, dict):
                # 已存在：只补空 posts，不覆盖记忆/权限
                if not existing.get("posts"):
                    existing["posts"] = list(posts)
                continue
            ensure_actor(state, name, posts=list(posts), authority=0.5)
            seeded += 1
        except Exception as e:  # noqa: BLE001
            _log.warning("init_minister_agents 建 %s 失败（跳过）：%s", name, e)
    return seeded


def new_game(mode: str = "史实"):
    """开局入口：`GameState` → 人口域初始化 → **POP→府库→建筑→漕运→常平仓→州仓→物理仓位 依次下沉州府级**。

    调用方应改用本函数而非直接 `GameState(...)`，否则隐户不会被注入、真账都不会下沉。
    """
    from core.game_state import GameState

    state = GameState(mode)
    init_population(state)              # 先注隐户（hidden 在 SPLIT_FIELDS 内）
    init_pops_seats(state)              # 再下沉，避免路级写落进派生镜像
    init_local_treasury_seats(state)    # 府库分摊依赖治所人口，必须排在其后
    init_buildings_seats(state)         # 首府判定同样依赖治所人口
    init_canal_seats(state)             # 漕运同样按首府承载（依赖 seats 已建）
    init_storage_seats(state)           # 常平仓同型（批次 4 仓储片 · M40a）
    init_prefectural_storage_seats(state) # 州仓同型（批次 4 仓储片 · M40b）
    init_spatial_warehouses_seats(state)  # 物理四仓位下沉（空间确权底座 · Bundle 1）

    # 🔴 M196：丝坊补座**必须在登记货主之前**（新座才有货主）
    init_workshop_expansion(state)      # M196：丝坊补座（绝对目标 28 座、幂等、不动钱货）
    init_workshop_owners(state)         # M66：作坊货主（产权落点，只登记字段、不动钱）
    init_building_owners(state)         # M91：建筑归属（P2 第一片，building_meta，零数值变化）
    init_minister_agents(state)         # C-1：中枢在任官员 Agent 运行态（复述/事权门禁前置）
    return state
