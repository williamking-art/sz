# -*- coding: utf-8 -*-
"""宋祚 · 局势 metric 注册表（core/situation_metrics.py）

依据：《宋祚局势系统实施规范》§3.2 / §12。
- 本模块是**唯一权威**的 metric 注册表：未注册 metric 一律拒绝（v2 DSL 用）；
- **v1 只启用 severity 派生所需项**（region.unrest / region.public_support / treasury）；
  其余（region.grain_months / army.morale / event_flag）在 v2 启用判定时按规范补入并补测试。
- 只读：不写任何 POP / 国库 / 内帑 / 州县 / 局势字段。
- 依赖方向固定：`situations / situation_metrics → region_brief`（单向，region_brief 不得反向读取）。

## 一次性快照（规范 §3.3）
`build_metric_snapshot(state, keys)` 在**一次调用内**把所有 metric 取完，
供 `evaluate(condition, snapshot)` 等纯函数消费——禁止判定过程中回读 state。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

from content.data import GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST
from core.numeric import parse_number as _finite, clamp as _clamp

log = logging.getLogger("situation_metrics")

__all__ = ["MetricSpec", "METRICS", "build_metric_snapshot", "SnapshotContext",
           "POP_SENTIMENT_CHANNELS", "CLERK_SENTIMENT_CHANNELS"]


class MetricSpec(NamedTuple):
    """metric 规格：实现 / 参数类型 / 返回类型 / 是否必填参数 / 缺失策略。"""
    fn: Callable[[Any, Optional[str], dict], Any]
    arg_type: Optional[str]
    return_type: str
    required_arg: bool
    missing_policy: str


# ---------------------------------------------------------------------------
# 快照上下文（一次取值，避免判定过程中回读 state）
# ---------------------------------------------------------------------------
class SnapshotContext:
    """构建快照时一次性收集的只读数据。**不得**写入 state。"""

    def __init__(self, state) -> None:
        # 快照期间的只读派生失败（**不静默**：并入 readout_errors → readout_status=partial）
        self.errors: List[str] = []
        self.treasury = _finite(getattr(state, "treasury", 0), 0.0)
        self.imperial_treasury = _finite(getattr(state, "imperial_treasury", 0), 0.0)
        self.prestige = _finite(getattr(state, "prestige", 0), 0.0)
        # POP 读数：宋祚每路 6 类 POP 结构各不相同，故按「路|阶层」全面预取（一次取值）
        self.pops: Dict[str, Dict[str, float]] = {}
        prefectures = getattr(state, "prefectures", None)
        if not isinstance(prefectures, dict):
            prefectures = {}
        self.prefs: Dict[str, Any] = prefectures
        if prefectures:
            for route, p in prefectures.items():
                if not isinstance(p, dict):
                    continue
                for cls, pop in (p.get("pops") or {}).items():
                    if not isinstance(pop, dict):
                        continue
                    size = _finite(pop.get("size"))
                    wealth = _finite(pop.get("wealth"))
                    self.pops[f"{route}|{cls}"] = {
                        "size": size,
                        "wealth": wealth,
                        "grain": _finite(pop.get("grain")),
                        "wealth_per_capita": (wealth / size) if size > 0 else 0.0,
                        "clan": _finite(pop.get("clan")),      # 士绅子池：宗室
                        "clerks": _finite(pop.get("clerks")),  # 官僚子池：吏
                        # 非经济维度：欠税（A1 科目）＝ 缴不动/不愿缴 → 该阶级顺从度的直接代理
                        "arrears": _finite(pop.get("欠税")),
                        "hoard": _finite(pop.get("窖银")),     # 士绅窖藏之银（退出流通＝不信任朝廷）
                    }
        # 地区读数：复用 region_brief 的既有口径（不复制算法）
        self.regions: Dict[str, Dict[str, Any]] = {}
        try:
            from core.region_brief import build_region_brief
            brief = build_region_brief(state)
            for row in brief.get("routes", []):
                self.regions[str(row.get("name"))] = row
            self.region_status = brief.get("readout_status", "ok")
            self.region_errors = list(brief.get("readout_errors") or [])
        except Exception as e:  # noqa: BLE001  只读派生失败不得中断面板
            log.warning("situation_metrics 取 region_brief 失败：%s", e)
            self.region_status = "partial"
            self.region_errors = [f"region_brief: {type(e).__name__}"]
        # 吏治（宋祚既有派生：吏怨缓动不归零、把持度、诏令执行折扣）与派系满意度
        # （官员满意度的载体——满意度低则配合度/执行度下降，见 core/clerks.py §16.4）
        #
        # **POP 归属说明**：吏是 `官僚 POP` 的 `clerks` 子池，`clerks.totals` 就是按各路人头
        # 加权出来的全国派生视图（吏数/吏怨/把持度/有效吏力）；派系满意度是 `官员`（官僚 POP）
        # 及士绅等的政治表达。二者都是 **同一条 POP 账本** 的派生读数，不另设账本。
        self.clerks: Dict[str, float] = {}
        self.clerks_view: Dict[str, Any] = {}
        self.factions: Dict[str, float] = {}
        self.execution_mult: float = 1.0
        try:
            from core.clerks import decree_execution_mult as _dem
            from core.clerks import totals as _clerk_totals
            raw = _clerk_totals(state) or {}
            for k, v in raw.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    self.clerks[str(k)] = _finite(v)
            self.clerks_view = {str(k): v for k, v in raw.items()}
            self.execution_mult = _clamp(_finite(_dem(state), 1.0), 0.0, 2.0)
        except Exception as e:  # noqa: BLE001
            log.warning("situation_metrics 取吏治读数失败：%s", e)
            self.errors.append(f"clerks: {type(e).__name__}")
        for name, f in (getattr(state, "factions", None) or {}).items():
            if isinstance(f, dict):
                self.factions[str(name)] = _finite(f.get("satisfaction"), 50.0)
        # 逐路吏治明细（吏怨/把持度**各省不同**——宋祚每路 POP 结构不同，故不得只取全国均值）
        self.clerks_routes: Dict[str, Dict[str, float]] = {}
        for route, p in (prefectures or {}).items():
            if not isinstance(p, dict):
                continue
            d = p.get("clerks_detail")
            if not isinstance(d, dict):
                continue
            self.clerks_routes[str(route)] = {
                "grievance": _finite(d.get("grievance"), 0.0),
                "grip": _finite(d.get("grip"), 0.0),
                "hereditary": _finite(d.get("hereditary"), 0.0),
                "extortion": _finite(d.get("extortion"), 0.0),
            }
        # 官制（官员）非经济维度：待阙堆积 / 冗官 / 定员（core/officialdom 为唯一权威）
        self.officials: Dict[str, Any] = {}
        try:
            from core.officialdom import totals as _off_totals
            raw_off = _off_totals(state) or {}
            self.officials = {str(k): v for k, v in raw_off.items()}
        except Exception as e:  # noqa: BLE001
            log.warning("situation_metrics 取官制读数失败：%s", e)
            self.errors.append(f"officialdom: {type(e).__name__}")
        # 兵 POP 的**军心通道**（军队督行政令，见 core/army_models.military_channels）
        self.army_routes: Dict[str, Dict[str, Any]] = {}
        self.army_nation: Optional[Dict[str, Any]] = None
        try:
            from core.army_models import military_channels
            self.army_nation = military_channels(state)
            for route in (prefectures or {}):
                row = military_channels(state, str(route))
                if row is not None:
                    self.army_routes[str(route)] = row
        except Exception as e:  # noqa: BLE001
            log.warning("situation_metrics 取军政读数失败：%s", e)
            self.errors.append(f"army: {type(e).__name__}")

    def faction(self, name: Optional[str]) -> Optional[float]:
        if not name:
            return None
        return self.factions.get(name)

    def region(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        return self.regions.get(name)

    def pop(self, key: Optional[str]) -> Optional[Dict[str, float]]:
        if not key:
            return None
        return self.pops.get(key)


# ---------------------------------------------------------------------------
# metric 实现
# ---------------------------------------------------------------------------
def _m_region_unrest(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("unrest"), 0.0)


def _m_region_public_support(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("public_support"), 0.0)


def _m_region_gentry(state, arg: Optional[str], ctx: SnapshotContext):
    """士绅抵抗 0–100（隐田蔽课 / 抗税 / 把持乡里）——士绅 POP 的非经济维度。"""
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("gentry_resistance"), 0.0)


def _m_region_fiscal(state, arg: Optional[str], ctx: SnapshotContext):
    """市面与财政健康 0–100（既有地区深化口径）——工匠/商人的经营环境。"""
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("fiscal"), 50.0)


def _m_region_mood(state, arg: Optional[str], ctx: SnapshotContext):
    """民情 0–100（与民心同源、口径更粗）。"""
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("mood"), 50.0)


def _m_region_literacy(state, arg: Optional[str], ctx: SnapshotContext):
    """**识字率** 0–100（2026-09-19 新增设定）：诏令实际效果的弱关联项之一。"""
    row = ctx.region(arg)
    return None if row is None else _finite(row.get("literacy"), 0.0)


def _m_literacy_national(state, arg: Optional[str], ctx: SnapshotContext):
    """全国识字率（全部 POP 按人口加权派生；旧档缺读数 → 缺失，不伪造）。"""
    v = getattr(state, "literacy", None)
    return None if v is None else _finite(v)


def _m_pop_literacy(state, arg: Optional[str], ctx: SnapshotContext):
    """**该类 POP 自有识字率**（路|阶层；0–100）。缺失 → 缺失（不伪造 0）。"""
    if not arg or "|" not in arg:
        return None
    route, _, cls = arg.partition("|")
    p = ctx.prefs.get(route)
    if not isinstance(p, dict):
        return None
    pop = ((p.get("pops") or {}).get(cls))
    if not isinstance(pop, dict) or pop.get("literacy") is None:
        return None
    return _finite(pop.get("literacy"))


def _m_treasury(state, arg: Optional[str], ctx: SnapshotContext):
    return ctx.treasury


def _m_pop_size(state, arg: Optional[str], ctx: SnapshotContext):
    pop = ctx.pop(arg)
    return None if pop is None else pop["size"]


def _m_pop_wealth(state, arg: Optional[str], ctx: SnapshotContext):
    pop = ctx.pop(arg)
    return None if pop is None else pop["wealth"]


def _m_pop_grain(state, arg: Optional[str], ctx: SnapshotContext):
    pop = ctx.pop(arg)
    return None if pop is None else pop["grain"]


def _m_pop_wpc(state, arg: Optional[str], ctx: SnapshotContext):
    """人均财富（贯/口）——民力与军心的直接信号；`size` 为 0 时返回 0。"""
    pop = ctx.pop(arg)
    return None if pop is None else pop["wealth_per_capita"]


def _m_pop_clan(state, arg: Optional[str], ctx: SnapshotContext):
    """士绅 POP 的宗室子池（人口口径，非独立账本）。"""
    pop = ctx.pop(arg)
    return None if pop is None else pop["clan"]


def _m_pop_clerks(state, arg: Optional[str], ctx: SnapshotContext):
    """官僚 POP 的吏子池。"""
    pop = ctx.pop(arg)
    return None if pop is None else pop["clerks"]


# —— 吏治 / 派系：POP 满意度 → 执行度的载体（宋祚「下了诏≠办了事」）——
def _m_clerks_grievance(state, arg: Optional[str], ctx: SnapshotContext):
    """全国吏怨（按各路人头加权的 0–100；缓动、不归零）。"""
    return None if not ctx.clerks else ctx.clerks.get("grievance")


def _m_clerks_grip(state, arg: Optional[str], ctx: SnapshotContext):
    """全国把持度（0–1，吏强官弱）。"""
    return None if not ctx.clerks else ctx.clerks.get("grip")


def _m_clerks_execution_mult(state, arg: Optional[str], ctx: SnapshotContext):
    """诏令执行折扣（`core/clerks.py` 唯一权威：`decree_execution_mult`，已 clamp 0–2）。"""
    return None if not ctx.clerks else ctx.execution_mult


def _m_clerks_effective(state, arg: Optional[str], ctx: SnapshotContext):
    """有效吏力 = 吏数 ×(1 − 吏怨/100)：**"冗而不足"的载体**（吏越多≠办事越多）。"""
    return None if not ctx.clerks else ctx.clerks.get("effective")


def _m_faction_satisfaction(state, arg: Optional[str], ctx: SnapshotContext):
    """派系（官员）满意度 0–100。缺失 ≠ 50：取不到就不给数（缺失策略见注册表）。"""
    return ctx.faction(arg)


def _m_pop_arrears_ratio(state, arg: Optional[str], ctx: SnapshotContext):
    """该路该阶级**欠税占其财富之比**（0–1）＝「缴不动/不愿缴」的顺从度代理。

    两个量都是 POP 既有字段（A1 欠税科目 / wealth），此处只作比值，不新增账本。
    士绅的 `窖银` 同样是退出流通的信任度信号，见 `pop.hoard_ratio`。
    """
    pop = ctx.pop(arg)
    if pop is None:
        return None
    wealth = pop["wealth"]
    if wealth <= 0:
        return None
    return round(max(0.0, pop["arrears"]) / wealth, 4)


def _m_pop_hoard_ratio(state, arg: Optional[str], ctx: SnapshotContext):
    """士绅**窖藏之银占其财富之比**（0–1）：窖藏越多＝越不信朝廷（不投资、不纳税）。"""
    pop = ctx.pop(arg)
    if pop is None or pop["wealth"] <= 0:
        return None
    return round(max(0.0, pop["hoard"]) / pop["wealth"], 4)


# —— 逐路吏治：宋祚每路 POP 结构不同 → 吏怨/把持度**各省不同**（不得只取全国均值）——
def _m_route_clerks_grievance(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.clerks_routes.get(arg or "")
    return None if row is None else row["grievance"]


def _m_route_clerks_grip(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.clerks_routes.get(arg or "")
    return None if row is None else row["grip"]


# —— 官制（官员 POP 的差遣结构）：待阙/冗官是**政令能否落地**的制度性来源 ——
def _m_officials_waiting(state, arg: Optional[str], ctx: SnapshotContext):
    """待阙官数（有官无差遣：领半俸、不办事）。"""
    v = ctx.officials.get("waiting")
    return None if v is None else _finite(v)


def _m_officials_redundant_rate(state, arg: Optional[str], ctx: SnapshotContext):
    """冗官率 = (官额 − 差遣定员) / 官额（>0 即「官多而事不举」）。

    `posts_quota <= 0`（定员尚未初始化）→ **缺失**：不得把「未定编」显示成冗官 100%
    （定员的初始化 `officialdom.ensure_quota` 是**写操作**，只读投影不得调用）。
    """
    officials = _finite(ctx.officials.get("officials"))
    quota = _finite(ctx.officials.get("posts_quota"))
    if officials <= 0 or quota <= 0:
        return None
    return round(max(0.0, officials - quota) / officials, 4)


def _m_officials_waiting_share(state, arg: Optional[str], ctx: SnapshotContext):
    """待阙率 = 待阙官 / 官额（领着半俸、无差遣可办——政令无人经办）。"""
    officials = _finite(ctx.officials.get("officials"))
    if officials <= 0:
        return None
    return round(max(0.0, _finite(ctx.officials.get("waiting"))) / officials, 4)


# —— 兵 POP 的军心通道：政令还要靠军队执行（core/army_models 为唯一权威）——
def _m_army_morale(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.army_routes.get(arg or "")
    return None if row is None else row["morale"]


def _m_army_troops(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.army_routes.get(arg or "")
    return None if row is None else float(row["troops"])


def _m_army_arrears(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.army_routes.get(arg or "")
    return None if row is None else float(row["arrears"])


def _m_army_enforcement(state, arg: Optional[str], ctx: SnapshotContext):
    row = ctx.army_routes.get(arg or "")
    return None if row is None else row["enforcement_mult"]


# ---------------------------------------------------------------------------
# **六类 POP 的非经济维度**（权威声明表；缺一类即视为漏项，测试直接断言本表）
# ---------------------------------------------------------------------------
# 口径（用户定稿 2026-09）：POP 带来的模拟**不止钱粮**——每一类 POP 都有自己的"心气"，
# 且都来自既有派生（不新造字段、不新开账本），逐路取值故**各省不同**：
#   农   → 民心（`region.public_support`）：缴得起、留得住，才有顺民；
#   士绅 → 士绅抵抗（`region.gentry_resistance`）+ 窖藏率（`pop.hoard_ratio`）：
#          隐田蔽课、抗税、窖银不流通＝不合作；
#   工匠 → 市面/财政（`region.fiscal`）+ 欠缴率（`pop.arrears_ratio`）：工役困则器用不供；
#   商人 → 市面/财政（`region.fiscal`）+ 欠缴率（`pop.arrears_ratio`）：商情滞则货不通；
#   官僚 → 冗官率（`officials.redundant_rate`）+ 派系满意度（`faction.satisfaction`）：
#          官多而事不举、待阙堆积＝政令无人办；
#   兵   → 军心（`army.morale`）+ 督行系数（`army.enforcement_mult`，含欠饷折扣）：
#          文书到了兵不动。
# 另有**吏**（官僚 POP 的 `clerks` 子池，单列不另设第 7 类 POP）：
#          `clerks.route_grievance` / `clerks.route_grip` → `clerks.execution_mult`（政令折扣）。
POP_SENTIMENT_CHANNELS: Dict[str, Dict[str, str]] = {
    "农": {"label": "民心", "primary": "region.public_support",
           "secondary": "pop.arrears_ratio", "source": "core/region_brief.py + POP 欠税"},
    "士绅": {"label": "士绅抵抗", "primary": "region.gentry_resistance",
             "secondary": "pop.hoard_ratio", "source": "core/region_brief.py + POP 窖银"},
    "工匠": {"label": "工困（市面/欠缴）", "primary": "region.fiscal",
             "secondary": "pop.arrears_ratio", "source": "core/region_brief.py + POP 欠税"},
    "商人": {"label": "商情（市面/欠缴）", "primary": "region.fiscal",
             "secondary": "pop.arrears_ratio", "source": "core/region_brief.py + POP 欠税"},
    "官僚": {"label": "官心（冗官/派系满意度）", "primary": "officials.redundant_rate",
             "secondary": "faction.satisfaction", "source": "core/officialdom.py + state.factions"},
    "兵": {"label": "军心（士气/欠饷）", "primary": "army.morale",
           "secondary": "army.enforcement_mult", "source": "core/army_models.py"},
}

# 吏（官僚 POP 子池）的通道——**不是第 7 类 POP**，故单列，由测试单独断言
CLERK_SENTIMENT_CHANNELS: Dict[str, str] = {
    "label": "吏怨/把持度 → 政令折扣",
    "primary": "clerks.route_grievance",
    "secondary": "clerks.execution_mult",
    "source": "core/clerks.py",
}


METRICS: Dict[str, MetricSpec] = {
    # —— 地区标量 ——
    "region.unrest": MetricSpec(_m_region_unrest, "州路名", "float", True,
                                "州不存在 → 缺失（node 判 False 并记 warning）"),
    "region.public_support": MetricSpec(_m_region_public_support, "州路名", "float", True,
                                        "州不存在 → 缺失（node 判 False 并记 warning）"),
    "region.gentry_resistance": MetricSpec(_m_region_gentry, "州路名", "float", True,
                                           "州不存在 → 缺失"),
    "region.fiscal": MetricSpec(_m_region_fiscal, "州路名", "float", True, "州不存在 → 缺失"),
    "region.mood": MetricSpec(_m_region_mood, "州路名", "float", True, "州不存在 → 缺失"),
    "region.literacy": MetricSpec(_m_region_literacy, "州路名", "float", True,
                                  "州不存在或无识字率读数 → 缺失"),
    "literacy.national": MetricSpec(_m_literacy_national, None, "float", False,
                                    "识字率未初始化 → 缺失（不伪造）"),
    "pop.literacy": MetricSpec(_m_pop_literacy, "路|阶层", "float", True,
                               "路/阶层缺失或无识字率读数 → 缺失（不伪造 0）"),
    "treasury": MetricSpec(_m_treasury, None, "float", False, "不可缺失"),
    # —— POP 级（宋祚核心：每路 6 类 POP 结构与规模各异）——
    "pop.size": MetricSpec(_m_pop_size, "路|阶层", "float", True, "路/阶层不存在 → 缺失"),
    "pop.wealth": MetricSpec(_m_pop_wealth, "路|阶层", "float", True, "路/阶层不存在 → 缺失"),
    "pop.grain": MetricSpec(_m_pop_grain, "路|阶层", "float", True, "路/阶层不存在 → 缺失"),
    "pop.wealth_per_capita": MetricSpec(_m_pop_wpc, "路|阶层", "float", True,
                                        "路/阶层不存在 → 缺失；size=0 → 0"),
    "pop.clan": MetricSpec(_m_pop_clan, "路|士绅", "float", True, "子池缺失 → 0（未初始化即无宗室）"),
    "pop.clerks": MetricSpec(_m_pop_clerks, "路|官僚", "float", True, "子池缺失 → 0（未初始化即无吏）"),
    # —— POP 的非经济维度（**六类各有**，见 POP_SENTIMENT_CHANNELS）——
    #   农 = region.public_support；士绅 = region.gentry_resistance + pop.hoard_ratio；
    #   工匠/商人 = region.fiscal + pop.arrears_ratio；官僚 = officials.* + faction.satisfaction；
    #   兵 = army.*；吏（官僚子池，单列）= clerks.*
    "pop.arrears_ratio": MetricSpec(_m_pop_arrears_ratio, "路|阶层", "float", True,
                                    "路/阶层缺失或 wealth≤0 → 缺失（不假装「无欠缴」）"),
    "pop.hoard_ratio": MetricSpec(_m_pop_hoard_ratio, "路|士绅", "float", True,
                                  "无士绅或 wealth≤0 → 缺失"),
    # —— POP 的**非经济**维度 ①：吏治（吏怨 / 把持度 → 政令折扣）——
    "clerks.grievance": MetricSpec(_m_clerks_grievance, None, "float", False,
                                   "吏制不可用 → 缺失（不回落 0，避免假装「吏无怨」）"),
    "clerks.grip": MetricSpec(_m_clerks_grip, None, "float", False, "吏制不可用 → 缺失"),
    "clerks.execution_mult": MetricSpec(_m_clerks_execution_mult, None, "float", False,
                                        "吏制不可用 → 缺失（结算侧自身回落 1.0）"),
    "clerks.effective": MetricSpec(_m_clerks_effective, None, "float", False, "吏制不可用 → 缺失"),
    "clerks.route_grievance": MetricSpec(_m_route_clerks_grievance, "路名", "float", True,
                                         "该路无吏制明细 → 缺失（新局尚未落 clerks_detail）"),
    "clerks.route_grip": MetricSpec(_m_route_clerks_grip, "路名", "float", True,
                                    "该路无吏制明细 → 缺失"),
    # —— POP 的**非经济**维度 ②：官制（待阙堆积 / 冗官 → 官多而事不举）——
    "officials.waiting": MetricSpec(_m_officials_waiting, None, "float", False,
                                    "官制不可用 → 缺失"),
    "officials.redundant_rate": MetricSpec(_m_officials_redundant_rate, None, "float", False,
                                           "官额 0 或官制不可用 → 缺失"),
    "officials.waiting_share": MetricSpec(_m_officials_waiting_share, None, "float", False,
                                          "官额 0 或官制不可用 → 缺失"),
    # —— POP 的**非经济**维度 ③：派系（官员/士绅）满意度 → 会签配合度 ——
    "faction.satisfaction": MetricSpec(_m_faction_satisfaction, "派系名", "float", True,
                                       "派系不存在 → 缺失（**不**默认 50）"),
    # —— POP 的**非经济**维度 ④：兵（军心 / 欠饷 → 军队督行政令）——
    "army.morale": MetricSpec(_m_army_morale, "路名", "float", True, "该路无驻军 → 缺失"),
    "army.troops": MetricSpec(_m_army_troops, "路名", "float", True, "该路无驻军 → 缺失"),
    "army.arrears": MetricSpec(_m_army_arrears, "路名", "float", True, "该路无驻军 → 缺失"),
    "army.enforcement_mult": MetricSpec(_m_army_enforcement, "路名", "float", True,
                                        "该路无驻军 → 缺失（无兵可督行）"),
    # —— v2 启用判定时补入（规范 §3.2 表）——
    # "region.grain_months" / "event_flag"
}

_POP_CLASSES = tuple(GRAIN_CONSUME_PER_CAPITA.keys())   # 6 类 POP 的权威来源


def _arg_values(spec: MetricSpec, ctx: SnapshotContext) -> List[Optional[str]]:
    """按参数类型枚举实参（快照一次取全，供判定直接查表）。"""
    if spec.arg_type == "州路名":
        return list(PREFECTURE_LIST)
    if spec.arg_type == "路名":
        return list(PREFECTURE_LIST)
    if spec.arg_type == "路|阶层":
        return [f"{route}|{cls}" for route in PREFECTURE_LIST for cls in _POP_CLASSES]
    if spec.arg_type == "路|士绅":
        return [f"{route}|士绅" for route in PREFECTURE_LIST]
    if spec.arg_type == "路|官僚":
        return [f"{route}|官僚" for route in PREFECTURE_LIST]
    if spec.arg_type == "派系名":
        return sorted(ctx.factions)
    return [None]


def _exists(spec: MetricSpec, arg: Optional[str], ctx: SnapshotContext) -> bool:
    """参数是否**应当**有取值（缺失即视为缺失值，不静默取 0）。

    - `州路名`：region_brief 未给出该路 → 异常，记 error；
    - `路名`：路名合法即通过——**该路无驻军/无吏制明细是正常事实**，
      取值为 None 不是错误（否则 readout_status 会因「内地无禁军」长期 partial）；
    - `路|阶层`：POP 表缺该键 → 异常，记 error；
    - `派系名`：由 `ctx.factions` 自身枚举，故正常恒存在。
    """
    if arg is None:
        return True
    if spec.arg_type == "州路名":
        return arg in ctx.regions
    if spec.arg_type == "路名":
        return arg in PREFECTURE_LIST
    if spec.arg_type and spec.arg_type.startswith("路|"):
        return arg in ctx.pops
    if spec.arg_type == "派系名":
        return arg in ctx.factions
    return True


def build_metric_snapshot(state, metric_keys: List[str]) -> Tuple[dict, List[str]]:
    """一次性取快照。返回 `(snapshot, errors)`。

    - 未注册 metric → 记 error 并跳过（**不**静默返回 0）；
    - metric 实现抛异常 → 记 error，该值缺失（v2 判定据此进程序兜底）；
    - 州路 / POP 不存在 → 视为缺失并记 warning。
    """
    errors: List[str] = []
    ctx = SnapshotContext(state)
    snapshot: Dict[str, Dict[Optional[str], Any]] = {}
    for key in metric_keys:
        spec = METRICS.get(key)
        if spec is None:
            errors.append(f"未注册 metric：{key}")
            log.warning("situation_metrics 未注册 metric：%s", key)
            continue
        table: Dict[Optional[str], Any] = {}
        for arg in _arg_values(spec, ctx):
            if spec.required_arg and not _exists(spec, arg, ctx):
                errors.append(f"{key}({arg})：参数不存在")
                table[arg] = None
                continue
            try:
                table[arg] = spec.fn(state, arg, ctx)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{key}({arg})：{type(e).__name__}")
                log.warning("situation_metrics 取值失败 %s(%s)：%s", key, arg, e)
                table[arg] = None
        snapshot[key] = table
    if ctx.region_status != "ok":
        errors.extend(ctx.region_errors)
    errors.extend(ctx.errors)
    # 除 metric 表外，随快照一并下发**已派生好**的通道读数（只读；供面板/AI 解释，
    # 不在投影层重算算法——各自仍是 core 内唯一权威：clerks / officialdom / army_models）。
    return {
        "metrics": snapshot,
        "treasury": ctx.treasury,
        "imperial_treasury": ctx.imperial_treasury,
        "region_status": ctx.region_status,
        "clerks": dict(ctx.clerks_view),
        "clerks_routes": {k: dict(v) for k, v in ctx.clerks_routes.items()},
        "officials": dict(ctx.officials),
        "factions": dict(ctx.factions),
        "army": dict(ctx.army_nation) if isinstance(ctx.army_nation, dict) else None,
        "army_routes": {k: dict(v) for k, v in ctx.army_routes.items()},
    }, errors
