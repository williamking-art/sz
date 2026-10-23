# -*- coding: utf-8 -*-
"""天道裁决引擎参数表（TianDao Params）——**数值标尺的唯一入口**。

为什么有这张表
--------------
`core/ai/tiandao_engine.py` 的 `gate` / `choose` / `score` 原先在方法体里内联了 132 个
数值常数（2026-10-21 审计用 ast 统计）：没有任何一处来自配置，也没人说得清哪个是
"玩法标尺"、哪个是"随手拍"。改一个数要先在 300 行里找到它，且改完无法回滚/对比。
本表把这些标尺全部收拢到一处，引擎只读不写。

口径纪律（与本仓库 `AGENTS.md` §3 一致）
----------------------------------------
1. **每个字段必须有一行注释写清「口径」**：它是什么标尺、量纲是什么、方向（越大越怎样）、
   以及为什么是这个值。`_dev_tools/game-dev/tests/test_tiandao_params_contract.py`
   会扫源码逐行断言这件事——**不写注释的字段等于没交付**。
2. **审计认定为"随手拍 / 两处不一致 / 无真实读数支撑"的参数，行尾标 `# 待校准`**。
   标注意味着"这个值目前没有依据，允许下一批按真实局面对齐"，不是"已确认"。
3. **单一事实源**：引擎里不得再出现裸玩法数值；新增可调项一律加在这里（同时给注释）。
4. **静态数据**：本模块零依赖、无副作用、可单独 `import`；引擎用模块级硬导入读取
   （`from content.data_tiandao import PARAMS`）——导入失败就该炸出来，**禁止**
   try/except 静默降级（否则"参数没生效"会变成静默行为漂移）。
5. **只放标尺，不放逻辑**：不要在这里写函数分支；判定流程属于引擎。

刻意未收录的常数
----------------
* `0` / `1.0` 这类**结构性哨兵**（如 `range` 边界、`int()` 截断、位掩码 `_MASK64`）不是玩法标尺，
  留在引擎里更易读；本表只收"改了会改玩法结论"的数值。
* `dice` 的 splitmix64 混洗常数属于算法实现，不是玩法参数。

本批（L1-a）修掉的 4 个缺陷与参数表的关系
------------------------------------------
* B2：`CORRUPTION_*` 原有一个 `0.5` 兜底（清廉度缺失时按 0.5 计）⇒ 概率恰好 `0.50 >= 阈值`
  ⇒ **缺失即判贪墨**。该兜底已删除，`integrity is None` 时引擎返回 `defined=False`。
  本表因此**故意没有** corruption 的中性兜底项。
* B3：`LABOR_ABSOLUTE_TREASURY` 用**地方府库量级（贯）**的绝对阈值，替代原来 `treasury >= 5000`
  ——旧值比真实国库（5,000,000 贯）小 3 个数量级，导致 `corvee` 分支实际不存在。
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Dict, Tuple

__all__ = ["TianDaoParams", "PARAMS", "param_names", "param_count"]


@dataclass(frozen=True)
class TianDaoParams:
    """天道引擎全部可调数值标尺（冻结；引擎按属性读取，测试可用 `dataclasses.replace` 克隆）。"""

    # =========================================================================
    # 通用标尺（多个 objective 共用；改这些等于同时改所有分支）
    # =========================================================================
    UNIT_SCALE: float = 1.0                 # 口径：0~1 归一标尺（灾情/清廉度/勤政/概率共用），钳位与互补(1-x)用
    UNREST_SCALE: float = 100.0             # 口径：民怨 0~100 分制的分母（局内 unrest 以"分"计）
    PRESTIGE_SCALE: float = 100.0           # 口径：国祚声望 0~100 分制的分母
    PRESTIGE_NEUTRAL: float = 50.0          # 口径：声望读数缺失时的中性基准（50 = 中平）；不是"缺失当良好" # 待校准
    PROB_FLOOR: float = 0.01                # 口径：gate 概率下钳，避免 0 ⇒ "永不通过"的死闸门
    PROB_CAP: float = 0.99                  # 口径：gate 概率上钳，避免 1 ⇒ "必然通过"的死闸门
    PROB_ROUND_DIGITS: int = 4              # 口径：概率/分数输出小数位（Softmax 归一残差回填依赖同一精度）
    CHOOSE_TEMPERATURE: float = 0.8         # 口径：choose 的 Softmax 温度（越小越确定；= 签名默认值）
    SOFTMAX_MIN_TEMPERATURE: float = 0.01   # 口径：温度下钳（防除零；也防"绝对必然"抹掉小概率选项）
    SOFTMAX_EVEN_NUMERATOR: float = 1.0     # 口径：数值异常时按 1/n 均分的分子（n = 选项数）

    # =========================================================================
    # WAIVE_*：恩泽蠲免陈年逋欠（gate）
    # 口径：三项加性打分，输出 0~1 的"应蠲免"倾向概率
    # =========================================================================
    WAIVE_BASE: float = 0.30                # 口径：无灾无怨的基线倾向（0.30 < 阈值 0.50 ⇒ 太平年不蠲免）
    WAIVE_DISASTER_W: float = 0.35          # 口径：灾情权重（灾情 0~1，灾重则蠲免诉求强）
    WAIVE_UNREST_W: float = 0.25            # 口径：民怨权重（民怨 0~100 归一后计入）
    WAIVE_INTEGRITY_W: float = 0.20         # 口径：官员清廉度权重（清官更愿为民请命；缺失按 0 贡献而非补中性值）

    # =========================================================================
    # CHANGPING_*：常平仓平粜开仓（gate）
    # 口径：只看粮价指数（price_ratio = 市价/基准价）偏离平价多少；库存为空是硬否决项
    # =========================================================================
    CHANGPING_BASE: float = 0.20            # 口径：平价时的基线倾向（0.20 < 阈值 ⇒ 不轻易开仓）
    CHANGPING_PRICE_NEUTRAL: float = 1.0    # 口径：粮价指数平价点（1.0 = 市价等于基准价）；price_ratio 缺失时按平价
    CHANGPING_PRICE_SLOPE: float = 1.5      # 口径：价格项斜率（指数每高出平价 1.0 ⇒ +1.5 概率，很快撞上限）
    CHANGPING_PRICE_TERM_MAX: float = 0.70  # 口径：价格项上限（防止高价把概率推成必然）
    CHANGPING_STOCK_EMPTY: float = 0.0      # 口径：库存判空线（stock <= 0 视为空仓；**stock 缺失不得当 0**，走价格公式）
    CHANGPING_EMPTY_PROB: float = 0.0       # 口径：空仓时的原始概率（引擎随后下钳到 PROB_FLOOR ⇒ 必不通过）

    # =========================================================================
    # CORRUPTION_*：仓吏雀鼠耗贪墨（gate）
    # 口径：清廉度越低 ⇒ 贪墨概率越高（单调）；integreity 缺失 ⇒ defined=False（B2）
    # =========================================================================
    CORRUPTION_BASE: float = 0.20           # 口径：清廉度=1.0（绝对清白）时的下限概率
    CORRUPTION_SLOPE: float = 0.60          # 口径：清廉度每降 1.0 增加的概率（上限 0.20+0.60=0.80）
    CORRUPTION_INSPECTOR_MULT: float = 0.20  # 口径：有御史巡按/监察时的概率乘数（强压制，但不清零——巡按也可能失察）

    # =========================================================================
    # REFUGEES_*：招募流民充厢军（gate）
    # 口径：流民人数（人）+ 民怨共同推高"该收容"的倾向
    # =========================================================================
    REFUGEES_BASE: float = 0.35             # 口径：无流民无民怨时的基线
    REFUGEES_FULL_MARK: float = 5000.0      # 口径：流民人数"满量"刻度（人）；5000 人 = 一州可动员上限量级 # 待校准
    REFUGEES_TERM_MAX: float = 0.45         # 口径：流民项上限（0.35+0.45=0.80，留民怨项空间）
    REFUGEES_UNREST_W: float = 0.25         # 口径：民怨权重（归一到 0~1 后计入）

    # =========================================================================
    # REFORM_*：知州贯彻新政（gate）
    # 口径：派系加成（新党+/旧党−）+ 勤政 + 声望；派系是"立场"，勤政是"能力"
    # =========================================================================
    REFORM_BASE: float = 0.45               # 口径：中立派、零勤政、声望 0 时的基线（略低于阈值 ⇒ 默认不判贯彻）
    REFORM_FACTION_BONUS: float = 0.30      # 口径：新党/变法派的加性加成（立场同向）
    REFORM_FACTION_MALUS: float = -0.25     # 口径：旧党/保守派的加性扣减（阳奉阴违的结构性动机）
    REFORM_DILIGENCE_W: float = 0.15        # 口径：勤政度权重（0~1）
    REFORM_PRESTIGE_W: float = 0.10         # 口径：国祚声望权重（归一到 0~1；声望高则政令易行）

    # =========================================================================
    # GENERIC_*：通用是非（无专项特征）
    # 口径：仅以声望与民怨做微调，围绕 0.50 摆动；也是 gate 默认阈值出处
    # =========================================================================
    GENERIC_BASE: float = 0.50              # 口径：通用基线（= 掷硬币），声望/民怨在其上微调
    GENERIC_PRESTIGE_W: float = 0.15        # 口径：声望权重（声望 100 ⇒ +0.15）
    GENERIC_UNREST_W: float = 0.15          # 口径：民怨权重（民怨 100 ⇒ −0.15）
    GENERIC_THRESHOLD: float = 0.50         # 口径：gate 默认判定阈值（= 签名默认值 threshold=0.50）

    # =========================================================================
    # TAX_*：夏秋两税征管宽严（choose: strict / moderate / lenient）
    # 口径：对 strict / lenient 两个边缘选项加偏置；moderate 是不动点
    # =========================================================================
    TAX_STRICT_INTEGRITY_LINE: float = 0.4  # 口径：清廉度分界（低于此判"会借严催中饱"⇒ 反向压制 strict）
    TAX_STRICT_BUMP: float = 0.4            # 口径：贪官时给 strict 的加成（贪 ⇒ 倾向严催以自肥）
    TAX_STRICT_MALUS: float = -0.3          # 口径：清官时给 strict 的扣减（清官不必靠严催）
    TAX_LENIENT_W: float = 0.3              # 口径：清廉度对 lenient 的正权重（清官更肯体恤）
    TAX_DISASTER_LINE: float = 0.5          # 口径：灾情分界（0~1；>0.5 判"成灾"⇒ 该宽征）
    TAX_DISASTER_LENIENT: float = 0.5       # 口径：成灾时给 lenient 的加成
    TAX_CALM_LENIENT: float = -0.2          # 口径：未成灾时给 lenient 的扣减（常态下宽征会亏国用）

    # =========================================================================
    # LABOR_*：劳役制度（choose: corvee 差役 / hired 雇役）
    # 口径（B3）：用**月度刚性支出**把府库折成"能撑几个月"，而不是拿裸贯数比阈值
    # =========================================================================
    LABOR_HIRED_MIN_MONTHS: float = 3.0     # 口径：府库够撑 3 个月即为"雇得起"（= 财政安全垫的默认月数）
    LABOR_ABSOLUTE_TREASURY: float = 200_000.0  # 口径：无月支出读数时的**路库见底线**（贯）。实测路库 270,000~1,950,000、中位约 690,000 ⇒ 20 万约 1/3 中位，只在路库被真正掏空时才转差役；旧值 5,000 低 3 个数量级（corvee 死分支）。⚑ 曾试 1,000,000（≈中位）但会让 procurement.py 的路级调用在开局大面积由雇役翻差役（工费 40%→0），Jev 裁定 A 0.742 取 200,000 # 待校准
    LABOR_HIRED_BIAS: float = 0.8           # 口径：雇役偏置（加性分值，作用在 Softmax 前的分数上）
    LABOR_CORVEE_BIAS: float = 0.9          # 口径：差役偏置（略大于雇役偏置 ⇒ 财政吃紧时更果断征差役）
    LABOR_MONTHLY_EXPENSE_MIN: float = 0.0  # 口径：月支出有效性下限（<= 此值视为无读数，退回绝对线）

    # =========================================================================
    # MERCHANT_*：商贾经营（choose: ship 贩运 / hoard 囤积 / local_sell 就地抛售）
    # 口径：价差推动贩运，灾荒推动囤积
    # =========================================================================
    MERCHANT_GAP_SLOPE: float = 0.5         # 口径：价差(gap)转分值的斜率（gap 单位=倍/指数）
    MERCHANT_GAP_TERM_MAX: float = 1.0      # 口径：价差项上限（防止单一因素压倒其它选项）
    MERCHANT_DISASTER_LINE: float = 0.4     # 口径：灾情分界（0~1）⇒ 判"灾荒可居奇"；**与 FARMER_/GENTRY_ 的 0.5 不一致** # 待校准
    MERCHANT_HOARD_BUMP: float = 0.6        # 口径：灾荒时给 hoard 的加成

    # =========================================================================
    # DECREE_*：路级知州对诏令的遵从反应（choose: vigorous/compliant/passive/defiant）
    # 口径：清廉+勤政 ⇒ 卖力/照办；贪且府库空 ⇒ 阳奉阴违(defiant)
    # =========================================================================
    DECREE_INTEGRITY_NEUTRAL: float = 0.5   # 口径：清廉度缺失时的中性基准（"不明底细按中平"） # 待校准
    DECREE_DILIGENCE_NEUTRAL: float = 0.5   # 口径：勤政度缺失时的中性基准（同"不明底细按中平"） # 待校准
    DECREE_VIGOROUS_INTEG_W: float = 0.30   # 口径：清廉度对 vigorous 的正权重
    DECREE_VIGOROUS_DILIG_W: float = 0.20   # 口径：勤政度对 vigorous 的正权重
    DECREE_COMPLIANT_BUMP: float = 0.10     # 口径：compliant（照章办事）的恒定加成——它是"默认基本盘"
    DECREE_PASSIVE_UNREST_LINE: float = 40.0  # 口径：民怨分界（0~100；过此线 ⇒ 州府消极观望）
    DECREE_PASSIVE_UNREST_BUMP: float = 0.25  # 口径：民怨高时给 passive 的加成
    DECREE_PASSIVE_CORRUPT_W: float = 0.25  # 口径：贪腐度((1-清廉))对 passive 的正权重
    DECREE_DEFIANT_CORRUPT_W: float = 0.60  # 口径：贪腐度对 defiant（阳奉阴违）的正权重（旧实现漏此项 ⇒ defiant 永不可达）
    DECREE_DEFIANT_POOR_TREASURY_LINE: float = 0.0  # 口径：府库"见底"判定线（贯；<= 此值 ⇒ 无钱办差 ⇒ 更可能抗命）
    DECREE_DEFIANT_POOR_TREASURY_BUMP: float = 0.20  # 口径：府库见底时给 defiant 的加成

    # =========================================================================
    # FARMER_*：破产小农出路（choose: mortgage_land 典田 / flee_refugee 逃荒）
    # 口径：债务 + 灾情 + 民怨推动逃荒；三者都是"逼走"的力量
    # =========================================================================
    FARMER_DEBT_FULL_MARK: float = 1000.0   # 口径：债务"满量"刻度（贯）；1000 贯 = 自耕农破产量级 # 待校准
    FARMER_DEBT_SLOPE: float = 0.4          # 口径：债务转分值斜率（满量时 +0.4）
    FARMER_DEBT_TERM_MAX: float = 0.8       # 口径：债务项上限
    FARMER_DISASTER_LINE: float = 0.5       # 口径：灾情分界（0~1）
    FARMER_DISASTER_BUMP: float = 0.5       # 口径：成灾时给 flee_refugee 的加成
    FARMER_UNREST_LINE: float = 50.0        # 口径：民怨分界（0~100）
    FARMER_UNREST_BUMP: float = 0.3         # 口径：民怨过线时给 flee_refugee 的加成

    # =========================================================================
    # GENTRY_*：士绅灾荒抉择（choose: charity_relief 赈济 / usury_annex 兼并）
    # 口径：灾荒与民变风险买平安；太平年景趁火打劫收田
    # =========================================================================
    GENTRY_DISASTER_LINE: float = 0.5       # 口径：灾情分界（0~1）
    GENTRY_DISASTER_CHARITY_BUMP: float = 0.6  # 口径：成灾时给 charity_relief 的加成（收乡望更划算）
    GENTRY_UNREST_CHARITY_LINE: float = 60.0   # 口径：民怨分界（0~100；高到要民变 ⇒ 士绅买平安）
    GENTRY_UNREST_CHARITY_BUMP: float = 0.4    # 口径：民变风险高时给 charity_relief 的加成
    GENTRY_CALM_UNREST_LINE: float = 20.0      # 口径：民怨"太平线"（<20 判无事 ⇒ 兼并阻力小）
    GENTRY_CALM_USURY_BUMP: float = 0.3        # 口径：太平年景给 usury_annex 的加成

    # =========================================================================
    # CANAL_*：漕运遇阻改道（choose: wait_dredge 等疏浚 / overland_cart 陆运 / borrow_grain 和籴）
    # 口径：河道阻塞率（block_rate，0~100 百分数）推高改道；畅通则等疏浚
    # =========================================================================
    CANAL_BLOCK_SCALE: float = 100.0        # 口径：阻塞率百分数分母（block_rate 以 0~100 传入）
    CANAL_OVERLAND_SLOPE: float = 1.0       # 口径：阻塞率对陆运的正权重（阻塞率 100% ⇒ +1.0）
    CANAL_BORROW_SLOPE: float = 0.6         # 口径：阻塞率对和籴/借兑的正权重
    CANAL_CLEAR_LINE: float = 0.4           # 口径：阻塞率分界（归一后 <0.4 判"基本畅通"）
    CANAL_WAIT_BUMP: float = 0.3            # 口径：基本畅通时给 wait_dredge 的加成

    # =========================================================================
    # SCORE_*：气数品位（score；考课四善三最 / 通用灾情）
    # 口径：两个分支都归一到"越好分越高"，输出 0~1 后按 levels 索引取档
    # =========================================================================
    SCORE_TAX_FULL: float = 1.2             # 口径：赋税完成度满分刻度（1.2 = 超额 20%；局内 tax_completion 上限即 1.2）
    SCORE_TAX_W: float = 0.40               # 口径：治绩（赋税）项权重
    SCORE_PEACE_UNREST_MARK: float = 80.0   # 口径：治平项饱和刻度（民怨 80 分时治平归零） # 待校准
    SCORE_PEACE_UNREST_CLAMP: float = 160.0  # 口径：治平项输入钳位（防极端民怨把分数推到负）
    SCORE_PEACE_W: float = 0.35             # 口径：治平（民怨）项权重
    SCORE_INTEGRITY_W: float = 0.25         # 口径：风纪（清廉）项权重
    SCORE_INTEGRITY_NEUTRAL: float = 0.5    # 口径：清廉度缺失时的中性基准（考课不能因缺数据贬人） # 待校准
    SCORE_UNREST_NEUTRAL: float = 0.0       # 口径：考课分支民怨缺失时的缺省（按"无民怨=治平满分"）# 待校准
    SCORE_SEVERITY_BASE: float = 1.0        # 口径：通用灾情分支的基座（分 = 基座 − 严重度均值 ⇒ 越好分越高）
    SCORE_RAW_MIN: float = 0.0              # 口径：最终分数钳位下限（0 = 最差）
    SCORE_RAW_MAX: float = 1.0              # 口径：最终分数钳位上限（1 = 最好）
    SCORE_ROUND_DIGITS: int = 4             # 口径：分数输出小数位（与档位索引的边界判定同精度）


#: 唯一入口：引擎 `from content.data_tiandao import PARAMS` 读取本实例。
PARAMS = TianDaoParams()


def param_names() -> Tuple[str, ...]:
    """全部参数名（按定义顺序）。测试/审计用它统计参数总数与逐项核对注释。"""
    return tuple(f.name for f in fields(TianDaoParams))


def param_count() -> int:
    """参数总数（`param_names()` 的长度；供契约测试断言"外置是真外置"）。"""
    return len(param_names())


def as_dict() -> Dict[str, object]:
    """参数快照（只读用途：日志/回测/人工比对）。"""
    return {name: getattr(PARAMS, name) for name in param_names()}
