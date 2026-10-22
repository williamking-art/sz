# -*- coding: utf-8 -*-
"""大宋天道裁决核心引擎（TianDao Engine）。

定位与设计哲学：
- “天道定因果骨肉，大模型着春秋笔墨”；
- 游戏本体内置，完全脱机、零网络依赖、零 Token 消耗、完全确定性回放；
- 提供四大标准裁决接口：
    1. gate (天命是非：二元断决，顺逆行止)
    2. choose (造化殊途：多元博弈，Softmax 归一化)
    3. score (气数品位：运势品阶，上中下考课)
    4. dice (天意机变：确定性伪随机扰动，完全可复盘)

契约纪律（逐条对齐 `game/core/ai/README.md` 与根 `AGENTS.md` §3）：
1. **缺失 ≠ 0 ≠ 1.0**：取不到的读数一律走 `default` 并在返回值里显式标注
   （`basis_undefined` / `defined`），**绝不**把缺失当成"良好"或"完美"；
2. **`0` 是合法值**：所有取值一律 `is None` 判缺失，**禁止** `x or default`（会吞掉 0）；
3. **无依据不得放行**：`gate` 在没有任何可读依据时 `verdict=False`、
   `probability=None`、`basis_undefined=True`（旧实现缺依据会撞阈值判 True）；
4. **签名向下兼容**：首参既可用位置参数，也可用旧关键字 `state_context=`；
5. **纯函数**：本引擎只出决断与概率，**不写 state**、不碰账本、不抛异常（除入参类型错）。

dispatch 口径（2026-10-17 修复）：旧实现只靠 `condition` 中文子串 / `criteria` 英文键名
隐式分派 ⇒ 改一句文案或改一个 option id 就会**静默改判定**。现改为**显式 `objective`
优先**（facade 全部显式传），子串/键名仅作未给 objective 时的向后兼容回退。

参数外置（2026-10-21 L1-a）：`gate` / `choose` / `score` 原先内联了 132 个数值常数，
现已全部收拢到 `content/data_tiandao.py` 的 `TianDaoParams` / `PARAMS`（唯一入口）。
本文件**不再持有玩法数值**；改标尺一律改参数表并在那里写清口径。
导入方式是**模块级硬导入**——参数表坏了就该在 import 时炸出来，禁止 try/except 静默降级
（否则"参数没生效"会静默变成行为漂移）。

本批（L1-a）同时修掉 4 个缺陷（其余行为保持不变）：
* **B1 `score` 运算符优先级**：旧写作
  `severity = (0.0 if disaster is None else … + (0.0 if unrest is None else …)) / 2.0`，
  `disaster is None` 时整个 `else` 分支不执行 ⇒ **unrest 被整项丢弃**（实测
  `score({"unrest":160})` 仍评上考 1.0）。另 `tax_completion` 缺省曾是 `1.0`
  （"缺失=赋税完美"）。现：可用项各自取值后平均，两项都缺 ⇒ `defined=False`；
  `tax_completion` 缺失 ⇒ 考课分支 `defined=False`（缺失不得当满分）。
* **B2 `granary_corruption` 无依据不得判贪墨**：旧实现 `integrity is None` 时按 `0.5` 兜底
  ⇒ `0.20+0.60*0.5 = 0.50` 恰好 `>=` 阈值 ⇒ **缺失即判贪墨**。现缺失即
  `defined=False, probability=None, verdict=False`（`has_inspector` / `supervision` 压制项保留）。
* **B3 `labor_policy` 量纲错 3 个数量级**：旧 `treasury >= 5000 ⇒ hired`，而真实国库
  5,000,000 贯、地方府库 270,000~1,950,000 贯 ⇒ `corvee` 分支实际不存在。现按
  "府库能撑几个月"（月支出读数）或地方府库量级绝对线判定。
* **B4 未知 `objective` fail-closed**：旧实现静默掉进 generic/无分支 ⇒ `defined=True`。
  现显式给出但不在本 mode 的 `OBJECTIVES` 里 ⇒ `defined=False`（未给 objective 的
  旧式按文案/键名推断出的分支**保留**，`clerk_decision` / `merchant_decision` 依赖它）。
* **B5 `changping_open` 库存口径**：`stock is None` **不得当 0**（走价格公式）；
  只有 `stock == 0`（真空仓）才置否。门面换源（`changping_stock`）由另一条线负责。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from content.data_tiandao import PARAMS

__all__ = ["TianDaoEngine", "OBJECTIVES"]

# =============================================================================
# 显式裁决目标（objective）——把"文案 → 分支"的隐式耦合改成一张可审计的表
# =============================================================================
# gate 类目标
GATE_OBJECTIVES = (
    "waive_arrears",        # 恩泽蠲免陈年逋欠
    "changping_open",       # 常平仓平粜开仓
    "granary_corruption",   # 仓吏雀鼠耗贪墨
    "recruit_refugees",     # 招募饥民为厢军
    "reform_compliance",    # 知州切实贯彻新政
    "generic",              # 通用是非（无专项特征）
)
# choose 类目标
CHOOSE_OBJECTIVES = (
    "tax_stance",           # 征管宽严 strict/moderate/lenient
    "labor_policy",         # 劳役 corvee/hired
    "merchant_trade",       # 商贾 ship/hoard/local_sell
    "decree_compliance",    # 路级遵从 vigorous/compliant/passive/defiant
    "farmer_path",          # 破产小农 mortgage_land/flee_refugee
    "gentry_path",          # 士绅 charity_relief/usury_annex
    "canal_reroute",        # 漕运 wait_dredge/overland_cart/borrow_grain
)
OBJECTIVES = {"gate": GATE_OBJECTIVES, "choose": CHOOSE_OBJECTIVES}

_MASK64 = (1 << 64) - 1
_MASK53 = (1 << 53) - 1


class TianDaoEngine:
    """大宋天道裁决体系核心引擎（纯函数、确定性、零外部依赖）。"""

    # 引擎标识（2026-10-17 由 `embedded_local` 重命名；全库无生产消费方，Jev p=0.994）
    PROVIDER_ID = "tiandao_local"

    # =========================================================================
    # 入参归一与取数（缺失≠0、0 是合法值）
    # =========================================================================
    @staticmethod
    def _bind_context(context: Any, kwargs: Dict[str, Any]) -> Any:
        """向下兼容：接受旧关键字 `state_context=`（薄桩只换类名不换签名会打爆调用方）。"""
        if context is None and "state_context" in kwargs:
            context = kwargs.pop("state_context")
        if kwargs:
            raise TypeError(
                "未知关键字参数：%s（可用 context / state_context）" % "、".join(sorted(kwargs))
            )
        return context

    @staticmethod
    def _get_num(ctx: Any, keys: Sequence[str], default: Optional[float]) -> Optional[float]:
        """按序取第一个**存在且非 None** 的数值读数。

        · `0` / `0.0` 是**合法值**，原样返回（禁止 `or default` 吞 0）；
        · 全部缺失或非数值 ⇒ `default`；`default=None` 表示"缺失"由调用方处理。
        """
        if not isinstance(ctx, dict):
            return default
        for k in keys:
            if k not in ctx:
                continue
            v = ctx.get(k)
            if v is None:
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                return f
        return default

    @classmethod
    def _gov(cls, ctx: Any) -> Dict[str, Any]:
        if not isinstance(ctx, dict):
            return {}
        for key in ("gov", "governor"):
            v = ctx.get(key)
            if isinstance(v, dict):
                return v
        return {}

    @classmethod
    def _official_integrity(cls, ctx: Any) -> Optional[float]:
        """官员清廉度（0~1）。**缺失即 None**（旧实现 `or 0.6` 会把 0.0 吞成 0.6）。"""
        v = cls._get_num(cls._gov(ctx), ("integrity",), None)
        if v is None:
            v = cls._get_num(ctx, ("integrity",), None)
        return None if v is None else max(0.0, min(PARAMS.UNIT_SCALE, v))

    @classmethod
    def _official_diligence(cls, ctx: Any) -> Optional[float]:
        v = cls._get_num(cls._gov(ctx), ("diligence",), None)
        if v is None:
            v = cls._get_num(ctx, ("diligence",), None)
        return None if v is None else max(0.0, min(PARAMS.UNIT_SCALE, v))

    # =========================================================================
    # Softmax（严格归一：舍入残差回填最大项）
    # =========================================================================
    @classmethod
    def _softmax(cls, scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
        """将分值字典转为概率分布字典（4 位小数，**和严格归一为 1.0**）。"""
        if not scores:
            return {}
        t = max(PARAMS.SOFTMAX_MIN_TEMPERATURE, float(temperature))
        max_s = max(scores.values())
        exp_vals = {k: math.exp((s - max_s) / t) for k, s in scores.items()}
        sum_exp = sum(exp_vals.values())
        if not math.isfinite(sum_exp) or sum_exp <= 0:
            even = round(PARAMS.SOFTMAX_EVEN_NUMERATOR / len(scores), PARAMS.PROB_ROUND_DIGITS)
            probs = {k: even for k in scores}
        else:
            probs = {k: round(v / sum_exp, PARAMS.PROB_ROUND_DIGITS)
                     for k, v in exp_vals.items()}
        # 舍入残差回填最大项（否则 4 选项实测和＝0.9999，"概率归一"是假的）
        diff = round(PARAMS.UNIT_SCALE - sum(probs.values()), PARAMS.PROB_ROUND_DIGITS)
        if diff:
            top = max(probs, key=probs.get)
            probs[top] = round(probs[top] + diff, PARAMS.PROB_ROUND_DIGITS)
        return probs

    # =========================================================================
    # 天意机变：确定性微扰（splitmix64；旧 LCG 单轮实测相邻种子差恒定）
    # =========================================================================
    @classmethod
    def dice(cls, seed: int, entropy: float = 0.05) -> float:
        """天意机变：由显式种子驱动的确定性微扰，返回 [-entropy, +entropy]。

        保证相同种子下结果 100% 确定（纯整数运算，跨进程/跨平台一致），
        不破坏时间线回放。**注意**：种子须由调用方提供（回合号 / 存档内种子），
        本引擎不自行取随机源。
        """
        ent = max(0.0, float(entropy))
        if ent <= 0.0:
            return 0.0
        h = (int(seed) & _MASK64) ^ 0x9E3779B97F4A7C15
        h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        h = ((h ^ (h >> 27)) * 0x94D049BB133111EB) & _MASK64
        h ^= h >> 31
        ratio = (h & _MASK53) / float(_MASK53)
        return round((ratio * 2.0 - 1.0) * ent, 5)

    # =========================================================================
    # 天命是非：gate
    # =========================================================================
    @classmethod
    def gate(
        cls,
        context: Union[str, Dict[str, Any], None] = None,
        condition: str = "",
        threshold: float = 0.50,   # 契约颈线：默认值须 = PARAMS.GENERIC_THRESHOLD（签名不改）
        objective: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """天命是非：二元闸门是非决断。

        返回::

            {"verdict": bool, "probability": float|None, "provider": "tiandao_local",
             "basis_undefined": bool, "objective": str, "defined": bool}

        **无依据 ⇒ 不放行**：`context` 不是 dict、或 dict 里没有任何可用读数时，
        `verdict=False`、`probability=None`、`basis_undefined=True`。
        `basis_undefined=True` 也涵盖"**该 objective 所需的关键读数缺失**"的情形
        （例：贪墨闸门缺清廉度，见 B2）。
        """
        context = cls._bind_context(context, kwargs)
        basis_undefined = True
        prob: Optional[float] = None
        obj = str(objective or "")
        explicit_objective = objective is not None

        # B4：显式给出的 objective 必须在本 mode 的白名单内，否则 fail-closed。
        # （旧实现会静默掉进 generic / 无分支 ⇒ defined=True，等于"未知目标当通用闸门"）
        if explicit_objective and obj not in GATE_OBJECTIVES:
            return {
                "verdict": False,
                "probability": None,
                "provider": cls.PROVIDER_ID,
                "basis_undefined": True,
                "objective": obj,
                "defined": False,
            }

        if isinstance(context, dict):
            disaster = cls._get_num(context, ("disaster", "disaster_level"), None)
            prestige_raw = cls._get_num(context, ("prestige", "stability"), None)
            stock = cls._get_num(context, ("stock", "storage"), None)
            price_ratio = cls._get_num(context, ("price_ratio",), None)
            unrest = cls._get_num(context, ("unrest",), None)
            refugees = cls._get_num(context, ("refugees",), None)
            integrity = cls._official_integrity(context)
            diligence = cls._official_diligence(context)
            faction = str(context.get("faction") or "")

            # 依据判定：至少有一个可用读数才算"有依据"
            basis_undefined = not any(
                v is not None
                for v in (disaster, prestige_raw, stock, price_ratio, unrest,
                          refugees, integrity, diligence)
            )

            if objective is None:
                obj = cls._gate_objective_from_text(str(condition or ""))

            if not basis_undefined:
                u = (0.0 if unrest is None
                     else max(0.0, min(PARAMS.UNREST_SCALE, unrest)) / PARAMS.UNREST_SCALE)
                dis = (0.0 if disaster is None
                       else max(0.0, min(PARAMS.UNIT_SCALE, disaster)))
                pres = (PARAMS.PRESTIGE_NEUTRAL if prestige_raw is None
                        else max(0.0, min(PARAMS.PRESTIGE_SCALE, prestige_raw)))
                integ = integrity
                dil = diligence
                ratio = (PARAMS.CHANGPING_PRICE_NEUTRAL if price_ratio is None
                         else price_ratio)

                if obj == "waive_arrears":
                    # 灾重、民怨高、官清廉 ⇒ 倾向蠲免（缺项按"无该项贡献"计，不冒充良好）
                    prob = (PARAMS.WAIVE_BASE
                            + dis * PARAMS.WAIVE_DISASTER_W
                            + u * PARAMS.WAIVE_UNREST_W
                            + (PARAMS.WAIVE_INTEGRITY_W * integ
                               if integ is not None else 0.0))
                elif obj == "changping_open":
                    # B5：**stock 缺失（None）不得当 0**——走价格公式；只有真空仓才硬否决。
                    # （stock 应由门面传常平仓 `changping_stock`，而不是太仓 `granary`）
                    if stock is not None and stock <= PARAMS.CHANGPING_STOCK_EMPTY:
                        prob = PARAMS.CHANGPING_EMPTY_PROB
                    else:
                        prob = (PARAMS.CHANGPING_BASE
                                + min(PARAMS.CHANGPING_PRICE_TERM_MAX,
                                      max(0.0, ratio - PARAMS.CHANGPING_PRICE_NEUTRAL)
                                      * PARAMS.CHANGPING_PRICE_SLOPE))
                elif obj == "granary_corruption":
                    # 单调：清廉度越低 ⇒ 贪墨概率越高；有御史巡按 ⇒ 显著压制
                    # （旧式 0.45*(1-integ) 上限 0.45 < 阈值 0.5 ⇒ 该闸门**数学上永不通过**）
                    has_inspector = bool(context.get("has_inspector")
                                         or context.get("supervision"))
                    if integ is None:
                        # B2：**无依据不得判贪墨**。旧实现按 0.5 兜底 ⇒
                        # 0.20+0.60*0.5 = 0.50 恰好 >= 阈值 ⇒ 缺失即判贪墨（危险方向）。
                        prob = None
                    else:
                        corr = (PARAMS.CORRUPTION_BASE
                                + PARAMS.CORRUPTION_SLOPE * (PARAMS.UNIT_SCALE - integ))
                        prob = corr * (PARAMS.CORRUPTION_INSPECTOR_MULT
                                       if has_inspector else PARAMS.UNIT_SCALE)
                elif obj == "recruit_refugees":
                    ref = 0.0 if refugees is None else max(0.0, refugees)
                    prob = (PARAMS.REFUGEES_BASE
                            + min(PARAMS.REFUGEES_TERM_MAX,
                                  ref / PARAMS.REFUGEES_FULL_MARK)
                            + u * PARAMS.REFUGEES_UNREST_W)
                elif obj == "reform_compliance":
                    bonus = (PARAMS.REFORM_FACTION_BONUS
                             if faction in ("reform", "新党") else (
                                 PARAMS.REFORM_FACTION_MALUS
                                 if faction in ("conservative", "旧党") else 0.0))
                    prob = (PARAMS.REFORM_BASE
                            + bonus
                            + (PARAMS.REFORM_DILIGENCE_W * dil if dil is not None else 0.0)
                            + PARAMS.REFORM_PRESTIGE_W * (pres / PARAMS.PRESTIGE_SCALE))
                else:
                    prob = (PARAMS.GENERIC_BASE
                            + PARAMS.GENERIC_PRESTIGE_W * (pres / PARAMS.PRESTIGE_SCALE)
                            - PARAMS.GENERIC_UNREST_W * u)

        if prob is None:
            return {
                "verdict": False,
                "probability": None,
                "provider": cls.PROVIDER_ID,
                "basis_undefined": True,
                "objective": obj or "generic",
                "defined": False,
            }

        prob = max(PARAMS.PROB_FLOOR, min(PARAMS.PROB_CAP, prob))
        return {
            "verdict": prob >= float(threshold),
            "probability": round(prob, PARAMS.PROB_ROUND_DIGITS),
            "provider": cls.PROVIDER_ID,
            "basis_undefined": basis_undefined,
            "objective": obj or "generic",
            "defined": True,
        }

    @staticmethod
    def _gate_objective_from_text(condition: str) -> str:
        """向后兼容：未给 objective 时按旧文案子串回退（新代码应显式传 objective）。"""
        cond = str(condition or "")
        if "蠲免" in cond or "豁免" in cond:
            return "waive_arrears"
        if "平粜" in cond or "开仓" in cond:
            return "changping_open"
        if "贪墨" in cond or "雀鼠耗" in cond or "私吞" in cond:
            return "granary_corruption"
        if "招募" in cond or "厢军" in cond or "收容" in cond:
            return "recruit_refugees"
        if "遵从" in cond or "新政" in cond or "变法" in cond:
            return "reform_compliance"
        return "generic"

    # =========================================================================
    # 造化殊途：choose
    # =========================================================================
    @classmethod
    def choose(
        cls,
        context: Union[str, Dict[str, Any], None] = None,
        instructions: str = "",
        criteria: Optional[Dict[str, float]] = None,
        temperature: float = 0.8,   # 契约颈线：默认值须 = PARAMS.CHOOSE_TEMPERATURE（签名不改）
        objective: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """造化殊途：多元博弈与意图抉择（Softmax 概率归一）。

        返回::

            {"verdict": str, "probabilities": dict, "provider": "tiandao_local",
             "objective": str, "defined": bool}
        """
        context = cls._bind_context(context, kwargs)
        scores: Dict[str, float] = {str(o): float(w) for o, w in (criteria or {}).items()}
        if not scores:
            return {"verdict": "", "probabilities": {}, "provider": cls.PROVIDER_ID,
                    "objective": str(objective or ""), "defined": False}

        explicit_objective = objective is not None
        if objective is None:
            objective = cls._choose_objective_from_keys(scores)
        obj = str(objective or "")

        # B4：显式 objective 不在本 mode 白名单 ⇒ fail-closed（不猜一个选项出来）。
        # 未给 objective 时的"按键名推断"路径保持原样（推断不出 ⇒ obj="" ⇒ 只做基础 Softmax）。
        if explicit_objective and obj not in CHOOSE_OBJECTIVES:
            return {"verdict": "", "probabilities": {}, "provider": cls.PROVIDER_ID,
                    "objective": obj, "defined": False}

        if isinstance(context, dict):
            integrity = cls._official_integrity(context)
            diligence = cls._official_diligence(context)
            treasury = cls._get_num(context, ("treasury", "local_treasury"), None)
            disaster = cls._get_num(context, ("disaster",), None)
            unrest = cls._get_num(context, ("unrest", "mood"), None)

            # 1. 征税宽严
            if obj == "tax_stance" and "strict" in scores and "lenient" in scores:
                if integrity is not None:
                    scores["strict"] += (PARAMS.TAX_STRICT_BUMP
                                         if integrity < PARAMS.TAX_STRICT_INTEGRITY_LINE
                                         else PARAMS.TAX_STRICT_MALUS)
                    scores["lenient"] += integrity * PARAMS.TAX_LENIENT_W
                if disaster is not None:
                    scores["lenient"] += (PARAMS.TAX_DISASTER_LENIENT
                                          if disaster > PARAMS.TAX_DISASTER_LINE
                                          else PARAMS.TAX_CALM_LENIENT)
            # 2. 劳役制度（B3）：府库够撑几个月则雇募，否则差役
            elif obj == "labor_policy" and "corvee" in scores and "hired" in scores:
                expense = cls._get_num(context, ("monthly_expense", "last_monthly_expense"),
                                       None)
                money = cls._get_num(context, ("treasury", "local_treasury"), None)
                if (expense is not None and expense > PARAMS.LABOR_MONTHLY_EXPENSE_MIN
                        and money is not None):
                    # 口径：府库 / 月度刚性支出 = 可支撑月数
                    if money / expense >= PARAMS.LABOR_HIRED_MIN_MONTHS:
                        scores["hired"] += PARAMS.LABOR_HIRED_BIAS
                    else:
                        scores["corvee"] += PARAMS.LABOR_CORVEE_BIAS
                elif money is not None:
                    # 无月支出读数 ⇒ 退回**路库量级**绝对线（国库 5,000,000 / 路库 27万~195万）
                    if money >= PARAMS.LABOR_ABSOLUTE_TREASURY:
                        scores["hired"] += PARAMS.LABOR_HIRED_BIAS
                    else:
                        scores["corvee"] += PARAMS.LABOR_CORVEE_BIAS
                # 两个财力键都缺失：不加偏置（**不**把缺失当"没钱"）
            # 3. 商贾经营：价差大走贩运，灾荒走囤积
            elif obj == "merchant_trade" and "ship" in scores and "hoard" in scores:
                gap = cls._get_num(context, ("gap", "price_gap"), None)
                if gap is not None:
                    scores["ship"] += min(PARAMS.MERCHANT_GAP_TERM_MAX,
                                          max(0.0, gap) * PARAMS.MERCHANT_GAP_SLOPE)
                if disaster is not None and disaster > PARAMS.MERCHANT_DISASTER_LINE:
                    scores["hoard"] += PARAMS.MERCHANT_HOARD_BUMP
            # 4. 地方知州遵从度（四类**都可被选中**；旧实现 defiant 无偏置 ⇒ 永不出现）
            elif obj == "decree_compliance" and "vigorous" in scores and "compliant" in scores:
                integ = (integrity if integrity is not None
                         else PARAMS.DECREE_INTEGRITY_NEUTRAL)
                dil = (diligence if diligence is not None
                       else PARAMS.DECREE_DILIGENCE_NEUTRAL)
                scores["vigorous"] += (integ * PARAMS.DECREE_VIGOROUS_INTEG_W
                                       + dil * PARAMS.DECREE_VIGOROUS_DILIG_W)
                scores["compliant"] += PARAMS.DECREE_COMPLIANT_BUMP
                scores["passive"] += (
                    (PARAMS.DECREE_PASSIVE_UNREST_BUMP
                     if (unrest is not None
                         and unrest > PARAMS.DECREE_PASSIVE_UNREST_LINE) else 0.0)
                    + (PARAMS.UNIT_SCALE - integ) * PARAMS.DECREE_PASSIVE_CORRUPT_W)
                scores["defiant"] += (PARAMS.UNIT_SCALE - integ) * PARAMS.DECREE_DEFIANT_CORRUPT_W \
                    + (PARAMS.DECREE_DEFIANT_POOR_TREASURY_BUMP
                       if (treasury is not None
                           and treasury <= PARAMS.DECREE_DEFIANT_POOR_TREASURY_LINE) else 0.0)
            # 5. 破产小农：典田 vs 逃荒（旧实现无分支 ⇒ 恒"典田"）
            elif obj == "farmer_path" and "mortgage_land" in scores and "flee_refugee" in scores:
                debt = cls._get_num(context, ("debt", "arrears"), None)
                if debt is not None:
                    scores["flee_refugee"] += min(
                        PARAMS.FARMER_DEBT_TERM_MAX,
                        max(0.0, debt / PARAMS.FARMER_DEBT_FULL_MARK)
                        * PARAMS.FARMER_DEBT_SLOPE)
                if disaster is not None and disaster > PARAMS.FARMER_DISASTER_LINE:
                    scores["flee_refugee"] += PARAMS.FARMER_DISASTER_BUMP
                if unrest is not None and unrest > PARAMS.FARMER_UNREST_LINE:
                    scores["flee_refugee"] += PARAMS.FARMER_UNREST_BUMP
            # 6. 士绅：赈济 vs 兼并（旧实现无分支 ⇒ 恒"兼并"）
            elif obj == "gentry_path" and "charity_relief" in scores and "usury_annex" in scores:
                if disaster is not None and disaster > PARAMS.GENTRY_DISASTER_LINE:
                    scores["charity_relief"] += PARAMS.GENTRY_DISASTER_CHARITY_BUMP
                    # 灾荒时设义庄收乡望更划算
                if unrest is not None and unrest > PARAMS.GENTRY_UNREST_CHARITY_LINE:
                    scores["charity_relief"] += PARAMS.GENTRY_UNREST_CHARITY_BUMP
                    # 民变风险高时士绅更要买平安
                if unrest is not None and unrest < PARAMS.GENTRY_CALM_UNREST_LINE:
                    scores["usury_annex"] += PARAMS.GENTRY_CALM_USURY_BUMP
            # 7. 漕运改道（旧实现无分支 ⇒ 恒"等疏浚"）
            elif obj == "canal_reroute" and "wait_dredge" in scores and "overland_cart" in scores:
                block = cls._get_num(context, ("block_rate", "canal_block"), None)
                if block is not None:
                    b = (max(0.0, min(PARAMS.CANAL_BLOCK_SCALE, block))
                         / PARAMS.CANAL_BLOCK_SCALE)
                    scores["overland_cart"] += b * PARAMS.CANAL_OVERLAND_SLOPE
                    scores["borrow_grain"] += b * PARAMS.CANAL_BORROW_SLOPE
                    if b < PARAMS.CANAL_CLEAR_LINE:
                        scores["wait_dredge"] += PARAMS.CANAL_WAIT_BUMP

        probs = cls._softmax(scores, temperature=temperature)
        best = max(probs, key=probs.get) if probs else ""
        return {
            "verdict": best,
            "probabilities": probs,
            "provider": cls.PROVIDER_ID,
            "objective": obj,
            "defined": bool(probs),
        }

    @staticmethod
    def _choose_objective_from_keys(scores: Dict[str, float]) -> str:
        """向后兼容：未给 objective 时按旧 `criteria` 键名回退。"""
        keys = set(scores)
        if {"strict", "lenient"} <= keys:
            return "tax_stance"
        if {"corvee", "hired"} <= keys:
            return "labor_policy"
        if {"ship", "hoard"} <= keys:
            return "merchant_trade"
        if {"vigorous", "compliant"} <= keys:
            return "decree_compliance"
        if {"mortgage_land", "flee_refugee"} <= keys:
            return "farmer_path"
        if {"charity_relief", "usury_annex"} <= keys:
            return "gentry_path"
        if {"wait_dredge", "overland_cart"} <= keys:
            return "canal_reroute"
        return ""

    # =========================================================================
    # 气数品位：score
    # =========================================================================
    @classmethod
    def score(
        cls,
        context: Union[str, Dict[str, Any], None] = None,
        instructions: str = "",
        levels: Union[Sequence[str], Tuple[str, ...]] = (),
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """气数品位：分级打分评等。

        🔴 **levels 语义（单一约定）**：必须按「**差 → 好**」排列
        （如 `("下考","中考","上考")`、`("大凶","平","大吉")`），
        `score` 越高 ⇒ 索引越靠后。旧实现在两个分支里单调方向相反
        （考课"越好越高"、灾情"越重越高"）⇒ 同参数不同 levels 顺序给出相反结论。

        两个分支都归一到「**越好分越高**」：
        · 考课四善三最：治绩(0.40) + 治平(0.35) + 风纪(0.25)；
        · 通用灾情：灾情/民怨越重 ⇒ 分越低。

        **缺失不冒充满分（B1）**：
        · 考课分支要求 `tax_completion` 存在——旧缺省是 `1.0`（"缺失=赋税完美"），
          现缺失即 `defined=False`；
        · 通用分支对 `disaster` / `unrest` **各自独立**取可用项再平均——旧实现有运算符
          优先级错误，`disaster is None` 时整项 `unrest` 被丢弃；两项皆缺 ⇒ `defined=False`。

        返回::

            {"level": str, "score": float|None, "provider": "tiandao_local",
             "basis_undefined": bool, "defined": bool}
        """
        context = cls._bind_context(context, kwargs)
        lv_list = list(levels or ())
        if not lv_list:
            return {"level": "", "score": None, "provider": cls.PROVIDER_ID,
                    "basis_undefined": True, "defined": False}

        raw: Optional[float] = None
        if isinstance(context, dict):
            has_appraisal = any(
                cls._get_num(context, (k,), None) is not None
                for k in ("tax_completion", "official_integrity")
            )
            if has_appraisal:
                # B1：`tax_completion` 缺省曾是 1.0（"缺失=赋税完美"）⇒ 现为 None 且不进入打分
                tax = cls._get_num(context, ("tax_completion",), None)
                if tax is not None:
                    unrest = cls._get_num(context, ("unrest",),
                                          PARAMS.SCORE_UNREST_NEUTRAL)
                    integ = cls._get_num(context, ("official_integrity",), None)
                    # 治平项在 80 分处饱和（旧实现同样是 80，保留以免再改玩法标尺）
                    peace = max(0.0, PARAMS.UNIT_SCALE - max(
                        0.0, min(PARAMS.SCORE_PEACE_UNREST_CLAMP, unrest))
                        / PARAMS.SCORE_PEACE_UNREST_MARK)
                    raw = (max(0.0, min(PARAMS.SCORE_TAX_FULL, tax))
                           / PARAMS.SCORE_TAX_FULL * PARAMS.SCORE_TAX_W
                           + peace * PARAMS.SCORE_PEACE_W
                           + (max(0.0, min(PARAMS.UNIT_SCALE, integ))
                              if integ is not None
                              else PARAMS.SCORE_INTEGRITY_NEUTRAL)
                           * PARAMS.SCORE_INTEGRITY_W)
            else:
                disaster = cls._get_num(context, ("disaster",), None)
                unrest = cls._get_num(context, ("unrest",), None)
                # B1：逐项独立取可用值，再对**可用项**求平均。
                # 旧式 `(0.0 if disaster is None else A + (0.0 if unrest is None else B)) / 2.0`
                # 因运算符优先级，disaster 缺失时整段 else 不执行 ⇒ unrest 被丢弃 ⇒ 恒 1.0。
                severity_items: List[float] = []
                if disaster is not None:
                    severity_items.append(max(0.0, min(PARAMS.UNIT_SCALE, disaster)))
                if unrest is not None:
                    severity_items.append(max(0.0, min(PARAMS.UNREST_SCALE, unrest))
                                          / PARAMS.UNREST_SCALE)
                if severity_items:
                    raw = PARAMS.SCORE_SEVERITY_BASE - (
                        sum(severity_items) / len(severity_items))   # 越好分越高

        if raw is None:
            return {"level": "", "score": None, "provider": cls.PROVIDER_ID,
                    "basis_undefined": True, "defined": False}

        raw = min(PARAMS.SCORE_RAW_MAX, max(PARAMS.SCORE_RAW_MIN, raw))
        idx = min(len(lv_list) - 1, int(raw * len(lv_list)))
        return {
            "level": lv_list[idx],
            "score": round(raw, PARAMS.SCORE_ROUND_DIGITS),
            "provider": cls.PROVIDER_ID,
            "basis_undefined": False,
            "defined": True,
        }
