# -*- coding: utf-8 -*-
"""作坊**货主（产权落点）**口径单点 —— M66（解除 M51 的 blocker）。

背景
----
实测：`owner_kind`/`owner_ref` 在 core 内**仅见 `construction_shadow`** ⇒ **107 作坊全无货主**，
`workshop_fund_shadow` 对每座报 `status="undefined"`（主线 D/E 卡口）。
Jev **choose A 0.665**：**只登记货主字段 + 幂等迁移**（官营 → `local:<路>`；民营 → `pop:<路>:商人`），
**不动任何钱**（营运资金/工资/利润接线留到 D 的下一批）。

划分规则**不臆造**：由**各作坊既有的收益语义**推导（逐条给依据）
------------------------------------------------------------------------
| 作坊 | 归属 | 依据（代码/裁定） |
|---|---|---|
| **酒坊** | **官营**（`local:<路>`） | 榷酒：酒课走 `state.wine_tax`（入内帑），收益归官府 ⇒ 官府专营 |
| **畜栏** | **民营**（`pop:<路>:商人`） | 产出为商品（meat 等），经工匠 `goods` 池由**民间成交**付钱（2026-10-08 用户裁定） |
| **麻坊** | **民营** | 成品（布）入工匠 `goods` 池、由民间成交付钱 |
| **丝坊** | **民营** | 成品（绸）入工匠 `goods` 池、由民间成交付钱 |

🔴 纪律
----
* **词表复用**：货主 id 用既有形式（`local:<路>` / `pop:<路>:商人`），**不新造**；
* **不臆造**：**未登记类型 / 判不出路** ⇒ `defined=False` + reason（**不猜**）；
* **幂等**：只填**缺失**字段，**不覆盖**既有 `owner`/`owner_ref`（读档/重复调用安全）；
* **不自持**：不产生与 POP 平行的存量载体（"作坊自持"已判违规，§3-1）；
* **零数值变化**：本模块只写 `state.workshops[wid]` 的 `owner`/`owner_kind`/`owner_reason` 三个字符串/枚举字段。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

#: 作坊类型 → `(owner_kind, 官营/民营, 依据)`
OWNER_BY_TYPE: Dict[str, Tuple[str, str, str]] = {
    "酒坊": ("local", "官营",
             "榷酒：酒课走 state.wine_tax（入内帑），收益归官府 ⇒ 官府专营；"
             "owner 取**路级官府**（地方府库已州府化，M37）"),
    "畜栏": ("pop:商人", "民营",
             "产出为商品（meat 等），经工匠 goods 池由**民间成交**付钱（2026-10-08 用户裁定）"),
    "麻坊": ("pop:商人", "民营", "成品（布）入工匠 goods 池、由民间成交付钱"),
    "丝坊": ("pop:商人", "民营", "成品（绸）入工匠 goods 池、由民间成交付钱"),
    # ---- M67 补漏（**配方面实有 6 型**，M66 只登记了 4 型）----
    #   `WORKSHOP_RECIPES` 里还有 `造纸坊`（麻→纸）与 `糖坊`（蔗→糖，G-6 产业链扩充）；
    #   其成品（纸/糖）与 绢/布 同路：**落 resources + 工匠 goods 池、由民间成交付钱**
    #   （见 `settlement_econ` 的 RESOURCE_DIMS 分支注释）⇒ 同属**民营**。
    "造纸坊": ("pop:商人", "民营",
               "成品（纸）与 绢/布 同路：入工匠 goods 池、由民间成交付钱（settlement_econ RESOURCE_DIMS 分支）"),
    "糖坊": ("pop:商人", "民营",
             "成品（糖）与 绢/布 同路：入工匠 goods 池、由民间成交付钱（settlement_econ RESOURCE_DIMS 分支）"),
    # ---- 2026-10-17 全审：M315/M316/M317 新增 13 型配方未登记货主 ----
    #   官营（钱监/官窑/军器/造船/印书/坑冶）⇒ `local:<路>`；民间皮革/被服/木作 ⇒ `pop:<路>:商人`。
    #   判据同 M66/M67：收益是否走官府账户（酒课式）或民间 goods 成交。
    "铸钱监": ("local", "官营", "钱监铸钱属国家货币主权，收益归官府 ⇒ 官营"),
    "官窑瓷坊": ("local", "官营", "官窑为官府窑场，精品瓷器供御/外销，收益归官府"),
    "兵器营造坊": ("local", "官营", "军器监系统官营作坊，产出军械不进入民间市场"),
    "火器制造坊": ("local", "官营", "火药火器属军国重器，官营管制"),
    "火药局": ("local", "官营", "火药局为官营军器机构，产出军需"),
    "造船作坊": ("local", "官营", "官营造船场承担漕船/战舰，收益归官府"),
    "印造经籍局": ("local", "官营", "国子监/印造局官刻书籍，收益归官府"),
    "冶铁作坊": ("local", "官营", "坑冶官营（与「铁」货主 state_operator 同口径）"),
    "冶铜熔铸所": ("local", "官营", "铜冶官营（与「铜」货主 state_operator 同口径）"),
    "木作机械坊": ("pop:商人", "民营", "木作/机械构件为民间工匠商品，入 goods 池成交"),
    "硝皮熟皮坊": ("pop:商人", "民营", "熟皮为民间皮革商品，入 goods 池成交"),
    "鞍具皮甲作": ("pop:商人", "民营", "鞍具皮甲为民间作坊商品（军需采购另计），入 goods 池成交"),
    "被服工坊": ("pop:商人", "民营", "被服军衣为民间作坊商品，入 goods 池成交"),
}

__all__ = ["OWNER_BY_TYPE", "workshop_type_of", "owner_for", "assign_owners",
           "survey_owner_assignment"]


def workshop_type_of(wid: Any) -> Optional[str]:
    """作坊 id（形如 `麻坊_京畿路_2`）⇒ 类型名；判不出 ⇒ `None`。"""
    if not isinstance(wid, str) or not wid:
        return None
    return wid.split("_")[0] or None


def owner_for(state, wid: str) -> Dict[str, Any]:
    """解析该作坊的**货主**（只读；不写 state）：`{defined, owner, owner_kind, reason}`。"""
    wtype = workshop_type_of(wid)
    if wtype is None:
        return {"defined": False, "owner": None, "owner_kind": None,
                "reason": "作坊 id 非法，无法判定类型"}
    rule = OWNER_BY_TYPE.get(wtype)
    if rule is None:
        return {"defined": False, "owner": None, "owner_kind": None,
                "reason": f"类型 {wtype!r} **未登记归属规则** ⇒ 不臆造（须先裁定并补表）"}
    kind, ownership, basis = rule
    route = None
    try:
        from core.domains.economy.seat_goods_readout import route_of_workshop
        route = route_of_workshop(state, wid)
    except Exception:                                       # noqa: BLE001
        log.warning("workshop_owner: 路名解析不可用 wid=%s", wid, exc_info=True)
    if not route:
        return {"defined": False, "owner": None, "owner_kind": None,
                "reason": f"判不出所属路（key={wid!r}）⇒ 不臆造地点"}
    owner = f"local:{route}" if kind == "local" else f"pop:{route}:商人"
    return {"defined": True, "owner": owner, "owner_kind": kind,
            "ownership": ownership, "reason": basis}


def assign_owners(state) -> Dict[str, Any]:
    """**幂等迁移**：给缺失货主的作坊补 `owner` / `owner_kind` / `owner_reason`。

    只填缺失（**不覆盖**既有值）；判不出归属的**跳过并计数**（不臆造）。返回统计。
    """
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"assigned": 0, "kept": 0, "undefined": 0, "reason": "无 state.workshops"}
    assigned = kept = undefined = 0
    samples = []
    for wid, row in ws.items():
        if not isinstance(row, dict):
            continue
        if row.get("owner") or row.get("owner_ref"):
            kept += 1
            continue
        rep = owner_for(state, wid)
        if not rep["defined"]:
            undefined += 1
            if len(samples) < 5:
                samples.append({"wid": wid, "reason": rep["reason"]})
            continue
        row["owner"] = rep["owner"]
        row["owner_kind"] = rep["owner_kind"]
        row["owner_reason"] = rep["reason"]
        assigned += 1
    return {"assigned": assigned, "kept": kept, "undefined": undefined,
            "undefined_samples": samples,
            "note": "只填缺失、不覆盖；判不出归属者跳过（不臆造）"}


def survey_owner_assignment(state) -> Dict[str, Any]:
    """只读对账：已登记/缺失/未定义计数 + 按类型分布（不写 state）。"""
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"total": 0, "reason": "无 state.workshops"}
    by_kind: Dict[str, int] = {}
    missing = 0
    undefined = 0
    for wid, row in ws.items():
        owner = row.get("owner") or row.get("owner_ref") if isinstance(row, dict) else None
        if not owner:
            missing += 1
            if not owner_for(state, wid)["defined"]:
                undefined += 1
            continue
        kind = str((row or {}).get("owner_kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {"total": len(ws), "with_owner": len(ws) - missing, "missing": missing,
            "undefined_rule": undefined, "by_kind": by_kind}
