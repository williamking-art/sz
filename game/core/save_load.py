# -*- coding: utf-8 -*-
"""宋祚 · 存档系统"""
import os
import json
from datetime import datetime

from content.data import SAVE_DIR


def _slot_path(slot: int) -> str:
    """存档槽位文件路径（save/load/slots 三处共用，避免硬编码漂移）。"""
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")


def save_game(state, slot: int = 1) -> bool:
    """保存游戏到指定槽位（含记忆知识库同步写盘）。"""
    import logging as _lg
    _slog = _lg.getLogger("save_load")
    os.makedirs(SAVE_DIR, exist_ok=True)
    # 记忆知识库（Phase 3a）：回合末原子写盘到 slot_{slot}.db
    # 审查 P2-2 修复：写盘失败记日志而非静默吞（防崩溃后无感知丢失记忆）
    try:
        state.memory.turn = state.turn
        state.memory_slot = slot
        _ok = state.memory.save(slot)
        if not _ok:
            _slog.warning("记忆库写盘失败（slot=%s），主存档继续但不包含本轮记忆更新", slot)
    except Exception as e:  # noqa: BLE001
        _slog.warning("记忆库写盘异常（slot=%s，不阻断主存档）：%s", slot, e)

    data = {
        "version": "0.1.0",
        "schema_version": 2,  # 经济全浮动重构 v2
        "save_time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "slot": slot,

        "year": state.year,
        "month": state.month,
        "turn": state.turn,
        "era_name": state.era_name,
        "difficulty": state.difficulty,

        "emperor_name": state.emperor_name,
        "emperor_health": state.emperor_health,
        "emperor_alive": state.emperor_alive,
        "is_abdicated": state.is_abdicated,
        "abdication_reason": state.abdication_reason,
        "art_mastery": state.art_mastery,
        "taoism_leaning": state.taoism_leaning,
        "pleasure_leaning": state.pleasure_leaning,

        "prestige": state.prestige,
        "arrival_rate_base": state.arrival_rate_base,
        "treasury": state.treasury,
        "imperial_treasury": state.imperial_treasury,
        "pending_inner_transfer": getattr(state, "pending_inner_transfer", None),
        "longterm_effects": getattr(state, "longterm_effects", []),
        "short_term_log": getattr(state, "short_term_log", []),
        "tool_registry": getattr(state, "tool_registry", {}),
        "branch_registry": getattr(state, "branch_registry", {}),
        "tech_registry": getattr(state, "tech_registry", {}),
        "minister_estate": getattr(state, "minister_estate", {}),
        "investments": getattr(state, "investments", {}),
        "era_state": getattr(state, "era_state", {}),
        "era_building_log": getattr(state, "era_building_log", []),
        "treaties": getattr(state, "treaties", {}),
        "_at_war": getattr(state, "_at_war", {}),
        "_sui_gong_mult": getattr(state, "_sui_gong_mult", {"辽": 1.0, "金": 1.0, "西夏": 1.0}),
        "_trade_income": getattr(state, "_trade_income", {}),
        "wine_tax": getattr(state, "wine_tax", 100000),
        "imperial_granary": getattr(state, "imperial_granary", 0),
        "mechanisms": getattr(state, "mechanisms", {}),

        # 仓廪 / 通货（新字段，兼容旧档缺省）
        "granary": getattr(state, "granary", 1500),
        "granary_cap": getattr(state, "granary_cap", 1500),
        "granary_stats": getattr(state, "granary_stats", {}),
        "money_supply": getattr(state, "money_supply", 60000000),
        "price_level": getattr(state, "price_level", 1.0),
        "grain_price": getattr(state, "grain_price", 1.0),
        "canal_block": getattr(state, "canal_block", 10),
        "single_whip": getattr(state, "single_whip", False),
        "timeline": getattr(state, "timeline", {}),
        "pending_breaks": getattr(state, "pending_breaks", {}),
        "pay_system": getattr(state, "pay_system", {"mode": "本色折色", "grain_ratio": 0.5, "cash_ratio": 0.5}),
        "economy_history": getattr(state, "economy_history", []),
        "economy_knowledge": getattr(state, "economy_knowledge", {}),
        "commerce_tax_rate": getattr(state, "commerce_tax_rate", 0.15),
        "tax_breakdown": getattr(state, "tax_breakdown", {"commerce": 0, "poll": 0}),
        "waste_reform": getattr(state, "waste_reform",
                                {"active": False, "kind": "", "savings": 0,
                                 "target": 0, "months_left": 0, "progress": 0}),

        "factions": state.factions,

        "external": state.external,
        "army_units": [vars(u) for u in state.army_units],
        "central_arsenal": {"stock": state.central_arsenal.stock},
        "defense_lines": state.defense_lines,

        "decree_bandwidth": state.decree_bandwidth,
        "direct_decree_used": state.direct_decree_used,
        "wolf_count": state.wolf_count,
        "pending_decrees": state.pending_decrees,
        "pending_secret_decrees": state.pending_secret_decrees,
        "active_decrees": state.active_decrees,
        "edict_drafts": getattr(state, "edict_drafts", []),
        "council_reviews": getattr(state, "council_reviews", {}),
        "dialogue_history": getattr(state, "dialogue_history", []),
        "last_audience": getattr(state, "last_audience", ""),

        "personal_action": state.personal_action,
        "imperial_action": getattr(state, "imperial_action", {}),
        "imperial_micro_count": getattr(state, "imperial_micro_count", 0),
        "major_policy": state.major_policy,
        "major_policy_target": state.major_policy_target,

        "active_events": state.active_events,
        "event_pressure": state.event_pressure,
        "event_history": state.event_history,

        "population": state.population,
        "population_satisfaction": state.population_satisfaction,
        "refugee_count": state.refugee_count,

        "disaster_severity": state.disaster_severity,
        "disaster_region": state.disaster_region,

        "diff_params": state.diff_params,
        "statistics": state.statistics,
        "spy_network": state.spy_network,

        "yamen": state.yamen,
        "prefectures": state.prefectures,
        "external_regimes": getattr(state, "external_regimes", {}),
        "longterm_public": getattr(state, "longterm_public", []),
        "longterm_secret": getattr(state, "longterm_secret", []),
        "minister_memory": getattr(state, "minister_memory", {}),
        "player_minister_status": getattr(state, "player_minister_status", {}),

        # 大臣忠诚度/贪腐度（后台隐藏，不可见）与中枢机构运行态（权限随职位）
        "loyalty": getattr(state, "loyalty", {}),
        "corruption": getattr(state, "corruption", {}),
        "central_orgs": getattr(state, "central_orgs", {}),
        "authority_matters": getattr(state, "authority_matters", {}),

        # 经济全浮动重构新增（向后兼容缺省）
        "payraise_budget": getattr(state, "payraise_budget", 0),
        "oversight": getattr(state, "oversight", 0.30),
        "resources": getattr(state, "resources", {}),
        "projects": getattr(state, "projects", {}),
        "workshops": getattr(state, "workshops", {}),
        "defense_lines": getattr(state, "defense_lines", {}),

        "land": state.land,

        "jiaozi": state.jiaozi,
        "maritime": state.maritime,
        "coin": state.coin,
        "bank": state.bank,
        "standard": state.standard,
        "exam": state.exam,
        "tech": state.tech,
        "diplomacy_log": state.diplomacy_log,
        "alliance_jin_liao": state.alliance_jin_liao,

        "settlement_log": state.settlement_log[-12:] if state.settlement_log else [],
        "game_over": state.game_over,
        "game_result": state.game_result,
        "victory": state.victory,
    }

    path = _slot_path(slot)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def _merge_regions(target: dict, saved) -> None:
    """把存档中的政权数据并入新版默认结构。

    旧存档缺失新增字段（name/population/unrest/... ）时保留默认值，
    从而保证读档后详情面板与舆图标签不会缺字段。
    """
    if not isinstance(saved, dict):
        return
    for key, val in saved.items():
        if not isinstance(val, dict):
            continue
        if key in target and isinstance(target[key], dict):
            target[key].update(val)
        else:
            target[key] = val


def load_game(slot: int = 1):
    """从指定槽位读取存档，返回 GameState 或 None"""
    path = _slot_path(slot)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 延迟导入避免循环
    from core.game_state import GameState

    state = GameState(data.get("difficulty", "史实"))

    # 记忆知识库（Phase 3a）：按槽位加载（损坏 → 重建空图，不阻断游戏）
    state.memory_slot = slot
    state.memory.turn = data.get("turn", 0)
    state.memory.load(slot)

    # 恢复基础时间
    state.year = data.get("year", 1101)
    state.month = data.get("month", 1)
    state.turn = data.get("turn", 0)
    state.era_name = data.get("era_name", "建中靖国")

    # 恢复皇帝
    state.emperor_name = data.get("emperor_name", "赵佶")
    state.emperor_health = data.get("emperor_health", 75)
    state.emperor_alive = data.get("emperor_alive", True)
    state.is_abdicated = data.get("is_abdicated", False)
    state.abdication_reason = data.get("abdication_reason", "")
    state.art_mastery = data.get("art_mastery", 85)
    state.taoism_leaning = data.get("taoism_leaning", 25)
    state.pleasure_leaning = data.get("pleasure_leaning", 30)

    # 恢复系统状态
    state.prestige = data.get("prestige", 55)
    state.arrival_rate_base = data.get("arrival_rate_base", 0.45)
    state.treasury = data.get("treasury", 5000000)
    state.imperial_treasury = data.get("imperial_treasury", 1000000)
    state.pending_inner_transfer = data.get("pending_inner_transfer")
    state.longterm_effects = data.get("longterm_effects", []) or []
    state.short_term_log = data.get("short_term_log", []) or []
    state.tool_registry = data.get("tool_registry", {}) or {}
    state.branch_registry = data.get("branch_registry", {}) or {}
    state.tech_registry = data.get("tech_registry", {}) or {}
    state.minister_estate = data.get("minister_estate", {}) or dict(getattr(state, "minister_estate", {}))
    state.investments = data.get("investments", {}) or {}
    state.era_state = data.get("era_state", {}) or dict(getattr(state, "era_state", {}))
    state.era_building_log = data.get("era_building_log", []) or []
    state.treaties = data.get("treaties", {}) or {}
    state._at_war = data.get("_at_war", {}) or {}
    state._sui_gong_mult = data.get("_sui_gong_mult", {"辽": 1.0, "金": 1.0, "西夏": 1.0}) or {"辽": 1.0, "金": 1.0, "西夏": 1.0}
    state._trade_income = data.get("_trade_income", {}) or {}
    state.wine_tax = data.get("wine_tax", getattr(state, "wine_tax", 100000))
    state.imperial_granary = data.get("imperial_granary", getattr(state, "imperial_granary", 0))
    state.mechanisms = data.get("mechanisms", getattr(state, "mechanisms", {}))

    # 恢复仓廪/通货（含旧档兼容默认）
    state.granary = data.get("granary", getattr(state, "granary", 1500))
    state.granary_cap = data.get("granary_cap", getattr(state, "granary_cap", 1500))
    state.granary_stats = data.get("granary_stats", getattr(state, "granary_stats", {}))
    state.money_supply = data.get("money_supply", getattr(state, "money_supply", 60000000))
    state.price_level = data.get("price_level", getattr(state, "price_level", 1.0))
    state.grain_price = data.get("grain_price", getattr(state, "grain_price", 1.0))
    state.canal_block = data.get("canal_block", getattr(state, "canal_block", 10))
    state.single_whip = data.get("single_whip", getattr(state, "single_whip", False))
    # 历史改写位（旧档缺省空 dict，自动兼容）
    state.timeline = data.get("timeline", getattr(state, "timeline", {}))
    # 待确认改写位（战略决策点·奏报朱批；旧档缺省空 dict，自动兼容）
    state.pending_breaks = data.get("pending_breaks", getattr(state, "pending_breaks", {}))
    state.pay_system = data.get("pay_system", getattr(state, "pay_system", {"mode": "本色折色", "grain_ratio": 0.5, "cash_ratio": 0.5}))
    state.economy_history = data.get("economy_history", getattr(state, "economy_history", []))
    state.economy_knowledge = data.get("economy_knowledge", getattr(state, "economy_knowledge", {}))
    state.commerce_tax_rate = data.get("commerce_tax_rate", getattr(state, "commerce_tax_rate", 0.15))
    state.tax_breakdown = data.get("tax_breakdown", getattr(state, "tax_breakdown", {"commerce": 0, "poll": 0}))
    state.waste_reform = data.get("waste_reform", getattr(state, "waste_reform",
                                  {"active": False, "kind": "", "savings": 0,
                                   "target": 0, "months_left": 0, "progress": 0}))
    # 旧档兼容：factions 按派系逐项合并，缺失的新字段保留 GameState 默认值
    saved_factions = data.get("factions", state.factions)
    if isinstance(saved_factions, dict):
        for fn, fdata in saved_factions.items():
            if fn in state.factions and isinstance(fdata, dict):
                state.factions[fn].update(fdata)
            else:
                state.factions[fn] = fdata
    state.external = data.get("external", state.external)
    # 军队真账：兵额已迁移到 army_units（list[ArmyUnit]），central_arsenal 为央级实物库
    from ui.panels_military import build_army_units, ArmyUnit, CentralArsenal  # 延迟导入，避免顶层互引
    if "army_units" not in data:
        # 旧档兼容：无 army_units 字段，从 state 重建
        state.army_units = build_army_units(state)
        state.central_arsenal = CentralArsenal()
    else:
        # 军队模型迁移（用户定稿·每路禁/厢/乡各一支）：
        #   ① 旧版单兵种（branch/troops）→ branches {"军籍:兵种": 人数}；
        #   ② 混合版（branches 键「军籍:兵种」复合键）→ 按军籍拆分到对应军队（每支单一军籍），兵额守恒。
        _units = []
        for d in data.get("army_units", []):
            if not isinstance(d, dict):
                continue
            d = dict(d)
            if "branches" not in d and "branch" in d:
                d["branches"] = {f"{d.get('tier', '禁军')}:{d.pop('branch', '轻步兵')}": int(d.pop("troops", 0))}
            brs = d.get("branches") or {}
            if any(":" in k for k in brs):
                # 复合键拆分：按军籍分组建（合并同军籍兵种），每支军队单一军籍
                by_tier = {}
                for k, n in brs.items():
                    t, b = k.split(":", 1) if ":" in k else (d.get("tier", "禁军"), k)
                    bucket = by_tier.setdefault(t, {})   # 先建桶再取，避免 RHS 先求值 KeyError
                    bucket[b] = bucket.get(b, 0) + n
                for t, brs2 in by_tier.items():
                    nd = dict(d)
                    nd["tier"] = t
                    nd["branches"] = brs2
                    _units.append(ArmyUnit(**nd))
            else:
                _units.append(ArmyUnit(**d))
        state.army_units = _units
        _stock = data.get("central_arsenal", {}).get("stock", {})
        state.central_arsenal = CentralArsenal(stock=_stock) if _stock else CentralArsenal()
    state.defense_lines = data.get("defense_lines", state.defense_lines)

    # 恢复诏令
    state.decree_bandwidth = data.get("decree_bandwidth", 6)
    state.direct_decree_used = data.get("direct_decree_used", 0)
    state.wolf_count = data.get("wolf_count", 0)
    state.pending_decrees = data.get("pending_decrees", [])
    state.pending_secret_decrees = data.get("pending_secret_decrees", [])
    state.active_decrees = data.get("active_decrees", [])
    state.edict_drafts = data.get("edict_drafts", getattr(state, "edict_drafts", []))
    state.council_reviews = data.get("council_reviews", getattr(state, "council_reviews", {}))
    state.dialogue_history = data.get("dialogue_history", getattr(state, "dialogue_history", []))
    state.last_audience = data.get("last_audience", getattr(state, "last_audience", ""))

    # 恢复施政
    state.personal_action = data.get("personal_action", "")
    # 皇帝个人行动矩阵（契约 v2）：旧档无 imperial_action 时由单值 personal_action 迁移
    ia = data.get("imperial_action") or {}
    if not isinstance(ia, dict) or not ia:
        _legacy = {"勤政": "临朝", "书画翰墨": "书画翰墨",
                   "崇道修醮": "崇道修醮", "宴游享乐": "宴游享乐"}.get(state.personal_action, "")
        if _legacy:
            ia = {"location": "宫里", "mode": "公开", "action": _legacy,
                  "prepared": False, "pending_months": 0, "target": ""}
    state.imperial_action = ia
    state.imperial_micro_count = int(data.get("imperial_micro_count", 0) or 0)
    # pending_imperial_trip = 准备中的 imperial_action（同一 dict 指针，不落档）
    state.pending_imperial_trip = state.imperial_action if state.imperial_action.get("pending_months", 0) > 0 else None
    state._emperor_ai = None   # 契约槽位为回合内瞬态，不落档
    state.major_policy = data.get("major_policy", "")
    state.major_policy_target = data.get("major_policy_target", "")

    # 恢复事件
    state.active_events = data.get("active_events", [])
    state.event_pressure = data.get("event_pressure", {})
    state.event_history = data.get("event_history", [])

    # 恢复人口
    state.population = data.get("population", 80000000)
    state.population_satisfaction = data.get("population_satisfaction", 55)
    state.refugee_count = data.get("refugee_count", 0)

    # 恢复灾荒
    state.disaster_severity = data.get("disaster_severity", 0)
    state.disaster_region = data.get("disaster_region", "")

    # 恢复其他
    state.diff_params = data.get("diff_params", state.diff_params)
    state.statistics = data.get("statistics", state.statistics)
    state.spy_network = data.get("spy_network", state.spy_network)
    state.settlement_log = data.get("settlement_log", [])

    # 恢复扩展维度
    state.yamen = data.get("yamen", state.yamen)
    _merge_regions(state.prefectures, data.get("prefectures"))
    _merge_regions(state.external_regimes, data.get("external_regimes"))
    state.longterm_public = data.get("longterm_public", [])
    state.longterm_secret = data.get("longterm_secret", [])
    state.minister_memory = data.get("minister_memory", {}) or {}
    # 代码审理（旧机制融入新机制）：旧 minister_memory（dict）加载时自动迁入
    # DialogueMemory（对话库，saves/slot_{slot}_dialogue.db）——新写入走新机制；
    # minister_memory 降为兼容读（旧档可读，不再新增写入——离任已双写图谱）。
    if state.minister_memory:
        try:
            from memory.dialogue_memory import get_dialogue_memory
            _dm = get_dialogue_memory(state)
            _dm.turn = state.turn
            for _name, _entries in list(state.minister_memory.items()):
                for _e in list(_entries or [])[-10:]:
                    try:
                        _dm.add_dialogue(_name, state.turn, _name, str(_e)[:200],
                                         intent="", stance="旧档迁移")
                    except Exception:
                        pass
        except Exception:
            pass
    state.player_minister_status = data.get("player_minister_status", {}) or {}
    state.loyalty = data.get("loyalty", state.loyalty)
    state.corruption = data.get("corruption", state.corruption)
    state.central_orgs = data.get("central_orgs", state.central_orgs)
    # 旧档兼容：中枢机构补齐 posts/holders/comissions（权限三层分离）
    # 无 posts/holders 的旧档，用原 lead 兜底为首个岗位在任者，保证换人不变权逻辑不崩。
    from content.ministers import org_lead, CENTRAL_ORG_INFO
    for oname, o in state.central_orgs.items():
        if not isinstance(o, dict):
            continue
        if not o.get("posts"):
            o["posts"] = [dict(p) for p in (CENTRAL_ORG_INFO.get(oname, {}).get("posts") or [])]
        if not o.get("holders"):
            o["holders"] = dict(CENTRAL_ORG_INFO.get(oname, {}).get("holders") or {})
        if "comissions" not in o:
            o["comissions"] = list(CENTRAL_ORG_INFO.get(oname, {}).get("comissions") or [])
        if not o.get("lead"):
            o["lead"] = org_lead(o)
        # 五层承接层旧档兼容：branches 地理挂载 / budget 经济生命周期
        if "branches" not in o:
            o["branches"] = {}
        for bk in ("budget_in", "budget_out", "net"):
            if bk not in o:
                o[bk] = 0
    # 五层②机制槽旧档兼容
    if not isinstance(getattr(state, "mechanisms", None), dict):
        state.mechanisms = {}
    # 五层⑤：各路 prefectures 缺 refugees/orgs 则补默认（避免旧档 KeyError）
    for pname, p in state.prefectures.items():
        if not isinstance(p, dict):
            continue
        p.setdefault("refugees", 0)
        p.setdefault("orgs", [])
        # 经济全浮动重构字段缺省兼容（grain 新口径 = 年总产，旧档 grain 为旧税基口径，读档后可能失真）
        p.setdefault("grain_yield", p.get("grain", 0))
        p.setdefault("yields", {})
        p.setdefault("officials", 1)
        p.setdefault("clerks", 8)
        p.setdefault("route_mult", 1.0)
        # 旧档兼容：地方财力缺省按"月税留成 25%"重建（贯），不用 storage（石）当财力
        p.setdefault("local_finance", round(p.get("monthly_tax", 200000) * 0.25))
        # 旧档兼容：地方府库（贯）缺省按"3 个月税入"重建
        p.setdefault("local_treasury", round(p.get("monthly_tax", 200000) * 3))
        # 旧档兼容：常平仓存粮（石）缺省按"月产 20%"重建（与 GameState 初值一致）
        p.setdefault("changping_stock", round(p.get("grain", 0) / 12 * 0.2))
        p.setdefault("pay_ratio", 0.5)
        p.setdefault("gap", 0)
        # POP 迁移（v2）：无 pops 的旧档用 _build_pops 重建；有 pops 则逐 POP 补 goods/窖银 键
        from content.data import RESOURCE_DIMS, RAW_DIMS
        _goods_dims = [d for d in RESOURCE_DIMS if d not in RAW_DIMS]
        if not isinstance(p.get("pops"), dict):
            from content.data import PREFECTURE_INFO
            from core.game_state import _build_pops
            _info = PREFECTURE_INFO.get(pname, {})
            if _info:
                p["pops"] = _build_pops(_info, _info.get("type", "腹里州路"))
        else:
            for _pop in p["pops"].values():
                if not isinstance(_pop, dict):
                    continue
                if not isinstance(_pop.get("goods"), dict):
                    _pop["goods"] = {d: 0 for d in _goods_dims}
                _pop.setdefault("窖银", 0)
                # A1 存档兼容：旧档 POP 无欠税科目则补 0（新结算读写 pop["欠税"]，防 KeyError）
                _pop.setdefault("欠税", 0)
    # 经济全浮动重构状态字段缺省兼容
    from content.data import RESOURCE_DIMS
    state.payraise_budget = data.get("payraise_budget", getattr(state, "payraise_budget", 0))
    state.oversight = data.get("oversight", getattr(state, "oversight", 0.30))
    saved_res = data.get("resources", {})
    if not isinstance(state.resources, dict):
        state.resources = {d: {"stock": 0, "cap": 5000} for d in RESOURCE_DIMS}
    for d in RESOURCE_DIMS:
        state.resources.setdefault(d, {"stock": 0, "cap": 5000})
    state.projects = data.get("projects", getattr(state, "projects", {}))
    state.workshops = data.get("workshops", getattr(state, "workshops", {}))
    if data.get("defense_lines"):
        state.defense_lines = data.get("defense_lines")
    state._derive_defense_lines() if hasattr(state, "_derive_defense_lines") else None
    state.authority_matters = data.get("authority_matters", state.authority_matters)
    state.land = data.get("land", state.land)
    # 旧档兼容：隐户锚（UI 不显示）缺失时补默认，保持总户 2500 万口径
    if isinstance(state.land, dict):
        state.land.setdefault("hidden_households", 5_000_000)
    state.jiaozi = data.get("jiaozi", state.jiaozi)
    state.maritime = data.get("maritime", state.maritime)
    state.coin = data.get("coin", state.coin)
    state.bank = data.get("bank", state.bank)
    state.standard = data.get("standard", state.standard)
    state.exam = data.get("exam", state.exam)
    state.tech = data.get("tech", state.tech)
    # 旧档兼容：补全新科技树字段；unlocked 为空则补默认根节点
    from content.data import TECH_INFO, DEFAULT_UNLOCKED
    for k, v in TECH_INFO.items():
        if k not in state.tech:
            state.tech[k] = v
    if not state.tech.get("unlocked"):
        state.tech["unlocked"] = list(DEFAULT_UNLOCKED)
    for k in ("researching", "assets", "pending_inventions",
              "dynamic_capabilities", "milestones", "generated_nodes",
              "signoffs"):
        if not isinstance(state.tech.get(k), dict):
            state.tech[k] = {} if k != "pending_inventions" else []
    # 五层③：研发管线 projects 旧档兼容
    if not isinstance(state.tech.get("projects"), dict):
        state.tech["projects"] = {}
    # B1 持久化：重建「聊出来的发明」节点表
    # 生成节点随存档保存（generated_nodes[*]["node"] 为完整元组），
    # 读档时重新注册进 content.data 全局表，保证 get_tech_node 能查到。
    try:
        from core.asset_context import _register_generated_node_global
        for gid, ginfo in (state.tech.get("generated_nodes") or {}).items():
            node = ginfo.get("node") if isinstance(ginfo, dict) else None
            if isinstance(node, (list, tuple)) and len(node) >= 10:
                _register_generated_node_global(gid, tuple(node))
    except Exception:
        pass
    state.diplomacy_log = data.get("diplomacy_log", [])
    state.alliance_jin_liao = data.get("alliance_jin_liao", False)

    state.game_over = data.get("game_over", False)
    state.game_result = data.get("game_result", "")
    state.victory = data.get("victory", False)

    return state


def get_save_slots() -> list:
    """获取所有存档槽位信息"""
    slots = []
    for i in range(1, 6):
        path = _slot_path(i)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                slots.append({
                    "slot": i,
                    "time": d.get("save_time_str", "未知"),
                    "year": d.get("year", 0),
                    "month": d.get("month", 1),
                    "era": d.get("era_name", ""),
                    "turn": d.get("turn", 0),
                })
            except:
                pass
        else:
            slots.append({"slot": i, "empty": True})
    return slots
