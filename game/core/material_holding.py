# -*- coding: utf-8 -*-
"""建材的**商品化**存取（E-1 · 2026-10-02）—— 州府级唯一读口。

## 用户裁定的三条口径

| 裁定 | 内容 |
|---|---|
| **C**（州府仓） | 施工侧**只从本地取料，取不到即缺料** ⇒ 建材**必须先运到**才能开工 |
| **C-c** | 工地**只从本地取**；缺料**不得**由系统自动代买/凭空补 |
| **E-1** | 🔴 **「建材也是商品啊」** ⇒ 建材是**商品**，存量落在**商人 POP `goods`**（POP 挂载律），商人因此有囤货与定价动机 |

## 🔴 为什么**没有仓明细层**了

本模块曾有过 `state.resources[dim]["by_pref"][州府][维]` 的仓明细。
E-1 之后建材在**商人 POP `goods`** 上，若仓明细**同时保留**，
就成了**同一物料的平行账本**——直接违反 POP 挂载律与「口径单点」。
故该层已**整体退役**（含 `allocate_by_*` / `set_material_holding` /
`move_material` / `consume_material`）。

`state.resources[dim]["stock"]` 仍保留为**全国总账/来源池**：
Step 4.45 的 `supply_merchant_materials()` 把其中的料**搬进商人货栈**，
**总量守恒、不凭空增物**。

## 维度命名空间已合并

政府工程原用 `RAW_DIMS_14` 中文名（`铁`/`石`/`木`），民间营造用 `RAW_DIMS`
英文名（`iron`/`stone`/`timber`）——二者在 `state.resources` 里本是
**两个不同单元格**，不合并会**同一物料双记**。
现经 `to_material_dim()` 在**仓边界**翻译成**同一套英文名**。

## 不变量（回归锁定）

1. **商品化**：建材只在**商人 POP `goods`**，无第二处账本；
2. **守恒**：`supply_merchant_materials()` 只是**搬运**，总量不变；
3. **缺失 ≠ 0**：商人 POP 不存在或无该维度 ⇒ `None`，**不回落 0**；
4. **缺料不静默**：扣不足返回**实扣量**，由调用方归因；
5. **不越路**：只从**本路**商人取，**不跨路借料**（否则"运没运到"不可观测）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 州府主键分隔符（`路|治所`）。商品维键恒不含它 —— 迁移期据此判别桶与扁平项。
SEAT_SEP = "|"

#: POP `goods` 内**州府建材归属子槽**的保留键（方案 A · 2026-10-03 用户裁定）。
#: 形如 `goods["建材"]["京畿路|开封府"]["木"]`。
SEAT_SLOT = "建材"

__all__ = [
    "MATERIAL_DIMS", "to_material_dim",
    "seat_yield_weights_of_circuit",
    "seat_weights_for", "supply_goods_to_seats",
    "circuit_seats", "merchant_of", "merchant_goods",
    "material_holding_for_circuit", "consume_for_circuit",
    "supply_merchant_materials", "trade_material",
    "holding_report",
    "SEAT_SEP", "is_seat_bucket_key", "goods_bucket", "goods_amount",
    "goods_set", "goods_add", "commodity_dims",
    "seat_slot", "seat_weights_of_circuit", "holder_pops_of_circuit",
    "material_holding_for_seat", "consume_for_seat", "seat_holding_report",
]

#: 🔴 建材 = 物料的**子集**（木/石/铁），不再是「与其它商品平行的另一类东西」。
#: 取自 `RAW_DIMS`（**2026-10-03 起全部物料维已统一为中文**）。
#: ⚠️ 物料维度名**唯一**，不存在中英双轨；`to_material_dim()` 保留为**恒等**以兼容
#: 既有调用点（`settlement_tech` / `civil_building` 等），**不再做翻译**。
MATERIAL_DIMS = ("木", "石", "铁")


# ══ 持有者解析 T2（2026-10-05） ══
#
# 🔴 **命名纪律**：经济经营关系键为 `economic_affiliation`（**不是** `faction` ——
#    该名已被政治派系 `state.factions` 占用）。政治派系决定政治支持，
#    **不决定货权**；「旧党能形成影响」≠「旧党是库存账户或收商税主体」。
#
# **解析必须只落到一个账户**（Codex《未完成设计对齐与改良方案_2026-10-05》）：
#     pop_slice | state_treasury | imperial_treasury | 经营主体账户
# 依契约分属多方时**不得**整笔归一方 —— 返回 None（`Missing`）交调用方归因。
#
# 🔴 **本表刻意留空**：`HOLDER_MAP` 尚未裁定任何维。
#    「维 → 经济归属关系」是**史料+玩法双重判断**，未裁定时**一律 Missing**，
#    绝不均摊、绝不默认民营、绝不从政治派系反推（见 POP改良方案 §2.1 第 5 条）。
#
#    裁定后按 `HOLDER_MAP[dim] = <关系键>` 逐维填入；
#    填入前本模块**只提供机制，不产出任何归属结论**。

HOLDER_MAP: Dict[str, str] = {
    # ══ 已裁定（史实明确，见 reviews/POP家计与赋税体系设计_2026-10-04 §6.25）══
    # 🧂 榷盐、官冶铁冶：**专卖即国家专营**，不在商人手中。
    "盐": "state_operator",
    "铁": "state_operator",
    # 🧵 蚕桑纺麻为**农户家庭手工业**（「男耕女织」）⇒ 户内自营。
    #    ⚠️ 此为**倾向**：官营佃种应另判 `state_operator`（官仓），
    #    须按该路的田亩权利人/契约判定，本表不预断。
    "丝": "household_self",
    "麻": "household_self",
    # 🍬 蔗糖为**农家副业**（家庭自营），非官营。
    "蔗": "household_self",
    # 🔴 **刻意留空**（Missing，不得臆断）：
    #   木/石/药材 —— 山泽之利归官、皇室经内诸司掌控，但**具体归国库还是内帑**
    #     取决于是否御苑/内诸司所辖，属**数据事实**，不由本表判定；
    #   果/茶 —— 庄园与自产并存，归属随路而异；
    #   金/银/铜 —— 金属≠钱，是实物存量，货权另议；
    #   马/牲畜 —— 蕃部与马监并存。
    #   ⇒ 未裁定即 Missing，调用方不得回落（POP改良方案 §2.1 第 5 条）。
}

HOLDER_TREASURY = "state_treasury"
HOLDER_IMPERIAL = "imperial_treasury"


def resolve_holder(dim: str, producer_id: Any = None,
                   economic_affiliation: Any = None,
                   contract_id: Any = None,
                   pdata: Optional[dict] = None) -> Optional[str]:
    """解析某物料维的**唯一货权账户**。返回载体键，未定/不适用 ⇒ `None`。

    返回值三选一（皆为**载体键**，非 POP 对象）：
      - `'pop:<阶层>:<关系键>'` —— POP 经济切片（经 `economic_affiliation` 确认）；
      - `'state_treasury'` —— 国库/官仓；
      - `'imperial_treasury'` —— 内帑/内库（山泽、内诸司、皇庄御苑）。

    `None` = **Missing**：该维归属未裁定、或证据不足。**不回落**为某一方，
    亦不按人口比例伪拆（POP改良方案 §2.1 第 5 条）。

    ⚠️ `economic_affiliation` 传入时**只接受已登记的关系键**；
    未登记（含 `unclassified`）⇒ 一律 Missing，不得据此定货权。
    """
    if not isinstance(dim, str) or not dim:
        return None
    rel = HOLDER_MAP.get(dim)
    if not rel:
        return None                                  # 归属未裁定 ⇒ Missing
    if contract_id is not None:
        # 依契约分属多方 ⇒ 本函数**无权**归并，返回 Missing 交调用方按契约拆分
        return None
    # 严禁：`unclassified` 一律 Missing —— 「不允许自动售卖」（POP改良方案）。
    if rel == "unclassified":
        return None
    if rel in ("imperial_operator", HOLDER_IMPERIAL):
        return HOLDER_IMPERIAL
    if rel in ("state_operator", HOLDER_TREASURY):
        return HOLDER_TREASURY
    if rel == HOLDER_IMPERIAL:
        return HOLDER_IMPERIAL
    if not isinstance(economic_affiliation, dict):
        return None
    if rel not in economic_affiliation:
        return None                                  # 该切片无此关系 ⇒ 证据不足
    _cls = producer_id if isinstance(producer_id, str) and producer_id else None
    if not _cls:
        return None
    return "pop:%s:%s" % (_cls, rel)

def to_material_dim(dim: str) -> Optional[str]:
    """物料维度**恒等**闸门（2026-10-03 起不再翻译）。

    · 属 `MATERIAL_DIMS`（木/石/铁）⇒ 原样返回；
    · **其它维度（含其它物料与成品）⇒ `None`**，调用方须据此**跳过**。

    ⚠️ **为何保留这个函数**：`settlement_tech` / `civil_building` / `settlement_agri`
    经它把「建材」与「非建材物料」分开；物料虽已统一命名，但**建材仍是需求侧的一类**
    （要运到、要付款），这层闸门是**用途过滤**而非**命名翻译**。
    """
    d = str(dim or "")
    return d if d in MATERIAL_DIMS else None

def circuit_seats(circuit: str) -> list:
    """该路全部治所（限定名 `路|治所`），取自 `CIRCUIT_INFO.members`。

    `CIRCUIT_INFO` 是州府实体清单的权威来源（`content/README.md` 已注明）。
    保留此函数是为了让**测试与工具**能把路映射到治所；
    ⚠️ 但**建材存取一律按路走商人 POP**，不再按治所分摊。
    """
    from content.geo_admin import CIRCUIT_INFO
    from core.prefecture_entity import seat_id_of
    info = CIRCUIT_INFO.get(circuit)
    if not info:
        return []
    out = []
    for m in (info.get("members") or []):
        try:
            out.append(seat_id_of(circuit, m[0]))
        except Exception:                      # noqa: BLE001 — 脏成员跳过，不猜
            continue
    return out


def is_seat_bucket_key(key: Any) -> bool:
    """`goods` 的键是**州府桶**（`治所→{dim:n}`）还是**扁平商品维**（`dim→n`）？

    判别依据稳定：州府主键恒形如 `路|治所`（`prefecture_entity.seat_id_of` 产出），
    商品维键恒**不含** `|`。二者不相交 ⇒ 迁移期两种形态可**无歧义共存**，
    这正是 349 处调用点能**逐步**迁移而不炸的基础。
    """
    return isinstance(key, str) and SEAT_SEP in key


def goods_bucket(goods, seat_id: Optional[str] = None, *, create: bool = False) -> Optional[dict]:
    """取 `goods[治所]` 州府桶；`seat_id=None` ⇒ 扁平区（空视图，不落键）。

    🔴 **迁移期纪律**：`goods` 可同时存在扁平 `dim→n` 与州府桶 `治所→{dim:n}`，
    **总量恒等于两者之和**（见 `goods_amount`）。
    建材的读写**一律走本模块访问口**，新代码不得裸取 `goods[dim]`。
    """
    if not isinstance(goods, dict):
        return None
    if seat_id is None:
        return {}
    b = goods.get(seat_id)
    if isinstance(b, dict):
        return b
    if not create:
        return None
    b = {}
    goods[seat_id] = b
    return b


def _num(v: Any) -> Optional[int]:
    """把 `goods` 里的值读成 int；非数值（含 bool）⇒ `None`（**不作 0 猜**）。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return int(v or 0)


def goods_amount(goods, dim: str, seat_id: Optional[str] = None) -> Optional[int]:
    """读建材存量。`seat_id=None` ⇒ **全量**（扁平 + Σ州府桶）。

    **缺失 ≠ 0**：该维**完全不存在** ⇒ `None`，以区分「没这个商品」与「有但为 0」。
    """
    if not isinstance(goods, dict):
        return None
    if seat_id is not None:
        b = goods_bucket(goods, seat_id)
        if not b:
            return None
        v = _num(b.get(dim))
        return v
    total = _num(goods.get(dim))
    for k, b in goods.items():
        if not is_seat_bucket_key(k) or not isinstance(b, dict):
            continue
        v = _num(b.get(dim))
        if v is not None:
            total = (total or 0) + v
    return total


def commodity_dims(goods) -> List[str]:
    """🔴 `goods` 里的**商品维键**（排除州府桶）。

    迁移期 `goods` 可能含 `治所→{dim:n}` 桶；任何
    `for dim in goods` / `goods.keys()` 的旧代码都**必须**改走本函数，
    否则会把桶（dict）当商品维参与算术（实测炸出 158 例）。

    仅返回**数值型**的键 —— 这是比「排除含 `|` 的键」更严也更稳的判据：
    桶是 dict、不是数，天然被排除；扁平项若被误写成非数值也不会混进来。
    """
    if not isinstance(goods, dict):
        return []
    return [k for k, v in goods.items()
            if isinstance(k, str) and not isinstance(v, (dict, bool))
            and isinstance(v, (int, float))]


def goods_set(goods, dim: str, value: int, seat_id: Optional[str] = None) -> int:
    """🔴 **单点写口**：设某治所（或扁平区）存量；返回写入后的量。"""
    v = max(0, int(value))
    if not isinstance(goods, dict):
        return 0
    if seat_id is None:
        goods[dim] = v
        return v
    b = goods_bucket(goods, seat_id, create=True)
    if b is None:
        return 0
    b[dim] = v
    return v


def goods_add(goods, dim: str, qty: int, seat_id: Optional[str] = None) -> int:
    """🔴 **单点累加口**：增量写入（州府桶或扁平区）；返回写入后的量。"""
    d = int(qty)
    if not isinstance(goods, dict):
        return 0
    if seat_id is None:
        cur = _num(goods.get(dim)) or 0
        return goods_set(goods, dim, cur + d)
    b = goods_bucket(goods, seat_id, create=True)
    if b is None:
        return 0
    cur = _num(b.get(dim)) or 0
    return goods_set(goods, dim, cur + d, seat_id)

def seat_slot(pop, seat_id: Optional[str] = None, *, create: bool = False) -> Optional[dict]:
    """兼容别名 → `goods_bucket(pop["goods"], seat_id)`。

    🔴 **口径（2026-10-03 用户裁定：州府桶放在 goods 里）**：
    `goods` 命名空间从「商品维 → 数量」扩为「**治所 → {商品维: 数量}**」，
    即 `goods["京畿路|开封府"]["木"]`。**建材仍然是货物**（E-1 不变），
    只是货物的存放粒度下沉到州府。

    **为何读侧必须走 `goods_amount()`**：全仓约定「`goods` 每个键都是商品维」——
    `production_chain.goods_direct_production_backup` 直接 `for gdim in list(goods)` **无过滤**，
    故键型一变就会被当商品维参与算术。`goods_amount()` 按 `is_seat_bucket_key()`
    区分「扁平项」与「州府桶」再求和，**迁移期与迁移后都正确**。
    """
    if not isinstance(pop, dict):
        return None
    return goods_bucket(pop.get("goods"), seat_id, create=create)


def seat_weights_of_circuit(circuit: str) -> List[Tuple[str, float]]:
    """该路各治所的**分摊权重**（州府人口）——建材州府级需求的分布依据。

    规格原话：*「建材的州府级**需求分布**正是 2 要落的户口分布」*
    （`specs/unified-civilian-market/tasks.md`）。
    归入席/无块席（`demog=None`，**缺失≠0**）**不参与分摊**，份额自然留在总额里。
    """
    from core.prefecture_entity import seats_of
    out: List[Tuple[str, float]] = []
    for e in seats_of(circuit, include_merged=False):
        demog = e.get("demog") or {}
        try:
            w = float(demog.get("population", 0) or 0)
        except (TypeError, ValueError):
            w = 0.0
        if w > 0:
            out.append((str(e.get("seat_id") or ""), w))
    return out


def holder_pops_of_circuit(state, circuit: str) -> List[dict]:
    """该路**带 `goods` 的全部 POP**（不限阶层）——建材可能落在其中任一个。

    ⚠️ 不能只取商人：见 `seat_slot` 的口径说明。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    pops = ((prefs.get(circuit) or {}).get("pops") or {})
    if not isinstance(pops, dict):
        return []
    return [p for p in pops.values()
            if isinstance(p, dict) and isinstance(p.get("goods"), dict)]


def seat_yield_weights_of_circuit(
        circuit: str, dim: str) -> List[Tuple[str, float]]:
    """**州府级产地权重**：该路各治所对 `dim` 的产出份额（G-2 新增）。

    与 `seat_weights_of_circuit`（人口权重）是**两种口径**，用途不同，不可互换：

    · **产地权重**：治所自己产多少 → 货理应先落在**产它的那个治所**；
    · **人口权重**：治所人多多少 → **无产地信息时**的兜底分摊（如国家配给）。

    ⚠️ **负产不参与加权**：`yields` 里负值表示该治所**消耗/亏损**（如京畿路盐为负，
    即本路输入而非产出），把它当权重会造出负的货量。负值一律跳过；若全路皆负 ⇒
    返回空列表，交由调用方回退人口权重（**不臆造归属**）。

    无 `yields` 数据（`None`）同样返回空 ⇒ 调用方回退人口权重。
    """
    from core.prefecture_entity import seats_of
    try:
        seats = seats_of(circuit, include_merged=False)
    except Exception:
        return []
    out: List[Tuple[str, float]] = []
    for s in seats:
        # `all_seats()` 产出的条目已自带 `seat_id`（形如 `路|治所`），直接取用
        sid = str(s.get("seat_id") or "")
        if not sid:
            continue
        demog = s.get("demog") or {}
        yields = demog.get("yields")
        if not isinstance(yields, dict):
            continue
        v = _num(yields.get(dim))
        if v is None or v <= 0:
            continue
        out.append((sid, float(v)))
    return out


SEAT_W = Tuple[str, float]


def _seat_name_of(seat_id: str) -> str:
    """`路|治所` 主键 → 治所名（去路前缀）。"""
    s = str(seat_id or "")
    return s.split("|", 1)[1] if "|" in s else s


def seat_tribute_dims(seat: str) -> frozenset:
    """该治所在《宋史·地理志》**进贡过哪些物料维**（卡1.4 · 存在性证据）。

    · 数据：`_dev_tools/sources/songshi/gong_prefecture.json`（195 条州府级贡物）；
    · 映射：`content/seat_products.py` 的显式映射表（66 条，覆盖 53% 贡物出现次数）。

    🔴 **贡物是存在性证据，不含数量** ⇒ 只用于**产地权重**，**不可当产量**。
    🔴 **无记录 ≠ 不产**（`缺失 ≠ 0`）⇒ 返回空集时**不得归零**，调用方须保留人口基础权重。
    """
    name = str(seat or "").strip()
    if not name:
        return frozenset()
    for suf in ("府", "军", "监", "州", "军州"):
        if name.endswith(suf) and len(name) > len(suf):
            name = name[: -len(suf)]
            break
    hit = _TRIBUTE_BY_SEAT.get(name)
    return hit if hit else frozenset()


#: 《宋史·地理志》治所贡物存在性索引：{治所名(去后缀): frozenset(物料维)}
_TRIBUTE_BY_SEAT: Dict[str, frozenset] = {}


def _build_tribute_index() -> Dict[str, Dict[str, frozenset]]:
    """加载 195 条州级贡物 → `{路: {治所: frozenset(维)}}` 与 `{路: frozenset(维)}`。

    **缺文件不报错**（返回空表）—— 行为退回纯人口权重，不因数据缺失而崩。
    """
    import json
    import os
    import re
    by_circuit: Dict[str, Dict[str, set]] = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "_dev_tools", "sources", "songshi",
                         "gong_prefecture.json")
    if not os.path.exists(path):
        return {}, {}
    try:
        recs = json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}, {}
    from content.seat_products import SEAT_PRODUCT_MAP
    for r in recs:
        r = r or {}
        circ = str(r.get("circuit") or "").strip()
        seat = str(r.get("seat") or "").strip()
        if not circ:
            continue
        dims = set()
        for g in re.split(r"[\u3001\uff0c,]", str(r.get("goods") or "")):
            dims.update(SEAT_PRODUCT_MAP.get(g.strip(), ()))
        if not dims:
            continue
        by_circuit.setdefault(circ, {}).setdefault(seat, set()).update(dims)
    circ_all = {c: frozenset().union(*v.values()) if v else frozenset()
                for c, v in by_circuit.items()}
    return ({c: {s: frozenset(x) for s, x in v.items()} for c, v in by_circuit.items()},
            circ_all)

_TRIBUTE_BY_SEAT, _TRIBUTE_BY_CIRCUIT = _build_tribute_index()


#: 贡物证据的**权重增强倍数**。有进贡记录的治所权重 ×该值。
#: 取 4 而非更大：既让特产州显著更重，又不把其余州压成 0（缺失 ≠ 0）。
TRIBUTE_WEIGHT_BONUS = 4.0


def seat_weights_for(state, circuit: str, dim: str) -> List[SEAT_W]:
    """**州府分桶权重**（G-2 骨架 + 卡1.4 差异化）。

    **人口基础权重 × 贡物证据增强**：该路在《宋史·地理志》进贡过 `dim` ⇒ 全路权重 ×4。

    🔴 **差异化现阶段只到路级**：两套命名路级 12/21 精确命中、治所级仅 7/126
    （子串匹配已否决：「京」会命中「上京」「东京」）。治所级待人工考据的别名对照表。

    **不臆造归属**：该路无治所 ⇒ 返回 `[]`，调用方不做分摊（份额留总账）。
    """    # ══ 卡1.4 差异化增强 ══
    # 🚦 治所级暂缓：游戏用简体简称（万州/京兆府/代州），《宋史》用带助词的完整地名
    #    （上洛/为晋宁/相如）—— 精确匹配仅 7/126；子串匹配已否决（「京」会命中「上京」）。
    #    待人工考据的显式别名对照表落地后再启用治所级，**不臆造**。
    # ✅ 路级可靠对齐（12/21 精确命中）⇒ 现阶段差异化的**主力来源**。
    _boost = (TRIBUTE_WEIGHT_BONUS
              if dim in circuit_tribute_dims(circuit) else 1.0)
    base = seat_weights_of_circuit(circuit)
    if not base:
        return []
    if _boost == 1.0:
        return base
    return [(sid, w0 * _boost) for sid, w0 in base]

def circuit_tribute_dims(circuit: str) -> frozenset:
    """该**路**在《宋史·地理志》进贡过哪些物料维（卡1.4 · 路级存在性证据）。

    路级比治所级**可靠**：两套命名 12/21 精确命中，治所级仅 7/126。
    ⇒ 差异化现阶段**以路级为主力**。

    缺失 ≠ 0：某路无记录 ⇒ 空集，调用方**不归零**，仍按人口权重分配。
    """
    name = str(circuit or "").strip()
    return _TRIBUTE_BY_CIRCUIT.get(name) or frozenset()


__all_TAIL__ = None

def _attribute_by_weights(pop: Optional[dict], weights: List[SEAT_W],
                        dim: str, qty: int) -> int:
    """按**给定权重**把 `qty` 拆进州府桶；尾差归权重最大者，Σ 精确等于 qty。

    与 `_attribute_to_seats`（固定人口权重）同手法，只是权重来源可外部给定。
    """
    if not weights or qty <= 0:
        return 0
    goods = pop.get("goods") if isinstance(pop, dict) else None
    if not isinstance(goods, dict):
        return 0
    tw = sum(x for _s, x in weights)
    if tw <= 0:
        return 0
    anchor = max(weights, key=lambda kv: kv[1])[0]
    parts = {s: int(round(qty * x / tw)) for s, x in weights}
    parts[anchor] += qty - sum(parts.values())
    for sid, v in parts.items():
        if v:
            goods_add(goods, dim, int(v), sid)
    return int(sum(parts.values()))


def supply_goods_to_seats(state, total: Optional[Dict[str, int]] = None,
                          dims: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """🔴 **G-2 骨架 · 全商品供给入州府桶**（取代只服务建材三维的旧入口）。

    · **维度**：默认 `GOODS_DIMS`（全商品目录）；`dims` 可限定子集（首批只验证既有维）。
    · **归属**：按 `seat_weights_for()` —— 有产地证据用产地，无则人口。
    · **守恒**：只是**搬运**，`state.resources[dim]` 总量不变；差额为未领余量。
    · **幂等**：按「库存 − 已持有」补足，重复调用不膨胀。

    ⚠️ 只做**供给侧落桶**；工坊投料走市场采购属 G-4，不在此。
    """
    from content.data import GOODS_DIMS as _ALL
    use_dims = list(dims) if dims else list(_ALL)
    prefs = getattr(state, "prefectures", {}) or {}
    res = getattr(state, "resources", None) or {}
    out: Dict[str, int] = {}
    for dim in use_dims:
        stock = int((res.get(dim) or {}).get("stock", 0) or 0) \
            if total is None else int(total.get(dim, 0) or 0)
        if stock <= 0:
            continue
        held = 0
        holders = []
        for route in prefs:
            goods = merchant_goods(state, route)
            if goods is None:
                continue
            cur = goods_amount(goods, dim)
            if cur is None:
                continue
            m = merchant_of(state, route)
            holders.append([route, max(1.0, float(m.get("size", 0) or 0))])
            held += int(cur)
        need = stock - held
        if need <= 0 or not holders:
            continue
        wsum = sum(h[1] for h in holders)
        for route, w in holders:
            give = int(round(need * w / wsum))
            if give <= 0:
                continue
            goods = merchant_goods(state, route)
            if goods is None:
                continue
            put = _attribute_by_weights(goods,
                                       seat_weights_for(state, route, dim), dim, give)
            out[dim] = out.get(dim, 0) + put
    return out


def _attribute_to_seats(pop: Optional[dict], circuit: str, dim: str, qty: int
                        ) -> int:
    """把本路新到手的 `qty` 按**州府人口**拆进州府子槽；返回归属量（== qty）。

    尾差归权重最大的治所（与 `supply_merchant_materials` 的路级处理同一手法），
    保证 `Σ(治所) == qty` **精确成立**，不产生无法归因的零头。
    """
    w = seat_weights_of_circuit(circuit)
    if not w or qty <= 0:
        return 0
    goods = pop.get("goods") if isinstance(pop, dict) else None
    if not isinstance(goods, dict):
        return 0
    tw = sum(x for _s, x in w)
    anchor = max(w, key=lambda kv: kv[1])[0]
    parts = {s: int(round(qty * x / tw)) for s, x in w}
    parts[anchor] += qty - sum(parts.values())
    for sid, v in parts.items():
        if v == 0:
            continue
        goods_add(goods, dim, int(v), sid)
    return sum(parts.values())


def material_holding_for_seat(state, seat_id: str, dim: str) -> Optional[int]:
    """🔴 **州府级建材存量**（方案 A 的新读口）：该治所在该路的建材量。

    · 跨该路**全部持仓 POP** 汇总（不假设只有商人持有）；
    · **无任何州府归属 ⇒ `None`**（缺失≠0，「没运到」必须与「有货但为 0」可区分）；
    · 该治所无地图府块/未分摊 ⇒ 同样 `None`（**不臆造归属**）。
    """
    if dim not in MATERIAL_DIMS:
        raise KeyError(f"非建材维度：{dim!r}")
    from core.prefecture_entity import split_seat_id
    circuit, _seat = split_seat_id(seat_id)
    if circuit is None:
        return None
    total: Optional[int] = None
    for pop in holder_pops_of_circuit(state, circuit):
        v = goods_amount(pop.get("goods"), dim, seat_id)
        if v is None:
            continue
        total = v if total is None else total + v
    return total


def consume_for_seat(state, seat_id: str, dim: str, amount: int) -> int:
    """🔴 **州府级扣料**：只从**本治所的归属量**里扣，返回**实扣量**。

    · **不跨州府借料**（"运没运到"必须可观测）；
    · 实扣不足 ⇒ 返回不足数，**由调用方归因为缺料**，不静默；
    · 只动**该治所桶**，不碰同 POP 的扁平区或其它治所（桶之间彼此独立）。
    """
    want = max(0, int(amount))
    if want == 0:
        return 0
    from core.prefecture_entity import split_seat_id
    circuit, _seat = split_seat_id(seat_id)
    if circuit is None:
        return 0
    taken = 0
    for pop in holder_pops_of_circuit(state, circuit):
        if taken >= want:
            break
        goods = pop.get("goods")
        cur = goods_amount(goods, dim, seat_id)
        if cur is None:
            continue
        take = min(cur, want - taken)
        if take <= 0:
            continue
        goods_set(goods, dim, cur - take, seat_id)
        taken += take
    return taken


def seat_holding_report(state) -> Dict[str, Any]:
    """州府桶不变量自检：按治所分列，并报**扁平区/其它桶**的并数。

    迁移期口径：建材总量 = 扁平项 + Σ州府桶。`flat` 列为该维扁平项的值
    （市集成交买入等**无州府来源**的料即落在这里，如实单列、不强行归属）。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    rows: List[Dict[str, Any]] = []
    ok = True
    for circuit in prefs:
        for pop in holder_pops_of_circuit(state, circuit):
            goods = pop.get("goods") or {}
            buckets = {k: v for k, v in goods.items()
                       if is_seat_bucket_key(k) and isinstance(v, dict)}
            if not buckets:
                continue
            for dim in MATERIAL_DIMS:
                per = {}
                for sid, dims in buckets.items():
                    v = _num(dims.get(dim))
                    if v is not None:
                        per[sid] = v
                if not per:
                    continue
                seat_sum = sum(per.values())
                flat = _num(goods.get(dim)) or 0
                rows.append({"circuit": circuit, "dim": dim,
                             "seat_sum": seat_sum, "flat": flat,
                             "total": seat_sum + flat,
                             "seats": len(per)})
                if seat_sum < 0 or flat < 0:
                    ok = False
    return {"ok": ok, "rows": rows}

def merchant_of(state, circuit: str) -> Optional[dict]:
    """该路的**商人 POP**（建材持有者）；不存在 ⇒ `None`。"""
    prefs = getattr(state, "prefectures", {}) or {}
    pops = (prefs.get(circuit) or {}).get("pops") or {}
    m = pops.get("商人") if isinstance(pops, dict) else None
    return m if isinstance(m, dict) else None


def merchant_goods(state, circuit: str) -> Optional[dict]:
    """该路商人 POP 的 `goods` 字典；不存在 ⇒ `None`。"""
    m = merchant_of(state, circuit)
    goods = m.get("goods") if isinstance(m, dict) else None
    return goods if isinstance(goods, dict) else None


def material_holding_for_circuit(state, circuit: str, dim: str) -> Optional[int]:
    """🔴 **路级读口**（E-1 唯一来源）：该路**商人 POP `goods`** 的建材存量。

    商人 POP 不存在或无该维度 ⇒ `None`（缺失≠0，**不回落 0**）。
    ⚠️ **只读**：不按需求凭空分配——建材是商品，存量来自商人实际经营。
    """
    if dim not in MATERIAL_DIMS:
        raise KeyError(f"非建材维度：{dim!r}")
    goods = merchant_goods(state, circuit)
    if not goods:
        return None
    return goods_amount(goods, dim)


def consume_for_circuit(state, circuit: str, dim: str, amount: int) -> int:
    """🔴 **路级扣料**（C-c 落笔口）：从**本路商人 `goods`** 扣，返回**实扣量**。

    · 商人/维度缺失 ⇒ 视为无料（**不按比例代填、不凭空造**）；
    · 实扣不足 ⇒ 返回不足数，**由调用方归因为缺料**，不静默吞掉；
    · **不跨路借料**（"运没运到"必须可观测，否则物流没有意义）。

    🔴 **扣减顺序＝州府级优先（2026-10-03）**：
    **先扣 `goods[治所]` 州府桶，桶耗尽才落扁平残量**。
    扁平项是「**无州府归属**」的料（市集成交买入等）；若先扣它，州府桶永不drained，
    则「料运到了哪个州府」对消费**完全不可观测** —— C-c 只剩形式。
    故次序是口径的一部分，不是实现细节。

    治所主键排序保证**确定性**（同样输入 → 同样扣哪个桶 ⇒ 可复算）。
    工地/工程目前仍是**路级**实体，故此处是「本路各治所桶的合计口径」；
    调用方若已知具体治所，应改用 `consume_for_seat()` 精确扣那一个桶。
    """
    want = max(0, int(amount))
    if want == 0:
        return 0
    goods = merchant_goods(state, circuit)
    if not goods:
        return 0
    taken = 0
    for sid in sorted(k for k in goods if is_seat_bucket_key(k)):
        if taken >= want:
            break
        cur = goods_amount(goods, dim, sid) or 0
        if cur <= 0:
            continue
        take = min(cur, want - taken)
        goods_set(goods, dim, cur - take, sid)
        taken += take
    if taken < want:
        flat = _num(goods.get(dim)) or 0
        if flat > 0:
            take = min(flat, want - taken)
            goods_set(goods, dim, flat - take)
            taken += take
    return taken


def supply_merchant_materials(state, total: Optional[Dict[str, int]] = None
                             ) -> Dict[str, int]:
    """把 `state.resources[dim]["stock"]` 的料**搬进各路商人货栈**（Step 4.45）。

    ⚠️ **只是搬运，总量守恒、不凭空增物**：每次按
    `stock − Σ(商人已持有)` 的**差额**补足，因此重复调用**幂等**、
    不会因"每月都跑一次"而无限膨胀。

    分配依据：**商人 POP 规模**（代表商业容量）；无商人的路不参与分配
    （其份额留在总账，**不按比例代填**）。

    ⚠️ **G-2 起**：本函数仅保留建材三维的历史入口；全商品供给走
    `supply_goods_to_seats()`（可限定维度、可按产地证据归属）。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    res = getattr(state, "resources", None) or {}
    out: Dict[str, int] = {}
    for dim in MATERIAL_DIMS:
        stock = int((res.get(dim) or {}).get("stock", 0) or 0) \
            if total is None else int(total.get(dim, 0) or 0)
        if stock <= 0:
            continue
        held = 0
        wts = []
        for route in prefs:
            goods = merchant_goods(state, route)
            if goods is None:
                continue
            cur = goods_amount(goods, dim)
            if cur is None:
                continue
            m = merchant_of(state, route)
            wts.append([route, max(1.0, float(m.get("size", 0) or 0))])
            held += int(cur)
        need = stock - held
        if need <= 0 or not wts:
            continue
        wsum = sum(w for _r, w in wts)
        anchor = max(wts, key=lambda kv: kv[1])[0]
        parts = {r: int(round(need * w / wsum)) for r, w in wts}
        parts[anchor] += need - sum(parts.values())
        for route, qty in parts.items():
            goods = merchant_goods(state, route)
            # 2026-10-03（州府桶）：新到手的量**按州府人口拆进 `goods[治所]` 桶**。
            # 🔴 **只写一处** —— 桶是权威，扁平区仅作「无州府归属」的如实单列；
            # 两处都写会**双计**（`goods_amount` 会把两者相加）。
            attributed = _attribute_to_seats(merchant_of(state, route), route, dim, int(qty))
            if attributed <= 0:
                # 该路无治所人口权重（如无地图府块）⇒ **不臆造归属**，如实落扁平区
                goods_add(goods, dim, int(qty))
        out[dim] = held + need
    return out


def trade_material(state, *, buyer_pop: dict, seller_pop: dict,
                   dim: str, qty: int, price: float,
                   purpose: str = "resale", trade_id: Optional[str] = None):
    """州府间**建材成交**（真·商人供货）—— **复用 `market.trade_goods`**。

    🔴 **E-1 后不再需要视图适配器**：料本来就在 POP `goods` 上，
    可直接把真 POP 交给 `trade_goods`（它本就按 `buyer/seller` 的
    `wealth` 与 `goods` 做**就地原子转移**）。

    不变量：
    ① `ΣPOP wealth` **不变**（钱从买方移到卖方，不创造不销毁）；
    ② `ΣPOP goods[建材]` **不变**（料只是换了持有者）；
    ③ 自成交由 `trade_goods` 自身 `buyer is seller` **拒绝**；
    ④ `unmet_qty` **原样返回**，调用方须归因，**不静默丢弃**。
    """
    from core.market import trade_goods

    if dim not in MATERIAL_DIMS:
        raise KeyError(f"非建材维度：{dim!r}")
    if buyer_pop is seller_pop:
        raise ValueError("买方与卖方不得为同一 POP（自成交不构成市场）")

    # 🔴 **C-c 护栏**：跨州府成交**不得瞬移**。
    # 建材必须"先运到"才能用——若本函数让货直接落进买方货栈，
    # "运没运到"就不可观测，物流便没有意义。
    # ⇒ 同路（市集内）走本函数；**跨路请用 `transport.dispatch`**。
    prefs = getattr(state, "prefectures", {}) or {}
    bc = _route_of(prefs, buyer_pop)
    sc = _route_of(prefs, seller_pop)
    if bc and sc and bc != sc:
        raise ValueError(
            f"跨州府建材成交不得瞬移（买方 {bc} / 卖方 {sc}）："
            f"请用 `core.transport.dispatch` 走真实在途")

    before_buyers = int((buyer_pop.get("goods") or {}).get(dim, 0) or 0)
    before_seller = int((seller_pop.get("goods") or {}).get(dim, 0) or 0)

    res = trade_goods(state, dim=dim, qty=int(qty), price=float(price),
                      buyer=buyer_pop, seller=seller_pop,
                      purpose=purpose, trade_id=trade_id)

    after_buyers = int((buyer_pop.get("goods") or {}).get(dim, 0) or 0)
    after_seller = int((seller_pop.get("goods") or {}).get(dim, 0) or 0)
    res["material_delta"] = {
        "buyer": after_buyers - before_buyers,
        "seller": after_seller - before_seller,
        "sum": (after_buyers - before_buyers) + (after_seller - before_seller),
    }
    return res


def _route_of(prefs: Dict[str, Any], pop: dict) -> Optional[str]:
    """某个 POP 属于哪一路（按对象同一性匹配）；匹配不到 ⇒ `None`。"""
    for route, info in (prefs or {}).items():
        pops = (info or {}).get("pops") or {}
        if isinstance(pops, dict) and any(v is pop for v in pops.values()):
            return route
    return None


def holding_report(state) -> Dict[str, Any]:
    """守恒自检：`Σ(各路商人建材) == resources[dim]["stock"]`（搬运守恒）。"""
    prefs = getattr(state, "prefectures", {}) or {}
    res = getattr(state, "resources", None) or {}
    rows: Dict[str, Any] = {}
    ok = True
    for dim in MATERIAL_DIMS:
        held = 0
        n = 0
        for route in prefs:
            goods = merchant_goods(state, route)
            if goods is None:
                continue
            cur = goods_amount(goods, dim)
            if cur is None:
                continue
            held += int(cur)
            n += 1
        stock = int((res.get(dim) or {}).get("stock", 0) or 0)
        rows[dim] = {"merchant_total": held, "stock_total": stock,
                     "gap": stock - held, "route_count": n}
        if held > stock:
            ok = False
    return {"ok": ok, "dims": rows}