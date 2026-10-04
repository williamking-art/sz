# -*- coding: utf-8 -*-
"""🔴 **州府级 POP 基座 + 读写桥**（2026-10-04 用户裁定 **方案乙**：POP 实体下沉州府级）。

## 裁定与约束

- **真账**：`prefectures[路]["seats"][治所]["pops"][类]` —— 每治所一个独立 POP；
- **路级 `pops`** 降为**只读派生聚合**（Σ 治所），写入必须落州府，
  否则构成 AGENTS §3-1 禁止的「与 POP 平行的账本」；
- 本模块已改写 `AGENTS.md` §3-1（前置条件，2026-10-04）。

## 拆分依据

宋有州府级户籍与仓储，故按**治所人口比例**拆分：`demog.population`（如京畿路开封府 510 万）。
🔴 **尾差归权重最大者**，保证 `Σ治所 == 路级原值` **逐字段精确相等**（不丢一钱一人）。

## 迁移状态

`pops` 直访仍有 **39 文件 / 197 处**。本模块**不改任何调用点**，
过渡期桥接是唯一允许的写入口；直访清零后路级 `pops` 才可退役。
"""
from typing import Dict, List, Optional

#: POP 6 类（AGENTS §3-1 挂载律：人只落这 6 类的 size）
POP_CLASSES = ("农", "士绅", "商人", "官僚", "兵", "工匠")

#: 拆分时需**逐字段守恒**的数值字段（尾差归权重最大者）
#: **均值类**字段：拆分与还原都按 `size` 加权（**不可求和**）。
#: `literacy`（识字率）本质是比率，若像其余字段一样求和，聚合后会翻数倍。
MEAN_FIELDS = ("literacy",)

#: **可加类**字段：拆分与还原都按人数权重求和。
SPLIT_FIELDS = ("size", "kou", "ding", "wealth", "hidden",
                 "欠税", "自耕农", "佃农", "富农", "贫农", "窖银")


def seat_pop_weights(circuit: str) -> List[tuple]:
    """该路各治所的人口权重 [(seat_id, pop), ...]（`demog.population`）。

    无治所或人口全缺 ⇒ 返回 []，调用方据此**不做拆分**（不臆造归属）。
    """
    try:
        from core.prefecture_entity import seats_of
        seats = seats_of(circuit, include_merged=False)
    except Exception:
        return []
    out = []
    for s in seats:
        sid = str(s.get("seat_id") or "")
        if not sid:
            continue
        demog = s.get("demog") or {}
        v = demog.get("population")
        if not isinstance(v, (int, float)) or v <= 0:
            continue
        out.append((sid, float(v)))
    return out


def _split_int(total: int, weights: List[tuple]) -> Dict[str, int]:
    """按权重拆整数，**尾差归权重最大者**，Σ 精确等于 `total`。"""
    if total == 0 or not weights:
        return {sid: 0 for sid, _w in weights}
    tw = sum(w for _s, w in weights)
    if tw <= 0:
        return {sid: 0 for sid, _w in weights}
    anchor = max(weights, key=lambda kv: kv[1])[0]
    parts = {sid: int(round(total * w / tw)) for sid, w in weights}
    parts[anchor] += total - sum(parts.values())
    return parts


def split_pops_to_seats(pdata: dict, circuit: str) -> int:
    """把路级 POP 聚合**就地拆入** `pdata["seats"][治所]["pops"]`。返回拆出的治所数。

    幂等：已有 `seats` 且非空则**直接返回**（不重复拆，避免二次拆分导致 double）。
    """
    if not isinstance(pdata, dict):
        return 0
    if pdata.get("seats"):
        return len(pdata["seats"])
    pops = pdata.get("pops") or {}
    if not isinstance(pops, dict) or not pops:
        return 0
    w = seat_pop_weights(circuit)
    if not w:
        return 0
    seats = {}
    for sid, _pop in w:
        seat_pops = {}
        for cls in POP_CLASSES:
            src = pops.get(cls)
            if not isinstance(src, dict):
                continue
            row = dict(src)
            for f in SPLIT_FIELDS:
                v = src.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    row[f] = _split_int(int(v), w).get(sid, 0)
            # 均值类（识字率）**原样复制**到每个治所：它本就是均值，按人口拆会引入
            # 取整误差；复制后聚合时按 size 加权即可**精确**还原路级原值。
            for f in MEAN_FIELDS:
                v = src.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    row[f] = float(v)          # 比率类保留浮点，取整会永久丢精度
            gd = src.get("goods")
            if isinstance(gd, dict):
                # 🔴 goods 已是「扁平标量 + 州府桶」双形态（见 material_holding.goods_bucket）。
                # 扁平标量按人口权重拆分；**已有的州府桶原样归位**到对应治所——
                # 早期版本直接忽略 dict 值，会把已州府化的建材**整体丢掉**。
                _flat = {}
                for k, v in gd.items():
                    if isinstance(v, dict):
                        continue
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        _flat[k] = int(v)
                _b = {}
                for _dk, _dv in _flat.items():
                    for _sid2, _v2 in _split_int(_dv, w).items():
                        if _v2:
                            _b.setdefault(_sid2, {})[_dk] = int(_v2)
                for _bk, _bv in gd.items():
                    if not isinstance(_bv, dict):
                        continue
                    _tgt = _b.setdefault(_bk, {})
                    for _dk, _dv in _bv.items():
                        if isinstance(_dv, (int, float)) and not isinstance(_dv, bool):
                            _tgt[_dk] = int(_tgt.get(_dk, 0)) + int(_dv)
                row["goods"] = _b
            seat_pops[cls] = row
        seats[sid] = {"pops": seat_pops}
    pdata["seats"] = seats
    return len(seats)


def aggregate_seat_pops(pdata: dict, cls: str) -> Optional[dict]:
    """**派生聚合**：Σ 各治所该类 POP ⇒ 路级视图。`seats` 不存在 ⇒ 返回 None。

    缺失 ≠ 0：无 `seats` 时返回 None（表示「未下沉」），不回落成空账。
    """
    if not isinstance(pdata, dict):
        return None
    seats = pdata.get("seats") or {}
    if not seats:
        return None
    rows = [(s.get("pops") or {}).get(cls) for s in seats.values()]
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return None
    out = dict(rows[0])
    for f in SPLIT_FIELDS:
        if any(isinstance(r.get(f), (int, float)) for r in rows):
            out[f] = sum(int(r.get(f, 0) or 0) for r in rows)
    for f in MEAN_FIELDS:
        # 🔴 均值类**按 size 加权还原**，不可求和（求和会让识字率翻数倍）。
        if any(isinstance(r.get(f), (int, float)) for r in rows):
            _num = sum(float(r.get(f, 0) or 0) * int(r.get("size", 0) or 0) for r in rows)
            _den = sum(int(r.get("size", 0) or 0) for r in rows)
            out[f] = (_num / _den) if _den > 0 else float(rows[0].get(f, 0) or 0)
    goods = {}
    for r in rows:
        for k, v in (r.get("goods") or {}).items():
            goods[k] = goods.get(k, 0) + int(v or 0)
    out["goods"] = goods
    return out


def survey_pops(state) -> Dict[str, object]:
    """**迁移对账**：逐路比对路级 POP 与 Σ治所 POP 是否**逐字段相等**。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats") or {}
        if seats:
            out["已下沉路由"] += 1
        pops = pdata.get("pops") or {}
        for cls in POP_CLASSES:
            src = pops.get(cls)
            agg = aggregate_seat_pops(pdata, cls)
            if not isinstance(src, dict) or not isinstance(agg, dict):
                continue
            for f in SPLIT_FIELDS + MEAN_FIELDS:
                a1 = src.get(f)
                a2 = agg.get(f)
                if not (isinstance(a1, (int, float)) and isinstance(a2, (int, float))):
                    continue
                _bad = abs(float(a1) - float(a2)) > 0.5 if f in MEAN_FIELDS else int(a1) != int(a2)
                if _bad:
                    out["字段失配"].append("%s/%s/%s: %s != %s" % (route, cls, f, a1, a2))
    return out


# ── 派生镜像与字段级桥接（2026-10-04 增补） ──
#
# 设计要点：`pops` 直访 197 处中**绝大多数是读取**（跨路求和 sum(size)、读 wealth 等）。
# 若要求全部改写为治所级遍历，工作量与出错面都不可控。
#
# 因此采用**派生镜像**方案：
#   · **真账**仍是 `seats[治所]["pops"]`；
#   · 路级 `pops` 是桥接层**维护的派生镜像**，供存量读取代码使用；
#   · **所有写入必须走** `pop_set` / `pop_add`，由它们先落州府、再刷新镜像，
#     从根上杜绝「镜像与真账漂移」。
#
# ⚠️ 一致性由 `assert_pops_consistent` 锁定（回归测试兜底）；直访清零后镜像即可退役。

_NUM_FIELDS = ("size", "kou", "ding", "wealth", "literacy", "hidden",
               "欠税", "自耕农", "佃农", "富农", "贫农", "窖银")


def sync_route_pops(pdata: dict) -> bool:
    """刷新路级 `pops` 派生镜像 = Σ治所。返回是否真的刷新了（有 seats 时）。"""
    if not isinstance(pdata, dict):
        return False
    seats = pdata.get("seats") or {}
    if not seats:
        return False
    pops = pdata.setdefault("pops", {})
    # 镜像刷新是**由真账派生的合法写入**，豁免守卫记账（否则会被误判成绕过桥接的直写）。
    with _pops_write_exempt():
        for cls in POP_CLASSES:
            agg = aggregate_seat_pops(pdata, cls)
            if not isinstance(agg, dict):
                continue
            row = pops.get(cls)
            if isinstance(row, dict):
                # 🔴 **合并而非替换**：`agg` 只含 SPLIT_FIELDS+goods，直接 `pops[cls] = agg`
                # 会**抹掉** `estate`/`estate_hoard`/`officials`/`clerks`/`on_post` 等
                # 不参与拆分的字段（实测导致 literacy 派生值漂移、存档往返后家产丢失）。
                row.update(agg)
            else:
                pops[cls] = agg
    return True


def pop_get(pdata: dict, cls: str, field: str = "size"):
    """**读**真账（治所级聚合）。未下沉时回落路级原账；都没有 ⇒ `None`（缺失≠0）。"""
    if not isinstance(pdata, dict):
        return None
    agg = aggregate_seat_pops(pdata, cls)
    if isinstance(agg, dict):
        return agg.get(field)
    row = (pdata.get("pops") or {}).get(cls)
    if isinstance(row, dict):
        v = row.get(field)
        return v if isinstance(v, (int, float)) else None
    return None


def _field_weights(pdata: dict, cls: str, field: str) -> List[tuple]:
    """写 delta 时的分摊权重：优先该字段在治所间的现有分布，缺失则用人口。

    例：征税扣的是 `wealth` ⇒ 按各治所 `wealth` 占比分摊，**比按人口更贴近真实承担**。
    """
    seats = (pdata or {}).get("seats") or {}
    if seats:
        out = []
        for sid, s in seats.items():
            row = ((s or {}).get("pops") or {}).get(cls) or {}
            v = row.get(field)
            if isinstance(v, (int, float)) and v > 0:
                out.append((sid, float(v)))
        if out:
            return out
    return seat_pop_weights(str((pdata or {}).get("name") or ""))


def pop_set(pdata: dict, cls: str, field: str, value) -> Optional[int]:
    """**写**真账：按当前治所分布把 `value` 铺到各治所，再刷新镜像。

    铺分而非「全给一个治所」是 POP 挂载律的要求（人只落 6 类 size，不得凭空造人）。
    返回写后真账合计；未下沉时返回 `None`。
    """
    if not isinstance(pdata, dict):
        return None
    seats = pdata.get("seats") or {}
    if not seats:
        return None
    w = _field_weights(pdata, cls, field)
    if not w:
        return None
    if field == "goods":
        gd = {k: int(v or 0) for k, v in (value or {}).items()}
        for sid, s in seats.items():
            rows = (s or {}).setdefault("pops", {})
            rows[cls] = rows.get(cls) or {}
            rows[cls]["goods"] = dict(gd)
        sync_route_pops(pdata)
        return int(sum(gd.values()))
    parts = _split_int(int(value or 0), w)
    for sid, s in seats.items():
        rows = (s or {}).setdefault("pops", {})
        rows[cls] = rows.get(cls) or {}
        rows[cls][field] = parts.get(sid, 0)
    sync_route_pops(pdata)
    return int(sum(parts.values()))


def pop_add(pdata: dict, cls: str, field: str, delta) -> Optional[int]:
    """**写**真账（增量）：读真账 → 加 → 按治所现有分布铺分 → 刷新镜像。"""
    if not isinstance(pdata, dict):
        return None
    if not (pdata.get("seats") or {}):
        return None
    cur = pop_get(pdata, cls, field)
    if not isinstance(cur, (int, float)):
        return None
    return pop_set(pdata, cls, field, max(0, int(cur) + int(delta or 0)))


def assert_pops_consistent(pdata: dict) -> List[str]:
    """断言路级镜像 == Σ治所（逐字段）。返回失配列表（空 = 通过）。"""
    bad = []
    if not isinstance(pdata, dict):
        return ["pdata 非 dict"]
    if not (pdata.get("seats") or {}):
        return []
    pops = pdata.get("pops") or {}
    for cls in POP_CLASSES:
        agg = aggregate_seat_pops(pdata, cls)
        row = pops.get(cls)
        if not isinstance(agg, dict) or not isinstance(row, dict):
            continue
        for f in _NUM_FIELDS:
            a1, a2 = agg.get(f), row.get(f)
            if isinstance(a1, (int, float)) and isinstance(a2, (int, float)) \
                    and int(a1) != int(a2):
                bad.append("%s/%s: 镜像 %s != 真账 %s" % (cls, f, a2, a1))
    return bad

# ── 路级 pops 只读守卫（2026-10-04 · 5b 退役路级 pops） ──
#
# 背景：路级 `pops` 是**派生镜像**（真账 = `seats[治所]["pops"]`）。所有**写入**已
# 桥接化，但「不再有人写路级 pops」此前只是一句**声明**，没有机制保证 —— 任何人新增
# 一行 `p["pops"]["农"]["size"] -= 1` 都不会被察觉，镜像会静默漂移。
#
# 做法：把路级 `pops` 与其各 POP 行包成 dict 子类，写入即**记账**；
# 再由测试跑长局断言**零违规**。这把声明变成了**可证明的不变量**。

_VIOLATIONS = []
_GUARD_INSTALLED = False

#: 豁免深度 > 0 时守卫**只记账不计数** —— `sync_route_pops` 的镜像刷新属合法写入，
#: 不能算作「绕过桥接的直写」。用 try/finally 保证一定复位。
_EXEMPT = []


class _pops_write_exempt:
    """上下文管理器：在其内部，守卫**不记账**。

    用于 `sync_route_pops` 这类「由真账刷新派生镜像」的合法写入，
    以免把镜像刷新误判成绕过桥接的直写。
    """

    __slots__ = ()

    def __enter__(self):
        _EXEMPT.append(1)
        return self

    def __exit__(self, *exc):
        if _EXEMPT:
            _EXEMPT.pop()
        return False


def _charging() -> bool:
    return not _EXEMPT
class _GuardedPops(dict):
    """路级 `pops` 只读守卫：任何**直接写入**都会记录到 `_VIOLATIONS`。"""

    __slots__ = ("_label",)

    def _rec(self, key, val):
        if not _charging():
            return
        if len(_VIOLATIONS) < 500:
            _VIOLATIONS.append("%s[%r] = %r" % (self._label, key, val))

    def __setitem__(self, key, value):
        self._rec(key, value)
        return dict.__setitem__(self, key, value)

    def update(self, *a, **k):
        self._rec("*update*", (a, k))
        return dict.update(self, *a, **k)

    def pop(self, *a, **k):
        self._rec("*pop*", a)
        return dict.pop(self, *a, **k)

    def popitem(self, *a, **k):
        self._rec("*popitem*", a)
        return dict.popitem(self, *a, **k)

    def clear(self):
        self._rec("*clear*", None)
        return dict.clear(self)


class _GuardedRow(dict):
    """单个 POP 行守卫（`pops[cls]`）：写入同样记账。"""

    __slots__ = ("_label",)

    def _rec(self, key, val):
        if not _charging():
            return
        if len(_VIOLATIONS) < 500:
            _VIOLATIONS.append("%s[%r] = %r" % (self._label, key, val))

    def __setitem__(self, key, value):
        self._rec(key, value)
        return dict.__setitem__(self, key, value)

    def update(self, *a, **k):
        self._rec("*update*", (a, k))
        return dict.update(self, *a, **k)

    def pop(self, *a, **k):
        self._rec("*pop*", a)
        return dict.pop(self, *a, **k)

    def popitem(self, *a, **k):
        self._rec("*popitem*", a)
        return dict.popitem(self, *a, **k)

    def clear(self):
        self._rec("*clear*", None)
        return dict.clear(self)


def install_pops_guard(pdata: dict, label: str = "") -> bool:
    """给一路装上只读守卫。**必须在该路已下沉（有 `seats`）之后**调用。"""
    if not isinstance(pdata, dict) or not pdata.get("seats"):
        return False
    pops = pdata.get("pops")
    if not isinstance(pops, dict):
        return False
    if not isinstance(pops, _GuardedPops):
        g = _GuardedPops(pops)
        g._label = label or "pops"
        pdata["pops"] = g
        for cls, row in list(g.items()):
            if isinstance(row, dict) and not isinstance(row, _GuardedRow):
                r = _GuardedRow(row)
                r._label = "%s/%s" % (g._label, cls)
                dict.__setitem__(g, cls, r)
    return True


def install_all_guards(state) -> int:
    """给 `state` 全部已下沉的路装守卫，返回装了几路。"""
    global _GUARD_INSTALLED
    n = 0
    for route, pdata in (getattr(state, "prefectures", None) or {}).items():
        if install_pops_guard(pdata, str(route)):
            n += 1
    _GUARD_INSTALLED = True
    return n


def pops_guard_violations() -> list:
    """返回守卫记录的**直接写入**列表（空 = 路级 `pops` 全程只读）。"""
    return list(_VIOLATIONS)


def reset_pops_guard() -> None:
    """清空守卫记账（测试用）。"""
    del _VIOLATIONS[:]

__all__ = ["POP_CLASSES", "SPLIT_FIELDS", "MEAN_FIELDS", "seat_pop_weights",
           "split_pops_to_seats", "aggregate_seat_pops", "survey_pops",
           "sync_route_pops", "pop_get", "pop_set", "pop_add",
           "assert_pops_consistent", "locate_pops",
           "pop_obj_set", "pop_obj_add",
           # 路级 pops 只读守卫（5b 退役）
           "install_pops_guard", "install_all_guards",
           "pops_guard_violations", "reset_pops_guard"]


def locate_pops(state, pop_obj) -> tuple:
    """**按 pop 对象反查**其所属 `(pdata, cls)`。找不到 ⇒ `(None, None)`。

    存在的理由：多数写入点手上只有 pop 对象（如 `for pop in p["pops"].values()`），
    没有 route dict 与类名。没有本入口时，每次调用都得手工传递，迁移成本被严重低估。

    O(路由×类) 扫描；财政/工坊这类每月只跑几次的路径足够。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    for _route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        pops = pdata.get("pops") or {}
        if not isinstance(pops, dict):
            continue
        for cls, row in pops.items():
            if row is pop_obj:
                return pdata, cls
    return None, None


def pop_obj_set(state, pop_obj, field: str, value) -> Optional[int]:
    """**写**真账（按 pop 对象定位）：先落州府、再刷镜像。未下沉 ⇒ `None`。"""
    pdata, cls = locate_pops(state, pop_obj)
    if pdata is None:
        return None
    return pop_set(pdata, cls, field, value)


def pop_obj_add(state, pop_obj, field: str, delta) -> Optional[int]:
    """**写**真账（按 pop 对象定位的增量）。未下沉 ⇒ `None`。"""
    pdata, cls = locate_pops(state, pop_obj)
    if pdata is None:
        return None
    return pop_add(pdata, cls, field, delta)