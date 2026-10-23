# -*- coding: utf-8 -*-
"""商品**品目**层（P-B0）—— 需求口味与应税分解的键空间（**只读数据 + 校验**）。

## 为什么另立品目，而不复用既有两张表

| 表 | 现有粒度 | 为什么不拿来当品目 |
|---|---|---|
| `COMMODITY_KINDS`（`data_constants.py:582-603`） | **4 类**：粮 / 原料 / 成品 / 军需 | 太粗：盐与铁同为「原料」，嗜好倍率与应税分解会完全同值 |
| `GOODS_CLASSES`（`data_constants.py:629-658`） | 只有 **食品 / 粮** 两个词条（父子），覆盖约 12 维 | 太窄：覆盖不到纺织、金属、矿产、军需等 |

故本品目层是**第三张、正交的表**：`kind` 管「能不能入粮仓 / 是否军需」，`GOODS_CLASSES` 管「粮的词条归属」，
本品目管「**需求口味 + 应税产值归类**」。三者并存，互不替代。

## 口径纪律

- **100% 覆盖**：`GOODS_CATEGORY` 的键必须与 `GOODS_DIMS` 完全相等（`validate()` 返回空才算过）。
  缺失 = 该维无法参与品目口径的嗜好/应税分解 ⇒ **必须暴露为问题**，不得静默当成「其他」。
- **一维一品目**：dict 的键天然唯一；不存在「一维属多类」。
- **不臆造**：品目划分照《食货志》与 `_dev_tools/game-docs/docs/` 下既有商品目录设计文档的分类，
  **不照搬**《物产新篇》的 40 类（那是明末断代）。
- **运行时新增维**：`GOODS_DIMS` 可经 `data_constants.register_raw_material` /
  `register_finished_good` 在运行时扩维。那两个函数会调用 `note_new_dim()`；
  未登记品目**只告警不拒绝**（拒绝会打断 AI 建新货的既有通道，且这层是口味/读数口径，不是账本）。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

__all__ = [
    "CATEGORY_ORDER", "GOODS_CATEGORY", "category_of", "category_goods",
    "categories", "validate", "note_new_dim",
]

#: 品目顺序（**展示与聚合顺序**）。21 个，覆盖 62 维。
CATEGORY_ORDER: Tuple[str, ...] = (
    "粮食", "茶", "盐", "丝织", "布帛", "糖果", "酿造", "肉食",
    "药材", "木材", "石料", "金属", "矿产燃料", "纸墨", "陶瓷",
    "皮革", "油脂", "牲畜", "军需", "机具", "珍货",
)

#: 商品维 → 品目。**键集必须 == GOODS_DIMS**（`validate()` 守之）。
#: 依据：原料按其用途、成品按其加工族、军需按其用途单列（与 `COMMODITY_KINDS` 的「军需」对齐）。
GOODS_CATEGORY: Dict[str, str] = {
    # ── 粮食 ──
    "米": "粮食", "麦": "粮食",
    # ── 茶 / 盐（专卖大宗，单列，便于与盐课/茶课读数对照）──
    "茶": "茶",
    "盐": "盐",
    # ── 丝织：生丝与丝织成品同族（同一条加工链）──
    "丝": "丝织", "绸": "丝织", "丝绸": "丝织",
    # ── 布帛：麻与麻/棉布成品 ──
    "麻": "布帛", "布": "布帛", "布料": "布帛",
    # ── 糖果：蔗、果、糖（甜味族）──
    "蔗": "糖果", "果": "糖果", "糖": "糖果",
    # ── 酿造：酒与酱醋 ──
    "wine": "酿造", "酱醋": "酿造",
    # ── 肉食 ──
    "meat": "肉食",
    # ── 药材 ──
    "药材": "药材",
    # ── 木材 / 石料（建材两族，与营造口径对齐）──
    "木": "木材", "木方": "木材",
    "石": "石料",
    # ── 金属：矿石、锭、精炼、铸币（都是金属本体，可再加工）──
    "铁": "金属", "铜": "金属", "锡": "金属", "金": "金属", "银": "金属",
    "熟铁": "金属", "精炼熟铜": "金属", "铁锭": "金属", "钢锭": "金属",
    "铜锭": "金属", "官铸铜钱": "金属",
    # ── 矿产燃料：黏土、煤、炭、硝、硫、薪（采掘/燃料族）──
    "黏土": "矿产燃料", "煤炭": "矿产燃料", "木炭": "矿产燃料",
    "硝石": "矿产燃料", "硫磺": "矿产燃料", "薪炭": "矿产燃料",
    # ── 纸墨：纸、墨、书籍、文房（文教族）──
    "纸": "纸墨", "纸张": "纸墨", "油墨": "纸墨",
    "文房四宝": "纸墨", "印造书籍": "纸墨",
    # ── 陶瓷 ──
    "精品瓷器": "陶瓷",
    # ── 皮革：生皮、熟皮、皮革 ──
    "皮毛": "皮革", "熟皮": "皮革", "皮革": "皮革",
    # ── 油脂 ──
    "食用油": "油脂",
    # ── 牲畜：活体与役畜 ──
    "牲畜": "牲畜", "马": "牲畜",
    # ── 军需：兵刃、火药、弹药、甲具、军衣、漕船（国家采购口径）──
    "兵刃器械": "军需", "火药": "军需", "火器弹药": "军需",
    "鞍具皮甲": "军需", "被服军衣": "军需", "漕船海舶": "军需",
    # ── 机具：通用机械件（中性中间物）──
    "机械构件": "机具", "机械零件": "机具",
    # ── 珍货：进口奢侈与精细器物（外销/赏赉口径）──
    "苏木": "珍货", "香药": "珍货", "珠宝": "珍货", "犀象": "珍货", "漆器": "珍货",
}


def category_of(dim: str) -> Optional[str]:
    """维 → 品目；未登记返回 `None`（**缺失≠"其他"**，调用方须显式处理）。"""
    return GOODS_CATEGORY.get(str(dim))


def category_goods(category: str) -> List[str]:
    """品目 → 其下维（按 `GOODS_CATEGORY` 插入序；未知品目返回 `[]`，不抛）。"""
    return [d for d, c in GOODS_CATEGORY.items() if c == str(category)]


def categories() -> Tuple[str, ...]:
    """全部品目（展示序）。"""
    return CATEGORY_ORDER


def validate(extra_dims: Optional[Sequence[str]] = None) -> List[str]:
    """自检：返回问题清单（空 = 通过）。供启动自检与用例调用。

    检查项：
    ① 每个 `GOODS_DIMS` 都有品目（缺失 → 报出维名）；
    ② 品目名都在 `CATEGORY_ORDER` 里（拼错 → 报出）；
    ③ 每个品目都非空（空品目 → 报出）；
    ④ `extra_dims`（运行时新增维）也必须有品目。
    """
    from content.data_constants import GOODS_DIMS

    problems: List[str] = []
    dims = list(GOODS_DIMS) + [str(d) for d in (extra_dims or ())]
    known = set(CATEGORY_ORDER)

    missing = [d for d in dims if d not in GOODS_CATEGORY]
    if missing:
        problems.append("未登记品目的维：%s" % (missing[:10],))

    bad_cat = sorted({c for c in GOODS_CATEGORY.values() if c not in known})
    if bad_cat:
        problems.append("品目名不在 CATEGORY_ORDER：%s" % (bad_cat[:10],))

    empty = [c for c in CATEGORY_ORDER if not category_goods(c)]
    if empty:
        problems.append("空品目：%s" % (empty[:10],))

    unknown_in_dims = [d for d in GOODS_CATEGORY if d not in set(GOODS_DIMS)]
    if unknown_in_dims:
        # 不是硬错误（可能是刚退役的维），但必须可见，免得"映射表悄悄长毛"
        problems.append("映射表含 GOODS_DIMS 之外的维（可能已退役）：%s"
                        % (unknown_in_dims[:10],))
    return problems


def note_new_dim(dim: str) -> Optional[str]:
    """运行时新增维的品目校验钩子：有品目返回之，无则**告警并返回 `None`**。

    🔴 刻意**不抛异常**：`register_raw_material` / `register_finished_good` 是 AI 建新货的
    既有通道，此处只做口径提示，不得打断注册。缺品目的后果是「该维不参与品目口径的
    嗜好/应税分解」，属可接受降级（不是账本错误）。
    """
    d = str(dim or "")
    if not d:
        return None
    cat = GOODS_CATEGORY.get(d)
    if cat is None:
        log.warning("goods_category: 新维 %r 未登记品目 —— 该维不参与品目口径的口味/应税分解；"
                    "如需参与，请在 content/goods_category.py 的 GOODS_CATEGORY 补一行", d)
    return cat


def _register_hook() -> None:
    """把 `note_new_dim` **向上登记**到 `data_constants.DIM_REGISTERED_HOOKS`。

    🔴 方向纪律：由本模块 import `data_constants`，**反之不行** ——
    `data_constants` 若 import 本模块即构成 `data_constants ↔ goods_category` 环，
    会被 `test_architecture_import_guard::test_no_new_cyclic_modules` 当场拦下（本批踩过）。
    钩子函数幂等：重复登记会被去重。
    """
    try:
        from content.data_constants import DIM_REGISTERED_HOOKS as _hooks
        if note_new_dim not in _hooks:
            _hooks.append(note_new_dim)
    except Exception as _e:                                      # noqa: BLE001
        log.warning("goods_category: 维注册钩子登记失败（%s）——运行时新维将得不到品目告警",
                    type(_e).__name__, exc_info=True)


_register_hook()
