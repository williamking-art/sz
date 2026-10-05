# -*- coding: utf-8 -*-
"""宋祚 · 宋侧产出链（批 4 · 外邦省域产业链设计 §11 S1/S2）。

**S1 原料产出链**：按路 `yields`（年额）÷ 12 × 建筑等级乘数 → 全局 `state.resources`
（单一真账，消费侧零改动）。消除「原料只出不进」缺口（设计 §0.3）。

**S2 商品单通道**：`_settle_granary` 的 POP 直产段（工匠 size→布/绸）并入本模块的
作坊 PM 口径——**成品唯一产出通道是作坊**；直产删除后带**不断供护栏**（供给不足
立即回退到旧直产，保证成交率 ≥ 改造前 90%）。

纪律：
- 产量是唯一增量；**建材三材落本路`商人` POP 的 `goods`**（B4-1 收窄版 B），
  其余原料仍只写 `state.resources[dim]["stock"]`；全程不碰钱/POP wealth；
- 旧档缺 yields 键 → `setdefault` 幂等跳过，不抛异常；
- `test_pop_identity._STEPS` 镜像须同步新步（调用侧在 settlement.py 接线时登记）。
"""
from __future__ import annotations

from typing import Dict, Optional

__all__ = ["settle_production_chain", "goods_direct_production_backup",
           "PRODUCTION_BUILDING_MULT", "BUILDING_MATERIAL_DIMS"]

#: **建材三材**（B4-1 收窄版 B · 2026-11）：这三样改由**本路商人 POP 持有**，
#: 工程/营造/农事经`material_market` **真付货款**采购，不再从国家仓"白扣"。
#:
#: 为什么只收窄到这三样（其余 8+ 维度不动）：
#: 建材的**消费侧只有三处**——`settlement_tech`（工程领料）、`civil_building`
#: （民居/货栈）、`settlement_agri`（维护料）。仓库其余引用是粮/铜/麻/丝等，
#: 与建材市场无关，一并改会把"接一个市场"变成"重排全链"。
BUILDING_MATERIAL_DIMS = ("木", "石", "铁")

# 建筑等级 → 产出乘数（与外邦 LV_OUTPUT_BONUS 同口径：1 + 0.05×(lv−1)）
PRODUCTION_BUILDING_MULT = 0.05
_BUILDING_LV_MAX = 5


def _building_mult(p: dict) -> float:
    """该路建筑等级综合乘数（取 POP 建筑最高等级；无建筑 → 1.0）。"""
    best_lv = 1
    for entry in (p.get("buildings") or {}).values():
        lv = 1
        if isinstance(entry, dict):
            try:
                lv = int(entry.get("lv", 1) or 1)
            except (TypeError, ValueError):
                lv = 1
        else:
            try:
                lv = int(entry or 1)
            except (TypeError, ValueError):
                lv = 1
        best_lv = max(best_lv, min(_BUILDING_LV_MAX, lv))
    return 1.0 + PRODUCTION_BUILDING_MULT * max(0, best_lv - 1)


def _write_warehouse(resources: dict, dim: str, add: int) -> None:
    """入国家仓（既有口径，**总量守恒的默认去向**）。"""
    slot = resources.setdefault(dim, {"stock": 0, "cap": 50_000})
    cap = int(slot.get("cap", 50_000) or 50_000)
    stock = int(slot.get("stock", 0) or 0)
    n = min(int(add), max(0, cap - stock))
    if n > 0:
        slot["stock"] = stock + n


def _pick_seat(p: dict, dim: str) -> Optional[str]:
    """按**产地证据**挑一个治所；无证据 ⇒ `None`（扁平区，**不伪拆**）。"""
    try:
        from core.material_holding import seat_weights_for
        w = seat_weights_for(p.get("name") or "", dim)
    except Exception:                                   # noqa: BLE001
        return None
    if not w:
        return None
    try:
        return max(w, key=lambda kv: kv[1])[0]
    except Exception:                                   # noqa: BLE001
        return None
def settle_production_chain(state, log: Optional[list] = None) -> Dict[str, int]:
    """S1 原料产出链：各路 `yields` 年额 ÷ 12 × 建筑乘数 → `state.resources`。

    返回 `{dim: 本月产量}`（诊断用）；产量封顶后溢出截断（不超 cap）。
    """
    logs = log if isinstance(log, list) else []
    produced: Dict[str, int] = {}
    _no_merchant_goods: list = []


    resources = getattr(state, "resources", None)
    if not isinstance(resources, dict):
        return produced
    # 归属解析：未裁定 ⇒ None ⇒ 维持原入仓口径
    def _resolve(_dim):
        from core.material_holding import resolve_holder as _rh
        return _rh(_dim)
    from content.data import RAW_DIMS
    for name, p in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(p, dict):
            continue
        yields = p.get("yields") or {}
        if not isinstance(yields, dict):
            continue
        mult = _building_mult(p)
        for dim in RAW_DIMS:
            annual = yields.get(dim)
            if annual is None:
                continue
            try:
                annual = float(annual)
            except (TypeError, ValueError):
                continue
            if annual <= 0:
                continue
            q = int(annual / 12.0 * mult)
            if q <= 0:
                continue
            if dim in BUILDING_MATERIAL_DIMS:
                # ⚠️ **回退（2026-11）**：曾试把建材改投商人 `goods`（B4-1 收窄版 B），
                # 但料款与工钱**共用出资阶层**会互相抢钱，且 `civil_building` 的
                # 缺料判定与实际采购**两处口径不一致**，导致失败集合随用例顺序漂移、
                # 难以收敛。故恢复"建材入国家仓、领料直接扣减"的既有口径。
                # B4-1 的"本地市场"仍为**未接线**（见 tasks.md 三选项与阻塞说明）——
                # 保留本常量为将来收窄版实现预留口径单点。
                pass
            slot = resources.setdefault(dim, {"stock": 0, "cap": 50_000})
            cap = int(slot.get("cap", 50_000) or 50_000)
            stock = int(slot.get("stock", 0) or 0)
            add = min(q, max(0, cap - stock))
            if add > 0:
                # ══ T3（2026-10-05）按归属分派 ══
                # 料不再一律进国家仓：`resolve_holder` 判给 POP 切片则落该路径农户；
                # 判给国库/内帑则**维持原行为**（零风险）；**Missing 也不阻断供给**。
                # 🔴 守恒：仓库存量转出多少、农户 holdings 就增多少，**总量不变**。
                _holder = _resolve(dim)
                if not _holder or not _holder.startswith("pop:"):
                    # 国库 / 内帑 / Missing ⇒ 走既有入仓路径（口径不变）
                    _write_warehouse(resources, dim, add)
                    produced[dim] = produced.get(dim, 0) + add
                    continue
                try:
                    _cls = _holder.split(":")[1]
                except IndexError:
                    _write_warehouse(resources, dim, add)
                    produced[dim] = produced.get(dim, 0) + add
                    continue
                _pops = p.get("pops") or {}
                _tgt = _pops.get(_cls) if isinstance(_pops, dict) else None
                if not isinstance(_tgt, dict):
                    # 该路无此阶层 ⇒ 证据不足，**不臆造持有人**，如实回落国家仓
                    _write_warehouse(resources, dim, add)
                    produced[dim] = produced.get(dim, 0) + add
                    continue
                _goods = _tgt.get("goods")
                if not isinstance(_goods, dict):
                    _goods = {}
                    _tgt["goods"] = _goods
                try:
                    from core.material_holding import goods_add as _gadd
                    _gadd(_goods, dim, add, _pick_seat(p, dim))
                    produced[dim] = produced.get(dim, 0) + add
                except Exception:                       # noqa: BLE001
                    # 归属分派失败 ⇒ **如实回落国家仓**，不吞料、不造钱
                    _write_warehouse(resources, dim, add)
                    produced[dim] = produced.get(dim, 0) + add
    if produced:
        top = sorted(produced.items(), key=lambda kv: -kv[1])[:4]
        logs.append("[产出链] 诸路原料产出：" + "、".join(f"{d}+{q}" for d, q in top))
    if _no_merchant_goods:
        # 缺 `goods` 槽的旧档/异常路：建材**未交付**（不是"入仓"）——如实留痕，
        # 不静默回落国家仓（回落＝无付款腿的白扣）。
        logs.append(f"[产出链][WARN] {len(_no_merchant_goods)} 路建材未交付"
                    f"（商人缺 goods 槽）：{'、'.join(_no_merchant_goods[:3])}"
                    f"{'等' if len(_no_merchant_goods) > 3 else ''}")
    return produced


def goods_direct_production_backup(artisan: dict, merchant: dict,
                                   prod_mult: float = 1.0) -> Dict[str, int]:
    """S2 不断供护栏：旧直产口径（工匠 size→布/绸 + 商人贩运）备用。

    仅在作坊单通道供给不足时调用，保证商品成交率 ≥ 改造前 90%。
    返回 `{gdim: 本月补产}`。
    """
    added: Dict[str, int] = {}
    # 2026-10-03：`goods` 已含 `治所→{dim:n}` 州府桶，**只有数值键才是商品维**。
    # 旧写法 `for gdim in list(goods)` 无过滤，会把桶（dict）当维名参与算术并覆写它。
    from core.material_holding import commodity_dims
    if isinstance(artisan, dict):
        for gdim in commodity_dims(artisan.get("goods")):
            _add = int(artisan.get("size", 0) * (0.10 if gdim == "绸" else 0.20) * prod_mult)
            if _add > 0:
                artisan.setdefault("goods", {})[gdim] = (
                    int(artisan["goods"].get(gdim, 0) or 0) + _add)
                added[gdim] = added.get(gdim, 0) + _add
    if isinstance(merchant, dict):
        for gdim in commodity_dims(merchant.get("goods")):
            _add = int(merchant.get("size", 0) * 0.10 * prod_mult)
            if _add > 0:
                merchant.setdefault("goods", {})[gdim] = (
                    int(merchant["goods"].get(gdim, 0) or 0) + _add)
                added[gdim] = added.get(gdim, 0) + _add
    return added
