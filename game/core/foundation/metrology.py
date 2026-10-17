# -*- coding: utf-8 -*-
"""大宋度量衡标准引擎（MetrologyEngine）与现代公制双轨接口。

## 规格与设计理念

在古代，度量衡从来不是纯粹的物理单位，而是**统治秩序、赋税盘剥、阶层博弈与商业贸易的基石**；
而在近代工业化中，公制度量衡（米、千克、升）则是**大规模流水线制造、零件互换与全国统一大市场的根本前提**。

定位：
1. **宋制为骨肉与默认体验**：
   - 容积（量）：1石(原粮) = 10斗 = 100升（宋官量 1升 ≈ 0.664 L，1石原粮约 59.2 kg）；
   - 重量（衡）：1石(重) = 120斤 = 1920两（1斤 = 16两，1斤 ≈ 640 g）；
   - 长度（度）：1丈 = 10尺 = 100寸（营造尺 1尺 ≈ 31.2 cm；省尺 1尺 ≈ 27.5 cm）；
   - 地积（亩）：1顷 = 100亩，1亩 = 240平方步（一步 = 5尺，1亩 ≈ 580~600 m²）。
2. **现代公制双向无缝转换接口**：
   - 预留 `to_metric` 与 `from_metric` 转换器，为玩家界面与现代公制模式提供接口；
   - 绝不写死静态单一换算，支持传入动态校准率（如官秤与大秤的加耗差额）。
3. **改度量衡的体制博弈（机制加成与社会阻力）**：
   - **生产标准化加成**：实行公制后，机械制造与工业作坊享受零部件互换（Interchangeability）加成（+25%~40%）；
   - **清丈防漏田**：公制平方标准使豪强无法利用大折小偷隐漏田，赋税实征率提升；
   - **吏胥利益反弹**：取消大斗收平斗放，砸碎仓吏“雀鼠耗与踢斛”特权，短期激化吏胥抗拒（grip上升，执行率受损）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

__all__ = [
    "MetrologyEngine",
    "SYSTEM_SONG_TRADITIONAL",
    "SYSTEM_SONG_UNIFIED",
    "SYSTEM_MODERN_METRIC",
    "METROLOGY_SYSTEMS",
    "active_effects",
]

# 度量衡体系枚举
SYSTEM_SONG_TRADITIONAL = "song_traditional"  # 传统宋制（官私混用、大斗大秤加耗）
SYSTEM_SONG_UNIFIED = "song_unified"          # 绍述统一度量衡（官定律令、营造尺官斗）
SYSTEM_MODERN_METRIC = "modern_metric"        # 现代科学公制（米、千克、升、公顷）
METROLOGY_SYSTEMS = (SYSTEM_SONG_TRADITIONAL, SYSTEM_SONG_UNIFIED, SYSTEM_MODERN_METRIC)

# 基础换算参数配置字典（可动态配置与加载，杜绝代码内部写死死数）
DEFAULT_CONVERSION_SPECS: Dict[str, Dict[str, float]] = {
    # 1. 容积（Volume: 基准单位 升 -> 升(Liters)）
    "volume": {
        "sheng_to_liter": 0.664,       # 宋制 1升 ≈ 0.664 升(L)
        "dou_to_sheng": 10.0,          # 1斗 = 10升
        "shi_to_sheng": 100.0,         # 1石 = 10斗 = 100升 (约 66.4 L)
    },
    # 2. 重量（Weight: 基准单位 斤 -> 千克(kg)）
    "weight": {
        "jin_to_kg": 0.640,            # 宋制 1斤 ≈ 0.640 kg
        "liang_per_jin": 16.0,         # 1斤 = 16两 (1两 = 40 g)
        "shi_weight_to_jin": 120.0,    # 1石重 = 120斤 (约 76.8 kg)
    },
    # 3. 长度（Length: 基准单位 尺 -> 米(m)）
    "length": {
        "chi_to_meter": 0.312,         # 营造尺 1尺 ≈ 0.312 米
        "cun_per_chi": 10.0,           # 1尺 = 10寸
        "zhang_to_chi": 10.0,          # 1丈 = 10尺 (约 3.12 m)
        "bu_to_chi": 5.0,              # 1步 = 5尺 (约 1.56 m)
    },
    # 4. 地积（Area: 基准单位 亩 -> 平方米(m²)）
    "area": {
        "mu_to_sqm": 584.0,            # 1亩 = 240平方步 ≈ 584 平方米 (约合 0.876 现代市亩)
        "qing_to_mu": 100.0,           # 1顷 = 100亩
        "hectare_to_sqm": 10000.0,     # 1公顷 = 10000 平方米
    },
}


class MetrologyEngine:
    """大宋度量衡标准转换与体制计算引擎。"""

    def __init__(self, custom_specs: Optional[Dict[str, Dict[str, float]]] = None):
        """初始化引擎，支持注入自定义/动态校准比。"""
        self.specs: Dict[str, Dict[str, float]] = custom_specs or DEFAULT_CONVERSION_SPECS

    # =========================================================================
    # 1. 双向转换核心接口 (Metric Conversions)
    # =========================================================================

    def to_metric(self, value: float, dimension: str, from_unit: str) -> Dict[str, Any]:
        """将宋制单位转为现代国际公制。
        
        dimension: "volume" (容积) / "weight" (重量) / "length" (长度) / "area" (地积)
        from_unit: 
            - volume: "shi" (石), "dou" (斗), "sheng" (升)
            - weight: "shi_weight" (石重), "jin" (斤), "liang" (两)
            - length: "zhang" (丈), "chi" (尺), "cun" (寸)
            - area: "qing" (顷), "mu" (亩)
        """
        val = float(value)
        dim = str(dimension).lower()
        unit = str(from_unit).lower()

        if dim == "volume":
            # 基准为升
            v_specs = self.specs["volume"]
            sheng = val
            if unit == "shi":
                sheng = val * v_specs["shi_to_sheng"]
            elif unit == "dou":
                sheng = val * v_specs["dou_to_sheng"]
            liters = sheng * v_specs["sheng_to_liter"]
            cubic_meters = liters / 1000.0
            return {
                "dimension": "volume",
                "liters": round(liters, 2),
                "cubic_meters": round(cubic_meters, 4),
                "standard_display": f"{round(liters, 2)} L ({round(cubic_meters, 4)} m³)",
            }

        elif dim == "weight":
            # 基准为斤
            w_specs = self.specs["weight"]
            jin = val
            if unit == "shi_weight" or unit == "shi":
                jin = val * w_specs["shi_weight_to_jin"]
            elif unit == "liang":
                jin = val / w_specs["liang_per_jin"]
            kg = jin * w_specs["jin_to_kg"]
            tons = kg / 1000.0
            return {
                "dimension": "weight",
                "kg": round(kg, 2),
                "metric_tons": round(tons, 4),
                "standard_display": f"{round(tons, 3)} 吨 ({round(kg, 1)} kg)",
            }

        elif dim == "length":
            # 基准为尺
            l_specs = self.specs["length"]
            chi = val
            if unit == "zhang":
                chi = val * l_specs["zhang_to_chi"]
            elif unit == "cun":
                chi = val / l_specs["cun_per_chi"]
            meters = chi * l_specs["chi_to_meter"]
            km = meters / 1000.0
            return {
                "dimension": "length",
                "meters": round(meters, 3),
                "km": round(km, 4),
                "standard_display": f"{round(meters, 2)} 米",
            }

        elif dim == "area":
            # 基准为亩
            a_specs = self.specs["area"]
            mu = val
            if unit == "qing":
                mu = val * a_specs["qing_to_mu"]
            sqm = mu * a_specs["mu_to_sqm"]
            hectares = sqm / a_specs["hectare_to_sqm"]
            return {
                "dimension": "area",
                "sq_meters": round(sqm, 2),
                "hectares": round(hectares, 4),
                "standard_display": f"{round(hectares, 3)} 公顷 ({round(sqm, 1)} m²)",
            }

        return {"dimension": dim, "error": f"未知的度量衡维度或单位: {dim}/{unit}"}

    def from_metric(self, value: float, dimension: str, to_unit: str) -> float:
        """从现代公制反向换算为宋制单位数量。"""
        val = float(value)
        dim = str(dimension).lower()
        unit = str(to_unit).lower()

        if dim == "volume":
            # value 为升(Liters)
            v_specs = self.specs["volume"]
            sheng = val / v_specs["sheng_to_liter"]
            if unit == "shi":
                return round(sheng / v_specs["shi_to_sheng"], 2)
            elif unit == "dou":
                return round(sheng / v_specs["dou_to_sheng"], 2)
            return round(sheng, 2)

        elif dim == "weight":
            # value 为千克(kg)
            w_specs = self.specs["weight"]
            jin = val / w_specs["jin_to_kg"]
            if unit == "shi" or unit == "shi_weight":
                return round(jin / w_specs["shi_weight_to_jin"], 2)
            elif unit == "liang":
                return round(jin * w_specs["liang_per_jin"], 2)
            return round(jin, 2)

        elif dim == "length":
            # value 为米(m)
            l_specs = self.specs["length"]
            chi = val / l_specs["chi_to_meter"]
            if unit == "zhang":
                return round(chi / l_specs["zhang_to_chi"], 2)
            elif unit == "cun":
                return round(chi * l_specs["cun_per_chi"], 2)
            return round(chi, 2)

        elif dim == "area":
            # value 为平方米(m²)
            a_specs = self.specs["area"]
            mu = val / a_specs["mu_to_sqm"]
            if unit == "qing":
                return round(mu / a_specs["qing_to_mu"], 2)
            return round(mu, 2)

        return 0.0

    # =========================================================================
    # 2. 体制机制与变法效益计算 (Reforms & Mechanics)
    # =========================================================================

    @classmethod
    def get_system_effects(cls, system_key: str = SYSTEM_SONG_TRADITIONAL) -> Dict[str, Any]:
        """获取不同度量衡体系对大宋世界的深层经济与政治加成/代价。"""
        if system_key == SYSTEM_MODERN_METRIC:
            return {
                "name": "现代公制万国体系",
                "standardization_level": 1.0,
                # 正向收益
                "manufacturing_mult": 1.30,       # 机械制造与工业流水线效率 +30% (零部件标准化互换)
                "logistics_loss_reduction": 0.25, # 跨路商品物流损耗减少 25% (杜绝大斗私耗)
                "tax_leakage_resistance": 0.15,   # 田亩与矿产偷漏税抗性 +15% (方田清丈标准统一)
                # 政治阻力与成本
                "clerk_grip_resistance": 0.12,    # 砸碎仓吏踢斛雀鼠耗特权，吏胥抗拒度上升
                "gentry_unrest_spike": 6.0,       # 触动地方宗族私斗私秤利益，短期民怨小幅激化
                "reform_cost": 300000,            # 铸造颁行标准铜量器官尺经费 (贯)
                "desc": "万国标准归一，百工器械皆有尺寸，大工业与机械化之无上阶梯。",
            }
        elif system_key == SYSTEM_SONG_UNIFIED:
            return {
                "name": "绍述统一度量衡",
                "standardization_level": 0.5,
                "manufacturing_mult": 1.10,
                "logistics_loss_reduction": 0.10,
                "tax_leakage_resistance": 0.06,
                "clerk_grip_resistance": 0.05,
                "gentry_unrest_spike": 2.0,
                "reform_cost": 100000,
                "desc": "颁行朝廷营造尺与铜斗，严惩私铸秤尺，整饬法度。",
            }
        else:
            return {
                "name": "北宋传统多轨度量衡",
                "standardization_level": 0.0,
                "manufacturing_mult": 1.0,
                "logistics_loss_reduction": 0.0,
                "tax_leakage_resistance": 0.0,
                "clerk_grip_resistance": 0.0,
                "gentry_unrest_spike": 0.0,
                "reform_cost": 0,
                "desc": "官市混用，大斗收而平斗放，州府异制，吏胥优裕而工械难精。",
            }

    @classmethod
    def format_quantity(
        cls,
        amount: float,
        dimension: str,
        system_key: str = SYSTEM_SONG_TRADITIONAL,
        engine: Optional[MetrologyEngine] = None
    ) -> str:
        """根据当前生效的度量衡体制，友好格式化输出数量文本。"""
        eng = engine or MetrologyEngine()
        val = float(amount)
        dim = str(dimension).lower()

        if system_key == SYSTEM_MODERN_METRIC:
            # 格式化为公制
            if dim == "grain" or dim == "volume":
                # 原粮石 -> 吨
                res = eng.to_metric(val, "weight", "shi_weight")
                return f"{res['metric_tons']} 吨 ({int(val):,} 石)"
            elif dim == "weight" or dim == "iron" or dim == "copper":
                # 斤 -> 千克/吨
                res = eng.to_metric(val, "weight", "jin")
                if res["metric_tons"] >= 1.0:
                    return f"{res['metric_tons']} 吨"
                return f"{res['kg']} kg"
            elif dim == "area" or dim == "land":
                # 亩 -> 公顷
                res = eng.to_metric(val, "area", "mu")
                return f"{res['hectares']} 公顷 ({int(val):,} 亩)"
            elif dim == "length":
                res = eng.to_metric(val, "length", "chi")
                return res["standard_display"]

        # 默认返回纯宋制格式
        if dim == "grain" or dim == "volume":
            return f"{int(val):,} 石"
        elif dim == "area" or dim == "land":
            return f"{int(val):,} 亩"
        elif dim in ("iron", "copper", "weight"):
            return f"{int(val):,} 斤"
        return f"{int(val):,}"

    @classmethod
    def get_active_system(cls, state: Any = None) -> str:
        """从 GameState 中获取当前生效的度量衡体系（缺省/非法/异常回退传统宋制）。

        P1（2026-10-17）：只接受枚举值 0/1/2；1.5、NaN、越界等**非法值**
        一律按传统 0 处理，不按阈值猜成“半统一/现代”。
        """
        if state is None:
            return SYSTEM_SONG_TRADITIONAL
        try:
            from core.domains.administration import institution
            sys_id = float(institution.get(state, "metrology_system_id", 0.0))
            if abs(sys_id - 2.0) < 1e-9:
                return SYSTEM_MODERN_METRIC
            if abs(sys_id - 1.0) < 1e-9:
                return SYSTEM_SONG_UNIFIED
            return SYSTEM_SONG_TRADITIONAL
        except Exception:
            return SYSTEM_SONG_TRADITIONAL

    @classmethod
    def active_effects(cls, state: Any = None) -> Dict[str, Any]:
        """当前体制的只读效果字典（缺省/非法=传统；绝不写 state）。"""
        return cls.get_system_effects(cls.get_active_system(state))

    @classmethod
    def apply_reform(cls, state: Any, target_system: str) -> Tuple[bool, str, Dict[str, Any]]:
        """推行度量衡变法：核销国库改制经费、激化吏胥抗拒、变更编制参数。"""
        if target_system not in METROLOGY_SYSTEMS:
            return False, f"未知的目标度量衡体系「{target_system}」", {}

        effects = cls.get_system_effects(target_system)
        cost = int(effects.get("reform_cost", 0))

        # 检查国库资金
        cur_treasury = getattr(state, "treasury", 0)
        if cur_treasury < cost:
            return False, f"国库帑银不足以颁行新度量衡（需 {cost:,} 贯，存 {cur_treasury:,} 贯）", {}

        # 扣减国库
        if cost > 0:
            state.treasury = cur_treasury - cost

        # 变更体制参数
        target_id = 0.0
        if target_system == SYSTEM_SONG_UNIFIED:
            target_id = 1.0
        elif target_system == SYSTEM_MODERN_METRIC:
            target_id = 2.0

        from core.domains.administration import institution
        institution.set_param(state, "metrology_system_id", target_id)

        # 调整吏胥把持度反弹
        grip_spike = effects.get("clerk_grip_resistance", 0.0)
        cur_grip = getattr(state, "clerk_grip", 0.3)
        state.clerk_grip = min(1.0, max(0.0, cur_grip + grip_spike))

        # 变法当次一次性触动地方宗族利益 → 全国民心/民怨读数下降（短期）
        gentry_spike = float(effects.get("gentry_unrest_spike", 0.0) or 0.0)
        if gentry_spike > 0:
            _sat = float(getattr(state, "population_satisfaction", 0) or 0)
            state.population_satisfaction = max(0.0, min(100.0, _sat - gentry_spike))

        msg = f"成功颁行「{effects['name']}」：铸衡经费 {cost:,} 贯已支应，生产效率倍率 ×{effects['manufacturing_mult']}。"
        return True, msg, effects


def active_effects(state: Any = None) -> Dict[str, Any]:
    """模块级只读入口：当前度量衡体制的 effects（默认/非法=传统 0）。"""
    return MetrologyEngine.active_effects(state)
