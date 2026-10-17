# -*- coding: utf-8 -*-
"""宋祚 · 核心游戏状态"""

# ══ 目录（**纯符号索引**，2026-09-27 起不写行号）══
#   背景：原为自动生成的行号目录，实测 46/46（game_state）与 38/38（commands）**行号全错**，
#   反而误导；行号会随每次编辑漂移，符号名不会。查定义位置请用 `rg 'def <名字>'`。
#      def    _next_month   —— 推进一个月份，返回新的 (year, month)。作为模块级纯函数，供 commands 与 settleme
#      def    _build_pops   —— 每路 POP 群体开局分配（参考维多利亚人口分层）。
#      def    _init_local_refugees   —— 按路本地流民开局基数：边镇/高动乱路略高，腹里近 0，体现北宋常态流徙而非开局危机。
#      def    _init_city_defense   —— 按路类型初始化城防（0~100）：边镇高，腹里低，京畿最高。
#      def    _garrison_by_tier   —— 某路各军籍兵额（人）聚合（供 to_public 快照，非真账）。
#      def    _external_province_lonlats   —— 外邦省真实经纬（Web 舆图用）：取 geo_admin.REGIME_GEO[regime] 多边形 bbox
#      class  GameState   —— 宋祚游戏主状态（经济计算族继承自 GameStateEconMixin）
#      .def   _init_external_regimes   —— 外部政权（41 个，完整数据 + 六阶 POP + 省份运行态 + 军队实体化）。
#      .def   _init_extensions   —— 扩展维度：金融/科举/科技/机制槽/外交/记忆/忠诚/贪腐 + 中枢机构运行态。
#      .def   __init__   
#      .def   get_prestige_info   
#      .def   change_prestige   —— 修改皇威，自动做上限截断。
#      .def   change_treasury   —— 修改国库（禁止穿底；负向请优先用 transfer_money 成对划转）
#      .def   change_imperial_treasury   —— 修改内帑（皇帝私库，与国库分理；禁止穿底）
#      .def   deficit_depth   —— 累计亏空深度（贯，B3）：破产/库藏空虚两档线的**唯一判据**。
#      .def   transfer_money   —— 钱组守恒划转：src → dst，返回实际划转额（不足则按 src 可付截断）。
#      .def   drain_pop_wealth   —— 从各路同阶层 POP wealth 按池比例扣款，返回实扣额（守恒来源用）。
#      .def   change_granary   —— 修改中央粮仓存粮（石），自动封顶于容量。
#      .def   granary_capacity_used   
#      .def   change_granary_cap   —— 新建仓储：扩建中央仓容量（石）。
#      .def   jiaozi_issue_limit   —— 交子可发行上限（第二节§2）：取「准备金 / 税收接受度 / 信用上限」三者最紧。
#      .def   ensure_finance_fields   —— 旧存档迁移：补齐 JIAOZI/BANK/STANDARD 新数据契约字段（幂等；**不改既有数值**）。
#      .def   establish_bank   —— 设立官营银行（第二节§3）：准备金自国库/内帑**守恒划入**，不凭空造钱。
#      .def   _derive_defense_lines   —— 由各路 army_units 聚合防线兵额（兵额唯一真账 = unit.troops）。
#      .def   defense_lines_view   —— 返回防区派生只读视图（每次调用实时聚合）。
#      .def   calc_decree_execution_rate   —— 计算诏令执行率。
#      .def   add_edict_draft   —— 将一道诏草加入待会签队列，返回 draft_id。
#      .def   get_edict_draft   
#      .def   minister_status   —— 返回大臣状态：'active' | 'dead' | 'dismissed'；缺省视为主事在朝。
#      .def   mark_minister_status   
#      .def   is_minister_available   
#      .def   remove_edict_draft   
#      .def   store_council_review   
#      .def   enqueue_ai_action   
#      .def   get_ai_pending   
#      .def   pop_ai_pending   
#      .def   set_ai_pending_status   
#      .def   update_era_name   
#      .def   _loyalty_band   —— 把后台忠诚度映射为定性档位（玩家不可见数值）。
#      .def   org_ministers   —— 返回某机构「依职权回话」的相关大臣：含各岗位在任者与在办差遣领办人。
#      .def   matter_org   —— 返回某事权当前 owner 机构名（改权限/越权授权后可动态变化）。
#      .def   get_state_summary   —— 获取完整状态，用于 AI 调用
#      .def   posture   —— AI 所需的精简脱敏态势字符串。
#      .def   refugee_count   —— 全局流民数 = 各路本地 refugees 求和（单一事实来源，避免双写漂移）。
#      .def   refugee_count   —— 兼容旧代码对 self.refugee_count 的赋值：按比例摊回各路（极端兜底，正常不应触发）。
# ══ 目录结束 ══

from content.data import (
    START_YEAR, START_MONTH, ERA_NAME_START, PRESTIGE_MAX, PRESTIGE_MIN, PRESTIGE_MONTHLY_CAP, PRESTIGE_MAJOR_EVENT_CAP,
    S_BASE, S_SUPPORT_WEIGHT, S_CONFLICT_WEIGHT, S_SECRET_BASE,
    CHANGPING_INIT_MONTHLY_SHARE,
    S_SECRET_LOYALTY_WEIGHT, S_DIRECT_BONUS, S_ZHONGZHI_SUPPORT_WEIGHT,
    E_MIN, E_MAX, ROUTE_MULT_DEFAULT,
    TREASURY_START, INNER_TREASURY_START, EMPEROR_HEALTH_START,
    EMPEROR_ART_START, EMPEROR_TAOISM_START, EMPEROR_PLEASURE_START,
    FACTION_INIT, FACTION_NAMES, EXTERNAL_FORCES,
    DEFENSE_LINES, DECREE_BASE_BANDWIDTH, DIFFICULTY_PRESETS,
    ERA_NAMES_HISTORY,
    get_prestige_level, desensitize_prestige, desensitize_arrival,
    desensitize_satisfaction, desensitize_treasury,
    EXTERNAL_REGIMES,
    YAMEN_LIST, YAMEN_INFO, PREFECTURE_LIST, PREFECTURE_INFO, LAND_INFO,
    JIAOZI_INFO, MARITIME_INFO, COIN_INFO, BANK_INFO, STANDARD_INFO,
    EXAM_INFO, TECH_INFO, PERSONS_PER_HOUSEHOLD,
    desensitize_trust, desensitize_shortage, desensitize_talent, desensitize_tech,
    GRANARY_START, GRANARY_START_CAP, GRANARY_CAP_SOFT, PRICE_LEVEL_BASE, MONEY_SUPPLY_START, PAY_SYSTEM_DEFAULT, CANAL_BLOCK_START,
    COMMERCE_TAX_RATE_DEFAULT, PREFECTURE_INITIAL_GRAIN_PRICE,
    desensitize_granary, desensitize_price, desensitize_canal,
    # 经济全浮动重构新增常量
    WINE_COIN_BASE,
    RESOURCE_DIMS,
)
from content.ministers import (
    loyalty_init, corruption_init, CENTRAL_ORG_INFO, AUTHORITY_MATTERS, org_lead,
)
from core.game_state_econ import GameStateEconMixin

#: 🔴 **玩法参数**（2026-10-05 首轮供料模拟调参）：原料仓容量上限。
#: 原为 50_000，而各路月产约 50-90 万/维 ⇒ **单月产出即被截断约 94%**，
#: 原料无法积累、工坊必然缺料。改为 3_000_000（约容 3-4 个月）。
#: ⚠️ 属**玩法设定**，非史实；与 `production_chain._DEFAULT_CAP` 保持一致。
RAW_STORE_CAP = 3_000_000


def _next_month(year: int, month: int):
    """推进一个月份，返回新的 (year, month)。作为模块级纯函数，供 commands 与 settlement 共用。"""
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


def _build_pops(info: dict, p_type: str) -> dict:
    """每路 POP 群体开局分配（参考维多利亚人口分层）。

    各 POP = {size(人数), wealth(钱/贯), grain(粮/石)}；钱粮守恒：
    士绅 wealth 为囤粮本钱、grain 为其囤粮，随低买高卖此消彼长。
    """
    from content.data import (
        POP_SHARE, GENTRY_TREASURY_SOUTH, GENTRY_TREASURY_NORTH,
        CIVILIAN_HOARD_SOUTH, CIVILIAN_HOARD_NORTH,
        RAW_DIMS,
    )
    from content.data_constants import PERSONS_PER_HOUSEHOLD
    pop_total = info.get("population", 0)
    south = p_type in ("财赋膏腴", "沿海市舶", "天府沃野")
    share_shen = POP_SHARE["士绅"] * (1.3 if south else 0.7)
    sz_shen = int(pop_total * share_shen)
    sz_gong = int(pop_total * POP_SHARE["工匠"])
    sz_shang = int(pop_total * POP_SHARE["商人"])
    _off = round(info.get("households", 0) * 0.00135)   # 官数（与 officials 派生同口径）
    sz_guan = _off + _off * 8                             # 官 + 吏（在籍人口的一部分，须从农里扣除）
    sz_nong = max(0, pop_total - sz_shen - sz_gong - sz_shang - sz_guan)
    monthly_grain = info.get("grain", 0) / 12.0
    monthly_tax = info.get("monthly_tax", 200_000)
    # 存量标定（B0.5）：人口由 4 口/户标定为 5 口/户（×1.25）后，**人均**存量保持不变。
    # 分两条腿：① **粮**——`PREFECTURE_INFO.grain`（年产量，同时是开局囤粮与月产粮的基数）
    #   已在数据层 ×1.25，故此处**不再乘** `_stock`（避免双重放大）；
    # ② **钱**——`monthly_tax` 是税收名义额基数（按 (ii) **不放大**，保财政绝对量），
    #   故开局 wealth 需乘 `_stock` 以保人均现金（否则农被"保底线"挤出、农税通道重回死账）。
    _stock = PERSONS_PER_HOUSEHOLD / 4.0
    # 商品种类（成品，多商品支持；后期玩家新增商品经 register_finished_good 加入）
    # 🔴 **E-1（用户 2026-10-02 裁定「建材也是商品啊」）**：建材
    # `timber`/`stone`/`iron` **也进 POP `goods`**，由商人持有与出售——
    # 否则建材只是"仓里的料"而非**商品**，商人没有囤货/定价动机。
    # 由此 `material_holding` 的州府级明细改由**本路商人 POP `goods`** 承载，
    # 原 `state.resources[dim]["by_pref"]` 明细**不再作为建材来源**（见 material_holding）。
    _goods_dims = [d for d in RESOURCE_DIMS if d not in RAW_DIMS] + \
        ["木", "石", "铁"]
    _g0 = lambda: {d: 0 for d in _goods_dims}
    return {
        # 隐户（不落籍）＝ `农` POP 的**加法**子池 `hidden`（口）—— POP 挂载律条 1/4：
        # 人口不再另立"第 7 类池"，但**不计入在籍**（`state.population` 仍 = Σsize + 流民）。
        "农": {"size": sz_nong, "wealth": int(monthly_tax * 0.5 * _stock),
               "grain": int(monthly_grain * 2.0),
               "hidden": 0, "goods": _g0(), "欠税": 0, "欠给": 0},
        "士绅": {
            "size": sz_shen,
            "wealth": int(monthly_tax * (GENTRY_TREASURY_SOUTH if south else GENTRY_TREASURY_NORTH) * _stock),
            "grain": int(monthly_grain * (CIVILIAN_HOARD_SOUTH if south else CIVILIAN_HOARD_NORTH)),
            "goods": _g0(),
            "窖银": 0,           # 士绅窖藏之银（贯）：退出流通、可后续掏出（挥霍/抄家）
            # 大臣家产的钱**物理落在本 POP**（POP 挂载律条 4；2026-09-27 迁移）：
            # `estate` = 家产持钱（加法子池，计入 pop_money）、`estate_hoard` = 家产窖藏
            # （计入 hoard_money）。`state.minister_estate[*]` 只是具名镜像，不得作为账本。
            "estate": 0,
            "estate_hoard": 0,
            "欠税": 0,           # 欠税科目（A1）：税征缺口累计，逐月追缴；存档兼容见 save_load 迁移
            # M34-①（2026-10-11）：**欠给**（政府欠该 POP 的钱，与欠税对称）——地方财政
            # 欠支落到**债权人 POP** 上（胥吏/衙役/官吏/工匠商人），不做无主体的悬账。
            "欠给": 0,
        },
        "工匠": {"size": sz_gong, "wealth": int(monthly_tax * 1.0 * _stock), "grain": int(monthly_grain * 0.1), "goods": _g0(), "欠税": 0, "欠给": 0},
        "商人": {"size": sz_shang, "wealth": int(monthly_tax * 2.0 * _stock), "grain": int(monthly_grain * 0.2), "goods": _g0(), "欠税": 0, "欠给": 0},
        "官僚": {"size": sz_guan,
                  # 身份子池（宋代官制设计 §13.3/§13.4）：官/吏分账，官再分在岗/待阙/祠禄。
                  # 不变量：size == officials + clerks；officials == on_post + waiting + sinecure。
                  # 权威源是这里的子池；`prefectures[].officials/clerks` 只是派生镜像
                  # （唯一写入点 `core.domains.administration.officialdom.sync_legacy_mirror`，供 Rust 后端与旧档读取）。
                  "officials": _off, "clerks": _off * 8,
                  "on_post": _off, "waiting": 0, "sinecure": 0,
                  # 注意：官僚人数由**户数**派生（`households × 0.00135`，不随"户均口数"变化），
                  # 故其开局存量需**抵消**粮基数的同比例放大（`/ _stock`），保持原人均缓冲
                  # （≈4.9 石/人 = 1~2 月口粮；见 `test_tuning_fixes` 的 Q2 定案）。
                  "wealth": int(monthly_tax * 0.5), "grain": int(monthly_grain * 0.02 / _stock),
                  "goods": _g0(), "欠税": 0, "欠给": 0,
                  # 🟢 M35-A（2026-10-11）：**身份经济记账层**——官/吏各自的财富归属（记账，
                  # **不改人口真账、不改粮耗**；两池合计 ≤ 整池 wealth，读侧派生 wealth_share）
                  "officials_wealth": 0, "clerks_wealth": 0,
                  # 🟢 M35-B：身份欠给（官欠俸／吏欠钱）——"欠谁的钱"决定后续政治效果
                  "officials_salary_arrears": 0, "clerks_pay_arrears": 0,
                  # 🟢 M35-C-1（2026-10-11 · 裁决 D1 甲/D2 甲/D3）：
                  #   役人（衙役）职业层——`runner_count`＝职业人口计数（**不进 size**，不破
                  #   `size == officials + clerks`；人口统计在**读侧**并入＝Σsize + Σoccupation）；
                  #   `occupation_income_runner`＝役人雇钱**记账层**累计（与 officials_wealth/
                  #   clerks_wealth 同性质：只记账，不改 POP wealth 真账、不进 m_all）。
                  "runner_count": 0, "occupation_income_runner": 0,
                  # 🟢 M35-C-1：役人身份欠给**挂靠本桶**（由兵桶幂等迁入；兵侧字段保留一版兼容）
                  "runners_pay_arrears": 0},
        # 官僚开局 grain = 月产×0.02（≈4.9石/人 = 1~2 月口粮缓冲；旧 0.1 为设计残留，见调参定案 Q2）
        "兵": {"size": 0, "wealth": 0, "grain": 0, "goods": _g0(), "欠税": 0, "欠给": 0,
                # 🟢 M35-B/C：士卒欠饷／衙役欠钱／乡兵欠给（身份欠给；军费算法不变）
                "soldiers_arrears": 0, "runners_pay_arrears": 0, "militia_pay_arrears": 0},
    }


def _init_local_refugees(info: dict) -> int:
    """按路本地流民开局基数：边镇/高动乱路略高，腹里近 0，体现北宋常态流徙而非开局危机。"""
    from content.data import PREFECTURE_TYPE_FRONTIER, PREFECTURE_TYPE_CAPITAL
    p_type = info.get("type", "腹里州路")
    unrest = info.get("unrest", 15)
    base = 800 if p_type in PREFECTURE_TYPE_FRONTIER else 200
    base += int(unrest * 30)            # 动乱越高，常态流民越多
    if info.get("is_capital") or p_type == PREFECTURE_TYPE_CAPITAL:
        base = max(0, base - 300)        # 京畿吸纳力强，基数更低
    return max(0, base)


def _init_agri_buildings(info: dict, p_type: str) -> dict:
    """开局**农业基础设施**存量（2026-10-11 · B2-R4 接线补缺）。

    起因：`core/settlement_agri.py` 的 7 条农业效果挂在**建筑/科技**上，
    而开局 `buildings == {}` ⇒ 宋境无可作用实体、增产恒 0。

    **只给存量实体，不给产出**：真正的增产必须走 `apply_agri_effects` 的
    「四项成本先扣后产」（土地真实转移 / 材料真扣 / 工时 / 维护），
    不存在零成本增产；此处仅让投资**有可作用对象**。

    ⚠️ **只配非岗位类、且无科技节点绑定的建筑**：
    ① `POP_BUILDING_TYPES`（农田/商铺/地主农庄/工坊/庄园/自耕农庄）是**岗位类**，
       开局配它们会引入就业岗，改变人口与岗位流动基线
       （`test_employment_flow_song` 明确守护"新局无岗位流动漂移"）；
    ② **不得配"肥料局"**——它是科技节点 `C4_fertilizer` 的**部署建筑**
       （`TECH_NODE_DEPLOY`），开局即配会使该科技一解锁 adoption 即达上限、
       科技树形同虚设（`test_projects_tech_review` 守护此点）。
    故只配 `水利`（增产+降损耗+疏浚运力）与 `常平仓`（降储粮损耗）。
    农田/庄园/肥料局类属**玩家可建设施**，应由 B4-7 民间营造或玩家决策产生。
    """
    from content.data import (PREFECTURE_TYPE_CAPITAL, PREFECTURE_TYPE_COASTAL,
                              PREFECTURE_TYPE_FRONTIER)
    if p_type == PREFECTURE_TYPE_CAPITAL or info.get("is_capital"):
        lv = 2               # 京畿：水利基础较好
    elif p_type in PREFECTURE_TYPE_COASTAL:
        lv = 2               # 沿海：圩田水利
    elif p_type in PREFECTURE_TYPE_FRONTIER:
        lv = 1               # 边镇：开发较浅
    else:
        lv = 1
    return {
        "水利": lv,          # 匹配注册表「水利」：提 yield_mult + 降损耗 + 疏浚漕运
        "常平仓": lv,        # 匹配「常平仓」：降储粮损耗
    }


def _init_city_defense(p_type: str) -> int:
    """按路类型初始化城防（0~100）：边镇高，腹里低，京畿最高。"""
    from content.data import PREFECTURE_TYPE_FRONTIER, PREFECTURE_TYPE_COASTAL, PREFECTURE_TYPE_CAPITAL
    if p_type == PREFECTURE_TYPE_CAPITAL:
        return 80
    if p_type in PREFECTURE_TYPE_FRONTIER:
        return 65
    if p_type in PREFECTURE_TYPE_COASTAL:
        return 50
    return 40


# 审查 P3 修复：_clamp 统一由 content.data.clamp 提供（单一权威源；
# 原 game_state / game_state_econ（模块级 + mixin 方法）共三份重复实现）
from content.data import clamp as _clamp  # noqa: E402,F401


def _garrison_by_tier(state, road: str) -> dict:
    """某路各军籍兵额（人）聚合（供 to_public 快照，非真账）。"""
    out: dict = {}
    for u in state.army_units:
        if u.station == road and u.troops > 0:
            out[u.tier] = out.get(u.tier, 0) + u.troops
    return out


def _external_province_lonlats(regime_key: str, provs_src: list):
    """外邦省真实经纬（Web 舆图用）：取 geo_admin.REGIME_GEO[regime] 多边形 bbox，
    按省序横向分布为中纬。无该政权的几何则返回 None（Web 舆图端跳过显示）。
    惰性导入 geo_admin，避免顶层循环依赖。"""
    try:
        from content.geo_admin import REGIME_GEO as _RGE
        _geo = _RGE.get(regime_key) or {}
        _poly = _geo.get("polygon") or []
    except Exception:
        _poly = []
    if not _poly or not provs_src:
        return None
    _lons = [p[0] for p in _poly]
    _lats = [p[1] for p in _poly]
    if not _lons:
        return None
    _minlon, _maxlon = min(_lons), max(_lons)
    _minlat, _maxlat = min(_lats), max(_lats)
    _n = len(provs_src)
    _out = []
    for _i in range(_n):
        _lon = _minlon + (_maxlon - _minlon) * (_i + 1) / (_n + 1)
        _lat = (_minlat + _maxlat) / 2
        _out.append([round(_lon, 3), round(_lat, 3)])
    return _out


def _pop_add(state, pop, field: str, delta):
    """**方案乙** POP 写入桥接的**延迟导入**入口。

    本模块是**最底层**（被几乎所有模块导入），顶层 `from core.pop_bridge import …`
    有循环依赖风险，故统一走函数内延迟导入。

    返回 `None` 表示该路**尚未下沉**（无 `seats`），调用方必须据此回落原写法。
    """
    from core.foundation.ledger.pop_bridge import pop_obj_add
    return pop_obj_add(state, pop, field, delta)


def _init_regime_tech(regime_type: str = "") -> dict:
    """外邦/主要国家政权的**科技树初始状态**（批 A：只建结构，不推进）。

    结构对齐宋侧 `state.tech` 的**字段口径**（`TECH_INFO` 的键 + 各科技项进度），
    但**数值独立**（承「底层一致，数值不同」）。

    🔴 **缺失 ≠ 0 ≠ 1.0**：只写**已知起点**，未研究的项**不写入**，
    由读侧显示「未定义」，不回落 0 假装已研究。
    """
    from content.data import TECH_INFO
    t = {"level": int(TECH_INFO.get("level", 0) or 0)}
    for _k, _v in (TECH_INFO or {}).items():
        if _k == "level":
            continue
        t[_k] = 0 if isinstance(_v, (int, float)) else _v
    t["researching"] = None      # 正在研究的节点 id；未开工为 None（不是 ""）
    # 🔴 免费起点（tier-0，银与时长皆 0）**开局即有**，与宋侧一致：
    #   否则所有 tier-1 节点的前置永远不满足 ⇒ 科技树彻底卡死（实测 next=None）。
    from core.domains.economy.regime_tech import _starter_node_ids
    t["unlocked"] = sorted(_starter_node_ids())
    t["deployed"] = []           # 已部署的科技建筑节点 id（TECH_NODE_DEPLOY 的子集）
    t["regime_type"] = regime_type
    return t


class GameState(GameStateEconMixin):
    """宋祚游戏主状态（经济计算族继承自 GameStateEconMixin）"""


    def _init_external_regimes(self) -> None:
        """外部政权（41 个，完整数据 + 六阶 POP + 省份运行态 + 军队实体化）。

        审查 2026-09：为每政权派生六阶 POP（`_ext_pop`）、省份运行态（`provinces`，
        独立人口/兵力）与**实体军队**（`armies`，每省 1 支，仿宋 ArmyUnit）。原
        EXTERNAL_REGIMES/_PROVINCES 结构保留。（2026-09-19 自 `__init__` 纯搬出，
        零行为变更）
        """
        from content.data import _ext_pop, _ext_pop_by_heads, external_provinces_of, \
            external_army_spec, external_province_buildings, EXTERNAL_ECON, \
            EXTERNAL_ECONOMY_REGIMES
        self.external_regimes: dict = {}
        for key, info in EXTERNAL_REGIMES.items():
            item = {k: v for k, v in info.items() if k != "hotspot"}
            item["growth_curve"] = dict(info["growth_curve"])
            item["rename_log"] = []
            population_wan = int(item.get("population", 0))
            regime_type = str(info.get("type", ""))
            power_val = int(item.get("power", 0))
            _hot = info.get("hotspot", (0.05, 0.05, 0.9, 0.9))
            _hx, _hy, _hw, _hh = float(_hot[0]), float(_hot[1]), float(_hot[2]), float(_hot[3])
            # 六阶 POP（口）——由总人口(万)与政权 type 派生
            item["pop"] = _ext_pop(regime_type, population_wan)
            # 外邦经济（2026-09-19）：政权库藏（岁币/税入落点；外邦账户**不在宋
            # ACCOUNTS**，对宋 M_ALL 为 burn 口径）与政权粮价初值。旧档经
            # _merge_regions 合并时缺失键保留此默认 → 存档兼容；结算步内另有
            # setdefault 兜底。
            _wealth0 = sum(int(v.get("wealth", 0) or 0) for v in item["pop"].values())
            item["treasury"] = max(0, int(_wealth0 * float(EXTERNAL_ECON["treasury_ratio"])))
            # 🔴 2026-10-06 用户裁定：主要国家**跟宋一样机制**，科技树挂钩的建筑也一样。
            #   政策实体**各自持有**自己的 `tech`（**不得**引用宋的 `state.tech` ——
            #   那是两个平行账本，违反 POP 挂载律律条 4）。
            #   首批只**建结构不推进**（批 A）；推进在 `_settle_external_economy`（批 B）。
            item["tech"] = _init_regime_tech(regime_type)
            item["grain_price"] = float(EXTERNAL_ECON["grain_price0"].get(
                regime_type, EXTERNAL_ECON["grain_price0"]["default"]))
            # 省份独立运行态：每省带 人口(口)/兵力(人)/权重 + 中心坐标 + 默认建筑 + 归省军队
            _troops_total = int(item["pop"].get("兵", {}).get("size", 0))
            _provinces = []
            _provs_src = external_provinces_of(key)
            _n = max(1, len(_provs_src))
            # 外邦省真实经纬（Web 舆图用）：取 REGIME_GEO 该政权多边形 bbox，按省序横向分布
            _lonlats = _external_province_lonlats(key, _provs_src)
            # 2026-09-22：三政权（辽/西夏/大理）经济拆到省域——每省挂六类 POP
            # （按该省**精确人口** × type 份额派生，省域经济撮合的权威账）；
            # 政权级 pop 保持原「国总人口 × 份额」派生（既有守恒断言基准：
            # Σ六阶 size ≈ 人口×万，≤5 人），wealth/grain 结算后由省域单向同步。
            # 其他政权维持简单模拟（无省域 POP，政权级 pop 即权威）。
            _prov_econ = key in EXTERNAL_ECONOMY_REGIMES
            # 2026-09-22 产业链：三政权省域挂 14 维原料产出（yields，按 type 系数 × 省人口派生）
            # + 省域建筑 level（×0.05/Lv 乘数作用于产出）+ 省域物资仓（resources，
            # 成品入池）；政权级挂 resources_regime（14 维原料仓，省域产出 → 政权仓
            # 汇总 → 雀鼠耗 → 省域作坊领料，原料在政权内真实流动）。
            _ry = EXTERNAL_ECON["RAW_YIELDS"].get(regime_type, EXTERNAL_ECON["RAW_YIELDS"]["default"])
            _raw_wan = max(1, _prov_pop_wan := (population_wan if not _prov_econ else population_wan))
            _raw_dims = list(EXTERNAL_ECON["RAW_DIMS"])
            for _idx, (pn, pw) in enumerate(_provs_src):
                _prov_pop = int(population_wan * 10000 * pw)
                _prov_troops = int(_troops_total * pw)
                # 省内坐标：在政权 hotspot 内按省序横向分布（展示/点击用，非精确史址）
                _cx = _hx + _hw * (_idx + 1) / (_n + 1)
                _cy = _hy + _hh * 0.5
                _prov_yield = {
                    rd: int(_prov_pop * float(_ry.get(rd, 0.0)))
                    for rd in _raw_dims
                } if _prov_econ else None
                _prov_res = {rd: 0 for rd in _raw_dims} if _prov_econ else None
                _provinces.append({
                    "name": pn, "weight": round(float(pw), 4),
                    "population": _prov_pop, "troops": _prov_troops,
                    "pops": _ext_pop_by_heads(regime_type, _prov_pop) if _prov_econ else None,
                    "yields": _prov_yield, "resources": _prov_res,
                    "center": [round(_cx, 4), round(_cy, 4)],
                    "center_lonlat": _lonlats[_idx] if _lonlats else None,
                    "buildings": external_province_buildings(regime_type, economy=_prov_econ),
                    "armies": [],
                })
            item["provinces"] = _provinces
            # 政权级 14 维原料仓（省域产出 → 政权仓 → 雀鼠耗 → 省域领料，两级流通）
            item["resources_regime"] = {rd: 0 for rd in _raw_dims} if _prov_econ else None
            # 兵 POP 对齐 Σ省兵力（int 权重分摊截断差归零，三元严格一致：兵POP==Σ省==Σ军队）
            item["pop"]["兵"]["size"] = sum(int(p["troops"]) for p in _provinces)
            # 军队实体化：每省 1 支军队，兵额=该省 troops，branches 按 type 拆兵种
            _core, _split, _tr_base, _mo_base = external_army_spec(regime_type)
            _training = max(20, min(90, _tr_base + min(25, power_val // 4)))
            _morale = max(30, min(90, _mo_base + min(20, power_val // 5)))
            _armies = []
            _seq = 0
            for _p in _provinces:
                _t = int(_p["troops"])
                if _t <= 0:
                    continue
                _seq += 1
                _branches = {}
                _rem = _t
                _keys = list(_split.keys())
                for _i, _bk in enumerate(_keys):
                    _n = int(_t * _split[_bk]) if _i < len(_keys) - 1 else _rem
                    if _n > 0:
                        _branches[_bk] = _n
                        _rem -= _n
                if not _branches:
                    continue
                _army = {
                    "uid": f"{key}_a{_seq:02d}",
                    "name": f"{_p['name']}·{_core}",
                    "tier": _core,
                    "branches": _branches,
                    "troops": sum(_branches.values()),
                    "morale": _morale,
                    "training": _training,
                    "equip": {},
                    "station": _p["name"],
                    "regime": key,
                }
                _armies.append(_army)
                _p["armies"].append(_army)   # 军队归入省份信息
            item["armies"] = _armies
            self.external_regimes[key] = item


    def _init_extensions(self) -> None:
        """扩展维度：金融/科举/科技/机制槽/外交/记忆/忠诚/贪腐 + 中枢机构运行态。

        2026-09-19 自 `__init__` 纯搬出，零行为变更。
        """
        # ---- 田亩户籍 ----
        self.land = dict(LAND_INFO)

        # ---- 奏对历史（召见大臣多轮对话） ----
        self.dialogue_history: list = []   # [(speaker, text), ...]
        self.last_audience: str = ""       # 最近召见的大臣

        # ---- 两段式回合推进（2026-09-21「民间情况先行」）----
        # 首段（同步）：economy+agent 注入 → 程序结算 → **民间反应（程序真值）**立即返回；
        # round2（daemon 线程）：AI 民间反应 / AI 官方月报 / AI 奏章 → 完成置 rich_ready。
        # 语义分工（用户定稿）：民间情况＝民间反应（局势+圣旨怎么看），月报＝官方总结
        # （数值变化/政务进度/人事变动）。旧档缺字段：save/load 幂等补齐。
        self.rich_report: str = ""         # 官方月报富化版（空 = 无富化，程序兜底即最终版）
        self.rich_civilian: str = ""       # AI 民间反应富化版（空 = 程序版已可读）
        self.rich_civilian_scenes: list = []  # ④ 民间反应分幕（农人/士绅/商贾）
        self.rich_ready: bool = False      # 本回合富化链是否已跑完（前端据此停止轮询）

        # ---- 扩展维度：金融/货币/市舶/交子/银行/本位 ----
        self.jiaozi = dict(JIAOZI_INFO)
        self.maritime = dict(MARITIME_INFO)
        self.coin = dict(COIN_INFO)
        self.bank = dict(BANK_INFO)
        self.standard = dict(STANDARD_INFO)

        # ---- 扩展维度：科举/学校 ----
        self.exam = dict(EXAM_INFO)

        # ---- 扩展维度：科技/工技 ----
        self.tech = dict(TECH_INFO)
        # 开局默认已启北宋既有之器（DEFAULT_UNLOCKED 9 根节点）
        if not self.tech.get("unlocked"):
            from content.data import DEFAULT_UNLOCKED
            self.tech["unlocked"] = list(DEFAULT_UNLOCKED)
        # 研发管线（五层③）：玩家可研项目 {名: {progress, masters, monthly_cost}}
        self.tech.setdefault("projects", {})

        # ---- 机制槽（五层②）：{机制名: {org, params, progress}} ----
        self.mechanisms: dict = {}

        # ---- 扩展维度：外交细化（金/辽/夏关系动作后的态势标记） ----
        self.diplomacy_log: list = []      # 外交动作记录
        self.alliance_jin_liao: bool = False  # 是否联金抗辽（海上之盟）
        # 外交对话协议（言枢密 diplomacy_dialogue 落地；存档持久化）
        self.treaties: dict = {}                 # {势力: [{type, terms, turn, year, month}]}
        self._at_war: dict = {}                  # {势力: 1/0} 战争标记
        self._sui_gong_mult: dict = {"辽": 1.0, "金": 1.0, "西夏": 1.0}   # 岁币倍率
        self._trade_income: dict = {}            # {势力: 榷场月入}

        # ---- 大臣长期记忆（真 function calling 落档；存档兼容旧档缺字段默认空） ----
        self.minister_memory: dict = {}    # {大臣名: [办差记录/长久偏好]}
        self.player_minister_status: dict = {}  # {大臣名: "active"|"dead"|"dismissed"} 角色状态校验
        self.minister_equipment: dict = {}      # {大臣名: {"slots": {...}, "bestowals": [...], "custom_tier": ...}} 官员独立公服与皇帝恩赏覆盖
        self.official_stats: dict = {}          # {官员名: OfficialProfile (五维量化能力+经验+特质历练计数器)}

        # ---- 大臣忠诚度（后台隐藏，不可见；0.0 离心 ~ 1.0 死忠）----
        # 注意：权限归属机构/职位（见 central_orgs），忠诚度归属个人，二者分离。
        self.loyalty: dict = loyalty_init()

        # ---- 大臣贪腐度（后台隐藏，不可见；0.0 清廉 ~ 1.0 贪墨极甚）----
        # 随制度/圣旨颁布后的事件联动变化，绝不进入任何 UI 文本。
        self.corruption: dict = corruption_init()

        # ---- 中枢机构运行态（权限跟随机构/职位，不跟随人）----
        # lead 由 posts[0].holder 派生（兼容旧接口）；posts/holders/comissions 承载权限。
        self.central_orgs: dict = {
            name: {
                "lead": org_lead(info),
                "belong": info.get("belong", "皇帝"),
                "scope": info.get("scope", ""),
                "authority": list(info.get("authority", [])),
                "matter_keys": list(info.get("matter_keys", [])),
                "posts": [dict(p) for p in info.get("posts", [])],   # 岗位表（属机构）
                "holders": dict(info.get("holders", {})),            # 人岗映射（换人不变权）
                "comissions": list(info.get("comissions", [])),      # 差遣列表（交差即撤）
                "abolished": False,        # 是否被裁撤
                "efficiency": 1.0,         # 运行效率倍率（改制后果结算用）
                "backlog": 0,              # 政务积压
                # ---- 五层承接层扩展字段 ----
                "branches": {},            # 地理挂载：{路名: [分机构名]}（与 prefectures[路]["orgs"] 双向索引）
                "budget_in": 0,           # 机构经济生命周期：本月进项（朝廷拨/民间工程，贯）
                "budget_out": 0,          # 机构经济生命周期：本月支出（工匠俸/工训营/流民口粮，贯）
                "net": 0,                 # 机构经济生命周期：本月净结余（受崩盘线约束）
            }
            for name, info in CENTRAL_ORG_INFO.items()
        }
        self.authority_matters: dict = {
            k: dict(v) for k, v in AUTHORITY_MATTERS.items()
        }

    def __init__(self, difficulty: str = "史实"):
        diff = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS["史实"])
        # P1-17：新开局清空 applier 变更日志（模块级全局跨局共享）
        try:
            from engine.state_applier import reset_change_log
            reset_change_log()
        except Exception:  # noqa: BLE001
            pass

        # ---- 时间 ----
        self.year: int = START_YEAR
        self.month: int = START_MONTH
        self.turn: int = 0
        self.era_name: str = ERA_NAME_START
        self.difficulty: str = difficulty
        self.difficulty_presets: dict = dict(diff)

        # ---- 皇帝 ----
        self.emperor_name: str = "赵佶"
        self.emperor_health: int = EMPEROR_HEALTH_START
        self.emperor_alive: bool = True
        self.is_abdicated: bool = False
        self.abdication_reason: str = ""

        # 皇帝三项
        self.art_mastery: int = EMPEROR_ART_START
        self.taoism_leaning: int = EMPEROR_TAOISM_START
        self.pleasure_leaning: int = EMPEROR_PLEASURE_START

        # ---- 皇威 ----
        self.prestige: int = diff["prestige_start"]
        self._prestige_history: list = []

        # ---- 到账率 ----
        self.arrival_rate_base: float = diff["arrival_base"]

        # ---- 财政四率容器（P1 双层税基；V1.3 终稿 §11）----
        # 默认值取自 content.data（单一权威源）；旧档缺省由 save_load._migrate_finance 幂等补值。
        from content.data import (FIN_COLLECTION_BASE, FIN_TRANSFER_RATE,
                                  FIN_KEEP_BASE, FIN_DIV_RATE, LOCAL_EXP_MULT_BASE)
        self.finance: dict = {
            "tax_version": 1,
            "collection_rate": FIN_COLLECTION_BASE,
            "transfer_rate": FIN_TRANSFER_RATE,
            "local_keep_rate": FIN_KEEP_BASE,
            "diversion_rate": FIN_DIV_RATE,
            # M34-①（裁决 2026-10-11）：**地方经费保障倍数**——对"地方责任科目应支"
            # （行政/治安/水利）的乘数，开局 1.0 ＝ **史实口径**（地方先养活行政，剩余上供）。
            # 玩家集权可经 `finance_rates` 诏令效果/改革轴下调（压地方经费 → 上供相对增），
            # 分权则上调。接口与四率同源（`apply_finance_reform`），存档迁移幂等补默认。
            "local_expense_mult": LOCAL_EXP_MULT_BASE,
        }
        # ---- 勾校案卷（P3 发现系统；V1.3 终稿 §7；Q11 抄没前置）----
        # {case_id: {id, route, outcome, fidelity, executor, secret, created_turn,
        #            status(证据在握/查无实据/反噬), evidence, judgement}}
        self.audit_cases: dict = {}
        # 🟢 M36-1（2026-10-11）：察访（差遣）**编制与在途容器**（监察世界接口层；**零财政耦合**）
        #   `inspection_tasks`＝在途任务列表；`inspection_agent_state`＝编制/计数（started/done/expired）
        #   口径见 `core/inspection.py`；**不自动派遣、不自动成案**（AI 决策）。
        self.inspection_tasks: list = []
        self.inspection_agent_state: dict = {"started": 0, "done": 0, "expired": 0}
        # 🟢 M36-3：巡察**反馈观察层**容器（累计观察量；只写此容器，不写财政/POP/吏治/案卷）
        #   结构见 `core/inspection.inspection_feedback_readout()`；`interpretation="record-only"`
        self.inspection_feedback: dict = {"observables": {}, "events": 0,
                                          "by_route": {}, "recent": []}
        # ---- 大臣财政疑虑奏报（M34-③；V1.3 §6 发现链二级"怀疑"）----
        # 唯一写入点：core.audit_case.record_suspicion（呈请/召对两处接线）
        self.discovery_suspicions: list = []

        # ---- 国库 ----
        self.treasury: int = TREASURY_START
        # 累计亏空深度（贯，B3 修复）：国库全程禁止穿底（见 change_treasury 的
        # max(0,…) 纪律），因此**不存在负余额**；原破产两档线（-500万/-2000万）
        # 针对「负国库」判定 → 永远不可达，game_over 与危机事件均成死分支。
        # 现改以「累计亏空深度」度量真实财政恶化：当月资金不足以覆盖支出时，
        # 差额累加于此；有结余时优先冲抵。content.data 的 TREASURY_CRISIS_LINE /
        # TREASURY_COLLAPSE_LINE 即比对此值（单位：贯，正数）。
        self.treasury_deficit: int = 0

        # ---- 内帑 / 内藏库（皇帝私库，与国库分理）----
        self.imperial_treasury: int = INNER_TREASURY_START
        # 内帑粮（石，皇帝私库的粮，皇庄皇租本色入此；田产的是粮不是钱，不折银）
        self.imperial_granary: int = 0
        # 酒课（贯/月，进内帑净入）：开局 WINE_COIN_BASE，随酒坊建设增加（见 _settle_workshops）
        self.wine_tax: int = WINE_COIN_BASE

        # ---- 经济全浮动重构新增状态 ----
        # 七维物资仓：{dim: {"stock": 现有, "cap": 容量}}
        self.resources: dict = {d: {"stock": 0, "cap": RAW_STORE_CAP} for d in RESOURCE_DIMS}
        # === 归属待定库存（2026-10-05 用户裁定 6.33） ===
        # 未归属原料（resolve_holder 缺失或证据不足）的**物理存放槽**。
        #
        # 存放地 != 货主：pending_stock **不并入** resources（后者被五处消费者
        # 当作**国库资产**：供给搬运/工坊投料/营造真扣/仓储读数/守恒自检）。
        # 本槽物料：不得出售、不得供工坊采购、不得计税；仅计入**实物守恒**。
        #
        # 结构：{路: {维: {qty, owner, owner_status, evidence_ref}}}
        # 缺 owner 或 owner_status != 已确权 => 一律视为**待定**。
        self.pending_stock: dict = {}
        # 工程系统（玩家手动发起，逐月推进）：{pid: {...}}
        self.projects: dict = {}
        # 🔴 建材**在途批次**（P0，2026-10-02）：`core/transport.dispatch` 写入。
        # **在途即"货已离源、尚未到"**，它是 C-c「只从本地取、取不到即缺料」
        # 能够成立的前提——没有在途，"运没运到"就不可观测，物流便无意义。
        # ⚠️ 缺货/缺坐标时**不产生凭空在途**（钱货两清或两不做）。
        self.material_transit: list = []
        # 制作/作坊系统（配方：粮→酒/肉 等）：{wid: {...}}
        # 加消耗修正·加工型消耗依托建筑：开局每路 2 酒坊 + 2 畜栏（各 ×5万石/月太仓粮耗 → 120万石/月），
        # 酒坊产酒增 wine_tax、畜栏产肉折钱入内帑（玩家可建更多；存档已序列化 workshops）
        from content.data import WORKSHOP_RECIPES
        self.workshops = {}
        _widx = 0
        # 2026-10-11（用户裁定 · 规格 market-civilian-economy B1）：补 **麻坊/丝坊**。
        # 起因：移除 `goods_direct_production_backup` 兜底直产后，宋境布/绸**无生产者**
        # （开局作坊全是酒坊/畜栏；`麻坊`/`丝坊` 只在配方表里、无建造入口），
        # 而消费端已改为"无货不买" ⇒ 布绸消费将立即归零。故开局即配置纺织作坊，
        # 使 `state.resources` 的 hemp/silk（原料）→ 作坊 → 工匠 goods 池（成品）
        # → 民间成交 这条链**有真实生产来源**（《建议》§5.1「每种商品应声明…生产配方」）。
        # 数量口径：每路 1 麻坊（产布，全阶层日用）＋ 每 3 路 1 丝坊（产绸，富阶层）；
        # 单坊月耗 1 万原料 vs 每路年产 hemp 50 万 / silk 100 万，供需匹配。
        for _r_idx, _rname in enumerate(PREFECTURE_INFO):
            for _ in range(2):
                _jw = WORKSHOP_RECIPES["酒坊"]
                self.workshops[f"酒坊_{_rname}_{_widx}"] = {
                    "name": "酒坊", "recipe": dict(_jw["recipe"]), "output_dim": _jw["output_dim"],
                    "yield": _jw["yield"], "active": True}
                _jc = WORKSHOP_RECIPES["畜栏"]
                self.workshops[f"畜栏_{_rname}_{_widx}"] = {
                    "name": "畜栏", "recipe": dict(_jc["recipe"]), "output_dim": _jc["output_dim"],
                    "yield": _jc["yield"], "active": True}
                _widx += 1
            # —— 纺织作坊（布/绸供给；B1 起为民间消费的真实卖方来源）——
            _jm = WORKSHOP_RECIPES["麻坊"]
            self.workshops[f"麻坊_{_rname}_{_widx}"] = {
                "name": "麻坊", "recipe": dict(_jm["recipe"]), "output_dim": _jm["output_dim"],
                "yield": _jm["yield"], "active": True}
            _widx += 1
            if _r_idx % 3 == 0:      # 绸属富阶层消费品，产量与需求匹配，勿过量
                _js = WORKSHOP_RECIPES["丝坊"]
                self.workshops[f"丝坊_{_rname}_{_widx}"] = {
                    "name": "丝坊", "recipe": dict(_js["recipe"]), "output_dim": _js["output_dim"],
                    "yield": _js["yield"], "active": True}
                _widx += 1
        # 🔴 M196（产能批·收口）：丝坊只铺 `_r_idx % 3 == 0` 的路（20 路⇒7 座），单座 yield=8000
        # ⇒ 满产仅覆盖绸需求 2.3%（M82 的 P1 真瓶颈）。按 Jev 裁决补到 **28 座**（旋钮乙 0.591 /
        # 量级甲 0.450 / 分布丁 0.388）；取**绝对目标⇒幂等**；只建实例、不动钱货、不改 yield（口径单点）。
        # ⚠️ 必须在**登记作坊货主之前**（`game_init.init_workshop_owners`）⇒ 新座才有货主。
        try:
            from core.domains.economy.workshop_opening import open_extra_workshops
            open_extra_workshops(self)
        except Exception:                                    # noqa: BLE001
            log.warning("开局丝坊补座失败（产能批；不影响新局，缺失≠0）", exc_info=True)
        # 内帑（甲口径）：imperial_treasury = 国库净结余抽成 + 榷酒课，与国库分理
        # 对话口谕内帑调拨（商量确认式）：皇帝谕发内帑入国库，大臣商量回奏、当场点「准」才守恒移库
        self.pending_inner_transfer = None   # {"amount": 贯, "turn": 回合}；None=无待准调拨
        # free_effect 长期制度队列（言枢密 v3 契约）：[{name, mode, duration, effects, cost}]，
        # 由 _settle_free_effects 在「长期诏」步位月度结算；存档已序列化
        self.longterm_effects: list = []
        # 记忆知识库（Phase 3a）：图谱存史、跨回合连贯；按存档槽位读写
        from memory.memory_graph import MemoryGraph
        self.memory = MemoryGraph()
        self.memory_slot = 0
        # 短期记忆库（Phase 3b，用户指示：短期不污染上下文、做过的事有记录）：
        # append-only 行为日志（圣旨/口谕/决策，全量保留、可追溯、**不注入 AI 上下文**）
        self.short_term_log: list = []
        # 大臣自设工具注册表（三方案：注册护栏 + 上限 16 + 存档持久化）
        self.tool_registry: dict = {}
        # 新兵种注册表（branch_registry 仿 tool_registry：玩家自由设立 + 门槛 + 存档）
        self.branch_registry: dict = {}
        # 玩家科技注册表（tech_registry 仿 branch_registry：承接天马行空 + 门槛 + 存档）
        self.tech_registry: dict = {}
        # 金融推演价格系数（通胀/通缩 ±5%，clamp [0.5,3.0]；月度重置不落档）
        self._price_mult: float = 1.0
        # 时代状态（建筑-时代交互，言枢密方案）：五维认知层 0-100 刻度（兴/平/衰 程序定幅迁移）
        from content.data import ERA_DIMENSIONS
        self.era_state: dict = {d: 50 for d in ERA_DIMENSIONS}
        # 建筑兴衰记录（记忆图谱 building 实体 + 毁损标记）
        self.era_building_log: list = []
        # 大臣家产（言枢密设计）：{大臣: {wealth, land}}；开局基线 ESTATE_INIT（存档序列化）
        from content.data import ESTATE_INIT
        self.minister_estate: dict = {k: dict(v) for k, v in ESTATE_INIT.items()}
        # POP 建筑（政府 projects 复用；POP 建筑按路）：prefectures[路].buildings 由 _build_pops 初始化
        # 投资记录（invest_decide 记账）：{invest_id: {field, fund, amount, return, risk, months_left, seized}}
        self.investments: dict = {}
        # 加俸预算（厚禄养廉政令投入，逐月驱动 pay_ratio 上升）
        self.payraise_budget: int = 0
        # 动态蓝图注册表（规格 decree-action-chain 任务 3）：`{dyn:xxxx: 蓝图dict}`。
        # 由 `core/blueprint_dynamic.register_dynamic_blueprint` 写入，随存档持久化；
        # `construction.resolve_blueprint` 优先查它 → 动态蓝图与静态蓝图走同一套
        # can_build / propose_project / 五态状态机 / 完工落成路径。
        self.dynamic_blueprints: dict = {}
        # 🔴 M176：**外贸逐笔流水**（主线 F · 载体甲，Jev 甲 0.875 / 维度分配甲 0.550）。
        # **append-only 事件流**：每笔 `{month, route, seat, partner, dim, qty, unit_price,
        # goods_value, freight, tax_over, tax_stay, tax_to, freight_to, direction, reason}`。
        # 🔴 **不是账本**：**禁止** `balance`/`stock`/`inventory`/`on_hand`/`holdings` 语义键
        #    （存量仍落 POP/国库/内帑/地方府库 ⇒ 守 §3-1「禁与 POP 平行的账本」）。
        # ⚠️ **本槽当前仅"建容器"——尚无写入者（未接线）**：
        #    · 因此**未登记** `save_load` 白名单（无写入者则无需持久化，避免"半接通"）；
        #    · 待实施批在 `settlement_econ.py:551-570`（市舶段）注入记账时，**同批**登记持久化。
        # 口径与守卫见 `specs/economy/unified-civilian-market/主线F_外贸真账_只读设计_2026-10-13.md` §8/§9。
        self.trade_journal: list = []
        # 行动提交登记表（规格任务 2「跨提交幂等」）：`{action_id: {pid, turn, route, schema_version}}`。
        # 由 `core/plan_commit.commit_plan` 写入；**跨提交**按 action id 拒绝重复立项。
        self.plan_actions: dict = {}
        # 商品**动态成交价**槽（规格 market-civilian-economy B2-4/5）：
        # 与 `content.data.MATERIAL_PRICE_BASE`（基准价，**只读锚**）分开的运行价。
        # 由 `core.market_price.record_trade_price` 写入；**不得就地改写基准表**。
        self.dynamic_prices: dict = {}
        # B2-R2 存档迁移用：旧格式的**全局**商品价（无路归属，不可反推）。
        # 读侧作全局回退；该路首次成交后被路级价覆盖。**不臆造归属路**。
        self.dynamic_prices_legacy: dict = {}
        # 官员个体 Agent 运行态（规格 market-civilian-economy B5·§3.3七项最小状态）：
        # `{actor_id: {status, posts, authority, memory, intents, known_info}}`。
        # **复用** `content.ministers.data.MINISTERS`（43 名具名人物），**不另造人物表**；
        # 记忆与意图**逐人隔离**（甲的私话不是乙亲闻），领域契约不得写入此处。
        self.minister_agents: dict = {}
        # 监察力度（整顿吏治提升，压缩贪腐扣减）
        self.oversight: float = 0.30

        # ---- 中央粮仓（太仓，实物粮石；田赋征本色经漕运汇聚于此）----
        self.granary: int = GRANARY_START
        self.granary_cap: int = GRANARY_START_CAP     # 仓容（石），可经新建仓储工程扩建
        self.granary_stats: dict = {"canal_in": 0, "military": 0, "converted": 0,
                                    "relief": 0, "tax": 0, "sparrow": 0, "canal_loss": 0,
                                    "official": 0}

        # ---- 通货 / 物价（货币经济学，钱/物之比）----
        self.money_supply: float = MONEY_SUPPLY_START   # 货币有效供给（贯）
        # ---- 货币口径（M0/M1/M2/M3）与对账（2026-09-18 阶段 B-1，见 core/money.py）----
        # silver_stock：海外白银**存量**（贯）。修复"把流量当存量"——原先
        #   `maritime.silver_in`（万两/年，流量）被 calc_price_level 直接当存量 ×10000，
        #   且从未进入任何持有账户。现按月经 `_settle_extensions` 累积入此存量。
        # money_audit：月度对账记录（只读视图产物）：{start, last, recent[], cum_residual}。
        #   不承载任何货币账户，权威源仍是 POP wealth 与国库/内帑。
        self.silver_stock: int = 0
        self.money_audit: dict = {}
        # ---- 官制（阶段 C，见 core/domains/administration/officialdom.py 与宋代官制设计 §六②/§七）----
        # posts_quota：差遣定员（**岗位**数，不是人）——这是唯一合法的非 POP 官制存量。
        #   0 = 尚未初始化，由 officialdom.ensure_quota() 按「中央机构岗位 ＋ 路级定员」重算。
        # official_rank_index：磨勘指数（品阶上浮 → 人均俸禄涨）。1.0 = 开局品阶结构。
        # recruit_log：入仕来源台账 {科举, 恩荫, 宗室, 举荐, 致仕补}——记录**流向**，不改人。
        # 官额/吏额/在岗/待阙/祠禄一律从 pops["官僚"] 派生，**此处不另存**（POP 挂载律）。
        self.posts_quota: int = 0
        self.official_rank_index: float = 1.0
        self.recruit_log: dict = {}
        # ---- 编制参数（阶段 C-7，见 core/institution.py）----
        # 只存**被政令改过的键**（缺键 = `INSTITUTION_PARAM_SPEC` 的默认值）→ 旧档天然兼容。
        # 决策 3：不做转轨系统；玩家用政令把这组参数移到公务员制的取值即可。
        self.institution_params: dict = {}
        self.price_level: float = PRICE_LEVEL_BASE      # 物价水平（基准 1.0）

        # ---- 工商征率（玩家可调，对工商经济总量按"几成"征收）----
        # 默认 0.15（抽一成五）：对 calc_commerce() 年工商产出征 15%。
        # 玩家经诏令/滑动条调整；调高增收但增民怨/商旅怨，调低减收但惠商。
        self.commerce_tax_rate: float = COMMERCE_TAX_RATE_DEFAULT
        # 开局预估月度税基（供第 0 回合 HUD 与悬浮明细展示，避免开局全 0）
        self.tax_breakdown: dict = {
            "commerce": 1130940,
            "poll": 389015,
            "tax_color": 864322,
            "盐": 498151
        }
        # 变法节流（省浮费/裁汰冗员）：隐性三冗不可见不可直裁，只能经长期变法逐月挤出水分。
        #   {"active": bool, "kind": "curtail_waste|reduce_office", "savings": 月省贯,
        #    "target": 目标月省贯, "months_left": 剩余月数, "progress": 0~100}
        self.waste_reform: dict = {"active": False, "kind": "", "savings": 0,
                                   "target": 0, "months_left": 0, "progress": 0}

        # ---- 漕运状态（0 通畅 ~ 100 阻塞）----
        self.canal_block: int = CANAL_BLOCK_START

        # ---- 一条鞭法（False=征本色 / True=田赋改征银入国库）----
        self.single_whip: bool = False

        # ---- 历史改写位（玩家改革改写史实）----
        # 玩家改革/战略达成充分条件后写入改写位，关闭或偏转史实硬锚。
        # {改写位id: {"year": 触发年, "label": 描述}}
        #   jin_crushed  灭金于萌芽（金军永不南侵）
        #   liao_ally    联辽抗金（辽免衰、金的崛起被压制）
        #   no_jingkang  避免靖康（国力/外交达线后金军南侵事件失效）
        self.timeline: dict = {}

        # ---- 待确认改写位（战略决策点·奏报朱批）----
        # 玩家成效达线后先写入此处为「候选」，并不直接改写历史；
        # 待奏报中「枢密院/军机密奏」由陛下朱批「准予/从长计议」后，
        # 才由 commands.confirm_timeline_break 正式落 timeline。
        # {改写位id: {"year": 年, "label": 描述}}
        #   jin_crushed  灭金于萌芽（金 power≤25）
        #   liao_ally    联辽抗金（辽 attitude≥70）
        #   no_jingkang  避免靖康（威望≥70+兵力≥280+金 invasion_will<40）
        self.pending_breaks: dict = {}

        # ---- 俸禄/军饷制度（支出侧货币化演化）----
        self.pay_system: dict = dict(PAY_SYSTEM_DEFAULT)

        # ---- 动态粮价（贯/石，区域+通货+季节+丰歉驱动）----
        self.grain_price: float = 1.0

        # ---- 经济信息不对称：真实层 vs 认知层（滞后奏报）----
        self.economy_history: list = []      # 真实层快照环形缓冲（近 12 月）
        self.economy_knowledge: dict = {}    # 认知层（朝廷实际掌握的奏报认知）

        # ---- 派系 ----
        self.factions: dict = {}
        for name in FACTION_NAMES:
            init = FACTION_INIT[name].copy()
            self.factions[name] = {
                "influence": init["influence"],
                "satisfaction": init["satisfaction"],
                "cohesion": init["cohesion"],
                "leader": init["leader"],
                "net_support": 0,  # stance * influence/100
                "decree_stance": 0,  # -1/0/+1 对当前政令态度
                "last_decree_comment": "",
            }

        # ---- 外部势力 ----
        self.external: dict = {}
        for k, v in EXTERNAL_FORCES.items():
            self.external[k] = v.copy()
        self.external["金"]["invasion_will"] = 0

        # ---- 军事（兵额唯一真账 = army_units 实体列表）----
        # 旧 self.armies（质量参数 dict）已废弃：质量并入 UNIT_TIER，战力由 _army_power 派生。
        # 旧各路 prefectures[路]["garrisons"] 已删除：兵额改由各路 army_units.troops 求和派生。
        # 延迟导入：core 不得顶层依赖 ui（避免潜伏环），见 TEAM.md 工程约束
        from core.domains.military.army_models import build_army_units, CentralArsenal
        self.army_units: list = build_army_units(self)
        # 中央武库
        self.central_arsenal: CentralArsenal = CentralArsenal()
        # defense_lines：fortification 取 DEFENSE_LINES 初值，garrison 由 army_units 聚合派生（见 _derive_defense）
        self.defense_lines: dict = {}
        for k, v in DEFENSE_LINES.items():
            self.defense_lines[k] = dict(v)  # v 仅含 fortification
        # 注意：_derive_defense_lines 依赖 self.army_units，须在军事初始化完成后调用（见下方）

        # ---- 诏令 ----
        self.decree_bandwidth: int = DECREE_BASE_BANDWIDTH
        self.direct_decree_used: int = 0
        self.wolf_count: int = 0   # 狼来了计数器
        self.pending_decrees: list = []  # 待执行圣旨（旧规则程序）
        self.pending_secret_decrees: list = []  # 待执行密令（即时，由 _settle_decrees 处理）
        self.pending_public_decrees: list = []  # 旧兼容字段（保留）
        self.longterm_public: list = []   # 在办公开事务（长期，月度推进）
        self.longterm_secret: list = []   # 在办密令（长期，月度推进）
        self.active_decrees: list = []  # 持续效力的政令
        self.edict_drafts: list = []    # 待会签诏草（诏令会签页）
        self.council_reviews: dict = {}  # draft_id -> 会签意见
        self.memorials: list = []  # 待审奏折（每回合开始按局势自动上折，君主批红）
        # AI 工具严格待批队列（审查 P0：AI 只有提议权，批红前不落地）
        self.ai_pending_actions: list = []

        # ---- 施政 ----
        self.personal_action: str = ""   # 旧单值个人行动（兼容旧档；新通道走 imperial_action）
        self.imperial_action: dict = {}  # 皇帝个人行动矩阵（契约 v2）：
        #   {location, mode, action, prepared, pending_months, target}；
        #   pending_months > 0 表示出京准备中（pending_imperial_trip 月度推进）
        self.pending_imperial_trip = None   # 出京准备期（= imperial_action 同一 dict；准备中非 None，成行后置 None）
        self.imperial_micro_count: int = 0  # 微服京城每月 1 次计数（程序限，结算月末归零）
        self._emperor_ai = None             # 皇帝个人行动 AI 推演槽位（契约 v2 结果，回合内瞬态不落档）
        self.major_policy: str = ""
        self.major_policy_target: str = ""

        # ---- 事件 ----
        self.active_events: list = []
        self.event_pressure: dict = {}
        self.event_history: list = []

        # ---- 人口/民生 ----
        self.population: int = 100_000_000  # 约1亿 = 2000 万明户 × PERSONS_PER_HOUSEHOLD(5)
        self.population_satisfaction: int = 55
        # 注意：refugee_count 已改为各路 refugees 求和的 property 派生（见类末），
        # 此处不再作为独立存储字段；保留兼容赋值语义由 property setter 兜底。

        # ---- 灾荒 ----
        self.disaster_severity: int = 0
        self.disaster_region: str = ""

        # ---- 难度系数 ----
        self.diff_params = diff

        # ---- 统计 ----
        self.statistics: dict = {
            "total_income": 0,
            "total_expenditure": 0,
            "total_decrees": 0,
            "total_wars": 0,
            "total_disasters": 0,
        }

        # ---- 锦衣卫渗透 (密折) ----
        self.spy_network: dict = {fn: 0.0 for fn in FACTION_NAMES}
        self.spy_network["宫禁"] = 0.5

        # ---- 记录 ----
        self.settlement_log: list = []
        self.game_over: bool = False
        self.game_result: str = ""
        self.victory: bool = False

        # ---- 四大机制改良（参考《明末：捞金模拟器》）----
        # 开局邸报（文言局势 + 待办三事）：new_game 时由 content/legacy_gazette 生成注入
        self.opening_gazette: dict = {}
        # 帝国修正（legacies）：开局即存在的条件式长期修正符，带消除条件
        self.legacies: dict = {}
        # 国策树（focus）：五大分支（政务/军事/科学/内卫/税务），时延推进 + AI长期记忆沉淀
        self.focus_tree: dict = {}
        try:
            from core.focus_mechanic import init_focus_tree
            init_focus_tree(self)
        except Exception:
            pass
        # 中枢当前在办国策：{branch, node_key, name, desc, power_level, elapsed_turns, total_turns, progress, cost_per_month, status, narrative_memory}
        self.active_focus: dict | None = None
        # 已施行完成的大策历史纪要：[{branch, node_key, name, power_level, year, month, turn, narrative_memory}]
        self.completed_focuses: list = []

        # ---- 局势（SituationRecord，规范 §1.2）----
        # **唯一落库的长期目标**：仅 `origin_kind == "event_pool"`；`legacy`/`focus`/`free_effect`
        # 只生成只读 Readout（`core/situations.py`），绝不在此双写。
        self.situations: list = []
        # ---- 月度奏章八章（批 3）：最近 12 月 [{year,month,chapters,couplet,diff_summary}] ----
        self.monthly_gazette: list = []
        # ---- 众生相分幕（P0）：AI 月报 scenes 数组 [{"scene","text"}] ----
        self.rich_report_scenes: list = []
        # 运行时态（**不落档**）：AI 档位 `_situation_grades`、本回合诏令携带的
        # `_situation_intents_this_turn`。
        self._situation_grades: dict = {}
        self._situation_intents_this_turn: list = []
        # 识字率（2026-09-19 新增设定，core/domains/culture/literacy.py）：全国 POP 加权派生值；
        # 逐路值 `prefectures[路]["literacy"]` 在州县/POP 建成后初始化（见下）
        self.literacy: float = 0.0

        # ---- 六部衙门 ----
        self.yamen: dict = {}
        for name in YAMEN_LIST:
            info = YAMEN_INFO[name]
            self.yamen[name] = {
                "duty": info["duty"],
                "faction": info["faction"],
                "efficiency": 60,          # 衙门施政效率 0-100
                "backlog": 0,              # 积压政务
                "acts": list(info["acts"]),
            }

        # ---- 地方州县 ----
        self.prefectures: dict = {}
        for name in PREFECTURE_LIST:
            info = PREFECTURE_INFO[name]
            p_type = info.get("type", "腹里州路")
            self.prefectures[name] = {
                "name": info.get("name", name),     # 舆图展示名（可由圣旨更名）
                "households": info["households"],   # 户数(户)
                "land": info["land"],               # 田亩(亩，在册 = 自耕农田 + 地主田 + 官田 + 皇庄)
                # 田亩归属（开局数据，随抑兼并/清丈/隐漏演化）：粮是田产的，按归属分配
                "self_farm_land": int(info["land"] * 0.40),   # 自耕农田（亩，主户自耕，产粮自留）
                "gentry_land": int(info["land"] * 0.50),      # 地主田（亩，士绅所有，佃户租种交租）
                "official_land": int(info["land"] * 0.08),    # 官田（亩，官府所有，租佃租入归国库）
                "imperial_land": int(info["land"] * 0.02),    # 皇庄（亩，皇室所有，产粮归内帑）
                "grain": info["grain"],             # 粮产(石)
                "mood": info["mood"],               # 民情 0-100
                "govern": info["govern"],           # 治理度 0-100
                "population": info["households"] * PERSONS_PER_HOUSEHOLD,  # 人口(口，在籍，户均 5 口；**以户为权威**)
                "unrest": info.get("unrest", 15),               # 动乱 0-100
                "monthly_tax": info.get("monthly_tax", 200_000),     # 月税实收锚(贯)→二税折色 tax_base
                "hidden_land": info.get("hidden_land", 0),      # 隐田(亩，开局数字 = land×25%，随清丈/隐漏回升演化)
                "storage": info.get("storage", 0),              # 存粮(石，州仓/上供仓，漕运只动此仓)
                # 常平仓存粮（石，平抑储备，与州仓 storage 分离、不参与漕运上供）：
                # 初值 = 月产 20%；容量上限 = 月产 50%（见 _settle_granary），防止籴入无上限膨胀
                "changping_stock": info.get("changping_stock",
                                            round(info.get("grain", 0) * CHANGPING_INIT_MONTHLY_SHARE)),
                # 经济全浮动重构新增字段（兼容缺省）
                "grain_yield": info.get("grain_yield", info["grain"]),   # 兼容旧字段：粮年产量(石/年)（新口径 grain 即年产，不再 ×12）
                "yields": dict(info.get("yields", {})),                        # 七维物资初值
                "officials": info.get("officials", round(info["households"] * 0.00135)),  # 官数（真实官；households 为在籍明户，×0.00135 → 全国约 2.7 万官，史实 2-4 万）
                "clerks": info.get("clerks", round(info["households"] * 0.00135) * 8),    # 吏数（=官×8，全国约 21.6 万，史实 20-30 万）
                "route_mult": info.get("route_mult", ROUTE_MULT_DEFAULT),                     # 路级乘数
                # 地方财力（贯，俸给足额率用）：地方留成月税实收的 25% 作俸给财力。
                # 单位统一：不得用 storage（石）当财力（贯），否则 pay_ratio 恒满、吏俸缺口恒 0。
                "local_finance": info.get("local_finance",
                                          round(info.get("monthly_tax", 200_000) * 0.25)),
                # 地方府库（贯）：州县常平仓粜籴的钱账（与中央国库分理），初值约 3 个月税入
                "local_treasury": info.get("local_treasury",
                                           round(info.get("monthly_tax", 200_000) * 3)),
                # POP 人口群体（参考维多利亚）：每路按职业分六群体，每群体 {size, wealth, grain}
                # 士绅 wealth/grain 即其囤粮居奇的资金与粮储（钱粮守恒，取代旧 civilian_granary/gentry_treasury）
                "pops": _build_pops(info, p_type),
                # POP 建筑（言枢密设计）：{农田/工坊/商铺/庄园: Lv1-5}，阶层 wealth 出资；
                # 效果乘数对既有公式（×0.05/Lv 封顶 ×2.0），守恒走既有路径；存档迁移缺省 {}
                #
                # 2026-10-11（规格 market-civilian-economy B2-R4 接线补缺）：
                # 开局原本**全空`{}`**，而 `core/settlement_agri.py` 的 7 条农业效果
                # （水利/常平仓/肥料局/农田/自耕农庄/地主农庄/水排筒车）全部挂在
                # **建筑或科技**上 ⇒ 宋境**无任何可作用实体**，`agri_grain_produced`
                # 实测恒为 0（接线正确但无对象）。故开局配置**农业基础设施**。
                #
                # 口径（避免"凭空调高产量"）：
                # · **只给存量实体，不给产出**——增产必须经`apply_agri_effects`
                #   走「四项成本先扣后产」（土地真实转移/材料真扣/工时/维护），
                #   不存在零成本增产；这里仅让投资**有可作用对象**；
                # · 等级按路等差（都城略高、边镇略低），与 `route_mult` 一致；
                # · 名称与 `AGRI_UPGRADE_EFFECTS` 的键**逐字一致**（匹配靠名字）。
                "buildings": _init_agri_buildings(info, p_type),
                "pay_ratio": 0.5,                                              # 俸给充足率初值
                "gap": 0,                                                      # 俸给缺口初值
                # 开局区域米价：按"京畿边镇贵、膏腴贱"原则给变量（避免开局全 1.00 平庸），
                # 后续由 calc_region_grain_price 每月按供需比动态调整覆盖此值。
                "grain_price": PREFECTURE_INITIAL_GRAIN_PRICE.get(p_type, 1.00),
                "type": p_type,
                "is_capital": info.get("is_capital", False),
                # ---- 按路本地流民池（五层地理挂载数据地基）----
                # 真相源为各路本地，全局 refugee_count 退化为各路求和派生。
                # 开局按 unrest/type 赋极低基数：边镇/高动乱路略高，腹里近 0。
                "refugees": _init_local_refugees(info),
                # 本路所辖机构分支列表（与 central_orgs[机构]["branches"] 双向索引）
                "orgs": [],
                "rename_log": [],
                # ---- 地区模型深化（参考《明末：捞金模拟器》）----
                # 控制势力：默认宋；领土争夺时可为"辽/西夏/金/叛军"等
                "controlled_by": info.get("controlled_by", "宋"),
                # 民心（0~100）：与 mood 同源，供地区深化结算与展示
                "public_support": info.get("public_support", info["mood"]),
                # 士绅抵抗（0~100）：士绅对朝廷政策的抵抗度（清丈/仰兼并时上升）
                "gentry_resistance": info.get("gentry_resistance",
                                              max(0, min(100, 100 - int(info["govern"])))),
                # 城防（0~100）：城防坚固度（边镇高、腹里低）
                "city_defense": info.get("city_defense",
                                         _init_city_defense(p_type)),
                # 财政（贯/月）：地方财政健康度（0~100，基于月税与支出）
                "fiscal": info.get("fiscal",
                                   max(0, min(100, round(int(info.get("monthly_tax", 200_000)) / 8000)))),
            }

        # 兵额回填到各路 POP：兵 POP.size = 该路 army_units 兵额合计（兵额唯一真账）
        for u in self.army_units:
            if u.station in self.prefectures and u.troops > 0:
                _bs = self.prefectures[u.station]["pops"]["兵"]
                if _pop_add(self, _bs, "size", u.troops) is None:
                    _bs["size"] += u.troops

        # 识字率（2026-09-19 新增）：**必须在 POP 建成、兵额回填之后**——
        # 目标值由 POP 结构（士绅+官僚占比、工匠+商人占比）派生，逐路各不相同。
        try:
            from core.domains.culture.literacy import init_literacy
            init_literacy(self)
            # 利益集团「立场占比」（给 POP 加政治派系标签；比率，非人口账本）——
            # 与识字率同批初始化：皆由 POP 结构派生，失败不得阻断开局。
            from core.domains.politics.split import ensure_faction_split
            ensure_faction_split(self)
        except Exception:  # noqa: BLE001  识字率/立场占比初始化失败不得阻断开局
            pass

        # 开局货币校准（A1 定稿）：修复 F1（士绅卖粮造币）后补开局货币，防跌回通缩地板。
        # 注入民间 wealth（按各 POP 财富比例分配），不注入国库——物价由民间购买力驱动。
        from content.data import START_MONEY_BOOST
        _boost = START_MONEY_BOOST
        _total_w = sum(pop.get("wealth", 0)
                       for _p in self.prefectures.values() for pop in _p["pops"].values())
        if _boost > 0 and _total_w > 0:
            for _p in self.prefectures.values():
                for pop in _p["pops"].values():
                    _bw = int(_boost * pop.get("wealth", 0) / _total_w)
                    if _pop_add(self, pop, "wealth", _bw) is None:
                        pop["wealth"] += _bw

        # 家产入 POP（2026-09-27，POP 挂载律条 4 迁移）：把 `minister_estate` 镜像的开局存量
        # **物化**到 `士绅` POP 的 `estate` 子池，此后"家产的钱"只存在于 POP 内、镜像与其恒等。
        # 旧口径下这批钱记在独立账户 `estate_wealth` 里且已被计入 M_ALL，故此处注入（而非从
        # 士绅 wealth 抽走）→ M_ALL 与迁移前一致，不产生对账残差。
        try:
            from core.domains.administration.estate_mechanic import sync_estate_slices
            sync_estate_slices(self)
        except Exception:  # noqa: BLE001  家产切片初始化失败不得阻断开局
            pass

        # 防区派生：此时 prefectures 已就绪（fortification 由 DEFENSE_LINES 初值，garrison 由各路聚合）
        self._derive_defense_lines()

        self._init_external_regimes()

        self._init_extensions()

        # 隐户入 POP（2026-09-27 方案 A，POP 挂载律条 1/4）：**必须放在 `_init_extensions()`
        # 之后** —— `state.land`（含 500 万户设计锚）在那里才建立（`:359`）。把它物化为各路
        # `农.hidden`（口）子池；此后隐户人口只存在于 POP 内，`land.hidden_households` 降为派生镜像。
        # 注意：隐户**不计入在籍** `state.population`（不落籍、不纳税）。
        # 🔴 隐户入 POP（2026-10-07 M25 裁定）：**移出 GameState**。
        #   初始化职责归人口域（ensure_hidden_in_pops），改由 application/game_init.py
        #   在 GameState 构造**之后**直接调用。本模块不再依赖人口业务域（§6-1。

        # 农的**职位子池**与**丁口子池**（B1a，2026-09-27 用户口径"一建筑多职位"＋"户"）：
        # `自耕农+富农+贫农+佃农 == 农.size`、`ding+kou == 农.size`（逐路，幂等；不改 size）。
        try:
            from core.foundation.ledger.pop_structure import ensure_farm_slices
            ensure_farm_slices(self)
        except Exception:  # noqa: BLE001  职位/丁口子池初始化失败不得阻断开局
            pass
    # ================================================================
    # 皇威工具
    # ================================================================
    def get_prestige_info(self) -> dict:
        level, w, authority = get_prestige_level(self.prestige)
        from content.data_constants import PRESTIGE_DISPLAY_MAX
        display_val = min(PRESTIGE_DISPLAY_MAX, self.prestige)
        return {
            "value": display_val,             # UI/对外展示层截断到 100
            "raw_value": self.prestige,       # 物理真账无上限积累
            "level": level,
            "multiplier": w,
            "authority_index": authority,
            "description": desensitize_prestige(display_val),
        }

    def change_prestige(self, delta: int, reason: str = "", is_major: bool = False):
        """修改皇威（物理累积无上限，仅保下限 PRESTIGE_MIN=0；UI对外截断为 100）。"""
        cap = PRESTIGE_MAJOR_EVENT_CAP if is_major else PRESTIGE_MONTHLY_CAP
        delta = max(-cap, min(cap, delta))
        self.prestige = max(PRESTIGE_MIN, self.prestige + delta)
        self._prestige_history.append((self.turn, delta, reason, self.prestige))

    # ================================================================
    # 国库工具
    # ================================================================
    def change_treasury(self, delta: int):
        """修改国库（禁止穿底；负向请优先用 transfer_money 成对划转）"""
        self.treasury = max(0, self.treasury + int(delta))

    def change_imperial_treasury(self, delta: int):
        """修改内帑（皇帝私库，与国库分理；禁止穿底）"""
        self.imperial_treasury = max(0, self.imperial_treasury + int(delta))

    def deficit_depth(self) -> int:
        """累计亏空深度（贯，B3）：破产/库藏空虚两档线的**唯一判据**。

        国库不得为负，故以「累计未能支付的支出」等价表达财政恶化程度；
        旧档无该字段时按 0 处理（兼容）。
        """
        return int(getattr(self, "treasury_deficit", 0) or 0)

    def transfer_money(self, src: str, dst: str, amount: int) -> int:
        """钱组守恒划转：src → dst，返回实际划转额（不足则按 src 可付截断）。

        src/dst 取值：
          - "treasury" / "imperial_treasury"
          - "pop:<路>:<阶层>"  如 "pop:两浙路:农"

        审查 M3：**目标不可写时不动 src 并返回 0**（旧实现销毁钱却报成功）。
        调用方据返回值记欠征/欠饷，故「返回 0」即「这笔没成交」。
        """
        amount = int(amount)
        if amount <= 0:
            return 0

        def _read(key):
            if key in ("treasury", "imperial_treasury"):
                return int(getattr(self, key, 0))
            if key.startswith("pop:"):
                _, road, pop = key.split(":", 2)
                p = self.prefectures.get(road)
                if not isinstance(p, dict):
                    return 0
                pp = (p.get("pops") or {}).get(pop)
                if not isinstance(pp, dict):
                    return 0
                return int(pp.get("wealth", 0))
            # 🔴 2026-10-05 **地方府库账户**（用户裁定「地方库优先」）：
            #   `local:<路>` 映射到**既有字段** `prefectures[路]["local_treasury"]`
            #   —— **不是新建账户**，故 `money.ACCOUNTS` 的聚合投影
            #   （`local_treasury_total` = Σ 各路字段）**不变、不双计**。
            if key.startswith("local:"):
                _parts = key.split(":", 2)
                p = self.prefectures.get(_parts[1])
                if not isinstance(p, dict):
                    return 0
                if len(_parts) == 2:
                    return int(p.get("local_treasury", 0) or 0)
                # 🟢 M37c-1 **治所级账户** `local:<路>:<治所>`：读**治所真账**
                #   （缺失 ⇒ 0，与 `local:<路>` 现状一致；未下沉路该治所无真账 ⇒ 0）
                _seat = (p.get("seats") or {}).get(_parts[2])
                if isinstance(_seat, dict):
                    return int(_seat.get("local_treasury", 0) or 0)
                return 0
            return 0

        def _write(key, val):
            if key in ("treasury", "imperial_treasury"):
                setattr(self, key, max(0, int(val)))
                return
            if key.startswith("pop:"):
                _, road, pop = key.split(":", 2)
                p = self.prefectures.get(road)
                if not isinstance(p, dict):
                    return
                pp = (p.get("pops") or {}).get(pop)
                if isinstance(pp, dict):
                    _nw = max(0, int(val))
                    if _pop_add(self, pp, "wealth", _nw - int(pp.get("wealth", 0) or 0)) is None:
                        pp["wealth"] = _nw

            # 🔴 地方府库写入（承 `_read` 同注释：映射**既有字段**，**非新建账户**）
            if key.startswith("local:"):
                _parts = key.split(":", 2)
                road = _parts[1]
                p = self.prefectures.get(road)
                if isinstance(p, dict):
                    _v = max(0, int(val))
                    # 🟢 主线 B（M37b）：地方府库真账在**治所**，路级是 Σ 派生镜像。
                    #   已下沉 ⇒ 走桥（写治所真账并刷新镜像）；**未下沉 ⇒ None ⇒ 回落原写法**。
                    from core.foundation.ledger import local_treasury_bridge as _ltb
                    if len(_parts) == 3:
                        # 🟢 M37c-1 **治所级账户** `local:<路>:<治所>`：**精确**写该治所（不重分摊）。
                        #   不做回落：目标不可写时 `_writable` 已返回 False ⇒ 划转本就不会发生；
                        #   若在此直写，反而会在未下沉路凭空造出治所真账（分叉）。
                        _ltb.seat_local_treasury_set(self, road, _parts[2], _v)
                        return
                    if _ltb.local_treasury_set(self, road, _v) is None:
                        p["local_treasury"] = _v
                    return
        def _writable(key):
            """目标是否**可写**（审查 M3）：原实现只判 src 可付，`_write(dst, …)` 在
            目标 POP 不存在时静默 no-op —— 钱被销毁却仍返回 `moved`，调用方据此记
            "已入库"。现先判 dst 可写，不可写则**不动 src**、返回 0。"""
            if key in ("treasury", "imperial_treasury"):
                return True
            if key.startswith("pop:"):
                _, road, pop = key.split(":", 2)
                p = self.prefectures.get(road)
                if not isinstance(p, dict):
                    return False
                return isinstance((p.get("pops") or {}).get(pop), dict)
            # 🔴 2026-10-05 **地方府库账户**（用户裁定「地方库优先」）：
            #   `local:<路>` 映射到**既有字段** `prefectures[路]["local_treasury"]`
            #   —— **不是新建账户**，故 `money.ACCOUNTS` 的聚合投影
            #   （`local_treasury_total` = Σ 各路字段）**不变、不双计**。
            if key.startswith("local:"):
                _parts = key.split(":", 2)
                p = self.prefectures.get(_parts[1])
                if not isinstance(p, dict):
                    return False
                if len(_parts) == 3:
                    # 🟢 M37c-1 **治所级账户** `local:<路>:<治所>`：仅当『该路已下沉 且 该治所存在』
                    #   才可写（Jev 裁定 P=0.999）——否则划转会静默无效、而调用方仍记"已入库"
                    #   ＝把钱销毁（本函数 docstring 记的审查 M3 同型坑）。
                    from core.foundation.ledger import local_treasury_bridge as _ltb
                    return _ltb.seat_local_treasury_writable(self, _parts[1], _parts[2])
                return True
            return False

        have = _read(src)
        if have <= 0 or not _writable(dst):
            return 0
        moved = min(have, amount)
        if moved <= 0:
            return 0
        _write(src, have - moved)
        _write(dst, _read(dst) + moved)
        return moved

    def drain_pop_wealth(self, pop_name: str, amount: int) -> int:
        """从各路同阶层 POP wealth 按池比例扣款，返回实扣额（守恒来源用）。"""
        amount = int(amount)
        if amount <= 0:
            return 0
        pools = []
        total = 0
        for road, p in (self.prefectures or {}).items():
            pp = (p.get("pops") if isinstance(p, dict) else None) or {}
            slot = pp.get(pop_name)
            if isinstance(slot, dict):
                w = int(slot.get("wealth", 0))
                if w > 0:
                    pools.append((slot, w))
                    total += w
        if total <= 0:
            return 0
        taken = 0
        for slot, w in pools:
            take = min(int(amount * w / total), int(slot.get("wealth", 0)))
            if _pop_add(self, slot, "wealth", -take) is None:
                slot["wealth"] = int(slot.get("wealth", 0)) - take
            taken += take
        return taken

    def change_granary(self, delta: int):
        """修改中央粮仓存粮（石），自动封顶于容量。"""
        self.granary = max(0, min(self.granary_cap, self.granary + delta))

    def granary_capacity_used(self) -> float:
        return self.granary / max(self.granary_cap, 1)

    def change_granary_cap(self, delta: int):
        """新建仓储：扩建中央仓容量（石）。"""
        self.granary_cap = max(0, min(GRANARY_CAP_SOFT, self.granary_cap + delta))

    # ================================================================
    # 金融数据契约（第二节§2/§3；第六节）——只读上限 + 幂等迁移 + 守恒开户
    # ================================================================
    def jiaozi_issue_limit(self) -> int:
        """交子可发行上限（第二节§2）：取「准备金 / 税收接受度 / 信用上限」三者最紧。

        准备金约束 = `_jiaozi_ceiling()`（准备金 × 皇威放宽系数，既有口径）；
        税收接受度 = jiaozi["tax_acceptance"]（0~1，官府课税接受交子的比例）；
        信用上限   = JIAOZI_CREDIT_FLOOR + (1−floor)×trust/100（0~1）。
        三者相乘向下取整。**只读**，不改任何账户（发行落地仍走既有发行路径）。
        """
        base = int(self._jiaozi_ceiling())
        jz = self.jiaozi if isinstance(getattr(self, "jiaozi", None), dict) else {}
        try:
            from content.data import JIAOZI_CREDIT_FLOOR, JIAOZI_TAX_ACCEPTANCE
        except Exception:  # noqa: BLE001 — 常量导入失败时退回契约默认值
            JIAOZI_TAX_ACCEPTANCE, JIAOZI_CREDIT_FLOOR = 0.80, 0.50
        try:
            tax_acc = max(0.0, min(1.0, float(jz.get("tax_acceptance", JIAOZI_TAX_ACCEPTANCE))))
        except (TypeError, ValueError):
            tax_acc = float(JIAOZI_TAX_ACCEPTANCE)
        try:
            trust = max(0.0, min(100.0, float(jz.get("trust", 0) or 0)))
        except (TypeError, ValueError):
            trust = 0.0
        floor = max(0.0, min(1.0, float(JIAOZI_CREDIT_FLOOR)))
        credit = floor + (1.0 - floor) * (trust / 100.0)
        return int(base * tax_acc * credit)

    def ensure_finance_fields(self) -> dict:
        """旧存档迁移：补齐 JIAOZI/BANK/STANDARD 新数据契约字段（幂等；**不改既有数值**）。

        返回 {空间: [新增键, ...]}。调用方为 save_load 读档迁移段（不在本任务写域；
        core.money 的防御式读取已能兜底缺键，故旧档不会崩，仅缺新字段展示）。
        """
        from content.data import BANK_INFO, JIAOZI_INFO, STANDARD_INFO
        added: dict = {}
        for name, defaults in (("jiaozi", JIAOZI_INFO), ("bank", BANK_INFO),
                               ("standard", STANDARD_INFO)):
            cur = getattr(self, name, None)
            if not isinstance(cur, dict):
                cur = dict(defaults)
                setattr(self, name, cur)
            miss = [k for k in defaults if k not in cur]
            for k in miss:
                cur[k] = defaults[k]
            if miss:
                added[name] = miss
        return added

    def establish_bank(self, reserve_guan: int, source: str = "treasury") -> dict:
        """设立官营银行（第二节§3）：准备金自国库/内帑**守恒划入**，不凭空造钱。

        `reserve_guan`（贯）从 source 划入 bank["reserve"]；bank["capital"] 维持
        legacy「万贯」口径，按 WON_PER_GUAN 折算（唯一换算入口 core.money）。
        返回 {ok, error, reserve, source_moved}；失败返回 ok=False + error（不静默成功）。
        """
        from content.data import WON_PER_GUAN
        amt = int(reserve_guan or 0)
        if amt <= 0:
            return {"ok": False, "error": "准备金须为正", "reserve": 0, "source_moved": 0}
        if source not in ("treasury", "imperial_treasury"):
            return {"ok": False, "error": f"非法来源 {source!r}", "reserve": 0, "source_moved": 0}
        avail = int(getattr(self, source, 0) or 0)
        moved = min(amt, avail)
        if moved <= 0:
            return {"ok": False, "error": "来源库藏不足", "reserve": 0, "source_moved": 0}
        # 守恒转移：source（M_ALL 账户）→ bank.reserve（M_ALL 账户），ΔM_ALL == 0
        # P0-4：capital 仅作 legacy 展示（万贯，bank_view），**不入 M3**（money.m3 已
        # 排除 capital，避免与 reserve 双计）。此处仍写 capital 以保持展示口径连续。
        setattr(self, source, avail - moved)
        b = self.bank
        b["reserve"] = int(b.get("reserve", 0) or 0) + moved
        b["capital"] = round((float(b.get("capital", 0) or 0) * WON_PER_GUAN + moved) / WON_PER_GUAN, 6)
        b["established"] = True
        b.setdefault("reserve_ratio", 0.20)
        b.setdefault("deposits", 0)
        b.setdefault("loans", 0)
        b.setdefault("overdue_rate", 0.0)
        b.setdefault("run_pressure", 0.0)
        b.setdefault("branches", 0)
        b.setdefault("target", "")
        return {"ok": True, "error": "", "reserve": int(b["reserve"]), "source_moved": moved}

    # 经济计算族见 core/game_state_econ.GameStateEconMixin（mixin 继承）
    def _derive_defense_lines(self):
        """由各路 army_units 聚合防线兵额（兵额唯一真账 = unit.troops）。"""
        ga = {line: 0 for line in self.defense_lines}
        for u in self.army_units:
            if u.defense_line in ga:
                ga[u.defense_line] += u.troops
        for k, v in self.defense_lines.items():
            v["garrison"] = int(ga.get(k, 0))

    def defense_lines_view(self) -> dict:
        """返回防区派生只读视图（每次调用实时聚合）。"""
        self._derive_defense_lines()
        return {k: dict(v) for k, v in self.defense_lines.items()}

    # ================================================================
    # 诏令执行率
    # ================================================================
    def calc_decree_execution_rate(self, faction_stances: dict, is_secret: bool = False,
                                    is_direct: bool = False, secret_loyalty: float = 0.5,
                                    is_zhongzhi: bool = False, org_hint: str = "政府") -> float:
        """计算诏令执行率。
        中旨（御笔强推）按机构归属执行率：内廷 1.0 / 政府 0.85 / 地方 0.60。"""
        from content.data import ZHONGZHI_AFFILIATION_RATE
        _, w, _ = get_prestige_level(self.prestige)

        # 净支持 = Σ(立场 × 影响力/100)
        net_support = 0.0
        faction_conflict = 0.0
        for name, stance in faction_stances.items():
            f = self.factions[name]
            inf = f["influence"] / 100.0
            if stance == 1:
                net_support += inf
            elif stance == -1:
                net_support -= inf
                faction_conflict += inf

        if is_secret:
            s = S_SECRET_BASE + secret_loyalty * S_SECRET_LOYALTY_WEIGHT
        elif is_zhongzhi:
            # 中旨绕过会签，执行率主要由机构归属决定
            base = ZHONGZHI_AFFILIATION_RATE.get(org_hint, 0.85)
            s = base + net_support * S_ZHONGZHI_SUPPORT_WEIGHT
        else:
            s = S_BASE + net_support * S_SUPPORT_WEIGHT
            if is_direct:
                # 狼来了机制已取消（审查 2026-09）：御笔直发恒有 +0.10 加成
                s += S_DIRECT_BONUS
            else:
                # 经会签的正式诏：门下封驳已消化的部分冲突，执行率略稳
                pass

        s -= faction_conflict * S_CONFLICT_WEIGHT

        return max(E_MIN, min(E_MAX, w * s))

    # ================================================================
    # 诏草与会签（拟旨·会签）
    # ================================================================
    def add_edict_draft(self, draft: dict) -> str:
        """将一道诏草加入待会签队列，返回 draft_id。"""
        import uuid
        did = "d" + uuid.uuid4().hex[:8]
        draft["id"] = did
        draft.setdefault("kind", "formal")
        draft.setdefault("org_hint", "政府")
        draft.setdefault("title", "御笔诏")
        draft.setdefault("body", "")
        draft.setdefault("effects", [])
        draft.setdefault("source_minister", "陛下亲拟")
        draft.setdefault("turn_created", self.turn)
        draft.setdefault("reviewed", False)
        self.edict_drafts.append(draft)
        return did

    def get_edict_draft(self, draft_id: str):
        for d in self.edict_drafts:
            if d.get("id") == draft_id:
                return d
        return None

    # ================================================================
    # 大臣角色状态（死亡 / 革职）校验 —— 防错：不在朝之臣不可办差
    # ================================================================
    def minister_status(self, name: str) -> str:
        """返回大臣状态：'active' | 'dead' | 'dismissed'；缺省视为主事在朝。"""
        return self.player_minister_status.get(name, "active")

    def mark_minister_status(self, name: str, status: str) -> None:
        if status in ("active", "dead", "dismissed"):
            self.player_minister_status[name] = status

    def is_minister_available(self, name: str) -> bool:
        return self.minister_status(name) == "active"

    def remove_edict_draft(self, draft_id: str):
        self.edict_drafts = [d for d in self.edict_drafts if d.get("id") != draft_id]
        self.council_reviews.pop(draft_id, None)

    def store_council_review(self, draft_id: str, review: dict):
        self.council_reviews[draft_id] = review

    def enqueue_ai_action(self, kind: str, title: str, summary: str,
                          payload: dict, proposer: str = "") -> str:
        import uuid
        aid = "ap" + uuid.uuid4().hex[:8]
        self.ai_pending_actions.append({
            "id": aid, "kind": kind, "title": title, "summary": summary,
            "payload": dict(payload or {}), "proposer": proposer,
            "turn": self.turn, "status": "pending",
        })
        # M34-③：AI 大臣**呈请**若含财政疑虑 → 记入发现链二级"怀疑"（唯一写入点）
        try:
            from core.audit_case import record_suspicion
            record_suspicion(self, f"{title} {summary}", source="呈请",
                             minister=proposer)
        except Exception:  # noqa: BLE001 — 奏报记录失败不得阻断呈请入队
            pass
        return aid

    def get_ai_pending(self, status: str = "pending") -> list:
        return [a for a in (self.ai_pending_actions or [])
                if status == "*" or a.get("status") == status]

    def pop_ai_pending(self, action_id: str):
        for a in self.ai_pending_actions or []:
            if a.get("id") == action_id:
                return a
        return None

    def set_ai_pending_status(self, action_id: str, status: str) -> bool:
        for a in self.ai_pending_actions or []:
            if a.get("id") == action_id:
                a["status"] = status
                return True
        return False

    # ================================================================
    # 年号管理
    # ================================================================
    def update_era_name(self):
        for year, name in sorted(ERA_NAMES_HISTORY.items(), reverse=True):
            if self.year >= year:
                self.era_name = name
                break

    # ================================================================
    # 改制推演素材（供结算 AI；忠诚度隐藏为定性档位，绝不下放数字）
    # ================================================================
    def _loyalty_band(self, name: str) -> str:
        """把后台忠诚度映射为定性档位（玩家不可见数值）。"""
        v = self.loyalty.get(name, 0.5)
        if v >= 0.75:
            return "效忠"
        if v >= 0.55:
            return "顺从"
        if v >= 0.38:
            return "敷衍"
        return "离心"


    # ================================================================
    # 中枢相关大臣（供廷议入对）
    # ================================================================
    def org_ministers(self, org_name: str) -> list:
        """返回某机构「依职权回话」的相关大臣：含各岗位在任者与在办差遣领办人。
        只返回在朝（loyalty 中存在）者；空岗/差遣未领办不纳入。
        """
        o = self.central_orgs.get(org_name)
        if not o or o.get("abolished"):
            return []
        names = []
        for holder in (o.get("holders") or {}).values():
            if holder and holder not in names:
                names.append(holder)
        for com in (o.get("comissions") or []):
            if isinstance(com, dict) and com.get("lead") and com["lead"] not in names:
                names.append(com["lead"])
        # 仅保留在朝者（loyalty 存在即视为可入对）
        return [n for n in names if n in self.loyalty]

    def matter_org(self, matter_key: str) -> str:
        """返回某事权当前 owner 机构名（改权限/越权授权后可动态变化）。"""
        info = self.authority_matters.get(matter_key) or {}
        return info.get("owner", "")

    # ================================================================
    # 获取完整状态摘要
    # ================================================================
    def get_state_summary(self) -> dict:
        """获取完整状态，用于 AI 调用"""
        pi = self.get_prestige_info()
        arrival = self.calc_arrival_rate()
        arrival_desc = desensitize_arrival(arrival)
        treasury_desc = desensitize_treasury(self.treasury)

        return {
            "time": f"{self.era_name}{self.year}年{self.month}月",
            "prestige": {"value": self.prestige, "level": pi["level"], "desc": pi["description"]},
            "health": self.emperor_health,
            "treasury": {"amount": self.treasury, "desc": treasury_desc},
            "imperial_treasury": {"amount": self.imperial_treasury, "desc": desensitize_treasury(self.imperial_treasury)},
            # 认知层滞后值（上月 economy_knowledge 快照，供脱敏层做"奏报延迟"）
            "treasury_lagged": self.economy_knowledge.get("treasury"),
            "imperial_treasury_lagged": self.economy_knowledge.get("imperial_treasury"),
            "granary_lagged": self.economy_knowledge.get("granary"),
            "refugee_count_lagged": self.economy_knowledge.get("refugee_count"),
            "arrival_rate": {"value": round(arrival, 2), "desc": arrival_desc},
            "factions": {
                name: {
                    "influence": f["influence"],
                    "satisfaction": f["satisfaction"],
                    "sat_desc": desensitize_satisfaction(f["satisfaction"]),
                }
                for name, f in self.factions.items()
            },
            "external": self.external,
            "military": {
                "garrisons": {
                    name: _garrison_by_tier(self, name)
                    for name in self.prefectures
                    if any(u.station == name and u.troops > 0 for u in self.army_units)
                },
                "armies": {u.unit_id: {"name": u.name, "tier": u.tier, "branches": dict(u.branches),
                                       "troops": u.troops, "morale": u.morale,
                                       "training": u.training, "station": u.station,
                                       "defense_line": u.defense_line}
                           for u in self.army_units},
                "defenses": self.defense_lines,
            },
            "population": self.population,
            "pop_satisfaction": self.population_satisfaction,
            "pop_sat_desc": desensitize_satisfaction(self.population_satisfaction),
            "refugee_count": self.refugee_count,
            "decree_bandwidth": self.decree_bandwidth,
            "pending_decrees": len(self.pending_decrees),
            "active_events": self.active_events,
            "event_pressure": self.event_pressure,
            "personal": {
                "art": self.art_mastery,
                "taoism": self.taoism_leaning,
                "pleasure": self.pleasure_leaning,
            },
            # ---- 扩展维度（脱敏） ----
            "finance_ext": {
                "jiaozi_trust": desensitize_trust(self.jiaozi["trust"]),
                "coin_shortage": desensitize_shortage(self.coin["shortage"]),
                "maritime_open": "广开市舶" if self.maritime["open"] else "市舶未广",
                "bank": "已设官营银行" if self.bank["established"] else "未设银行",
                "commerce_tax": self._describe_tax_rate(),
            },
            # ---- 仓廪 / 通货（脱敏定性，供 AI 认知层） ----
            "granary_ext": {
                "granary": desensitize_granary(self.granary, self.granary_cap),
                "granary_util": round(self.granary_capacity_used(), 2),
                "price": desensitize_price(self.grain_price),
                "price_level": round(self.price_level, 2),
                "canal": desensitize_canal(self.canal_block),
                "pay": self.pay_system.get("mode", "本色折色"),
                "whip": "已行一条鞭" if self.single_whip else "仍征本色",
            },
            "granary_amount": self.granary,
            # ---- 米价趋势（数值供脱敏层比较，不直发 AI） ----
            "grain_price": round(self.grain_price, 3),
            "grain_price_prev": round(self.economy_knowledge.get("grain_price", self.grain_price), 3),
            "exam_ext": {
                "open": "开科取士" if self.exam["open"] else "停科",
                "mode": self.exam["mode"],
                "talent": desensitize_talent(self.exam["talent_pool"]),
            },
            "tech_ext": {
                "level": desensitize_tech(self.tech["level"]),
                "gunpowder": self.tech["gunpowder"],
            },
            "diplomacy_ext": {
                "alliance": "已联金抗辽" if self.alliance_jin_liao else "未结海上之盟",
            },
            # 大臣角色状态（死亡/革职）摘要：供叙事防错与锚定
            "minister_states": {
                n: st for n, st in self.player_minister_status.items()
                if st in ("dead", "dismissed")
            },
        }

    @property
    def posture(self) -> str:
        """AI 所需的精简脱敏态势字符串。

        改进：国库/太仓/流民用区间脱敏（"约X至Y万缗"）替代纯定性
        （"充裕"），让 AI 知道量级可做有依据判断，但区间内不确定性
        使其无法精确计算最优解——这才是真实的决策混沌。
        认知层滞后：经济读数用上月快照（economy_knowledge），模拟奏报延迟。
        """
        from ai.desensitize import desensitize_band
        s = self.get_state_summary()
        fin = s.get("finance_ext", {})
        ex = s.get("exam_ext", {})
        te = s.get("tech_ext", {})
        gr = s.get("granary_ext", {})
        _att = lambda a: "友善" if a >= 70 else ("一般" if a >= 40 else ("敌视" if a >= 20 else "仇敌"))
        # 区间脱敏：国库/太仓/流民用区间+认知层滞后，其余仍用定性
        _treasury_band = desensitize_band(
            s["treasury"]["amount"], "缗", width_pct=0.20,
            lag_value=s.get("treasury_lagged"))
        _granary_band = desensitize_band(
            s.get("granary_amount", 0), "石", width_pct=0.20,
            lag_value=s.get("granary_lagged")) if s.get("granary_amount", 0) > 0 else "太仓告罄"
        _ref = s.get("refugee_count", 0)
        _ref_band = desensitize_band(
            _ref, "口", width_pct=0.25,
            lag_value=s.get("refugee_count_lagged")) if _ref > 0 else "无"
        # 基本国策长期记忆与正在施行政务
        _focus_parts = []
        if getattr(self, "completed_focuses", None):
            _c_names = [f["name"] for f in self.completed_focuses if isinstance(f, dict)]
            if _c_names:
                _focus_parts.append(f"已定大策：{'、'.join(_c_names[-4:])}")
        _act = getattr(self, "active_focus", None)
        if _act and isinstance(_act, dict) and _act.get("status") == "in_progress":
            _focus_parts.append(f"在施大策：{_act.get('name')}({_act.get('progress', 0)}%)")
        _focus_str = f"国策：{'；'.join(_focus_parts)}；" if _focus_parts else ""

        return (
            f"时间：{s['time']}；皇威：{s['prestige']['desc']}；"
            f"国库：{_treasury_band}（{s['treasury']['desc']}）；"
            f"太仓：{_granary_band}；流民：{_ref_band}；民心：{s['pop_sat_desc']}；"
            f"{_focus_str}"
            f"金融：交子{fin.get('jiaozi_trust','')}、{fin.get('coin_shortage','')}、{fin.get('maritime_open','')}；"
            f"仓廪：{gr.get('granary','')}、米价{gr.get('price','')}、"
            f"漕运{gr.get('canal','')}、{gr.get('whip','')}、俸禄{gr.get('pay','')}；"
            f"科举：{ex.get('open','')}（{ex.get('mode','')}）、人才{ex.get('talent','')}；"
            f"科技：{te.get('level','')}；外交：{s.get('diplomacy_ext',{}).get('alliance','')}；"
            f"金态度：{_att(self.external.get('金',{}).get('attitude',50))}，"
            f"辽态度：{_att(self.external.get('辽',{}).get('attitude',50))}，"
            f"西夏态度：{_att(self.external.get('西夏',{}).get('attitude',50))}。"
        )

    # ================================================================
    # 五层⑤：按路本地流民 —— 全局 refugee_count 退化为各路求和派生
    # ================================================================
    @property
    def refugee_count(self) -> int:
        """全局流民数 = 各路本地 refugees 求和（单一事实来源，避免双写漂移）。"""
        return sum(p.get("refugees", 0) for p in self.prefectures.values())

    @refugee_count.setter
    def refugee_count(self, value):
        """兼容旧代码对 self.refugee_count 的赋值：按比例摊回各路（极端兜底，正常不应触发）。"""
        total = sum(p.get("refugees", 0) for p in self.prefectures.values())
        if total <= 0:
            # 无现有流民时把新值均摊到非京畿路
            roads = [k for k, p in self.prefectures.items() if not p.get("is_capital")]
            if roads:
                share = value // len(roads)
                for k in roads:
                    self.prefectures[k]["refugees"] = share
        else:
            ratio = value / total
            for p in self.prefectures.values():
                p["refugees"] = int(p.get("refugees", 0) * ratio)
