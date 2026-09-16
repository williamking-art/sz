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
               "yields": {"tea": 300000, "silk": 0, "hemp": 200000, "cane": 0,
                          "fruit": 150000, "timber": 2000000, "stone": 400000,
                          "iron": 300000, "salt": 0}},
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
def split_circuit_demog(circuit: str,
                        area_map: dict[str, float]) -> dict[str, dict[str, object]]:
    """city 路按治所面积×锚点拆到州/府。area_map 须含该路全部治所（键=治所名）。

    返回 {治所名: {name, circuit, population, households, land, grain,
                  monthly_tax, yields{}}}；未知路或空面积返回 {}。
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


def regime_prefecture_demog(reg_key: str | None = None) -> dict[str, dict[str, object]]:
    """辽/西夏：州/府级人口经济（州府名 → demog）。

    面积未知时按州府数平摊（等权近似，供无舆图预览；正式数据以
    regime_prefectures.geojson 属性为准）。
    """
    out: dict[str, dict[str, object]] = {}
    keys = [reg_key] if reg_key else list(REGIME_DEMOG)
    for key in keys:
        tab = REGIME_PREFECTURES.get(key, {})
        area_map = {pname: 1.0 for prefs in tab.values() for pname in prefs}
        out.update(split_regime_prefecture_demog(key, area_map))
    return out