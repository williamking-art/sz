# -*- coding: utf-8 -*-
"""维多利亚3（Victoria 3）风格生产方式（Production Methods, PM）与中性中间物架构引擎（单一权威源）。

## 规格与背景（M317 / 建筑生产方式与通用中性中间物）

依据用户指示与 Jev 裁定方案 A（概率 0.9819）：
1. **原料纠偏与简化**：
   - 瓷器原料简化规范为：`黏土`（高岭土）+ `煤炭`（或 `木炭`）；
   - 火药原料史实规范为：`硝石` + `硫磺` + `木炭`（《武经总要》一硝二磺三木炭）。
2. **通用中性中间产物体系（Neutral Intermediate Commodities）**：
   - 金属类：`铁锭`、`钢锭`、`铜锭`；
   - 木作与机械：`木方`、`机械零件`；
   - 纺织被服：`布料`、`丝绸`；
   - 化工皮革文教：`火药`、`皮革`、`纸张`；
   - 彻底终结下游每种终端产品都需要特定专用中间件的孤儿物料困境；
   - 所有终端装备（兵器、火器、战船、鞍甲、经书、被服、未来蒸汽机）全部链式消费中性中间物。
3. **维多利亚3风格生产方式（Production Methods, PM）架构**：
   - 产业建筑是实体容器，拥有四大 PM 槽位：
     - **主工艺槽（Base PM）**：决定物料配方与投入产出比；
     - **动力方式槽（Power PM）**：决定动力源（人力手摇 / 水力机械 / 蒸汽动力机组），提供全局产能跃升乘数；
     - **所有权模式槽（Ownership PM）**：决定经营与收益归属（官营直辖 / 民办商贾 / 官督民办特许扑买）；
     - **组织形态槽（Organization PM）**：决定工匠与劳工分工（行会作坊 1.0x / 工场手工业 1.8x / 机械化动力大工厂 4.0x）；
   - 支持随玩家科技演进、地理水利条件（如临近大河水运）与产业政策动态切换 PM。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from content.data_constants import MATERIAL_PRICE_BASE
from core.domains.economy.macro_climate import ALL_CIRCUITS_21

log = logging.getLogger(__name__)

__all__ = [
    "NEUTRAL_INTERMEDIATES",
    "ProductionMethod",
    "PM_REGISTRY",
    "BUILDING_DEFAULT_PMS",
    "can_switch_pm",
    "switch_pm",
    "get_building_pms",
    "calculate_building_throughput",
    "relative_throughput_multiplier",
]

#: 十大通用中性中间物目录（大宗流通商品）
NEUTRAL_INTERMEDIATES = [
    "铁锭", "钢锭", "铜锭", "木方", "机械零件",
    "布料", "丝绸", "皮革", "纸张", "火药"
]


@dataclass
class ProductionMethod:
    """单个生产方式（Production Method）规范。"""
    id: str                                    # 唯一标识符
    name: str                                  # 中文名
    category: str                              # "base" (基础工艺) | "power" (动力方式) | "ownership" (所有权) | "organization" (生产组织形态)
    building_types: List[str]                  # 适用的建筑类型
    inputs: Dict[str, float] = field(default_factory=dict)       # 单位输入消耗
    outputs: Dict[str, float] = field(default_factory=dict)      # 单位产出
    worker_demand: Dict[str, int] = field(default_factory=dict)  # 工匠用工需求
    maintenance: Dict[str, float] = field(default_factory=dict)  # 维持损耗
    throughput_mult: float = 1.0               # 产能与效率倍数
    prereq_tech: Optional[str] = None          # 前置科技
    prereq_waterway: bool = False              # 是否必须临近水系
    description: str = ""                      # 历史背景与说明


#: 全局权威生产方式注册表（PM Registry）
PM_REGISTRY: Dict[str, ProductionMethod] = {
    # ---------------- 1. 冶铁重工业生产方式 ----------------
    "pm_smelting_charcoal": ProductionMethod(
        id="pm_smelting_charcoal",
        name="木炭土炉冶炼",
        category="base",
        building_types=["冶铁工场", "工坊"],
        inputs={"铁": 10.0, "木炭": 8.0},
        outputs={"铁锭": 6.0},
        worker_demand={"工匠": 20},
        throughput_mult=1.0,
        description="传统小高炉，耗炭量大，产出生铁熟铁混合物。",
    ),
    "pm_smelting_coke": ProductionMethod(
        id="pm_smelting_coke",
        name="焦炭高炉冶炼",
        category="base",
        building_types=["冶铁工场", "工坊"],
        inputs={"铁": 8.0, "煤炭": 2.0},
        outputs={"铁锭": 8.0},
        worker_demand={"工匠": 25},
        throughput_mult=1.5,
        description="宋代徐州、太原开创之焦炭炼铁，脱硫增碳，产出优质铁锭。",
    ),
    "pm_crucible_steel": ProductionMethod(
        id="pm_crucible_steel",
        name="百炼炒钢坩埚法",
        category="base",
        building_types=["冶铁工场", "工坊"],
        inputs={"铁锭": 8.0, "煤炭": 4.0},
        outputs={"钢锭": 6.0},
        worker_demand={"工匠": 30},
        throughput_mult=1.2,
        description="沈括《梦溪笔谈》灌钢法与坩埚炼钢，产出锻造机械与枪管的高强度钢锭。",
    ),

    # ---------------- 2. 动力方式槽位（通用） ----------------
    "pm_power_manual": ProductionMethod(
        id="pm_power_manual",
        name="人力手工驱动",
        category="power",
        building_types=["冶铁工场", "纺织工场", "木作器械坊", "造纸印书局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={"工匠": 10},
        throughput_mult=1.0,
        description="纯人工摇车、拉风橐与踏碓，受体力极大限制。",
    ),
    "pm_power_water": ProductionMethod(
        id="pm_power_water",
        name="水排水力机械组",
        category="power",
        building_types=["冶铁工场", "纺织工场", "木作器械坊", "造纸印书局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={"工匠": 5},
        maintenance={"机械零件": 0.1},
        prereq_waterway=True,
        throughput_mult=2.5,
        description="杜诗水排与宋代水力大纺车，借黄河汴河江水之力，产能提升2.5倍。",
    ),
    "pm_power_steam": ProductionMethod(
        id="pm_power_steam",
        name="蒸汽动力机组",
        category="power",
        building_types=["冶铁工场", "纺织工场", "木作器械坊", "造纸印书局", "工坊"],
        inputs={"煤炭": 5.0},
        outputs={},
        worker_demand={"工匠": 8},
        maintenance={"机械零件": 2.0},
        prereq_tech="steam_engine_unlocked",
        throughput_mult=6.0,
        description="现代玩家推进之近代工业之源，彻底打破地理与水利制约，产能暴涨6倍。",
    ),

    # ---------------- 3. 陶瓷琉璃生产方式 ----------------
    "pm_ceramics_charcoal": ProductionMethod(
        id="pm_ceramics_charcoal",
        name="松柴窑烧青瓷",
        category="base",
        building_types=["官窑瓷坊", "工坊"],
        inputs={"黏土": 10.0, "木炭": 6.0},
        outputs={"精品瓷器": 4.0},
        worker_demand={"工匠": 25},
        throughput_mult=1.0,
        description="南方龙窑松柴还原焰烧造，胎质温润细腻，宋代传世经典。",
    ),
    "pm_ceramics_coal": ProductionMethod(
        id="pm_ceramics_coal",
        name="石炭大窑烧瓷",
        category="base",
        building_types=["官窑瓷坊", "工坊"],
        inputs={"黏土": 10.0, "煤炭": 4.0},
        outputs={"精品瓷器": 6.0},
        worker_demand={"工匠": 20},
        throughput_mult=1.5,
        description="北方定窑、磁州窑采用石炭高窑，炉温高而均衡，规模化大宗出口。",
    ),

    # ---------------- 4. 火药化工生产方式 ----------------
    "pm_gunpowder_standard": ProductionMethod(
        id="pm_gunpowder_standard",
        name="一硝二磺三木炭",
        category="base",
        building_types=["火药局", "工坊"],
        inputs={"硝石": 5.0, "硫磺": 3.0, "木炭": 2.0},
        outputs={"火药": 8.0},
        worker_demand={"工匠": 15},
        throughput_mult=1.0,
        description="《武经总要》标准配比，捣碎研磨过筛制成军用黑火药。",
    ),

    # ---------------- 5. 机械制造与中性组装生产方式 ----------------
    "pm_tools_machinery": ProductionMethod(
        id="pm_tools_machinery",
        name="机械零件模锻",
        category="base",
        building_types=["木作机械坊", "工坊"],
        inputs={"铁锭": 6.0, "木方": 4.0},
        outputs={"机械零件": 4.0},
        worker_demand={"工匠": 25},
        throughput_mult=1.0,
        description="制造通用齿轮、轴承、连杆、翻车水轮与铁制母机配件。",
    ),

    # ---------------- 6. 下游装配生产方式（链式消费中性物） ----------------
    "pm_firearms_assembly": ProductionMethod(
        id="pm_firearms_assembly",
        name="神机火器总装",
        category="base",
        building_types=["火器制造坊", "兵器营造坊", "工坊"],
        inputs={"钢锭": 4.0, "铜锭": 2.0, "火药": 4.0, "木方": 2.0},
        outputs={"火器弹药": 3.0},
        worker_demand={"工匠": 35},
        throughput_mult=1.0,
        description="铸铜铁炮管，装配木托与火药，产出突火枪与铁火炮。",
    ),
    "pm_shipbuilding_barges": ProductionMethod(
        id="pm_shipbuilding_barges",
        name="干坞漕船总装",
        category="base",
        building_types=["造船作坊", "工坊"],
        inputs={"木方": 12.0, "铁锭": 2.0, "布料": 3.0},
        outputs={"漕船海舶": 0.1},
        worker_demand={"工匠": 40},
        throughput_mult=1.0,
        description="以木方骨架、铁钉紧固、麻帆布料装配平底大漕船。",
    ),
    "pm_printing_press": ProductionMethod(
        id="pm_printing_press",
        name="活字雕版印造",
        category="base",
        building_types=["印造经籍局", "工坊"],
        inputs={"纸张": 8.0, "油墨": 2.0},
        outputs={"印造书籍": 3.0},
        worker_demand={"工匠": 15},
        throughput_mult=1.0,
        description="经纸张浸润、松烟油墨覆刷、活字雕版压印成册，印行经史子集与交子盐引。",
    ),
    "pm_ink_making": ProductionMethod(
        id="pm_ink_making",
        name="松烟桐油炼墨",
        category="base",
        building_types=["墨坊", "造纸印书局", "工坊"],
        inputs={"木炭": 4.0},
        outputs={"油墨": 6.0},
        worker_demand={"工匠": 10},
        throughput_mult=1.0,
        description="烧松取烟、桐油点烟，配入麝香皮胶，研制徽墨与印刷重油墨。",
    ),
    "pm_four_treasures": ProductionMethod(
        id="pm_four_treasures",
        name="文房雅玩手作",
        category="base",
        building_types=["文房作坊", "工坊"],
        inputs={"纸张": 4.0, "油墨": 2.0, "石": 2.0},
        outputs={"文房四宝": 1.0},
        worker_demand={"工匠": 20},
        throughput_mult=1.0,
        description="湖笔、徽墨、宣纸、端歙名砚，士绅科举与文人唱和雅致刚需消费。",
    ),
    "pm_living_oil_paste": ProductionMethod(
        id="pm_living_oil_paste",
        name="粮油酱醋工坊",
        category="base",
        building_types=["粮油酱园", "工坊"],
        inputs={"麻": 4.0, "铁": 1.0},
        outputs={"食用油": 3.0, "酱醋": 3.0},
        worker_demand={"工匠": 12},
        throughput_mult=1.0,
        description="柴米油盐酱醋茶民生七事工坊，压榨麻油菜籽油，发酵酱油陈醋。",
    ),

    # ---------------- 7. 所有权与经营模式槽位 ----------------
    "pm_ownership_state": ProductionMethod(
        id="pm_ownership_state",
        name="官办官营直辖",
        category="ownership",
        building_types=["冶铁工场", "官窑瓷坊", "火药局", "火器制造坊", "造船作坊", "印造经籍局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={},
        throughput_mult=1.0,
        description="朝廷度支发饷，产品全额解送国库太仓与官工料场。",
    ),
    "pm_ownership_private": ProductionMethod(
        id="pm_ownership_private",
        name="民间商帮自营",
        category="ownership",
        building_types=["冶铁工场", "纺织工场", "木作机械坊", "官窑瓷坊", "印造经籍局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={},
        throughput_mult=1.15,
        description="民间商人自筹资金、自主雇工，追求商业利润，向官府纳三十税一。",
    ),
    "pm_ownership_charter": ProductionMethod(
        id="pm_ownership_charter",
        name="官督民办扑买",
        category="ownership",
        building_types=["冶铁工场", "官窑瓷坊", "工坊"],
        inputs={},
        outputs={},
        worker_demand={},
        throughput_mult=1.2,
        description="官府核发特许牌照，商人竞标承包，官府坐收巨额榷税。",
    ),

    # ---------------- 8. 生产组织形态槽位（作坊 vs 工场 vs 工业化大生产） ----------------
    "pm_org_craft_guild": ProductionMethod(
        id="pm_org_craft_guild",
        name="行会手工作坊",
        category="organization",
        building_types=["冶铁工场", "纺织工场", "木作机械坊", "官窑瓷坊", "火药局", "火器制造坊", "造船作坊", "印造经籍局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={"工匠": 100},
        maintenance={},
        throughput_mult=1.0,
        description="传统行会师徒制，精工细作，完全依赖高熟练度工匠，受个体体力技艺制约，无流水规模效益。",
    ),
    "pm_org_manufactory": ProductionMethod(
        id="pm_org_manufactory",
        name="工场手工业分工",
        category="organization",
        building_types=["冶铁工场", "纺织工场", "木作机械坊", "官窑瓷坊", "火药局", "火器制造坊", "造船作坊", "印造经籍局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={"工匠": 8, "工人": 25},
        maintenance={"铁锭": 0.05},
        throughput_mult=1.8,
        description="手工业工场分工协作，工匠充任监工与技师，大量雇佣散工流水装配，产能达到传统作坊1.8倍。",
    ),
    "pm_org_industrial_factory": ProductionMethod(
        id="pm_org_industrial_factory",
        name="机械化动力大工厂",
        category="organization",
        building_types=["冶铁工场", "纺织工场", "木作机械坊", "官窑瓷坊", "火药局", "火器制造坊", "造船作坊", "印造经籍局", "工坊"],
        inputs={},
        outputs={},
        worker_demand={"工匠": 5, "工人": 60},
        maintenance={"机械零件": 1.0},
        throughput_mult=4.0,
        description="近代动力流水线大工厂，母机日夜轰鸣，彻底实现标准化工业化大生产，产能暴增4倍，吸纳海量城市劳工。",
    ),
}

#: 默认初始建筑生产方式配置
BUILDING_DEFAULT_PMS: Dict[str, Dict[str, str]] = {
    "冶铁工场": {"base": "pm_smelting_coke", "power": "pm_power_manual", "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild"},
    "官窑瓷坊": {"base": "pm_ceramics_coal", "power": "pm_power_manual", "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild"},
    "火药局": {"base": "pm_gunpowder_standard", "power": "pm_power_manual", "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild"},
    "木作机械坊": {"base": "pm_tools_machinery", "power": "pm_power_manual", "ownership": "pm_ownership_private", "organization": "pm_org_craft_guild"},
    "火器制造坊": {"base": "pm_firearms_assembly", "power": "pm_power_manual", "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild"},
    "造船作坊": {"base": "pm_shipbuilding_barges", "power": "pm_power_manual", "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild"},
    "印造经籍局": {"base": "pm_printing_press", "power": "pm_power_manual", "ownership": "pm_ownership_private", "organization": "pm_org_craft_guild"},
}


def get_building_pms(state: Any, circuit: str, seat_id: str, building_name: str) -> Dict[str, str]:
    """读取某治所某建筑当前生效的四大生产方式槽位（幂等回退；只读，不建空键）。"""
    stats = getattr(state, "statistics", None)
    if isinstance(stats, dict):
        pm_store = stats.get("seat_production_methods")
        key = f"{circuit}:{seat_id}:{building_name}"
        if isinstance(pm_store, dict) and key in pm_store:
            row = pm_store[key]
            if isinstance(row, dict):
                return dict(row)

    # 回退到默认配置
    return dict(BUILDING_DEFAULT_PMS.get(building_name, {
        "base": "pm_smelting_charcoal",
        "power": "pm_power_manual",
        "ownership": "pm_ownership_private",
        "organization": "pm_org_craft_guild",
    }))


def _pm_product(pms: Dict[str, str]) -> Optional[float]:
    """四槽 `throughput_mult` 乘积；任一槽缺失/未知/非有限 ⇒ None（不猜）。"""
    total = 1.0
    for slot in ("base", "power", "ownership", "organization"):
        pid = (pms or {}).get(slot)
        pm = PM_REGISTRY.get(pid) if isinstance(pid, str) else None
        if pm is None:
            return None
        try:
            val = float(pm.throughput_mult)
        except (TypeError, ValueError):
            return None
        if val != val or val in (float("inf"), float("-inf")):
            return None
        total *= val
    return total


def relative_throughput_multiplier(
    state: Any, circuit: str, seat_id: str, building_name: str,
) -> float:
    """当前 PM 相对**建筑默认四槽**的产出倍率（只读；默认配置恒 1.0）。

    默认中性：`current_mult / default_mult`。非法/缺失 PM、未知建筑、
    default 非正/不可读 ⇒ 1.0（安全中性，不改变平衡）。
    """
    try:
        default = BUILDING_DEFAULT_PMS.get(building_name)
        if not isinstance(default, dict):
            return 1.0
        default_mult = _pm_product(default)
        if default_mult is None or default_mult <= 0:
            return 1.0
        current = get_building_pms(state, circuit, seat_id, building_name)
        current_mult = _pm_product(current)
        if current_mult is None or current_mult <= 0:
            return 1.0
        return float(current_mult / default_mult)
    except Exception:  # noqa: BLE001 — 读侧失败必须中性，不影响结算
        return 1.0


def can_switch_pm(
    state: Any,
    circuit: str,
    seat_id: str,
    building_name: str,
    target_pm_id: str,
) -> Tuple[bool, str]:
    """前置条件检查：是否允许切换到指定的生产方式。"""
    if target_pm_id not in PM_REGISTRY:
        return False, f"未知的生产方式: {target_pm_id}"

    pm = PM_REGISTRY[target_pm_id]

    # 1. 建筑类型契约检查
    if building_name not in pm.building_types and "工坊" not in pm.building_types:
        return False, f"生产方式 {pm.name} 不适用于建筑 {building_name}"

    # 2. 科技前置检查
    if pm.prereq_tech:
        tech_unlocked = bool(getattr(state, pm.prereq_tech, False))
        if not tech_unlocked:
            return False, f"需要解锁前置科技: {pm.prereq_tech}"

    # 3. 地理水利条件检查（如水排水力必须临水）
    if pm.prereq_waterway:
        from core.domains.economy.waterway_seats import waterway_tier_route
        tier = waterway_tier_route(circuit)
        if tier not in ("强", "有"):
            return False, f"{circuit} 缺乏大江水运条件，无法架设水排机组"

    # 4. 工业化大工厂动力前置检查（必须依托水力或蒸汽动力，严禁人力手摇流水线工厂）
    if target_pm_id == "pm_org_industrial_factory":
        cur_pms = get_building_pms(state, circuit, seat_id, building_name)
        cur_power = cur_pms.get("power", "pm_power_manual")
        if cur_power not in ("pm_power_water", "pm_power_steam"):
            return False, "机械化大工厂必须依赖水力或蒸汽动力机组，无法在纯手工驱动下运转"

    return True, "满足切换前置条件"


def switch_pm(
    state: Any,
    circuit: str,
    seat_id: str,
    building_name: str,
    target_pm_id: str,
) -> bool:
    """切换建筑生产方式（受控写操作）。"""
    allowed, reason = can_switch_pm(state, circuit, seat_id, building_name, target_pm_id)
    if not allowed:
        log.warning(f"切换生产方式失败 [{building_name} -> {target_pm_id}]: {reason}")
        return False

    pm = PM_REGISTRY[target_pm_id]
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    pm_store = stats.setdefault("seat_production_methods", {})
    key = f"{circuit}:{seat_id}:{building_name}"
    cur_pms = pm_store.setdefault(key, dict(BUILDING_DEFAULT_PMS.get(building_name, {
        "base": "pm_smelting_charcoal", "power": "pm_power_manual", "ownership": "pm_ownership_private", "organization": "pm_org_craft_guild"
    })))

    # 更新对应槽位
    cur_pms[pm.category] = target_pm_id
    log.info(f"[{circuit}:{seat_id}] {building_name} 成功切换 {pm.category} 生产方式为: {pm.name}")
    return True


def calculate_building_throughput(
    state: Any,
    circuit: str,
    seat_id: str,
    building_name: str,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """计算某建筑在当前激活的四大生产方式组合下的综合物料吞吐、用工与产出。"""
    active_pms = get_building_pms(state, circuit, seat_id, building_name)
    base_pm = PM_REGISTRY.get(active_pms.get("base", ""))
    power_pm = PM_REGISTRY.get(active_pms.get("power", ""))
    ownership_pm = PM_REGISTRY.get(active_pms.get("ownership", ""))
    org_pm = PM_REGISTRY.get(active_pms.get("organization", ""))

    if not base_pm:
        return {"inputs": {}, "outputs": {}, "net_value": 0.0}

    # 综合产能倍数 = 基础工艺倍数 × 动力倍数 × 所有权加成 × 组织形态乘数
    total_mult = (
        (base_pm.throughput_mult)
        * (power_pm.throughput_mult if power_pm else 1.0)
        * (ownership_pm.throughput_mult if ownership_pm else 1.0)
        * (org_pm.throughput_mult if org_pm else 1.0)
        * scale
    )

    inputs: Dict[str, float] = {}
    for k, v in base_pm.inputs.items():
        inputs[k] = round(v * total_mult, 2)

    # 叠加动力额外消耗（如蒸汽机耗焦煤）与维持损耗
    if power_pm and power_pm.inputs:
        for k, v in power_pm.inputs.items():
            inputs[k] = round(inputs.get(k, 0.0) + v * total_mult, 2)
    if power_pm and power_pm.maintenance:
        for k, v in power_pm.maintenance.items():
            inputs[k] = round(inputs.get(k, 0.0) + v * total_mult, 2)

    # 叠加组织形态维保消耗（如工场磨损、大工厂母机磨损）
    if org_pm and org_pm.maintenance:
        for k, v in org_pm.maintenance.items():
            inputs[k] = round(inputs.get(k, 0.0) + v * total_mult, 2)

    outputs: Dict[str, float] = {}
    for k, v in base_pm.outputs.items():
        outputs[k] = round(v * total_mult, 2)

    # 用工结构核算（工匠 vs 劳工）
    worker_demand: Dict[str, int] = {}
    if org_pm and org_pm.worker_demand:
        for role, count in org_pm.worker_demand.items():
            worker_demand[role] = int(round(count * scale))
    elif base_pm.worker_demand:
        for role, count in base_pm.worker_demand.items():
            worker_demand[role] = int(round(count * scale))

    # 计算物料加工净增值
    input_cost = sum(inputs.get(k, 0.0) * MATERIAL_PRICE_BASE.get(k, 50) for k in inputs)
    output_val = sum(outputs.get(k, 0.0) * MATERIAL_PRICE_BASE.get(k, 100) for k in outputs)
    net_value = round(output_val - input_cost, 2)

    return {
        "building": building_name,
        "circuit": circuit,
        "seat_id": seat_id,
        "active_pms": active_pms,
        "total_mult": round(total_mult, 2),
        "inputs": inputs,
        "outputs": outputs,
        "worker_demand": worker_demand,
        "net_value": net_value,
        "ownership": ownership_pm.name if ownership_pm else "民办商营",
        "organization": org_pm.name if org_pm else "行会手工作坊",
    }

