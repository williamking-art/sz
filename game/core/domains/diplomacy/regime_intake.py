# -*- coding: utf-8 -*-
"""占领的经济后果（P5.6，2026-10-19）。

口径（用户裁定）：
1. **损失比例不写死**：由**天道**出「掠夺烈度」档位（无/轻/中/重/极重 + 叙事），
   程序把档位换算成系数（架构纪律：天道只出档位，数值一律程序算）。
2. 天道缺档时**不假装无事**：按**攻城方式**（受降/围城/力攻/屠城）程序推导，并记录来源。
3. 损失落在 POP 上：人口 / 财富 / 存粮；掠夺所得（损失财富的一半）入占领方 treasury。
4. 税基残破 devastation 由**同一档位**决定起始值，占领方按残破度征税（**不冻结**），
   每月 +0.10 恢复，封顶 1.0；归还后残破保留、掠夺不退。

天道契约（待接线为独立 AI 契约，现支持注入/provider）：
    state._occupation_ai = {"loot_severity": "重", "note": "力攻破城，纵兵三日"}

也支持注册 provider：register_occupation_severity_provider(fn)，
fn(state, region_ids) -> {"loot_severity": 档位, "note": ...}。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["apply_occupation_damage", "regime_intake", "collect_occupation_tax",
           "recover_devastation", "resolve_severity", "severity_profile",
           "register_occupation_severity_provider",
           "OCCUPATION_SEVERITY_LEVELS", "CAPTURE_TYPE_DEFAULT_SEVERITY",
           "DEVASTATION_RECOVERY", "TAX_RATE_ON_WEALTH", "LOOT_SHARE"]

OCCUPATION_SEVERITY_LEVELS = ("无", "轻", "中", "重", "极重")

_SEVERITY_LOSS: Dict[str, Tuple[float, float, float]] = {
    "无": (0.000, 0.000, 0.000),
    "轻": (0.005, 0.04, 0.04),
    "中": (0.015, 0.09, 0.09),
    "重": (0.030, 0.15, 0.15),
    "极重": (0.060, 0.30, 0.30),
}

_SEVERITY_DEVASTATION: Dict[str, float] = {
    "无": 0.95, "轻": 0.80, "中": 0.70, "重": 0.60, "极重": 0.45,
}

CAPTURE_TYPE_DEFAULT_SEVERITY = {
    "受降": "轻", "围城": "中", "力攻": "重", "屠城": "极重",
}

DEVASTATION_RECOVERY = 0.10
TAX_RATE_ON_WEALTH = 0.01
LOOT_SHARE = 0.5

_PROVIDERS: List[Callable] = []


def register_occupation_severity_provider(fn: Callable) -> None:
    _PROVIDERS.append(fn)


def _slot(state) -> Dict[str, Any]:
    got = getattr(state, "_occupation_ai", None)
    return got if isinstance(got, dict) else {}


def _ask_providers(state, region_ids: List[str]) -> Dict[str, Any]:
    for fn in reversed(_PROVIDERS):
        try:
            got = fn(state, region_ids)
            if isinstance(got, dict) and got.get("loot_severity") in OCCUPATION_SEVERITY_LEVELS:
                return got
        except Exception:  # noqa: BLE001
            continue
    return {}


def resolve_severity(state, region_ids: List[str], *, capture_type: str = "") -> Dict[str, Any]:
    """天道档位优先；缺档按攻城方式推导；都缺 ⇒ 中 + 明确来源。"""
    slot = _slot(state)
    if slot.get("loot_severity") in OCCUPATION_SEVERITY_LEVELS:
        return {"severity": slot["loot_severity"], "source": "天道",
                "note": slot.get("note") or ""}
    prov = _ask_providers(state, region_ids)
    if prov:
        return {"severity": prov["loot_severity"], "source": "天道(provider)",
                "note": prov.get("note") or ""}
    ct = str(capture_type or "").strip()
    if ct in CAPTURE_TYPE_DEFAULT_SEVERITY:
        return {"severity": CAPTURE_TYPE_DEFAULT_SEVERITY[ct], "source": "程序推导(攻城方式)",
                "note": "天道缺档；按 %s 推导" % ct}
    return {"severity": "中", "source": "程序兜底(缺档且无攻城方式)",
            "note": "天道与我方推导均缺档，取中性档——不是精确值"}


def severity_profile(severity: str) -> Dict[str, Any]:
    sev = severity if severity in OCCUPATION_SEVERITY_LEVELS else "中"
    sz, wl, gr = _SEVERITY_LOSS[sev]
    return {"severity": sev, "size_loss": sz, "wealth_loss": wl, "grain_loss": gr,
            "devastation_start": _SEVERITY_DEVASTATION[sev]}


def _song_seat_pops(state, route: str, seat: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None) or {}
    row = ((prefs.get(route) or {}).get("seats") or {}).get(seat)
    if not isinstance(row, dict):
        return None
    pops = row.get("pops")
    return pops if isinstance(pops, dict) else None


def apply_occupation_damage(state, region_ids: List[str], *, to_regime: str,
                            capture_type: str = "") -> Dict[str, Any]:
    book = getattr(state, "regions", None) or {}
    sev = resolve_severity(state, region_ids, capture_type=capture_type)
    prof = severity_profile(sev["severity"])
    lost = {"size": 0, "wealth": 0, "grain": 0}
    loot = 0
    touched: List[str] = []
    skipped: List[str] = []
    seat_gap: List[str] = []
    for rid in region_ids:
        r = book.get(rid)
        if not isinstance(r, dict) or r.get("level") != "T1":
            continue
        if isinstance(r.get("devastation"), (int, float)):
            skipped.append(rid)
            continue
        r["devastation"] = prof["devastation_start"]
        r["loot_severity"] = prof["severity"]
        touched.append(rid)
        ref = r.get("prefecture_ref") or {}
        if ref.get("route"):
            seat_gap.append(rid)
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
            dsz = int(round(sz * prof["size_loss"]))
            dwl = int(round(wl * prof["wealth_loss"]))
            dgr = int(round(gr * prof["grain_loss"]))
            v["size"], v["wealth"], v["grain"] = sz - dsz, wl - dwl, gr - dgr
            lost["size"] += dsz
            lost["wealth"] += dwl
            lost["grain"] += dgr
            loot += int(round(dwl * LOOT_SHARE))
    if loot:
        info = (getattr(state, "external_regimes", None) or {}).get(to_regime)
        if isinstance(info, dict):
            info["treasury"] = int(info.get("treasury") or 0) + loot
    return {"ok": True, "touched": touched, "skipped": skipped,
            "seat_write_gap": seat_gap, "lost": lost, "loot": loot,
            "severity": prof["severity"], "severity_source": sev["source"],
            "severity_note": sev.get("note"), "devastation": prof["devastation_start"]}


def regime_intake(state, regime: str) -> Dict[str, Any]:
    book = getattr(state, "regions", None) or {}
    t1 = [dict(r, region_id=rid) for rid, r in book.items()
          if isinstance(r, dict) and r.get("owner") == regime and r.get("level") == "T1"]
    pop_people = 0
    pop_known = False
    land_total = 0
    land_missing: List[str] = []
    devs: List[float] = []
    tax_base = 0
    for r in t1:
        dev = float(r.get("devastation") if isinstance(r.get("devastation"), (int, float)) else 1.0)
        devs.append(dev)
        ref = r.get("prefecture_ref") or {}
        pops = (_song_seat_pops(state, str(ref["route"]), str(ref.get("seat")))
                if ref.get("route") else r.get("pop"))
        if isinstance(pops, dict):
            pop_known = True
            w = 0
            for cls, v in pops.items():
                if isinstance(v, dict):
                    pop_people += int(v.get("size") or 0)
                    w += int(v.get("wealth") or 0)
            tax_base += int(w * dev * TAX_RATE_ON_WEALTH)
        if ref.get("route"):
            land_missing.append(r.get("region_id"))
        elif isinstance(r.get("land"), (int, float)):
            land_total += int(r["land"])
        else:
            land_missing.append(r.get("region_id"))
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
        "note": "用户裁定：不冻结；烈度由天道出档、程序换算；税按残破度征",
    }


def collect_occupation_tax(state) -> Dict[str, Any]:
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
        if r.get("owner_at_init") in (None, owner):
            continue
        dev = float(r.get("devastation") if isinstance(r.get("devastation"), (int, float)) else 1.0)
        ref = r.get("prefecture_ref") or {}
        if ref.get("route"):
            continue
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
