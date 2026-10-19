# -*- coding: utf-8 -*-
"""占领的经济后果（P5.6，2026-10-19；**用户裁定覆盖 Jev 的「冻结」口径**）。

用户原话：「怎么会冻结税产呢？占领后会产生财产流失，这个我理解；为什么会冻结呢」

正确模型：
1. **一次性财产流失**（掠夺/逃户）：占领当刻，该州府 POP 人口 −3%、财富 −15%、存粮 −15%；
   掠夺所得（损失财富的一半）入占领方 treasury；
2. **税基残破**：残破度 `devastation` 从 0.6 起，占领方**按残破度征税**（不冻结！）；
3. **逐月恢复**：每月 +0.10，封顶 1.0；归还后残破**保留**（战争破坏不返还），掠夺所得不退。

数据来源：
- 外邦 T1：`region["pop"]`（6 类 size/wealth/grain）；
- 宋 T1：`prefectures[路][seats][治所]["pops"]`（真账）；宋座财产损失需走桥，**本轮只计税不改账**（登记 gap）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["apply_occupation_damage", "regime_intake", "collect_occupation_tax",
           "recover_devastation", "DEVASTATION_START", "DEVASTATION_RECOVERY",
           "TAX_RATE_ON_WEALTH"]

#: 占领当刻残破度
DEVASTATION_START = 0.6
#: 每月恢复步长
DEVASTATION_RECOVERY = 0.10
#: 月度税率（对可征财富的比例；残破度直接乘在税基上）
TAX_RATE_ON_WEALTH = 0.01
#: 一次性流失：人口 / 财富 / 存粮
DAMAGE_SIZE = 0.03
DAMAGE_WEALTH = 0.15
DAMAGE_GRAIN = 0.15
#: 掠夺所得占损失财富的比例
LOOT_SHARE = 0.5


def _song_seat_pops(state, route: str, seat: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None) or {}
    row = ((prefs.get(route) or {}).get("seats") or {}).get(seat)
    if not isinstance(row, dict):
        return None
    pops = row.get("pops")
    return pops if isinstance(pops, dict) else None


def apply_occupation_damage(state, region_ids: List[str], *, to_regime: str) -> Dict[str, Any]:
    """占领当刻：一次性流失 + 设残破度 + 掠夺入账（**幂等**：已有 devastation 则跳过）。"""
    book = getattr(state, "regions", None) or {}
    lost = {"size": 0, "wealth": 0, "grain": 0}
    loot = 0
    touched: List[str] = []
    skipped: List[str] = []
    for rid in region_ids:
        r = book.get(rid)
        if not isinstance(r, dict) or r.get("level") != "T1":
            continue
        if isinstance(r.get("devastation"), (int, float)):
            skipped.append(rid)
            continue
        r["devastation"] = DEVASTATION_START
        touched.append(rid)
        ref = r.get("prefecture_ref") or {}
        if ref.get("route"):      # 宋座：本轮只设残破度，不改财产（需桥，登记 gap）
            continue
        pops = r.get("pop")
        if not isinstance(pops, dict):
            continue
        for cls, v in pops.items():
            if not isinstance(v, dict):
                continue
            sz = int(v.get("size") or 0)
            wl = int(v.get("wealth") or 0)
            gr = int(v.get("grain") or 0)
            dsz = int(round(sz * DAMAGE_SIZE))
            dwl = int(round(wl * DAMAGE_WEALTH))
            dgr = int(round(gr * DAMAGE_GRAIN))
            v["size"], v["wealth"], v["grain"] = sz - dsz, wl - dwl, gr - dgr
            lost["size"] += dsz
            lost["wealth"] += dwl
            lost["grain"] += dgr
            loot += int(round(dwl * LOOT_SHARE))
    if loot:
        info = (getattr(state, "external_regimes", None) or {}).get(to_regime)
        if isinstance(info, dict):
            info["treasury"] = int(info.get("treasury") or 0) + loot
    return {"ok": True, "touched": touched, "skipped": skipped, "lost": lost,
            "loot": loot, "devastation": DEVASTATION_START}


def regime_intake(state, regime: str) -> Dict[str, Any]:
    """接收方口径：人口/土地 + **可征税产（按残破度）**。"""
    book = getattr(state, "regions", None) or {}
    t1 = [dict(r, region_id=rid) for rid, r in book.items()
          if isinstance(r, dict) and r.get("owner") == regime and r.get("level") == "T1"]
    pop_people = 0
    pop_known = False
    wealth_total = 0
    tax_base = 0
    land_total = 0
    land_missing: List[str] = []
    devs: List[float] = []
    for r in t1:
        dev = float(r.get("devastation") if isinstance(r.get("devastation"), (int, float)) else 1.0)
        devs.append(dev)
        ref = r.get("prefecture_ref") or {}
        pops = (_song_seat_pops(state, str(ref["route"]), str(ref.get("seat")))
                if ref.get("route") else r.get("pop"))
        if isinstance(pops, dict):
            pop_known = True
            for cls, v in pops.items():
                if isinstance(v, dict):
                    pop_people += int(v.get("size") or 0)
                    wealth_total += int(v.get("wealth") or 0)
        if ref.get("route"):
            land_missing.append(r.get("region_id"))
        elif isinstance(r.get("land"), (int, float)):
            land_total += int(r["land"])
        else:
            land_missing.append(r.get("region_id"))
        tax_base += int(wealth_total * 0)  # 占位避免误算；下面按州府分别累计
    # 逐州府累计可征税（wealth × dev × 税率）
    for r in t1:
        dev = float(r.get("devastation") if isinstance(r.get("devastation"), (int, float)) else 1.0)
        ref = r.get("prefecture_ref") or {}
        pops = (_song_seat_pops(state, str(ref["route"]), str(ref.get("seat")))
                if ref.get("route") else r.get("pop"))
        if not isinstance(pops, dict):
            continue
        w = sum(int((v or {}).get("wealth") or 0) for v in pops.values() if isinstance(v, dict))
        tax_base += int(w * dev * TAX_RATE_ON_WEALTH)
    avg_dev = round(sum(devs) / len(devs), 3) if devs else None
    return {
        "regime": regime,
        "t1_count": len(t1),
        "population_people": pop_people if pop_known else None,
        "population_wan": round(pop_people / 10000.0, 2) if pop_known else None,
        "population_reason": None if pop_known else "州府人口缺失（缺失≠0）",
        "land": land_total if not land_missing else None,
        "land_missing_regions": land_missing,
        "devastation_avg": avg_dev,
        "tax_base": tax_base,
        "collectable_tax": tax_base,
        "tax_output_frozen": False,
        "note": "用户裁定：不冻结；按残破度征税（残破逐月恢复）",
    }


def collect_occupation_tax(state) -> Dict[str, Any]:
    """月度：占领方按残破度征税（从 POP 财富扣，入政权 treasury）；宋座本轮只计不动账。"""
    book = getattr(state, "regions", None) or {}
    regimes = getattr(state, "external_regimes", None) or {}
    total = 0
    per: Dict[str, int] = {}
    for rid, r in book.items():
        if not isinstance(r, dict) or r.get("level") != "T1":
            continue
        owner = r.get("owner")
        if not owner or owner == "宋":
            continue
        # 只对**被占领地**征税（owner ≠ 建表时归属）；本国固有领地由既有外邦结算负责，防双征
        if r.get("owner_at_init") in (None, owner):
            continue
        dev = float(r.get("devastation") if isinstance(r.get("devastation"), (int, float)) else 1.0)
        ref = r.get("prefecture_ref") or {}
        if ref.get("route"):
            continue          # 宋座：财产损失/征税需走桥（登记 gap）
        pops = r.get("pop")
        if not isinstance(pops, dict):
            continue
        due = 0
        for cls, v in pops.items():
            if not isinstance(v, dict):
                continue
            w = int(v.get("wealth") or 0)
            take = int(round(w * TAX_RATE_ON_WEALTH * dev))
            if take > 0:
                v["wealth"] = w - take
                due += take
        if due:
            info = regimes.get(owner)
            if isinstance(info, dict):
                info["treasury"] = int(info.get("treasury") or 0) + due
            per[owner] = per.get(owner, 0) + due
            total += due
    return {"ok": True, "collected": total, "by_regime": per}


def recover_devastation(state, *, step: float = DEVASTATION_RECOVERY) -> Dict[str, Any]:
    """月度：残破度恢复（封顶 1.0）；返回恢复条数。"""
    book = getattr(state, "regions", None) or {}
    n = 0
    for r in book.values():
        if not isinstance(r, dict):
            continue
        d = r.get("devastation")
        if isinstance(d, (int, float)) and d < 1.0:
            r["devastation"] = min(1.0, round(float(d) + step, 4))
            n += 1
    return {"ok": True, "recovered": n}
