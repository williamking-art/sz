# -*- coding: utf-8 -*-
"""宋祚 · 声明式月度结算管线与步骤注册表（Settlement Pipeline）。

职责：
- 集中声明月度结算流水线的全部子步骤（Step 0 ~ Step 11.5）；
- 规范化步骤元数据：ID、相位、中文名、调用句柄、关键性（critical）；
- 提供执行器 execute_pipeline，按因果顺序执行，支持耗时度量与容错隔离；
- 提供权威步骤注册表 STEPS，供测试镜像与对账断言直接比对（消灭测试生产两张皮）。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("songzuo.pipeline")

__all__ = [
    "SettlementStep",
    "SettlementPipeline",
    "get_default_pipeline",
    "get_pipeline_step_pairs",
]


@dataclass
class SettlementStep:
    """单个结算子步骤规范。"""
    id: str                  # 机器可读唯一标识（如 "industry_chains"）
    phase: str               # 业务相位（如 "production", "logistics", "finance"）
    name: str                # 中文名称（如 "四大实体产业链"）
    func: Callable           # 执行函数：签名通常为 fn(state, log) 或 fn(state)
    critical: bool = False   # 是否关键核心步（True: 失败直接抛出并整月回滚；False: 失败记 WARN 不阻断）
    description: str = ""    # 机制说明
    raw_func: Optional[Callable] = None  # 原始权威函数对象（若 func 为包装层，此处保留原生引用供镜像核验）

    @property
    def target_func(self) -> Callable:
        """获取底层真实执行的目标函数（供镜像对账与调用探针使用）。"""
        return self.raw_func if self.raw_func is not None else self.func


    def execute(self, state: Any, log_sink: Optional[List[str]] = None, **kwargs: Any) -> Any:
        """安全执行当前步骤，记录耗时与容错。"""
        if log_sink is None:
            log_sink = []
        t0 = time.perf_counter()
        try:
            import inspect
            sig = inspect.signature(self.func)
            param_names = list(sig.parameters.keys())

            wants_log = len(param_names) >= 2 and any(p in ("log", "log_sink") for p in param_names[:2])
            extra_args = {k: v for k, v in kwargs.items() if k in param_names}

            if wants_log:
                res = self.func(state, log_sink, **extra_args)
            elif len(param_names) >= 1:
                res = self.func(state, **extra_args)
            else:
                res = self.func()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return res
        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            log.warning("结算步骤 [%s:%s] 异常 (%.2fms): %r", self.id, self.name, dt_ms, e, exc_info=True)
            if self.critical:
                raise
            log_sink.append(f"[{self.name}][WARN] 推进失败：{e!r}")
            return None


class SettlementPipeline:
    """声明式结算管线调度器。"""

    def __init__(self, steps: Optional[List[SettlementStep]] = None):
        self._steps: List[SettlementStep] = list(steps or [])

    def register(self, step: SettlementStep) -> None:
        """追加注册一个结算步骤。"""
        self._steps.append(step)

    @property
    def steps(self) -> List[SettlementStep]:
        """获取已注册的全部步骤只读列表。"""
        return list(self._steps)

    def execute(self, state: Any, log_sink: List[str], **kwargs: Any) -> List[str]:
        """按声明顺序顺序执行全部步骤。"""
        for step in self._steps:
            step.execute(state, log_sink, **kwargs)
        return log_sink


def build_default_steps() -> List[SettlementStep]:
    """构建《宋祚》现行权威结算步骤注册表（严格保持因果顺序）。"""
    from core.settlement_steps import (
        _settle_decrees, _settle_factions, _settle_economy,
        _settle_land_local, _settle_region_deepen, _settle_literacy,
        _settle_longterm_decrees, _simulate_external,
        _settle_projects, _settle_workshops, _settle_upkeep,
        _settle_granary, _settle_officialdom, _settle_clan, _settle_clerks,
        _settle_finance, _settle_external_economy, _settle_extensions,
        _settle_econ_prices, _settle_treasury,
        _settle_military_diplomacy, _evaluate_timeline_breaks,
        _settle_events, _settle_disaster, _settle_hidden,
        _settle_bank_stock, _settle_emperor_personal
    )
    from core.settlement import (
        _settle_mechanisms, _settle_tech, _settle_org_economy,
        _settle_legacies, _settle_focus,
        _settle_situations, _settle_faction_metrics,
        IMPERIAL_ACTION_ENABLED
    )

    # 包装导入的扩展步
    from core.domains.production.settlement_agri import apply_agri_effects
    from core.domains.production.production_chain import settle_production_chain
    from core.domains.production.farm_procurement import procure_from_farmers, sell_surplus_to_merchants
    from core.domains.economy.industry_chains import settle_industry_chains
    from core.foundation.ledger.material_holding import supply_goods_to_seats
    from core.transport import arrive_due
    from core.material_trade import procure_materials
    from core.civil_building import apply_civil_construction
    from core.domains.economy.pop_livelihood import settle_pop_livelihood

    def _step_spatial_in_transit(state: Any, log: List[str]) -> None:
        from core.foundation.ledger.spatial_warehouse_bridge import (
            advance_in_transit_batches,
            advance_passenger_trips,
        )
        sp_arr = advance_in_transit_batches(state, days=30)
        if sp_arr:
            tot = sum(float(b.get("net_delivered", 0.0) or 0.0) for b in sp_arr)
            log.append(f"[空间在途] 本月运抵 {tot:.1f} 实物（{len(sp_arr)} 批，已清算沈括途耗）")
        p_arr = advance_passenger_trips(state, days=30)
        if p_arr:
            log.append(f"[客运时空] 本月抵达 {len(p_arr)} 批次人员旅程")

    def _step_population_alignment(state: Any, log: List[str]) -> None:
        occ_total = 0
        for p in getattr(state, "prefectures", {}).values():
            guan = ((p.get("pops") or {}).get("官僚")
                    if isinstance(p.get("pops"), dict) else None)
            if isinstance(guan, dict):
                occ_total += int(guan.get("runner_count", 0) or 0)
        pop_total = sum(pop["size"] for p in getattr(state, "prefectures", {}).values()
                         for pop in p["pops"].values()) + getattr(state, "refugee_count", 0) + occ_total
        state.population = max(10_000_000, pop_total)

    def _step_inspection_tick(state: Any, log: List[str]) -> None:
        from core.inspection import inspection_tick
        inspection_tick(state, log)

    def _step_farm_slices_sync(state: Any, log: List[str]) -> None:
        from core.foundation.ledger.pop_structure import check_farm_invariants, sync_all_farm_slices
        audit = getattr(state, "settlement_audit", None)
        if not isinstance(audit, dict):
            audit = {}
            state.settlement_audit = audit
        fixed = sync_all_farm_slices(state)
        if fixed:
            audit["farm_slice_fixes"] = fixed
        bad = check_farm_invariants(state)
        if bad:
            audit["farm_slice_violations"] = bad[:5]

    def _step_emperor_wrapper(state: Any, log: List[str]) -> None:
        if IMPERIAL_ACTION_ENABLED:
            _settle_emperor_personal(state, log)

    def _step_spontaneous_reclamation(state: Any, log: List[str]) -> None:
        from core.domains.economy.land_reclamation import reclaim_land_civilian_spontaneous
        from core.domains.economy.macro_climate import ALL_CIRCUITS_21
        tot = 0.0
        g_price = float(getattr(state, "grain_price", 1.0) or 1.0)
        for r in ALL_CIRCUITS_21:
            p = (getattr(state, "prefectures", {}) or {}).get(r, {})
            grip = float(p.get("clerks_detail", {}).get("grip", 0.45) if isinstance(p.get("clerks_detail"), dict) else (p.get("grip", 0.45) or 0.45))
            res = reclaim_land_civilian_spontaneous(state, r, clerk_grip=grip, grain_price=g_price)
            tot += res.get("reclaimed_total", 0.0)
        if tot > 0:
            log.append(f"[垦荒] 本月民间自发辟荒开垦 {tot:,.1f} 亩（民田与庄园隐田并进）")

    steps = [
        # Phase 1: 诏令与前置政治
        SettlementStep("decrees", "control", "诏令执行", _settle_decrees, critical=True),
        SettlementStep("factions", "politics", "派系态度冲击", _settle_factions, critical=False),

        # Phase 2: 实体生产与地力内生
        SettlementStep("economy", "production", "经济基础", _settle_economy, critical=True),
        SettlementStep("land_local", "production", "田亩地方", _settle_land_local, critical=False),
        SettlementStep("land_reclamation", "production", "民间自发辟荒", _step_spontaneous_reclamation, critical=False),
        SettlementStep("agri_effects", "production", "农业投资效果", apply_agri_effects, critical=False),
        SettlementStep("region_deepen", "production", "地区模型深化", _settle_region_deepen, critical=False),
        SettlementStep("literacy", "culture", "识字率演化", _settle_literacy, critical=False),
        SettlementStep("longterm", "decree", "长期拟旨推进", _settle_longterm_decrees, critical=False),
        SettlementStep("external", "diplomacy", "外部政权模拟", _simulate_external, critical=False),

        # Phase 3: 物料加工、产业链与空间物流
        SettlementStep("production_chain", "industry", "原料内生产出", settle_production_chain, critical=False),
        SettlementStep("procure_from_farmers", "trade", "官府和买", procure_from_farmers, critical=False),
        SettlementStep("sell_surplus_to_merchants", "trade", "民间余料售出", sell_surplus_to_merchants, critical=False),
        SettlementStep("industry_chains", "industry", "四大实体产业链", settle_industry_chains, critical=False),
        SettlementStep("supply_goods_to_seats", "logistics", "建材入货栈配货", supply_goods_to_seats, critical=False),
        SettlementStep("arrive_due", "logistics", "建材在途到货", arrive_due, critical=False),
        SettlementStep("spatial_logistics", "logistics", "沈括途耗与客运时空", _step_spatial_in_transit, critical=False),
        SettlementStep("procure_materials", "trade", "商人补货下单", procure_materials, critical=False),

        # Phase 4: 工程、营造与维持费
        SettlementStep("projects", "construction", "国家工程营建", _settle_projects, critical=True),
        SettlementStep("workshops", "industry", "作坊配方生产", _settle_workshops, critical=False),
        SettlementStep("civil_construction", "construction", "民间自发营造", apply_civil_construction, critical=False),
        SettlementStep("upkeep", "finance", "资产维持费", _settle_upkeep, critical=True),

        # Phase 5: 生计消费与官吏制度
        SettlementStep("granary", "granary", "仓廪漕运与粮市", _settle_granary, critical=True),
        SettlementStep("pop_livelihood", "pop", "POP微观家计与民怨", settle_pop_livelihood, critical=False),
        SettlementStep("officialdom", "administration", "官制与有阙授职", _settle_officialdom, critical=True),
        SettlementStep("clan", "administration", "宗室俸禄", _settle_clan, critical=True),
        SettlementStep("clerks", "administration", "吏制吏额与把持度", _settle_clerks, critical=True),

        # Phase 6: 宏观财政再分配与信用
        SettlementStep("finance", "finance", "财政收支与政府采购", _settle_finance, critical=True),
        SettlementStep("external_economy", "economy", "辽夏省域经济", _settle_external_economy, critical=False),
        SettlementStep("extensions", "credit", "货币信用与交子", _settle_extensions, critical=False),
        SettlementStep("econ_prices", "market", "路线物价指数", _settle_econ_prices, critical=False),
        SettlementStep("treasury", "finance", "国库封桩", _settle_treasury, critical=True),

        # Phase 7: 政治上层建筑派生与军事天下
        SettlementStep("faction_metrics", "politics", "利益集团满意度派生", _settle_faction_metrics, critical=True),
        SettlementStep("military", "military", "军事外交", _settle_military_diplomacy, critical=False),
        SettlementStep("timeline", "history", "历史改写位评估", _evaluate_timeline_breaks, critical=False),
        SettlementStep("mechanisms", "legacy", "机制槽修正", _settle_mechanisms, critical=False),
        SettlementStep("tech", "tech", "科技研发管线", _settle_tech, critical=False),
        SettlementStep("org_economy", "institution", "机构经济生命周期", _settle_org_economy, critical=False),
        SettlementStep("legacies", "legacy", "帝国修正", _settle_legacies, critical=False),
        SettlementStep("focus", "focus", "国策树度支与效果", _settle_focus, critical=False),
        SettlementStep("events", "event", "史官事件压力", _settle_events, critical=False),
        SettlementStep("disaster", "disaster", "灾荒与开仓赈济", _settle_disaster, critical=False),
        SettlementStep("situations", "situation", "局势系统DSL", _settle_situations, critical=False),

        # Phase 8: 皇帝行动与隐藏状态
        SettlementStep("emperor", "imperial", "皇帝个人行动", _step_emperor_wrapper, critical=False, raw_func=_settle_emperor_personal),
        SettlementStep("hidden", "hidden", "隐藏状态激变", _settle_hidden, critical=False),

        # Phase 9: 会计不变量硬收敛对账
        SettlementStep("population_align", "audit", "在籍人口总账校正", _step_population_alignment, critical=True),
        SettlementStep("inspection_tick", "administration", "差遣在途状态迁移", _step_inspection_tick, critical=False),
        SettlementStep("farm_slices_sync", "audit", "农丁口职位子池对齐", _step_farm_slices_sync, critical=False),
        SettlementStep("bank_stock", "finance", "抵当所存款硬收敛", _settle_bank_stock, critical=True),
    ]
    return steps


_DEFAULT_PIPELINE: Optional[SettlementPipeline] = None


def get_default_pipeline() -> SettlementPipeline:
    """获取单例结算流水线调度器。"""
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None:
        _DEFAULT_PIPELINE = SettlementPipeline(build_default_steps())
    return _DEFAULT_PIPELINE


def get_pipeline_step_pairs() -> List[Tuple[str, Callable]]:
    """导出 (step_id, step_func) 权威对账对，供测试镜像直接引用。"""
    pipeline = get_default_pipeline()
    return [(step.id, step.execute) for step in pipeline.steps]
