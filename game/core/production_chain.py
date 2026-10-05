# -*- coding: utf-8 -*-
"""宋祚 · 宋侧产出链（批 4 · 外邦省域产业链设计 §11 S1/S2）。

**S1 原料产出链**：按路 `yields`（年额）÷ 12 × 建筑等级乘数 → 全局 `state.resources`
（单一真账，消费侧零改动）。消除「原料只出不进」缺口（设计 §0.3）。

**S2 商品单通道**：`_settle_granary` 的 POP 直产段（工匠 size→布/绸）并入本模块的
作坊 PM 口径——**成品唯一产出通道是作坊**；直产删除后带**不断供护栏**（供给不足
立即回退到旧直产，保证成交率 ≥ 改造前 90%）。

纪律：
- 产量是唯一增量；按 `resolve_holder` 分派到**三类去向**：
    ① `state.resources[dim]["stock"]`（**已确权国库/内帑**，受 cap 约束）；
    ② 本路该阶层 POP 的 `goods`（**已确权 POP 切片**，不受国库 cap 约束）；
    ③ `state.pending_stock`（**归属待定**，6.33 用户裁定）。
  ⚠️ 待定料**存放地 ≠ 货主**：不得被采购/出售/投料/计税，
  仅计入实物守恒（`Σ 产出 == 国库 + POP + 待定`）；全程不碰钱/POP wealth；
- 🔴 **账实一致**：两个写入函数均返回**实际入账量**，`produced` **只能按返回值**记；
  否则会出现「记了产量但实物没入账」（曾实测守恒破裂：21917891 vs 5516234）；
- 旧档缺 yields 键 → `setdefault` 幂等跳过，不抛异常；
- `test_pop_identity._STEPS` 镜像须同步新步（调用侧在 settlement.py 接线时登记）。
"""
from __future__ import annotations

from typing import Dict, Optional

#: 🔴 **玩法参数**（2026-10-05 首轮供料模拟调参）：原料仓容量上限。
#: 原为 50_000，而各路月产约 50-90 万/维 ⇒ **单月产出即被截断 94%**，
#: 原料几乎无法积累、工坊必然缺料。改为 3_000_000（约容 3-4 个月产出）。
#: ⚠️ 属**玩法设定**，非史实数据；可调。
_DEFAULT_CAP = 3_000_000

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


def _write_warehouse(resources: dict, dim: str, add: int) -> int:
    """入国家仓（既有口径）。**返回实际入账量**（cap 截断后可能少于 `add`）。

    🔴 账实一致：调用方**只能按返回值**记 `produced`，否则会出现
    「记了产量但实物没入账」，破坏实物守恒对账。
    """
    slot = resources.setdefault(dim, {"stock": 0, "cap": _DEFAULT_CAP})
    cap = int(slot.get("cap", _DEFAULT_CAP) or _DEFAULT_CAP)
    stock = int(slot.get("stock", 0) or 0)
    n = min(int(add), max(0, cap - stock))
    if n > 0:
        slot["stock"] = stock + n
    return n



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
def _write_pending(state, route: str, dim: str, add: int) -> int:
    """写入**归属待定槽**（用户裁定 6.33）。

    🔴 该槽**不并入** `state.resources` —— 后者被五处消费者当作**国库资产**。
    物料在此**不得出售、不得供工坊采购、不得计税**，仅计入**实物守恒**。
    """
    ps = getattr(state, "pending_stock", None)
    if not isinstance(ps, dict):
        ps = {}
        state.pending_stock = ps
    rk = str(route or "")
    slot = ps.setdefault(rk, {})
    ent = slot.setdefault(dim, {"qty": 0, "owner": None,
                                "owner_status": "\u5f52\u5c5e\u5f85\u5b9a",
                                "evidence_ref": None})
    ent["qty"] = int(ent.get("qty", 0) or 0) + int(add)
    return int(add)

def pending_total(state, dim: Optional[str] = None) -> int:
    """Σ 归属待数量（**实物守恒对账用**；不含已确权）。"""
    ps = getattr(state, "pending_stock", None)
    if not isinstance(ps, dict):
        return 0
    tot = 0
    for slot in ps.values():
        if not isinstance(slot, dict):
            continue
        for d, ent in slot.items():
            if dim is not None and d != dim:
                continue
            if not isinstance(ent, dict):
                continue
            if ent.get("owner_status") == "\u5df2\u786e\u6743":
                continue                      # 已确权不计入待定
            tot += int(ent.get("qty", 0) or 0)
    return tot

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
            slot = resources.setdefault(dim, {"stock": 0, "cap": _DEFAULT_CAP})
            cap = int(slot.get("cap", _DEFAULT_CAP) or _DEFAULT_CAP)
            stock = int(slot.get("stock", 0) or 0)
            _holder = _resolve(dim)
            _to_pop = bool(_holder) and _holder.startswith("pop:")
            _to_state = _holder in ("state_treasury", "imperial_treasury")
            if _to_state:
                add = q                      # 待定/POP 各有独立容器，不得被国库 cap 截断（6.33）
            else:
                add = min(q, max(0, cap - stock))
            if add > 0:
                # ══ T3 + 6.33（2026-10-05）按归属分派 ══
                # `resolve_holder` 判给 POP 切片 => 落该路径该阶层 goods；
                # 判给国库/内帑 => 入国家仓（口径不变）；
                # **Missing（未裁定/证据不足）=> 归属待定槽**（6.33）：
                #   存放地 != 货主，**不并入 resources**，不得出售/采购/计税。
                if not _to_pop:
                    # 6.33 账实一致：**按实际入账量**记 produced（国库 cap 可能截断）
                    _in = (_write_warehouse(resources, dim, add) if _to_state
                           else _write_pending(state, name, dim, add))
                    if _in > 0:
                        produced[dim] = produced.get(dim, 0) + int(_in)
                    continue
                try:
                    _cls = _holder.split(":")[1]
                except IndexError:
                    _write_pending(state, name, dim, add)
                    produced[dim] = produced.get(dim, 0) + add
                    continue
                _pops = p.get("pops") or {}
                _tgt = _pops.get(_cls) if isinstance(_pops, dict) else None
                if not isinstance(_tgt, dict):
                    # 该路无此阶层 ⇒ 证据不足，**不臆造持有人**，如实回落国家仓
                    _write_pending(state, name, dim, add)
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
                    _write_pending(state, name, dim, add)
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
