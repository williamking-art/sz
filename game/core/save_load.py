# -*- coding: utf-8 -*-
"""宋祚 · 存档系统

工具函数（_safe_int/_safe_float/_slot_path/_strip_unknown_faction_keys）已拆至
`core/save_load_util.py`，此处 re-export 保持既有 import 路径不变。
"""

# ══ 目录（自动生成 2026-09-21，纯注释；重复运行会先移除旧块再插入）══
#      14    def  _strip_unknown_faction_keys   —— 清理旧存档里**已废弃的集团名键**（2026-09-19 集团改名，用户定稿"不迁移"）。
#      41    def  _safe_int   —— 宽松取整：空值 / 布尔 / 数字串可转则转；非法字符串、容器、NaN/inf → `default`。
#      62    def  _safe_float   —— 宽松取浮点：语义同 `_safe_int`，并剔除 NaN / ±inf。
#      79    def  _slot_path   —— 存档槽位文件路径（save/load/slots 三处共用，避免硬编码漂移）。
#      84    def  save_game   —— 保存游戏到指定槽位（含记忆知识库同步写盘）。
#     289    def  _merge_regions   —— 把存档中的政权数据并入新版默认结构。
#     306    def  _load_situations   —— 载入校验（规范 §9）：返回 `(kept, bad)`。
#     330    def  load_game   —— 从指定槽位读取存档，返回 GameState 或 None（损坏档返回 None 并备份 .corrupt）
#     818    def  get_save_slots   —— 获取所有存档槽位信息
# ══ 目录结束 ══
import json
import math
import os
from datetime import datetime

from content.data import SAVE_DIR, ROUTE_MULT_DEFAULT, FACTION_NAMES, CHANGPING_INIT_MONTHLY_SHARE
from core.save_load_util import (  # noqa: F401 — re-export 兼容
    FACTION_NAME_SET, _safe_float, _safe_int, _strip_unknown_faction_keys,
)


#: 槽位约定（勿擅自收窄）：0 = **自动存档槽**（`finish_turn` 每年正月与终局写入，
#: 见 core/commands.py）；1–5 = 玩家可见槽（`get_save_slots` 只列这些）；
#: >5 = 测试/临时槽（多个回归用例刻意用 6/7/8/9/99 做隔离）。
#: 故 save/load **只校验「非负整数」**，不做 1–5 钳制 —— 钳制会打断自动存档并炸掉一批用例。
SLOT_MIN = 0


def _slot_ok(slot) -> bool:
    """槽位合法性：非负整数（HTTP 层的 Pydantic 已挡住类型注入，此处兜住内部调用）。"""
    return isinstance(slot, int) and not isinstance(slot, bool) and slot >= SLOT_MIN


def _slot_path(slot: int) -> str:
    """存档槽位文件路径（save/load/slots 三处共用，避免硬编码漂移）。

    刻意留在本模块：读模块级 `SAVE_DIR`，测试 monkeypatch.setattr(save_load, "SAVE_DIR")
    才能重定向；抽到 save_load_util 会让 patch 失效。
    """
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")


def save_game(state, slot: int = 1) -> bool:
    """保存游戏到指定槽位（含记忆知识库同步写盘）。

    槽位约定见 `SLOT_MIN` 注释：0 为自动存档槽，>5 供测试隔离，均可写。
    非法槽位（负数/非整数）→ 记日志并返回 False，绝不写盘。
    """
    import logging as _lg
    _slog = _lg.getLogger("save_load")
    if not _slot_ok(slot):
        _slog.error("存档槽位非法（slot=%r），拒绝写盘", slot)
        return False
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
        "schema_version": 3,  # v3：局势系统（state.situations / SituationRecord，规范 §9）
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
        # 识字率（2026-09-19 新增设定）：全国 POP 加权派生值；逐路值随 prefectures 往返
        "literacy": getattr(state, "literacy", 0.0),
        "arrival_rate_base": state.arrival_rate_base,
        "treasury": state.treasury,
        # 累计亏空深度（B3）：破产两档线判据，须随档持久化
        "treasury_deficit": getattr(state, "treasury_deficit", 0),
        "imperial_treasury": state.imperial_treasury,
        "pending_inner_transfer": getattr(state, "pending_inner_transfer", None),
        "longterm_effects": getattr(state, "longterm_effects", []),
        "short_term_log": getattr(state, "short_term_log", []),
        "monthly_gazette": getattr(state, "monthly_gazette", [])[-12:],
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
        # 货币口径（阶段 B-1）：白银存量 ＋ 月度对账记录（旧档缺省 → 0 / {}）
        "silver_stock": getattr(state, "silver_stock", 0),
        "money_audit": getattr(state, "money_audit", {}),
        # 官制（阶段 C）：差遣定员、磨勘指数、入仕来源台账。
        # 注意 posts_quota 是**岗位**数（唯一合法的非 POP 官制存量，见官制设计 §六②）；
        # 官额/吏额一律从 pops["官僚"] 派生，**不得**在此另存。
        "posts_quota": getattr(state, "posts_quota", 0),
        "official_rank_index": getattr(state, "official_rank_index", 1.0),
        "recruit_log": getattr(state, "recruit_log", {}),
        # 编制参数（阶段 C-7）：只存改过的键；缺键 = content.data.INSTITUTION_PARAM_SPEC 默认值
        "institution_params": getattr(state, "institution_params", {}),
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
        # 局势（SituationRecord，schema 3 起；旧档缺该键 → 载入为 []，见 load）
        "situations": [dict(r) for r in getattr(state, "situations", []) or []
                       if isinstance(r, dict)],

        "decree_bandwidth": state.decree_bandwidth,
        "direct_decree_used": state.direct_decree_used,
        "wolf_count": state.wolf_count,
        "pending_decrees": state.pending_decrees,
        "pending_secret_decrees": state.pending_secret_decrees,
        "active_decrees": state.active_decrees,
        "edict_drafts": getattr(state, "edict_drafts", []),
        "council_reviews": getattr(state, "council_reviews", {}),
        "memorials": getattr(state, "memorials", []),
        "ai_pending_actions": getattr(state, "ai_pending_actions", []),
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
        # 两段式回合推进（2026-09-21「民间情况先行」）：AI 富化月报 + 就位标记 + 民间反应富版
        "rich_report": getattr(state, "rich_report", ""),
        "rich_civilian": getattr(state, "rich_civilian", ""),
        "rich_civilian_scenes": getattr(state, "rich_civilian_scenes", []),
        "rich_ready": bool(getattr(state, "rich_ready", False)),
        "settle_error": getattr(state, "settle_error", ""),

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
        # 四大机制改良（参考《明末：捞金模拟器》）：开局邸报 / 帝国修正 / 国策树
        "opening_gazette": getattr(state, "opening_gazette", {}),
        "legacies": getattr(state, "legacies", {}),
        "focus_tree": getattr(state, "focus_tree", {}),
        "active_focus": getattr(state, "active_focus", None),
        "completed_focuses": getattr(state, "completed_focuses", []),
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
        # 注（2026-09-18 全审 F601）：本键在 `:101` 已写过一次（`state.defense_lines`），
        # 此处原为重复键（`getattr(state, "defense_lines", {})`，读同一属性，值等价），
        # 属无声重复定义 —— 已删除。详见 review_2026-09-18.md 与 ruff `--select F601`。

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
    # 审查 P1-8 修复（原子写）：先写 .tmp 再 os.replace 原子替换。
    # 原实现直接以 "w" 打开目标文件写 JSON，写盘中断/崩溃会把存档（尤其唯一自动槽
    # slot_0，每年正月与终局都覆盖它）截断成半截 JSON → 丢档。
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise
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


def _load_situations(raw) -> tuple:
    """载入校验（规范 §9）：返回 `(kept, bad)`。

    - `raw` 非 list → 视为空表（旧档 schema 2 → 3 的迁移路径，**不伪造**任何长期目标）；
    - 每条先补默认（`normalize_record`）再校验（`validate_record`）；
    - **非法条目隔离并记 warning，不拒档**；未知键保留、不参与判定。
    """
    from core.situations import normalize_record, validate_record
    if not isinstance(raw, list):
        return [], [(0, f"非 list（{type(raw).__name__}）")]
    kept, bad = [], []
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            bad.append((i, "非 dict"))
            continue
        norm = normalize_record(r)
        errs = validate_record(norm)
        if errs:
            bad.append((i, "；".join(errs[:3])))
            continue
        kept.append(norm)
    return kept, bad


def load_game(slot: int = 1):
    """从指定槽位读取存档，返回 GameState 或 None（损坏档返回 None 并备份 .corrupt）

    非法槽位（负数/非整数）与「档不存在」同口径返回 None（不抛、不记错误日志）：
    读档是高频探测路径，缺档属正常。
    """
    if not _slot_ok(slot):
        return None
    path = _slot_path(slot)
    if not os.path.exists(path):
        return None

    # 审查 P1-9 修复（损坏恢复）：原实现裸 json.load，损坏档抛 JSONDecodeError 穿到
    # UI 造成崩溃式失败。现捕获解析/IO 异常，备份损坏档（便于事后排查）后返回 None，
    # 调用方（UI/后端）可按「读档失败，存档可能已损坏」正常提示。
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:  # JSONDecodeError ⊂ ValueError；UnicodeDecodeError 亦然
        import logging as _lg
        _lg.getLogger("save_load").error(
            "存档损坏，无法读取（slot=%s）：%s；已备份为 %s.corrupt", slot, e, path)
        try:
            os.replace(path, path + ".corrupt")
        except OSError:
            pass
        return None
    if not isinstance(data, dict):
        import logging as _lg
        _lg.getLogger("save_load").error("存档结构非法（slot=%s）：顶层非对象", slot)
        try:
            os.replace(path, path + ".corrupt")
        except OSError:
            pass
        return None

    # P2-10：schema_version 不得因非法类型抛异常 —— 安全解析失败即走损坏档路径
    # （日志 + .corrupt 备份 + None），由调用方按「读档失败/存档可能已损坏」处理。
    _ver_raw = data.get("schema_version", 1)
    _ver = _safe_int(_ver_raw, default=None)
    if _ver is None:
        import logging as _lgv
        _lgv.getLogger("save_load").error(
            "存档 schema_version 非法（slot=%s，值=%r），按损坏档处理", slot, _ver_raw)
        try:
            os.replace(path, path + ".corrupt")
        except OSError:
            pass
        return None
    if _ver > 3:
        import logging
        logging.getLogger("save_load").error(
            "存档 schema_version=%s 高于本程序支持的 3，拒绝加载", _ver)
        return None

    # 延迟导入避免循环
    from core.game_state import GameState

    state = GameState(data.get("difficulty", "史实"))
    # P1-17：读档也清空 applier 变更日志，避免上一局残留污染本局审计切片
    try:
        from engine.state_applier import reset_change_log
        reset_change_log()
    except Exception:  # noqa: BLE001
        pass

    # P2-10：turn 等数值字段安全解析（被写坏成字符串/容器时不得抛未捕获异常）
    _saved_turn = _safe_int(data.get("turn", 0), 0)

    # 记忆知识库（Phase 3a）：按槽位加载（损坏 → 重建空图，不阻断游戏）
    state.memory_slot = slot
    state.memory.turn = _saved_turn
    state.memory.load(slot)
    # 审查 B-1/J-10 修复（读档「记得未来」）：记忆库每回合落盘，而主存档只在手动/正月
    # 更新，故 db 内的 turn 可能远大于本档 turn；`load()` 会用它覆盖上面按存档对齐的水位
    # （实测 state.turn=0 / memory.turn=20）→ 检索把未发生的回合当既成事实注入。
    # 以主存档 turn 为准重新对齐（检索侧另有 turn 封顶，见 memory_graph.query/query_sql）。
    state.memory.turn = _saved_turn

    # 恢复基础时间
    state.year = data.get("year", 1101)
    state.month = data.get("month", 1)
    state.turn = _saved_turn
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
    # 累计亏空深度（B3）：旧档缺省为 0（兼容）
    state.treasury_deficit = _safe_int(data.get("treasury_deficit", 0), 0)
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
    # 货币口径（阶段 B-1）：旧档无此二字段时按 0 / {} 迁移，不破坏既有语义
    state.silver_stock = _safe_int(data.get("silver_stock", getattr(state, "silver_stock", 0)), 0)
    state.money_audit = data.get("money_audit", getattr(state, "money_audit", {})) or {}
    # 官制（阶段 C）：旧档缺省 0 → 由 officialdom 按「中央机构岗位 ＋ 路级定员」重算一次
    state.posts_quota = _safe_int(data.get("posts_quota", getattr(state, "posts_quota", 0)), 0)
    state.official_rank_index = _safe_float(
        data.get("official_rank_index", getattr(state, "official_rank_index", 1.0)), 1.0)
    state.recruit_log = data.get("recruit_log", getattr(state, "recruit_log", {})) or {}
    state.institution_params = data.get(
        "institution_params", getattr(state, "institution_params", {})) or {}
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
    # 集团改名（2026-09-19 用户定稿）：`东南士人→中立派`、`西军集团→军功集团`、
    # `宦官集团→皇党集团`（改用 FACTION_POP_BASIS.aliases 里已备好的名称）。
    # **旧档不迁移** —— 用户定稿"按新开局重建 factions"：
    #   · `state.factions` 保留 GameState 的新开局默认值，**不合并**旧档派系数据；
    #   · 旧名**不再作为未知派系加入**（原 `else: state.factions[fn] = fdata` 会让旧名
    #     变成幽灵派系，而 `calc_decree_execution_rate` 遍历 `faction_stances` 时会
    #     `self.factions[旧名]` 直接 KeyError → 读档即崩）；
    #   · 旧名仍留在各集团 `aliases` 里（`resolve_faction_key` 可反查），故 AI/事件
    #     文本里出现旧名时仍能归一，不影响在玩内容。
    saved_factions = data.get("factions")
    if isinstance(saved_factions, dict):
        # **同名派系照常合并**（如新党/旧党：其进度与改名无关，绝不因改名凭空丢失）
        for fn, fdata in saved_factions.items():
            if fn in state.factions and isinstance(fdata, dict):
                state.factions[fn].update(fdata)
        # **旧名不迁移**（用户定稿）：改名涉及的旧派系键被丢弃——不走原 `else` 分支
        # （原实现会把旧名当**幽灵派系**加入 `state.factions`，而 `calc_decree_execution_rate`
        # 遍历 `faction_stances` 时会 `self.factions[旧名]` → 读档即崩）。
        _dropped = sorted(str(k) for k in saved_factions if k not in FACTION_NAME_SET)
        if _dropped:
            import logging as _lg6
            _lg6.getLogger("save_load").warning(
                "旧存档含已改名集团（东南士人/西军集团/宦官集团），按用户定稿不迁移，"
                "其进度不并入新集团（同名派系不受影响）；忽略的旧派系：%s", _dropped)
    state.external = data.get("external", state.external)
    # 军队真账：兵额已迁移到 army_units（list[ArmyUnit]），central_arsenal 为央级实物库
    # 迁移逻辑拆至 save_load_util.migrate_army_units（零行为变更）
    from core.army_models import build_army_units, CentralArsenal  # 延迟导入，避免顶层互引
    if "army_units" not in data:
        # 旧档兼容：无 army_units 字段，从 state 重建
        state.army_units = build_army_units(state)
        state.central_arsenal = CentralArsenal()
    else:
        from core.save_load_util import migrate_army_units
        _units, _arsenal = migrate_army_units(data)
        state.army_units = _units
        state.central_arsenal = _arsenal
    state.defense_lines = data.get("defense_lines", state.defense_lines)

    # ---- 局势（规范 §9：schema 2 → 3 迁移）----
    # 旧档无 `situations` 键 → 迁移为空表（**不伪造**任何长期目标）；
    # 载入校验：必填键 / 类型 / 枚举 / 条件结构；**非法条目隔离并记 warning**（不拒档），
    # 未知键保留、不参与判定。
    try:
        import logging as _lg2
        _kept, _bad = _load_situations(data.get("situations", []))
        state.situations = _kept
        if _bad:
            _lg2.getLogger("save_load").warning(
                "存档有 %d 条局势非法，已隔离（不参与结算）：%s", len(_bad), _bad[:5])
            try:
                state.situations_load_errors = [f"#{i}: {m}" for i, m in _bad]
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001  局势载入失败不得阻断读档
        import logging as _lg3
        _lg3.getLogger("save_load").warning("存档 situations 载入异常，按空表继续：%s", e)
        state.situations = []

    # 恢复诏令
    state.decree_bandwidth = data.get("decree_bandwidth", 6)
    state.direct_decree_used = data.get("direct_decree_used", 0)
    state.wolf_count = data.get("wolf_count", 0)
    state.pending_decrees = data.get("pending_decrees", [])
    state.pending_secret_decrees = data.get("pending_secret_decrees", [])
    state.active_decrees = data.get("active_decrees", [])
    state.edict_drafts = data.get("edict_drafts", getattr(state, "edict_drafts", []))
    state.council_reviews = data.get("council_reviews", getattr(state, "council_reviews", {}))
    state.memorials = data.get("memorials", getattr(state, "memorials", []))
    state.ai_pending_actions = data.get("ai_pending_actions", getattr(state, "ai_pending_actions", []))
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
    state.imperial_micro_count = _safe_int(data.get("imperial_micro_count", 0), 0)
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
    # 两段式回合推进（2026-09-21）：富化字段幂等补齐（旧档无 → 空/False）
    state.rich_report = str(data.get("rich_report", "") or "")
    state.rich_civilian = str(data.get("rich_civilian", "") or "")
    state.rich_civilian_scenes = data.get("rich_civilian_scenes", []) or []
    state.rich_ready = bool(data.get("rich_ready", False))
    state.settle_error = str(data.get("settle_error", "") or "")

    # 恢复灾荒
    state.disaster_severity = data.get("disaster_severity", 0)
    state.disaster_region = data.get("disaster_region", "")

    # 恢复其他
    state.diff_params = data.get("diff_params", state.diff_params)
    state.statistics = data.get("statistics", state.statistics)
    state.spy_network = data.get("spy_network", state.spy_network)
    state.settlement_log = data.get("settlement_log", [])
    state.monthly_gazette = data.get("monthly_gazette", []) or []

    # 恢复扩展维度
    state.yamen = data.get("yamen", state.yamen)
    _merge_regions(state.prefectures, data.get("prefectures"))
    # 识字率（2026-09-19 新增设定；P2-11 修复）：遵守 POP 挂载律——全国识字率是
    # **POP 派生视图**，唯一权威是 `prefectures[路].pops[阶层].literacy`。载入后**始终**
    # 由逐路 POP 加权重算（core.literacy.national_literacy）；存档顶层 `literacy` 字段
    # 仅作**迁移诊断**，不得覆盖派生值。旧档缺逐路值 → init_literacy 幂等补齐（保留兼容），
    # 仅补齐 POP 读数，不新增任何独立账本。
    try:
        from core.literacy import init_literacy as _init_lit
        from core.literacy import national_literacy as _nat_lit
        _init_lit(state)
        _derived_lit = _nat_lit(state)
        if _derived_lit is not None:
            state.literacy = _derived_lit
        _saved_lit = _safe_float(data.get("literacy"), default=None)
        if _saved_lit is not None and _derived_lit is not None \
                and abs(_saved_lit - _derived_lit) > 0.01:
            import logging as _lg_lit
            _lg_lit.getLogger("save_load").warning(
                "存档顶层 literacy=%.2f 与 POP 派生值 %.2f 不一致；以 POP 派生值为权威"
                "（顶层仅作迁移诊断）", _saved_lit, _derived_lit)
    except Exception as e:  # noqa: BLE001  识字率载入失败不得阻断读档
        import logging as _lg4
        _lg4.getLogger("save_load").warning("识字率载入异常：%s", e)
    # 利益集团「立场占比」：旧档无 → 幂等补齐开局锚点；坏值 → 归一 Σ=1
    try:
        state.faction_split = data.get("faction_split") or getattr(state, "faction_split", None)
        from core.faction_split import ensure_faction_split
        ensure_faction_split(state)
    except Exception as e:  # noqa: BLE001
        import logging as _lg5
        _lg5.getLogger("save_load").warning("立场占比载入异常：%s", e)
    # 集团改名后的**残留键清理**（用户定稿：不迁移；但绝不留 KeyError 隐患）——
    # 旧档的 `faction_split` 与各诏令 `faction_stances` 里可能仍是旧名，而
    # `calc_decree_execution_rate` 会 `self.factions[名]` 取值 → 不清则读档即崩。
    _stripped = _strip_unknown_faction_keys(state)
    if _stripped:
        import logging as _lg7
        _lg7.getLogger("save_load").warning(
            "旧存档含已废弃的集团名键，已清理（不迁移）：%s", _stripped)
    _merge_regions(state.external_regimes, data.get("external_regimes"))
    state.longterm_public = data.get("longterm_public", [])
    state.longterm_secret = data.get("longterm_secret", [])
    # 四大机制改良（旧档缺省兼容）：开局邸报 / 帝国修正 / 国策树
    state.opening_gazette = data.get("opening_gazette", {}) or {}
    state.legacies = data.get("legacies", {}) or {}
    state.focus_tree = data.get("focus_tree", {}) or {}
    state.active_focus = data.get("active_focus", None)
    state.completed_focuses = data.get("completed_focuses", []) or []
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
        p.setdefault("route_mult", ROUTE_MULT_DEFAULT)
        # 旧档兼容：地方财力缺省按"月税留成 25%"重建（贯），不用 storage（石）当财力
        p.setdefault("local_finance", round(p.get("monthly_tax", 200000) * 0.25))
        # 旧档兼容：地方府库（贯）缺省按"3 个月税入"重建
        p.setdefault("local_treasury", round(p.get("monthly_tax", 200000) * 3))
        # 旧档兼容：常平仓存粮（石）缺省按"月产 20%"重建（与 GameState 初值一致）
        p.setdefault("changping_stock", round(p.get("grain", 0) * CHANGPING_INIT_MONTHLY_SHARE))
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

    # 金融契约迁移（2026-09-19 金融整改）：旧档补齐 jiaozi/bank/standard 新字段
    # （发行/流通/准备金/兑付率/界期、存款/贷款/准备金率/逾期率/挤兑、记账与市场汇率）。
    # 幂等：`ensure_finance_fields` 不覆盖存档已有值，缺什么补什么。
    try:
        state.ensure_finance_fields()
    except Exception as e:  # noqa: BLE001  金融字段迁移失败不得阻断读档（core.money 有防御式兜底）
        import logging as _lg6
        _lg6.getLogger("save_load").warning("金融字段迁移异常：%s", e)
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
            except (OSError, ValueError) as e:
                # 审查 P3：裸 except 会吞掉一切且静默丢槽。改为具名异常 + 记日志 +
                # 显式标记损坏槽（UI 显示「存档损坏」而非误报空槽/槽位消失）。
                import logging as _lg
                _lg.getLogger("save_load").warning("存档槽 %s 读取失败：%s", i, e)
                slots.append({"slot": i, "corrupt": True, "time": "存档损坏",
                              "year": 0, "month": 1, "era": "", "turn": 0})
        else:
            slots.append({"slot": i, "empty": True})
    return slots
