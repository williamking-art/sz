# -*- coding: utf-8 -*-
"""M36.7-B+ **大臣内容层登记表**（Q2 职责↔domain 映射 · Q9 标签登记 · v1 锁定）。

定位：**内容层静态数据**（随代码发布，运行时只读；AI/引擎均不得改写）。
纪律（M36.7-A §17）：
- 机器判断只认**登记枚举**；自由文本（`traits`/`role` 原文）只作叙事；
- 映射不清 ⇒ **标 `unknown`**，不猜、不按名气补全；
- 标签**只描述取向**（供 persona/立场/表达），**不得**用于权限、能力档位或数值；
- 新增 domain/标签 ⇒ **先登记再使用**（未登记不参与派生）。

⚠️ 本表覆盖范围以**实测档案**为准（2026-10-11：43 人 / 13 个 `trait_ids` / 6 类派系）；
「先登记、核义」，不擅自合并、改名或改变既有机制含义。
"""
from typing import Dict, Tuple

__all__ = ["DOMAIN_ENUM", "DOMAIN_LABELS", "ROLE_DOMAIN_KEYWORDS", "CENTRAL_KEYWORDS",
           "TRAIT_REGISTRY", "domains_of_role", "is_registered_trait", "registry_note"]

#: v1 领域枚举（M36.7-A §3 锁定；扩容须另裁）
DOMAIN_ENUM: Tuple[str, ...] = ("military", "finance", "personnel", "justice",
                               "works", "diplomacy", "agri", "culture")
DOMAIN_LABELS: Dict[str, str] = {
    "military": "军务", "finance": "财政", "personnel": "铨选吏治", "justice": "刑狱",
    "works": "工役水利", "diplomacy": "邦交", "agri": "农桑仓储", "culture": "文教礼制",
}

#: 职责（`role` 原文）→ domain 的关键词映射。**顺序无关**；命中即计入（可多域）。
ROLE_DOMAIN_KEYWORDS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("枢密", "兵", "军", "马", "步军", "武", "防御", "边", "将"), ("military",)),
    (("户", "财", "度支", "盐", "市舶", "钱", "漕", "转运", "三司"), ("finance",)),
    (("农", "粮", "仓", "屯田", "常平", "提举"), ("agri",)),
    (("吏", "铨", "选", "御史", "台谏", "司谏", "谏", "中丞", "官"), ("personnel",)),
    (("刑", "法", "大理", "审", "狱", "提刑"), ("justice",)),
    (("工", "水", "河", "匠", "将作", "营缮"), ("works",)),
    (("礼", "学", "太学", "翰林", "国子", "秘", "文"), ("culture",)),
    (("外交", "邻", "馆", "客", "互市", "国信"), ("diplomacy",)),
)
#: 中枢重臣关键词（选人时用于"domain 未命中不足"时的**规则化**补足，非硬编码人名）
CENTRAL_KEYWORDS: Tuple[str, ...] = ("相", "仆射", "侍郎", "尚书", "中书", "门下",
                                     "平章", "参政", "枢密使")

#: 标签登记（Q9）：语义＋**允许的消费方**＋**禁止用途**。未登记标签不得参与派生。
TRAIT_REGISTRY: Dict[str, Dict[str, object]] = {
    "聚敛": {"semantics": "取向：好聚财利，偏重财用收入", "consumers": ("persona", "stance")},
    "刚直": {"semantics": "取向：直言敢谏，不避权贵", "consumers": ("persona",)},
    "军略": {"semantics": "取向：留意兵事、知用兵大略", "consumers": ("persona",)},
    "忠勇": {"semantics": "取向：临事敢任、勇于效命", "consumers": ("persona",)},
    "阿附": {"semantics": "取向：趋附权势、不主己见", "consumers": ("persona",)},
    "调停": {"semantics": "取向：居中调和、避免激化", "consumers": ("persona",)},
    "权谋": {"semantics": "取向：重权术谋略、善察势", "consumers": ("persona",)},
    "理财": {"semantics": "取向：留意钱谷调度（**取向，非能力**）", "consumers": ("persona",)},
    "变法": {"semantics": "取向：主更张法度", "consumers": ("persona",)},
    "才艺": {"semantics": "取向：长于文艺之事", "consumers": ("persona",)},
    "清正": {"semantics": "取向：持身清介", "consumers": ("persona",)},
    "揽权": {"semantics": "取向：好揽事权", "consumers": ("persona",)},
    "怯懦": {"semantics": "取向：遇事畏缩", "consumers": ("persona",)},
}
#: 所有登记标签的**统一禁止用途**（D1/D4/D5）
TRAIT_FORBIDDEN = ("competence", "permission", "numeric_effect", "world_state")


def domains_of_role(role_text: str) -> Tuple[Tuple[str, ...], str]:
    """职责原文 → domains。返回 `(domains, note)`；**未命中 ⇒ 空集＋`unknown`**（不猜）。"""
    t = str(role_text or "")
    if not t.strip():
        return (), "unknown:职责缺失"
    hits = []
    for kws, doms in ROLE_DOMAIN_KEYWORDS:
        if any(k in t for k in kws):
            for d in doms:
                if d not in hits:
                    hits.append(d)
    if not hits:
        return (), "unknown:职责未登记"
    return tuple(hits), ""


def is_central_role(role_text: str) -> bool:
    """是否中枢重臣（用于"domain 命中不足"时的规则化补足）。**只读**。"""
    t = str(role_text or "")
    return any(k in t for k in CENTRAL_KEYWORDS)


def is_registered_trait(trait: str) -> bool:
    """标签是否已登记（Q9：未登记不得参与派生）。"""
    return str(trait or "") in TRAIT_REGISTRY


def registry_note() -> str:
    """登记表自述（供台账/UI 引用；避免文档与数据脱节）。"""
    return (f"domain 枚举 {len(DOMAIN_ENUM)} 类；职责关键词组 {len(ROLE_DOMAIN_KEYWORDS)} 组；"
            f"登记标签 {len(TRAIT_REGISTRY)} 个；标签统一禁止用途：{'/'.join(TRAIT_FORBIDDEN)}")
