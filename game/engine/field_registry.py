# -*- coding: utf-8 -*-
"""宋祚 · applier 写契约的字段单点注册（`game/engine/field_registry.py`）

🔴 **范围刻意收窄**：本模块只承载 `game/engine/state_applier.py` 六套路径/规则集合的
**唯一数据源**——

    VALID_PATHS / NON_NEG_PREFIXES / MONEY_PATHS / GRAIN_PATHS / RANGE_100_FIELDS / CLAMP_01_FIELDS

**它不是全项目元数据中心**：
  · 不承载单位（贯/石/比率）、真账归属、镜像关系、唯一写者——它们的权威源在机制文档与各机制
    模块，生命周期与本表不同（见 `_dev_tools/game-docs/specs/cross-cutting/field-registry/design.md` §3）。
  · **不承载匹配语义**。`state_applier` 的五个 matcher 保持原样：同一路径在不同集合里语义本就
    可能不同（例：`NON_NEG_PREFIXES` 的 `"granary"` 是无边界前缀，而 `VALID_PATHS` 的 `"granary"`
    是精确匹配）。B-1 只统一**数据源**，不统一**判定**。

计数（迁移前实测）：六集合合计 84 条登记 → 去重 **38 行**声明。

改写纪律：
  · 新增可写字段 ⇒ 在 `RULES` 加**一行**，`cons` 与 `kind` 必须显式给（`EXEMPT` 也要写）。
  · 路径名命中钱粮语义词而 `cons=EXEMPT` ⇒ 必须给 `exempt_reason`
    （🔴 关键词**只触发写理由**，绝不参与守恒分类）。
  · 自检：`validate_registry()`；测试期由 `_dev_tools/game-dev/tests/test_field_registry_parity.py` 执行。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "Kind", "Cons", "PathRule", "RULES", "derive", "validate_registry",
    "MONEY_WORDS", "VALID_PATHS", "NON_NEG_PREFIXES", "MONEY_PATHS",
    "GRAIN_PATHS", "RANGE_100_FIELDS", "CLAMP_01_FIELDS",
]


class Kind(Enum):
    """值类型。决定"哪些数值元数据是必需的"——非数值字段不得带守恒/非负/上限语义。"""

    NUMERIC = "numeric"
    NON_NUMERIC = "non_numeric"


class Cons(Enum):
    """守恒分类。**必填**：`EXEMPT` 也必须显式声明（这是治"漏注册"的机关）。"""

    MONEY = "money"
    GRAIN = "grain"
    EXEMPT = "exempt"


#: 钱粮语义词：命中只要求写 `exempt_reason`，**不决定分类**（不自动归入 MONEY/GRAIN）。
MONEY_WORDS: Tuple[str, ...] = (
    "wealth", "grain", "treasury", "granary", "money",
    "budget", "savings", "cost", "tax", "revenue", "payment",
)
_MONEY_WORD_RE = re.compile("|".join(MONEY_WORDS), re.IGNORECASE)


@dataclass(frozen=True)
class PathRule:
    """一条路径的写契约声明（六个集合的原子数据源）。

    字段顺序即派生顺序；`path` 字符串与迁移前逐字一致。
    """

    path: str
    kind: Kind
    cons: Cons
    writable: bool = False                 # → VALID_PATHS
    non_neg: bool = False                  # → NON_NEG_PREFIXES
    max_100: bool = False                  # → RANGE_100_FIELDS（0-100 百分制）
    clamp01: bool = False                  # → CLAMP_01_FIELDS（0-1，当前无成员）
    exempt_reason: Optional[str] = None    # cons=EXEMPT 且命中钱粮语义词时必填
    source: str = ""                       # 口径出处／事故编号（承接原注释）
    legacy: Optional[str] = None            # 历史例外说明（失效通道、只读镜像等）


_N = Kind.NUMERIC
_X = Kind.NON_NUMERIC
_M = Cons.MONEY
_G = Cons.GRAIN
_E = Cons.EXEMPT

# ---------------------------------------------------------------------------
# 38 行声明（迁移前六集合去重）
#   · 前 35 行 = 原 VALID_PATHS 全集（顺序沿用其原顺序）
#   · 末 3 行  = 原 NON_NEG_PREFIXES 独有（不在白名单）——E2/通配行，**原样保留**
# ---------------------------------------------------------------------------
RULES: Tuple[PathRule, ...] = (
    # ---- 顶层国库 / 内帑 / 太仓 ----
    PathRule("treasury", _N, _M, writable=True, non_neg=True),
    PathRule("imperial_treasury", _N, _M, writable=True, non_neg=True),
    PathRule("granary", _N, _G, writable=True, non_neg=True),
    PathRule("prestige", _N, _E, writable=True, non_neg=True, max_100=True),
    # M2（用户 2026-10-01 定稿 (a)）：真实分账基金；发放腿须与官僚 POP wealth 成对，
    # 漏 MONEY 会被配对校验判成"缺来源"而整批拒绝（当时表现为 transfer_public_funds_to_pops 返回 0）。
    PathRule("payraise_budget", _N, _M, writable=True, non_neg=True,
             source="M2 分账基金；三处同注册教训 2026-10-01"),
    PathRule("population_satisfaction", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("art_mastery", _N, _E, writable=True, non_neg=True, max_100=True,
             legacy="E4 冻结：audit 记刷分风险（进七维评价）；可写性维持现状，不属 B-1"),
    # ---- 动态维度（尾点前缀，唯一一条）----
    PathRule("era_state.", _N, _E, writable=True,
             legacy="E3 冻结：月结 settle_era_links 覆盖 ⇒ 白名单在但写入永不生效；能力问题另裁"),
    # ---- 路级状态 ----
    PathRule("prefectures.*.mood", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.govern", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.unrest", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.grain", _N, _G, writable=True, non_neg=True),
    PathRule("prefectures.*.storage", _N, _G, writable=True, non_neg=True),
    # ---- POP 子池：守恒按 6 类（钱）/ 2 类（粮）具体声明 ----
    # 🔴 这 8 条**不标 non_neg**：原 NON_NEG_PREFIXES 对 POP 钱粮用的是两条**通配行**
    #    （见文件末尾 `prefectures.*.pops.*.wealth` / `.*.grain`），而非逐类登记。
    #    同一概念在两个集合里用不同粒度是本工程的既有形态；B-1 原样保留，不合并粒度。
    #    （实测教训：若此处也标 non_neg，NON_NEG_PREFIXES 会从 24 涨到 32 条 ⇒ 派生不一致。）
    PathRule("prefectures.*.pops.农.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.pops.农.grain", _N, _G, writable=True),
    PathRule("prefectures.*.pops.士绅.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.pops.士绅.grain", _N, _G, writable=True),
    PathRule("prefectures.*.pops.工匠.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.pops.商人.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.pops.官僚.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.pops.兵.wealth", _N, _M, writable=True),
    PathRule("prefectures.*.refugees", _N, _E, writable=True, non_neg=True),
    # ---- 派系 ----
    PathRule("factions.*.satisfaction", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("factions.*.influence", _N, _E, writable=True, non_neg=True, max_100=True),
    # ---- 四大机制改良 ----
    PathRule("land.hidden_rate", _N, _E, writable=True,
             source="税率隐漏率（非人口）；land.hidden_households 才是人口派生镜像"),
    PathRule("waste_reform.active", _N, _E, writable=True),
    PathRule("waste_reform.savings", _N, _E, writable=True, non_neg=True,
             exempt_reason="E6 冻结：只承载非负判定；守恒分类维持现状（不在 MONEY_PATHS）"),
    PathRule("defense_lines.*.fortification", _N, _E, writable=True,
             legacy="E5 冻结：与 garrison 的非负不对称，维持现状"),
    PathRule("defense_lines.*.garrison", _N, _E, writable=True, non_neg=True),
    PathRule("legacies.*.active", _N, _E, writable=True),
    PathRule("legacies.*.progress", _N, _E, writable=True, non_neg=True),
    PathRule("prefectures.*.public_support", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.gentry_resistance", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.city_defense", _N, _E, writable=True, non_neg=True, max_100=True),
    PathRule("prefectures.*.controlled_by", _X, _E, writable=True,
             source="字符串字段（默认「宋」）；validate_changes 对 set/add/mul 强制数值 ⇒ 实际仅 remove/push"),
    # ---- 原 NON_NEG_PREFIXES 独有 3 行（不在白名单）——原样保留，不收窄、不删除 ----
    PathRule("prefectures.*.pops.*.wealth", _N, _E, non_neg=True,
             exempt_reason="非负通配行；守恒分组按 6 个具体 POP 类声明（MONEY_PATHS），本行不参与分类"),
    PathRule("prefectures.*.pops.*.grain", _N, _E, non_neg=True,
             exempt_reason="非负通配行；粮守恒按 农/士绅 两条具体声明（GRAIN_PATHS），本行不参与分类"),
    PathRule("land.hidden_households", _N, _E, non_neg=True,
             legacy="E2 冻结：已从白名单移除的派生镜像；经白名单不可达，保留原样"),
)


def derive(rules: Sequence[PathRule] = RULES) -> Dict[str, List[str]]:
    """由声明派生六个集合（**唯一生成路径**）。顺序 = 声明顺序。

    顺序说明：六个集合**各自的顺序无法由单一声明同时复现**（存在 4 节点约束环，见 design.md §2.3），
    故本函数不承诺顺序恒等；顺序不变性由行为测试证明（谓词与管道结果对排列不敏感）。
    """
    return {
        "VALID_PATHS": [r.path for r in rules if r.writable],
        "NON_NEG_PREFIXES": [r.path for r in rules if r.non_neg],
        "RANGE_100_FIELDS": [r.path for r in rules if r.max_100],
        "CLAMP_01_FIELDS": [r.path for r in rules if r.clamp01],
        "MONEY_PATHS": [r.path for r in rules if r.cons is Cons.MONEY],
        "GRAIN_PATHS": [r.path for r in rules if r.cons is Cons.GRAIN],
    }


_DERIVED = derive(RULES)

#: ⚠️ 类型保持 `list`（与迁移前逐字一致），避免任何 API 类型变化；见 design.md §3.1。
VALID_PATHS: List[str] = _DERIVED["VALID_PATHS"]
NON_NEG_PREFIXES: List[str] = _DERIVED["NON_NEG_PREFIXES"]
RANGE_100_FIELDS: List[str] = _DERIVED["RANGE_100_FIELDS"]
CLAMP_01_FIELDS: List[str] = _DERIVED["CLAMP_01_FIELDS"]
MONEY_PATHS: List[str] = _DERIVED["MONEY_PATHS"]
GRAIN_PATHS: List[str] = _DERIVED["GRAIN_PATHS"]


def _semantics(r: PathRule) -> Tuple:
    return (r.kind, r.cons, r.writable, r.non_neg, r.max_100, r.clamp01)


def validate_registry(rules: Sequence[PathRule] = RULES) -> List[str]:
    """自检：**校验实际传入的值**（运行期 isinstance），不依赖 dataclass 类型标注。

    返回错误清单（空 = 通过）。供测试期调用；**不**在 import 期断言（保持运行行为不变）。
    """
    errs: List[str] = []
    if not isinstance(rules, (list, tuple)):
        return ["rules 必须是 list/tuple，得到 %s" % type(rules).__name__]

    seen: Dict[str, Tuple] = {}
    for i, r in enumerate(rules):
        if not isinstance(r, PathRule):
            errs.append("rules[%d] 不是 PathRule：%s" % (i, type(r).__name__))
            continue
        p = r.path
        tag = "rules[%d](%r)" % (i, p)
        # ---- 值类型（运行期校验实际值）----
        if type(p) is not str:
            errs.append("%s path 必须是 str：%s" % (tag, type(p).__name__))
            p = None
        elif (not p) or (p != p.strip()) or ("" in (p[:-1] if p.endswith(".") else p).split(".")):
            # 尾点 = 合法的“前缀标记”形态（唯一一例 `era_state.`），只检查其前部分是否成段
            errs.append("%s path 格式非法（空串/首尾空白/空段；尾点仅允许作前缀标记）" % tag)
        if not isinstance(r.kind, Kind):
            errs.append("%s kind 必须是 Kind：%r" % (tag, r.kind))
        if not isinstance(r.cons, Cons):
            errs.append("%s cons 必须是 Cons（必填；EXEMPT 也要显式写）：%r" % (tag, r.cons))
        for f in ("writable", "non_neg", "max_100", "clamp01"):
            if type(getattr(r, f)) is not bool:
                errs.append("%s %s 必须是 bool：%r" % (tag, f, getattr(r, f)))
        for f in ("exempt_reason", "source", "legacy"):
            v = getattr(r, f)
            if v is not None and type(v) is not str:
                errs.append("%s %s 必须是 str/None：%r" % (tag, f, v))

        # ---- 语义不变式 ----
        if r.max_100 and r.clamp01:
            errs.append("%s 不得同时 max_100 与 clamp01" % tag)
        if r.kind is not Kind.NUMERIC:
            if r.non_neg or r.max_100 or r.clamp01 or r.cons is not Cons.EXEMPT:
                errs.append("%s kind=NON_NUMERIC 不得带 non_neg/max_100/clamp01 或守恒分类" % tag)
        if r.cons in (_M, _G):
            if not r.writable:
                errs.append("%s cons=%s 但 writable=False（守恒组必须在白名单内）" % (tag, r.cons.value))
            if r.kind is not Kind.NUMERIC:
                errs.append("%s cons=%s 但 kind 非数值" % (tag, r.cons.value))
        if r.cons is _E and isinstance(p, str) and _MONEY_WORD_RE.search(p) and not r.exempt_reason:
            errs.append(
                "%s cons=EXEMPT 且路径命中钱粮语义词，必须给 exempt_reason"
                "（关键词只触发写理由，不决定分类）" % tag)

        # ---- 重复声明 ----
        if isinstance(p, str):
            if p in seen:
                if seen[p] == _semantics(r):
                    errs.append("%s 重复声明同一 path（同语义）" % tag)
                else:
                    errs.append("%s 重复声明同一 path 但语义不一致：%r vs %r"
                                % (tag, seen[p], _semantics(r)))
            else:
                seen[p] = _semantics(r)

    # ---- 集合关系（由传入 rules 现算，不用模块级常量）----
    d = derive(rules)
    v = set(d["VALID_PATHS"])
    for name, key in (("MONEY_PATHS", "MONEY_PATHS"), ("GRAIN_PATHS", "GRAIN_PATHS"),
                      ("RANGE_100_FIELDS", "RANGE_100_FIELDS"), ("CLAMP_01_FIELDS", "CLAMP_01_FIELDS")):
        extra = sorted(set(d[key]) - v)
        if extra:
            errs.append("%s ⊆ VALID_PATHS 不成立，越界成员：%s" % (name, extra))
    extra = sorted(set(d["RANGE_100_FIELDS"]) - set(d["NON_NEG_PREFIXES"]))
    if extra:
        errs.append("RANGE_100_FIELDS ⊆ NON_NEG_PREFIXES 不成立，越界成员：%s" % extra)
    return errs
