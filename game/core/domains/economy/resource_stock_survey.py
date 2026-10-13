# -*- coding: utf-8 -*-
"""商品/物料存量（`state.resources`）州府化 —— 前置**只读取证**（M63）。

背景：`state.resources` 是**全国口径**（`{dim: {stock, cap}}`），M41–M62 的多个只读读数依赖它。
主线「仓储/商品存量」要求把它州府化，但 AGENTS.md/M37 的教训是**先桥后沉、顺序不可颠倒**。
本模块**只取证、不下沉、不改数值**（Jev choose A 0.693）。

三件读数
--------
1. `stock_summary(state)`：逐维 `stock`/`cap`/**可读性**（缺失≠0）+ 合计 + cap 缺失维清单；
2. `direct_write_sites()`：**写点台账**（file / marker / 分类 / 说明）——`marker` 是源码里必须存在的
   片段，由 `test_resource_stock_survey.py` **存在性用例**兜底，**台账不会腐烂**；
3. `mediation_status()`：探 `engine.state_applier` 是否可读，以及其公开集合里是否提到
   `resources`/`stock` ⇒ 判断「写 stock 是否经 applier 中介」。

🔴 关键区分（本批取证结论，见 `specs/cross-cutting/商品物料存量州府化_前置取证_2026-10-13.md`）：
**`resources` 的 `stock` 写入不经过 applier**（11 处直接写点即证），而 **M40b 的耦合对象是
`storage` 字段** ⇒ 二者**不是同一物**，M40c 的 blocker **不能**直接引用 M40b 的结论。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: 写点台账：`(相对 game/ 的路径, 源码片段 marker, 方向, 说明, 已否走桥)`
#: 🔴 marker 必须能在源码里逐字存在（存在性用例兜底）；改动写点时请同步台账。
#: **`已否走桥`**：M64a「先桥」进度——`True` 表示该点已「先问桥、未接管则回落原写法」。
DIRECT_WRITE_SITES: Tuple[Tuple[str, str, str, str, bool], ...] = (
    ("core/domains/production/production_chain.py",
     'slot["stock"] = stock + n', "入", "生产链 `_write_warehouse`：入国库仓（返回实际入账量）",
     True),
    ("core/domains/production/farm_procurement.py",
     'slot["stock"] = int(slot.get("stock", 0) or 0) + take', "入", "和买入仓（有路）", True),
    ("core/settlement_econ.py",
     '_gr_raw["stock"] = n', "入/出", "粮维写回（**量语义是 total 非增量** ⇒ 需 `stock_set` 语义，本批未桥）",
     False),
    ("core/settlement_econ.py",
     '_slot["stock"] = max(0, _cur_s - int(round(got)))', "出", "作坊投料扣减（可定路）", True),
    ("core/settlement_econ.py",
     '_slot["stock"] = min(_cap, int(round(_new))) if _cap > 0 else int(round(_new))', "入",
     "作坊产出入仓（cap 截断；可定路）", True),
    ("core/material_market.py",
     'base["stock"] = stock', "写", "物料市场基座写（**全国口径、无路**）", False),
    ("core/material_market.py",
     'slot["stock"] = max(0, int(round(rest_stock)))', "出", "官仓售料（**全国口径、无路**）", False),
    ("core/material_market.py",
     'dslot["stock"] = int(_read_int(dslot.get("stock")) or 0)', "入",
     "买入入仓（**全国口径、无路**）", False),
    ("core/material_market.py",
     'slot["stock"] = max(0, int(round(left_stock)))', "出", "官仓领料（**全国口径、无路**）", False),
    ("core/domains/economy/settlement_econ_helpers.py",
     '_res["stock"] = max(0, _cur_stock - _want_take)', "出", "铸钱扣铜料（**全国口径**）", False),
    ("core/settlement_finance.py",
     '_slot["stock"] = _cur + _taken', "入", "熔铜池溢出 → 铜料入仓（**全国口径**）", False),
)

#: 只读访问方（**不作为写点**，列出以说明改动的读数影响面）
READONLY_CONSUMERS = (
    "core/domains/economy/stock_identity.py（库存快照/Δ）",
    "core/domains/economy/stock_flow.py（流量账登记）",
    "core/domains/economy/material_trade_ops.py（供料按存量）",
    "core/domains/production/settlement_agri.py（材料成本）",
    "core/civil_building.py（营造扣料）",
)

__all__ = ["SCHEMA_VERSION", "DIRECT_WRITE_SITES", "READONLY_CONSUMERS",
           "direct_write_sites", "stock_summary", "mediation_status"]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def direct_write_sites() -> List[Dict[str, Any]]:
    """写点台账（副本，含 `bridged` 桥接进度）。"""
    return [{"file": f, "marker": m, "direction": d, "note": n, "bridged": bool(b)}
            for f, m, d, n, b in DIRECT_WRITE_SITES]


def bridge_coverage() -> Dict[str, Any]:
    """**先桥**进度：`{total, bridged, pending, pending_files}`（M64a 用；不靠嘴说覆盖率）。"""
    sites = direct_write_sites()
    pending = [s for s in sites if not s["bridged"]]
    return {"total": len(sites), "bridged": len(sites) - len(pending),
            "pending": len(pending),
            "pending_files": sorted({s["file"] for s in pending}),
            "note": ("`bridged=True` ＝ 该点已「先问桥、未接管则回落原写法」；"
                     "未桥接点多为**全国口径、无路**（见各点 note），按 Jev 甲 0.817 **保持全国池**")}


def stock_summary(state) -> Dict[str, Any]:
    """逐维 `stock`/`cap`/可读性 + 合计 + cap 缺失维（**只读**；缺失≠0）。"""
    res = getattr(state, "resources", None)
    if not isinstance(res, dict):
        return {"readable": False, "reason": "无 state.resources（缺失≠0）", "dims": {}, "total": None}
    dims: Dict[str, Any] = {}
    total = 0.0
    total_ok = True
    no_cap: List[str] = []
    for dim, cell in res.items():
        stock = _num(cell.get("stock")) if isinstance(cell, dict) else _num(cell)
        cap = _num(cell.get("cap")) if isinstance(cell, dict) else None
        dims[str(dim)] = {"stock": None if stock is None else int(stock),
                          "cap": None if cap is None else int(cap)}
        if stock is None:
            total_ok = False
        else:
            total += stock
        if cap is None:
            no_cap.append(str(dim))
    return {"readable": True, "reason": None, "dims": dims,
            "total": int(total) if total_ok else None,
            "cap_missing_dims": sorted(no_cap),
            "note": "全国口径（**不是**本地市场）；州府化前置见本模块 docstring 与取证文档"}


def mediation_status() -> Dict[str, Any]:
    """探「写 `resources.stock` 是否经 `engine.state_applier` 中介」。

    `rules_hit`：applier 模块的公开集合里提到 `resources`/`stock` 的名字（命中即需人工细看）。
    结论以**写点台账**（11 处直接写）为准 —— 本函数只报"探到了什么"，不在探不到时下断言。
    """
    out: Dict[str, Any] = {"applier_available": False, "rules_hit": [], "reason": None}
    try:
        from engine import state_applier as sa
    except Exception as e:                                  # noqa: BLE001
        out["reason"] = f"engine.state_applier 不可导入：{type(e).__name__}"
        return out
    out["applier_available"] = True
    for name in dir(sa):
        if name.startswith("__"):
            continue
        try:
            v = getattr(sa, name)
        except Exception:                                   # noqa: BLE001
            continue
        if isinstance(v, (tuple, list, set, frozenset)):
            for x in v:
                sx = str(x)
                if "resources" in sx or "stock" in sx:
                    out["rules_hit"].append(f"{name}:{sx}")
                    break
    out["reason"] = None if out["rules_hit"] else \
        ("applier 的公开集合里**未见** resources/stock ⇒ 与 11 处直接写点一致："
         "stock 写入**不经** applier（**但这是探针级证据，非完备证明**）")
    return out
