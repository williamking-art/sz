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

#: U0001f534 2026-10-08（批 1-A）**派生型子池**：拆分后按 (派生字段, 基准字段, 总量字段) 逐治所**重算**。
#:
#:   为什么：`officials` 与 `clerks` 若**各自独立按权重拆分**，各自总和虽守恒，
#:   但**逐治所** `officials + clerks` 会与该治所 `size` 偏移 ±1（各自取整）。
#:   实测新局：**23 个治所**不满足 `officials + clerks == size`。
#:
#:   修法：拆分后以**总量字段（size）为权威**重算派生字段 ⇒ 不变量**构造即成立**，
#:   无需在新局/读档各插一次修正（也避免给伪档“加门”）。
_DERIVED_SEAT_FIELDS = (("clerks", "officials", "size"),)

#: **可加类**字段：拆分与还原都按人数权重求和。
#: 🔴 `grain` 于 2026-10-04 加入（G-3 片5 回填）：粮是**总量**（石/ding），可加；
#:   它此前只在路级，导致「运没运到」对粮**不可观测** —— 裁定甲要求粮走州府桶。
#: 🔴 **身份/家产子池于 2026-10-08 加入**（用户裁定：既然州府级人口权重已���，就应拆下去）。
#:
#:   此前它们**不在此表** ⇒ `sync_route_pops` 对它们执行的是「把路级值**原样复制**到每个治所」，
#:   导致 **Σ治所 == 路级 × 治所数**（治所侧虚高 N 倍）。按治所读这些字段会算错。
#:
#:   实测修正前：`士绅.estate` 路级 305,000 / 治所和 1,960,669（≈6.4 倍）；
#:   `官僚.officials` / `clerks` / `on_post` 同形。
#:
#:   改后按 `size` 权重拆分，**Σ治所 == 路级**，路级回归纯派生镜像。
SPLIT_FIELDS = ("size", "kou", "ding", "wealth", "hidden",
                 "欠税", "自耕农", "佃农", "富农", "贫农", "窖银", "grain",
                 # 身份与家产子池（可加类：均为计数或总量）
                 "estate", "estate_hoard",
                 "officials", "clerks", "on_post", "waiting", "sinecure",
                 # 🔴 2026-10-08 用户裁定补入：宗族子池 `clan`（原 6 项清单**漏了它**，
                 #   2026-10-08 复核发现时才补上——「已下沉」的结论一度不成立）。
                 #   宗族挂 `士绅.clan`（AGENTS §3-1 推论），与身份子池同形：计数型、可按 size 权重拆分。
                 "clan")


def seat_pop_weights(circuit: str) -> List[tuple]:
    """该路各治所的人口权重 [(seat_id, pop), ...]（`demog.population`）。

    无治所或人口全缺 ⇒ 返回 []，调用方据此**不做拆分**（不臆造归属）。
    """
    try:
        from core.foundation.ledger.prefecture_entity import seats_of
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


def split_int(total: int, weights: List[tuple]) -> Dict[str, int]:
    """按权重拆整数，**尾差归权重最大者**，Σ 精确等于 `total`。

    第十二包（2026-10-07）由 `_split_int` 提升为显式接口：本包其他模块与
    `grain_bridge` 都要用它，按 §6 规则 2 不得借用私有符号。
    ⚠️ `total == 0` 或权重和 `<= 0` 时返回**每个治所 0**（不是 `{}`）——
    调用方据此区分"拆了但都是 0"与"没有治可拆"，别顺手改成返回空表。
    """
    if total == 0 or not weights:
        return {sid: 0 for sid, _w in weights}
    tw = sum(w for _s, w in weights)
    if tw <= 0:
        return {sid: 0 for sid, _w in weights}
    anchor = max(weights, key=lambda kv: kv[1])[0]
    parts = {sid: int(round(total * w / tw)) for sid, w in weights}
    parts[anchor] += total - sum(parts.values())
    return parts

# 迁移期兼容别名（旧私有名）。`core/pop_bridge.py` 薄桩的 dir()/__all__ 含 `_split_int`，
# 公开面必须守恒 ⇒ 只能留别名，不能改名了事；新代码请用 `split_int`。
_split_int = split_int


# ══ economic_affiliation 子池（G-3/T1 · 2026-10-05） ══
#
# 🔴 **命名纪律**：经济经营关系**不得**叫 `faction` —— 该名已被**政治派系**占用
#    （`state.factions` + `FACTION_POP_BASIS` / `FACTION_SPEC`：新党/旧党/皇党/军功/中立）。
#    见 `reviews/POP改良方案_2026-10-05.md`。政治派系**跨阶层且可重叠**，
#    经济归属是**互斥子池**，两者语义不同、不可共用键。
#
# **为什么需要独立通道**：子池是**嵌套 dict**（`关系键 -> {size,wealth,goods}`），
# 而 `SPLIT_FIELDS` 的拆分逻辑是「逐字段求和」，嵌套值会被跳过。
# ⇒ 不能塞进该列表，否则拆分时整块丢失。
#
# **挂载律**（与 POP 挂载律一致）：子池是父 POP 的**分区**，不是并行账本；
#    `Σ child.size == parent.size`；不适用时**不造空池**；缺依据保 `unclassified`。

AFFILIATION_FIELDS = ("size", "kou", "ding", "wealth", "grain", "窖银", "欠税")


def split_affiliation_to_seats(src: dict, weights: List[tuple]) -> dict:
    """把路级 POP 的 `economic_affiliation` 子池**拆入**各治所。

    - 按**人口权重**拆分（与扁平字段同权重，保证 `Σ 治所 == 路级`）；
    - 嵌套 `goods` 按「扁平 + 州府桶」双形态处理（同 `split_pops_to_seats`）；
    - **无权重或无子池 ⇒ 返回 {}**（不臆造归属，不造空池）。
    """
    aff = src.get("economic_affiliation")
    if not isinstance(aff, dict) or not aff:
        return {}
    if not weights:
        return {}
    out = {}
    for sid, _p in weights:
        local = {}
        for rel, row in aff.items():
            if not isinstance(row, dict):
                continue
            seg = {}
            for f in AFFILIATION_FIELDS:
                v = row.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    seg[f] = split_int(int(v), weights).get(sid, 0)
            gd = row.get("goods")
            if isinstance(gd, dict):
                _b = {}
                for _dk, _dv in gd.items():
                    if isinstance(_dv, dict) or not isinstance(_dv, (int, float)) or isinstance(_dv, bool):
                        continue
                    for _sid2, _v2 in split_int(int(_dv), weights).items():
                        if _v2:
                            _b.setdefault(_sid2, {})[_dk] = int(_v2)
                for _bk, _bv in gd.items():
                    if not isinstance(_bv, dict):
                        continue
                    _tgt = _b.setdefault(_bk, {})
                    for _dk, _dv in _bv.items():
                        if isinstance(_dv, (int, float)) and not isinstance(_dv, bool):
                            _tgt[_dk] = int(_tgt.get(_dk, 0) or 0) + int(_dv)
                if _b:
                    seg["goods"] = _b
            if seg:
                local[rel] = seg
        if local:
            out[sid] = local
    return out


def aggregate_affiliation(seat_pops: dict) -> Optional[dict]:
    """**派生聚合**：Σ 各治所子池 ⇒ 路级 `economic_affiliation`。

    与扁平字段同口径（求和），`goods` 按州府桶累加。
    **缺失 ≠ 0**：无任何治所带子池 ⇒ 返回 `None`（表示「未下沉」），不回落空账。
    """
    if not isinstance(seat_pops, dict) or not seat_pops:
        return None
    total = {}
    for sid, pops in seat_pops.items():
        if not isinstance(pops, dict):
            continue
        for row in pops.values():
            if not isinstance(row, dict):
                continue
            aff = row.get("economic_affiliation")
            if not isinstance(aff, dict) or not aff:
                continue
            for rel, seg in aff.items():
                if not isinstance(seg, dict):
                    continue
                tgt = total.setdefault(rel, {})
                for f in AFFILIATION_FIELDS:
                    v = seg.get(f)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        tgt[f] = int(tgt.get(f, 0) or 0) + int(v)
                gd = seg.get("goods")
                if isinstance(gd, dict):
                    tg = tgt.setdefault("goods", {})
                    for _bk, _bv in gd.items():
                        if not isinstance(_bv, dict):
                            continue
                        t2 = tg.setdefault(_bk, {})
                        for _dk, _dv in _bv.items():
                            if isinstance(_dv, (int, float)) and not isinstance(_dv, bool):
                                t2[_dk] = int(t2.get(_dk, 0) or 0) + int(_dv)
    return total or None

def rederive_seat_fields(pdata: dict) -> int:
    """按 `_DERIVED_SEAT_FIELDS` 逐治所**重算派生字段**；返回被修正的治所数。

    U0001f534 2026-10-08（批 1-D）为何提到 `sync_route_pops` 里：派生字段（如 `clerks = size - officials`）
    的**不变量应在每次刷镜像时被强制**，而不是只在下沉当刻。否则任何改
    `size`/`officials` 的写入路径都会让派生字段**变陈旧**。
    """
    if not isinstance(pdata, dict):
        return 0
    seats = pdata.get("seats") or {}
    if not seats:
        return 0
    fixed = 0
    for _seat in seats.values():
        _sp = (_seat or {}).get("pops") or {}
        for _cls in POP_CLASSES:
            _row = _sp.get(_cls)
            if not isinstance(_row, dict):
                continue
            _ch = False
            for _d, _base, _tot in _DERIVED_SEAT_FIELDS:
                _tv = _row.get(_tot)
                _bv = _row.get(_base)
                if (isinstance(_tv, (int, float)) and not isinstance(_tv, bool)
                        and isinstance(_bv, (int, float)) and not isinstance(_bv, bool)):
                    _want = max(0, int(_tv) - int(_bv))
                    if _row.get(_d) != _want:
                        _row[_d] = _want
                        _ch = True
            if _ch:
                fixed += 1
    return fixed


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
                    row[f] = split_int(int(v), w).get(sid, 0)
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
                    for _sid2, _v2 in split_int(_dv, w).items():
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
            # economic_affiliation 子池（互斥分区，**独立通道**：嵌套 dict 不能进 SPLIT_FIELDS）
            _aff = split_affiliation_to_seats(src, w)
            if _aff:
                row["economic_affiliation"] = _aff
            seat_pops[cls] = row
        seats[sid] = {"pops": seat_pops}
    pdata["seats"] = seats
        # U0001f534 2026-10-08（批 1-A）派生子池逐治所重算：以总量字段为权威，
    #   保证不变量在**拆分当刻**就成立（而非靠后续结算跟修）。
    for _seat in seats.values():
        _sp = (_seat or {}).get("pops") or {}
        for _cls in POP_CLASSES:
            _row = _sp.get(_cls)
            if not isinstance(_row, dict):
                continue
            for _d, _base, _tot in _DERIVED_SEAT_FIELDS:
                _tv = _row.get(_tot)
                _bv = _row.get(_base)
                if (isinstance(_tv, (int, float)) and not isinstance(_tv, bool)
                        and isinstance(_bv, (int, float)) and not isinstance(_bv, bool)):
                    _row[_d] = max(0, int(_tv) - int(_bv))
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
    # 🔴 2026-10-08（批 1-A）**强度归一**：逐行**只累加数值项**，非数值（伪档/损坏档里的
    #   dict）**跳过而不崩**。原写法 `any(isinstance(...))` 只查“有没有一行是数”，
    #   随后 `sum(int(r.get(f,0) or 0))` 会对**另一行的 dict** 抛 `TypeError` ⇒ 避免了整档拒载。
    def _nums(_f, _cast=int):
        return [_cast(r.get(_f)) for r in rows
                if isinstance(r.get(_f), (int, float)) and not isinstance(r.get(_f), bool)]
    for f in SPLIT_FIELDS:
        _vals = _nums(f, int)
        if _vals:
            out[f] = sum(_vals)
    for f in MEAN_FIELDS:
        # 🔴 均值类**按 size 加权还原**，不可求和（求和会让识字率翻数倍）。
        _pv = [(float(r.get(f)), int(r.get("size", 0) or 0)) for r in rows
               if isinstance(r.get(f), (int, float)) and not isinstance(r.get(f), bool)
               and isinstance(r.get("size", 0), (int, float))]
        if _pv:
            _num = sum(v * sz for v, sz in _pv)
            _den = sum(sz for _v, sz in _pv)
            out[f] = (_num / _den) if _den > 0 else float(_pv[0][0])
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
    # economic_affiliation 子池：各治所汇总（独立通道，不走 SPLIT_FIELDS）
    _aff = aggregate_affiliation([(s.get("pops") or {}) for s in seats.values()])
    if _aff:
        out["economic_affiliation"] = _aff
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
    # U0001f534 2026-10-08（批 1-D）先强制**逐治所派生字段**，再聚合 ⇒
    #   任何改 `size`/`officials` 的写入都自动保持派生不变量。
    rederive_seat_fields(pdata)
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
    parts = split_int(int(value or 0), w)
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
#: 结构化守卫记录：与 `_VIOLATIONS` 一一对应，供批 2 归因探针读取。
#: 不改变旧列表格式；合法镜像刷新仍由 `_pops_write_exempt` 完全豁免。
_VIOLATION_DETAILS = []
#: 批 2-1 诊断开关；默认关闭，避免生产守卫为调用栈付出额外开销。
_GUARD_TRACE = False
# 🔴 M32：守卫安装标志改为**原地可变容器**（非 `global` 重绑）。旧转发桩
# `core.pop_bridge` 的 `from ... import _GUARD_INSTALLED` 因此与实现侧恒为**同一 list 对象**，
# 杜绝 install/uninstall 整体重绑导致的跨测对象身份分叉（b9 判据③误报"第二份实现"）。
# 与 M30 `_ALIAS_INDEX` 原地 clear/update 同构；当前无消费者读取该标志，读法若启用应为 `_GUARD_INSTALLED[0]`。
_GUARD_INSTALLED = [False]

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


def set_pops_guard_trace(enabled: bool = True) -> None:
    """开启/关闭守卫调用点诊断（批 2-1 探针使用，默认关闭）。"""
    global _GUARD_TRACE
    _GUARD_TRACE = bool(enabled)


def _trace_detail() -> dict:
    if not _GUARD_TRACE:
        return {}
    try:
        import sys
        # _trace_detail → _rec → __setitem__/update → 生产调用方
        fr = sys._getframe(3)
        return {"file": fr.f_code.co_filename, "line": fr.f_lineno,
                "function": fr.f_code.co_name}
    except Exception:
        return {}


class _GuardedPops(dict):
    """路级 `pops` 只读守卫：任何**直接写入**都会记录到 `_VIOLATIONS`。"""

    __slots__ = ("_label",)

    def _rec(self, key, val):
        if not _charging():
            return
        if len(_VIOLATIONS) < 500:
            _VIOLATIONS.append("%s[%r] = %r" % (self._label, key, val))
            _VIOLATION_DETAILS.append({"label": self._label, "op": key, "value": val, **_trace_detail()})

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
            _VIOLATION_DETAILS.append({"label": self._label, "op": key, "value": val, **_trace_detail()})

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
    n = 0
    for route, pdata in (getattr(state, "prefectures", None) or {}).items():
        if install_pops_guard(pdata, str(route)):
            n += 1
    _GUARD_INSTALLED[0] = True
    return n


def uninstall_all_guards(state) -> int:
    """把各路路级 `pops` 守卫**还原为普通 dict**（与 `install_all_guards` 成对收尾）。

    存在的理由：守卫是 `_GuardedPops`/`_GuardedRow` dict 子类，只在结算**观察期**存在。
    结算结束必须还原，否则：
      · 存档 / 深拷贝会带上守卫子类与 `_label` 槽（非数据字段）；
      · 结算之后的玩家命令若做路级派生刷新，会被**误记账**进 `_VIOLATIONS`。
    还原只换容器类型（dict 子类 → plain dict），**键值数据一字不动**。
    未装守卫的路为 no-op；返回还原了几路（幂等）。
    """
    n = 0
    for _route, pdata in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(pdata, dict):
            continue
        pops = pdata.get("pops")
        if not isinstance(pops, _GuardedPops):
            continue
        plain = {}
        for cls, row in pops.items():
            plain[cls] = dict(row) if isinstance(row, _GuardedRow) else row
        pdata["pops"] = plain
        n += 1
    _GUARD_INSTALLED[0] = False
    return n


def pops_guard_violations() -> list:
    """返回守卫记录的**直接写入**列表（空 = 路级 `pops` 全程只读）。"""
    return list(_VIOLATIONS)


def reset_pops_guard() -> None:
    """清空守卫记账（测试用）。"""
    del _VIOLATIONS[:]
    del _VIOLATION_DETAILS[:]
    global _GUARD_TRACE
    _GUARD_TRACE = False

__all__ = ["POP_CLASSES", "SPLIT_FIELDS", "MEAN_FIELDS", "seat_pop_weights",
    "split_int",
           "split_pops_to_seats", "aggregate_seat_pops", "survey_pops",
           "sync_route_pops", "pop_get", "pop_set", "pop_add",
           "assert_pops_consistent", "locate_pops",
           "pop_obj_set", "pop_obj_add",
           # 路级 pops 只读守卫（5b 退役）
           "install_pops_guard", "install_all_guards", "uninstall_all_guards",
           "pops_guard_violations", "pops_guard_violation_details", "set_pops_guard_trace", "reset_pops_guard"]


def pops_guard_violation_details() -> list:
    """返回与守卫记录同步的结构化 payload（批 2-1 归因使用）。"""
    return list(_VIOLATION_DETAILS)


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