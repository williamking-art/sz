# -*- coding: utf-8 -*-
"""content/demography.py — 州/府级人口经济派生（只读，单一权威源）

宋：PREFECTURE_INFO（20 路路级总量）× 州府实界面积占比 × SONG_SEAT_WEIGHTS
    × → 拆到 CIRCUIT_INFO.members 每一治所（与 prefectures.geojson 同构；
      键名沿用 PREFECTURE_INFO：population/households/land/grain/monthly_tax/yields）。
辽/西夏：REGIME_DEMOG（道/司级总量）× 州府块面积占比 × demog_mult
    × → 拆到 REGIME_PREFECTURES 每一州府（键名沿用 REGIME_DEMOG：
      population/households/land/grain/tax/yields）。

拆分恒等式：Σ子分量 == 父级分量（拾整尾差并入权重最大块），由生成器构建时断言。
几何面积由调用方（build_map_basemap / build_map_geo）在构建期传入——
运行时不依赖 assets/map/raw 原始文件，纯派生态零副作用。

口径注：yields 允许负值（区域外运），按同一权重拆分，负尾差并入最大块。
"""
from __future__ import annotations

from content.geo_admin import REGIME_DEMOG, REGIME_PREFECTURES
from content.data import PREFECTURE_INFO

# ============================================================
# 宋州府史实锚点（权重 >1 的重镇；仅路治一级，member 级默认 1.0）
# 悬空键（不在任何路 members 中）静默忽略，不报错不阻塞。
# ============================================================
SONG_SEAT_WEIGHTS: dict[str, float] = {
    "开封府": 1.6,   # 东京：北宋首都，户口冠绝天下
    "河南府": 1.3,   # 西京洛阳：士宦渊薮
    "大名府": 1.4,   # 北京大名：河北军政都会
    "太原府": 1.3,   # 河东帅府，兵家重地
    "京兆府": 1.3,   # 关中首府
    "扬州":   1.2,   # 淮南富庶，盐漕枢纽
    "江宁府": 1.2,   # 金陵：东南形胜
    "杭州":   1.4,   # 两浙都会，人口冠东南
    "洪州":   1.1,   # 江南西道首府
    "潭州":   1.1,   # 荆湖南路都会
    "福州":   1.2,   # 福建首府，市舶兴盛
    "成都府": 1.4,   # 天府之国
    "广州":   1.3,   # 市舶巨港
    "江陵府": 1.2,   # 荆南重镇，控扼江汉
    "夔州":   0.9,   # 峡江险远，户口疏稀
    # 黔中（羁縻区）：播州杨氏开发最早、户口最盛；矩州(今贵阳)次之；彝部地广人稀
    "播州":   2.0,   # 播州杨氏（今遵义）黔北最盛
    "矩州":   1.8,   # 黔中都会（今贵阳）
    "思州":   1.2,   # 今铜仁
    "普宁州": 1.0,   # 今安顺
    "自杞国": 0.9,   # 今黔西南
    "都云":   0.9,   # 今黔南
    "古州":   0.9,   # 今黔东南
    "罗氏鬼国": 0.8,  # 今毕节（彝族罗氏，地广人稀）
    "汤望州": 0.8,   # 今六盘水
    "台湾府": 0.05,  # 宋代台湾不入版籍（土著，人口仅数万），整体直挂福建路
}

# ============================================================
# 非经济单位的地理路（CIRCUIT_INFO.game_unit=None）：不入 20 路经济体系
#    不进 PREFECTURE_INFO / state.prefectures、不开局生成作坊（避免改动开局
#    经济平衡与存档），人口经济仅供舆图州府层与"玩家划分省级"取数。
# ============================================================
EXTRA_CIRCUIT_DEMOG: dict[str, dict[str, object]] = {
    # 黔中路（今贵州）：宋代羁縻州/部族区，山多田少、户口不入版籍，约 30 万口
    "黔中路": {"name": "黔中路", "households": 60000, "land": 2000000,
               "grain": 2200000, "population": 300000, "monthly_tax": 25000,
               "yields": {"茶": 300000, "丝": 0, "麻": 200000, "蔗": 0,
                          "果": 150000, "木": 2000000, "石": 400000,
                          "铁": 300000, "盐": 0}},
}


def _weighted(names: list[str], area_map: dict[str, float],
              weight_map: dict[str, float]) -> tuple[list[float], int]:
    """面积×锚点 → 归一化权重与最大权重块下标（尾差落点）。"""
    ws = [area_map[n] * weight_map.get(n, 1.0) for n in names]
    total = sum(ws) or 1.0
    shares = [w / total for w in ws]
    top = max(range(len(names)), key=lambda i: ws[i])
    return shares, top


def _split_dim(value: float, names: list[str], shares: list[float],
               top: int) -> dict[str, int]:
    """标量按权重拆分（拾整），尾差并入权重最大块，保证 Σ==value。"""
    parts = {n: round(value * s) for n, s in zip(names, shares)}
    diff = value - sum(parts.values())
    if diff:
        parts[names[top]] += diff
    return parts


# ============================================================
# 宋：路级总量 → 府/州级
# ============================================================
def _split_dim_scoped(value: float, shares: dict, blocked_names: list,
                      blocked_share: float) -> "tuple[dict[str, int], int]":
    """把 `value` 中属于**有块**治所的那一份分派下去，返回 (各块份额, 省级残留)。

    口径：先按史实权重算出"有块治所合计占多少"（`blocked_share`），只分派
    `round(value × blocked_share)`；拾整尾差并入**有块中权重最大者**（沿用既有
    "尾差归最大块"口径）；余额 `value − Σ各块` 即**省级归入份额**，一分不摊给邻府。
    """
    vb = round(value * blocked_share)
    shares_sum = sum(shares[n] for n in blocked_names) or 1.0
    norm = {n: shares[n] / shares_sum for n in blocked_names}
    parts = {n: round(vb * norm[n]) for n in blocked_names}
    anchor = max(blocked_names, key=lambda n: norm[n])
    parts[anchor] += vb - sum(parts.values())
    return parts, value - sum(parts.values())


def split_circuit_demog_scoped(
        circuit: str, area_map: dict[str, float],
        merged_seats: "tuple[str, ...] | list[str]" = ()) -> "tuple[dict[str, dict[str, object]], dict[str, object]]":
    """路级总量 → (府/州级各块, **省级归入残留**)。

    口径（用户 2026-09-29 裁决）：**无地图府块的治所按历史数据（`CIRCUIT_INFO.members`）
    归入省级**——它们不参与府级摊派，其史实权重份额**不从邻府分得、也不摊给邻府**，
    而是留在路级作为 `residual` 返回。逐维恒等式：

        Σ(府块) + residual == 路级总量                     （拾整后逐维精确相等）

    · 权重表用 `SONG_SEAT_WEIGHTS`（史实锚点，重镇 >1）；归入省级的治所**无几何**，
      面积按 `1.0` 计（与 `prefecture_demog()` 的等权近似同源），锚点照取。
    · `merged_seats` 为空时与 `split_circuit_demog` **完全同行为**（残留 `{}`，走旧路径）。
    """
    base = PREFECTURE_INFO.get(circuit) or EXTRA_CIRCUIT_DEMOG.get(circuit)
    if not base or not area_map:
        return {}, {}
    names = sorted(area_map)
    merged = [str(n) for n in merged_seats if n]                  # 只登记，不参与分派
    if not merged:
        return split_circuit_demog(circuit, area_map), {}

    # 全体治所（有块 + 省级归入）共同参与权重归一：归入省级者的史实份额因此**不被放大**
    # 到邻府头上（这正是"归入省级"要解决的隐式摊派）。
    all_names = sorted(set(names) | set(merged))
    weights = {n: area_map.get(n, 0.0) or 1.0 for n in all_names}
    shares, _top = _weighted(all_names, weights, SONG_SEAT_WEIGHTS)
    share_of = dict(zip(all_names, shares))
    blocked_share = sum(share_of[n] for n in names) or 1.0

    out: dict[str, dict[str, object]] = {n: {"name": n, "circuit": circuit} for n in names}
    residual: dict[str, object] = {"circuit": circuit, "merged_seats": sorted(set(merged))}

    for dim in ("population", "households", "land", "grain", "monthly_tax"):
        v = base.get(dim)
        if v is None:
            continue
        parts, res = _split_dim_scoped(v, share_of, names, blocked_share)
        for n, val in parts.items():
            out[n][dim] = val
        residual[dim] = res
    for dim in sorted(base.get("yields", {})):
        parts, res = _split_dim_scoped(base["yields"][dim], share_of, names, blocked_share)
        for n, val in parts.items():
            out[n].setdefault("yields", {})[dim] = val      # ← 键是**货品名**（如 silk），不是 "yields"
        residual.setdefault("yields", {})[dim] = res
    return out, residual


def split_circuit_demog(circuit: str,
                        area_map: dict[str, float]) -> dict[str, dict[str, object]]:
    """city 路按治所面积×锚点拆到州/府。area_map 须含该路全部治所（键=治所名）。

    返回 {治所名: {name, circuit, population, households, land, grain,
                  monthly_tax, yields{}}}；未知路或空面积返回 {}。

    ⚠️ 本函数**只覆盖 area_map 里的治所**——历史表中有、但无地图府块的治所会被
    静默漏掉（其份额摊给邻府）。需要"省级归入"口径时请用
    `split_circuit_demog_scoped(circuit, area_map, merged_seats)`。
    """
    base = PREFECTURE_INFO.get(circuit) or EXTRA_CIRCUIT_DEMOG.get(circuit)
    if not base or not area_map:
        return {}
    names = sorted(area_map)
    shares, top = _weighted(names, area_map, SONG_SEAT_WEIGHTS)
    out: dict[str, dict[str, object]] = {}
    for n in names:
        out[n] = {"name": n, "circuit": circuit}
    for dim in ("population", "households", "land", "grain", "monthly_tax"):
        v = base.get(dim)
        if v is None:
            continue
        for n, val in _split_dim(v, names, shares, top).items():
            out[n][dim] = val
    for dim in sorted(base.get("yields", {})):
        for n, val in _split_dim(base["yields"][dim], names, shares, top).items():
            out[n].setdefault("yields", {})[dim] = val
    return out


# ============================================================
# 辽/西夏：道/司级总量 → 州/府级
# ============================================================
def split_regime_prefecture_demog(
        reg_key: str, area_map: dict[str, float]) -> dict[str, dict[str, object]]:
    """政权州府按块面积×demog_mult 拆到州府（area_map 键=州府名）。

    返回 {州府名: {name, regime, sub_road, population, households, land,
                  grain, tax, yields{}}}；未知政权或空面积返回 {}。
    """
    demog = REGIME_DEMOG.get(reg_key)
    if not demog or not area_map:
        return {}
    bases = demog.get("district_base", {})
    mults = demog.get("demog_mult", {})
    out: dict[str, dict[str, object]] = {}
    for rname, prefs in REGIME_PREFECTURES.get(reg_key, {}).items():
        base = bases.get(rname)
        if not base:
            continue
        names = sorted(n for n in prefs if n in area_map)
        if not len(names) == len(prefs):
            # 面积缺失（建块时被剔空的州府）：跳过，交由生成器断言兜底
            continue
        shares, top = _weighted(names, area_map, mults)
        for n in names:
            out[n] = {"name": n, "regime": reg_key, "sub_road": rname}
        for dim in ("population", "households", "land", "grain", "tax"):
            v = base.get(dim)
            if v is None:
                continue
            for n, val in _split_dim(v, names, shares, top).items():
                out[n][dim] = val
        for dim in sorted(base.get("yields", {})):
            for n, val in _split_dim(base["yields"][dim], names, shares, top).items():
                out[n].setdefault("yields", {})[dim] = val
    return out


# ============================================================
# 顶层只读 API（供 UI/AI/生成器统一取数；不写存档、不落库）
# ============================================================
# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：逐路人口结构派生：待接州县面板
def prefecture_demog() -> dict[str, dict[str, object]]:
    """宋：全部州/府级人口经济（治所名 → demog）。

    面积未知（无 raw 时）自动降级：按成员数平摊（面积占比等权近似，
    仅供无舆图环境预览；正式数据以 prefectures.geojson 属性为准）。
    """
    out: dict[str, dict[str, object]] = {}
    for cname, info in _circuit_members().items():
        area_map = {m[0]: 1.0 for m in info}
        out.update(split_circuit_demog(cname, area_map))
    return out


def _circuit_members() -> dict[str, list[tuple[str, object, object, object]]]:
    from content.geo_admin import CIRCUIT_INFO
    return {c: list(v.get("members", []))
            for c, v in CIRCUIT_INFO.items()}


# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：外邦省级人口派生：待接邦交面板

#: 🔴 外邦（辽/西夏/吐蕃/大理）州府级数值的**口径标记**。
#: 这些数值**不是史料**：权重来自 `REGIME_DEMOG[k]["demog_mult"]`（**设定值**），
#: 面积未知时按州府数**等权**近似，再归一到 `district_base` 的道/区域总量。
#: 与宋的 `historical`（崇宁户实测）**性质不同**，必须在读数里显式可见，
#: **禁止**在 UI/AI 口径中显示成"史实户口"（用户 2026-10-02 裁定：夏/大理走估算）。
BASIS_ESTIMATE = "estimate"

#: 🔴 **无史料总量**的政权（西夏/吐蕃/大理）：其州府级数值由本项目**玩法设定**的
#: 道/区域总量按权重分摊而来，**不存在可靠的历史总量**（已实测：
#: 《宋史》西夏传通篇无户口、大理传无户口、吐蕃仅有零散"降附部族"数）。
#: 设计文档（`docs/AI推演与民间经济营造市场落地建议.md` §验收断言）规定：
#: 「**史料缺失显示为"玩法设定/未有可靠总量"，不会显示为 0 或伪装成史料值**」。
#: 故本表一律标 `setting`，**不得**标 `historical`。
BASIS_SETTING = "setting"

#: 政权 → 数值来源说明（回答"谁报告、依据是什么"）
REGIME_SOURCE: dict[str, str] = {
    "辽": "《辽史·地理志》官方案语「各郡县户总计之不过五十五万有奇」"
          "（**史料上限**；用户 2026-10-02 定为 55 万户，逐道为按比例分摊非史料）",
    "西夏": "**玩法设定/未有可靠总量**——《宋史》夏国传未载户口；"
            "仅凉州有孤证「户二万五千六百九十三，口十二万八千一百九十三」",
    "吐蕃": "**玩法设定/未有可靠总量**——《宋史》吐蕃传仅有零散『降附部族』户口数",
    "大理": "**玩法设定/未有可靠总量**——《宋史》大理传未载户口",
}

#: 史料口径 vs 设定口径（决定 `basis` 取值）
_REGIME_BASIS = {
    "辽": "historical_ub",      # historical upper bound：史料上限，逐道为分摊
    "西夏": BASIS_SETTING,
    "吐蕃": BASIS_SETTING,
    "大理": BASIS_SETTING,
}


def regime_prefecture_demog(reg_key: str | None = None) -> dict[str, dict[str, object]]:
    """辽/西夏/吐蕃/大理：州/府级人口经济（州府名 → demog）。

    🔴 **口径**：`basis` 取值区分三态——
    - `"historical_ub"`（辽）：父级总量**有史料上限**，但**逐道/逐府为按比例分摊**，
      不是逐府史料；
    - `"setting"`（西夏/吐蕃/大理）：**玩法设定/未有可靠总量**，
      依设计文档验收断言，**不得显示为史料值、也不得显示为 0**；
    - 权重来源为 `demog_mult`（设定值）+ 真实面积，故**无一条是史料级州府值**。

    `REGIME_PREFECTURES` 已含州府级清单（辽 18 府州/西夏 9/吐蕃 4/大理 12），
    本函数即在其上做区域→州府的分配。
    """
    out: dict[str, dict[str, object]] = {}
    keys = [reg_key] if reg_key else list(REGIME_DEMOG)
    for key in keys:
        tab = REGIME_PREFECTURES.get(key, {})
        area_map = {pname: 1.0 for prefs in tab.values() for pname in prefs}
        rows = split_regime_prefecture_demog(key, area_map)
        basis = _REGIME_BASIS.get(key, BASIS_SETTING)
        src = REGIME_SOURCE.get(key, "**玩法设定/未有可靠总量**")
        for name, row in rows.items():
            row["basis"] = basis
            row["regime"] = key
            row["source"] = src
            row["is_historical"] = basis == "historical_ub"
        out.update(rows)
    return out