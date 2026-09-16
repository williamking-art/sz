# -*- coding: utf-8 -*-
"""构建舆图底图与宋路实界（真实地理数据版）。

输入 assets/map/raw/（fetch_basemap.py 产物）：
    ne_50m_land.geojson                    陆地/海岸线
    ne_10m_rivers_lake_centerlines.geojson 河流
    ne_10m_lakes.geojson                   湖泊
    datav_{adcode}_full.json × 33          DataV 地级政区
输出 assets/map/web/：
    land.geojson              陆地（视野过滤）
    rivers.geojson            河流（视野裁剪切段）
    lakes.geojson             湖泊（视野裁剪）
    circuits.geojson          宋路实界：地级政区按质心归属并入各路（属性兼容旧路层）
    circuit_borders.geojson   路级外框（并集边界线，含 label_at）
    prefectures.geojson       州/府级实界：同一归属再按治所切一刀，州/府独立成块
                              （可单独选中、可由圣旨改名；并集恒等于所在路）
    prefecture_borders.geojson 州/府级外框（并集边界线，含 label_at）

归属算法：地级政区质心 → 最近治所（CIRCUIT_INFO members 的经纬度，游戏
真值）所在路与治所；距离 > SEED_CAP 视为游戏未建模区域（如京东东路）不归属。
路级与州/府级共用同一次判定，故两级边界天然自洽（无缝隙、无重叠）。
CIRCUIT_BOUNDS 示意界不再参与生成，渲染的是真政区合并结果。

用法：python build_map_basemap.py
"""
from __future__ import annotations

import json
import math
import os
import sys

from shapely.geometry import Point, box, mapping, shape
from shapely.ops import linemerge, unary_union

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from content.geo_admin import CIRCUIT_BOUNDS, CIRCUIT_INFO, MAP_VIEW

RAW = os.path.join(BASE, "assets", "map", "raw")
WEB = os.path.join(BASE, "assets", "map", "web")
MARGIN = 1.0
BBOX = (MAP_VIEW["west"] - MARGIN, MAP_VIEW["south"] - MARGIN,
        MAP_VIEW["east"] + MARGIN, MAP_VIEW["north"] + MARGIN)
SEED_CAP = 1.3  # 度；地级政区质心距最近治所超过此值 → 游戏未建模区域，不归属

# 燕云十六州（辽南京道/西京道，游戏单列）不并入宋路：京津、大同、朔州
EXCLUDE_ADCODES = ("1101", "1201", "1402", "1406")

# 种子上限(SEED_CAP)之外、但史实应属宋的零星地级:强制归属(玩法抽象)
FORCE_CIRCUIT: dict = {
    # 海南(广南西路)
    "三亚市": "广南西路", "三沙市": "广南西路", "五指山市": "广南西路",
    "东方市": "广南西路", "昌江黎族自治县": "广南西路", "乐东黎族自治县": "广南西路",
    "陵水黎族自治县": "广南西路", "保亭黎族苗族自治县": "广南西路",
    # 川渝/鄂/陕/桂零星
    "泸州市": "成都府路", "大足区": "成都府路", "永川区": "成都府路",
    "潼南区": "成都府路", "荣昌区": "成都府路",
    "安康市": "利州路", "十堰市": "京西路",
    "百色市": "广南西路", "河池市": "广南西路",
    "榆林市": "陕西路",
    # 淮东/京东零星
    "宿州市": "淮南东路", "青岛市": "京东东路", "威海市": "京东东路",
    # 贵州全省归宋（用户指示：贵州划给宋；史实宋代贵州主体为夔州路羁縻州，
    # 非大理版图——原 REGIME_PARTS 把「贵州省」整块划给大理，此处改归宋）。
    # 又按用户指示：贵州单独成省 → 归新设「黔中路」（不并入夔州路）。
    "贵阳市": "黔中路", "六盘水市": "黔中路", "遵义市": "黔中路",
    "安顺市": "黔中路", "毕节市": "黔中路", "铜仁市": "黔中路",
    "黔西南布依族苗族自治州": "黔中路", "黔东南苗族侗族自治州": "黔中路",
    "黔南布依族苗族自治州": "黔中路",
}

# 路-省白名单：受限路只收本省地级（省级 adcode 前两位）。黔中路的种子位于贵州，
# 若无限制会吸走邻省地级（泸州→应属成都府路、昭通/曲靖→应属大理）。
CIRCUIT_PROV_LIMIT: dict[str, set] = {"黔中路": {"52"}}

# 省级整体直挂：无 DataV 地级数据、或按用户指示不再细切州府的省级整体
#   {省级名: (路名, 州/府名, 标签位[经,纬])}
#   台湾岛整体作为福建路下的「台湾府」（宋代台湾不入版籍，游戏抽象；
#   不走"地级质心→最近治所"归属，避免台湾成为种子吸走福建沿海地级）。
PROVINCE_WHOLE_SEAT: dict = {"台湾省": ("福建路", "台湾府", [121.0, 23.6])}

# DataV 地级政区省级文件（710000 台湾无地级数据，宋亦无台湾建制，跳过）
PROVINCES = [
    "110000", "120000", "130000", "140000", "150000", "210000", "220000",
    "230000", "310000", "320000", "330000", "340000", "350000", "360000",
    "370000", "410000", "420000", "430000", "440000", "450000", "460000",
    "500000", "510000", "520000", "530000", "540000", "610000", "620000",
    "630000", "640000", "650000", "810000", "820000",
]


def _load_raw(name: str):
    with open(os.path.join(RAW, name), encoding="utf-8") as fh:
        return json.load(fh)


def _save_web(name: str, obj) -> None:
    with open(os.path.join(WEB, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[basemap] {name:<24} features={len(obj.get('features', []))}")


def _clip(g):
    """裁剪到视野，返回几何列表（可能为空）。"""
    clipped = g.intersection(box(*BBOX))
    if clipped.is_empty:
        return []
    if clipped.geom_type in ("Polygon", "MultiPolygon",
                             "LineString", "MultiLineString"):
        return [clipped]
    return [x for x in getattr(clipped, "geoms", [])
            if x.geom_type in ("Polygon", "MultiPolygon",
                               "LineString", "MultiLineString")]


def _outside(g) -> bool:
    x0, y0, x1, y1 = g.bounds
    return x1 < BBOX[0] or x0 > BBOX[2] or y1 < BBOX[1] or y0 > BBOX[3]


def build_land() -> None:
    data = _load_raw("ne_50m_land.geojson")
    feats = []
    for f in data["features"]:
        g = shape(f["geometry"])
        if g.is_empty or _outside(g):
            continue
        feats.append(f)
    _save_web("land.geojson", {"type": "FeatureCollection", "features": feats})


def build_rivers() -> None:
    data = _load_raw("ne_10m_rivers_lake_centerlines.geojson")
    feats = []
    for f in data["features"]:
        g = shape(f["geometry"])
        if g.is_empty or _outside(g):
            continue
        props = {k: f["properties"].get(k)
                 for k in ("name", "name_zh", "scalerank")}
        for gm in _clip(g):
            if gm.geom_type in ("LineString", "MultiLineString"):
                feats.append({"type": "Feature", "properties": props,
                              "geometry": mapping(gm)})
    _save_web("rivers.geojson", {"type": "FeatureCollection", "features": feats})


def build_lakes() -> None:
    data = _load_raw("ne_10m_lakes.geojson")
    feats = []
    for f in data["features"]:
        g = shape(f["geometry"])
        if g.is_empty or _outside(g):
            continue
        props = {k: f["properties"].get(k) for k in ("name", "name_zh")}
        for gm in _clip(g):
            if gm.geom_type in ("Polygon", "MultiPolygon"):
                feats.append({"type": "Feature", "properties": props,
                              "geometry": mapping(gm)})
    _save_web("lakes.geojson", {"type": "FeatureCollection", "features": feats})


def _seat_index():
    """[(经度, 纬度, 路名, 治所名)] — 治所作为归属种子（路/州府两级同源）。"""
    pts = []
    for cname, info in CIRCUIT_INFO.items():
        for m in info.get("members", []):
            pts.append((m[2], m[3], cname, m[0]))
    return pts


def _nearest_seat(c, seeds, cap=None):
    """质心 → 最近治所 (路名, 治所名)；cap 非空时超距返回 None。

    路级与州/府级共用同一归属判定：地级政区整块归其最近治所，
    故州/府级碎块并集恒等于同路板块（无缝隙、无重叠）。
    """
    best, bd = None, (math.inf if cap is None else cap)
    kx = math.cos(math.radians(c.y))
    for lon, lat, cname, sname in seeds:
        d = math.hypot((lon - c.x) * kx, lat - c.y)
        if d < bd:
            bd, best = d, (cname, sname)
    return best


def build_circuits() -> None:
    seeds = _seat_index()
    feats = []
    for ad in PROVINCES:
        data = _load_raw(f"datav_{ad}_full.json")
        for f in data["features"]:
            if str(f["properties"].get("adcode", "")).startswith(EXCLUDE_ADCODES):
                continue
            g = shape(f["geometry"])
            if g.is_empty:
                continue

            # 剔除廊坊北三县飞地(北纬 > 39.62°，位于北京与天津之间辽国南京道腹心)
            if f["properties"].get("name") == "廊坊市" and g.geom_type == "MultiPolygon":
                from shapely.geometry import MultiPolygon
                south_parts = [poly for poly in g.geoms if poly.centroid.y <= 39.62]
                if south_parts:
                    g = south_parts[0] if len(south_parts) == 1 else MultiPolygon(south_parts)
            hit = _nearest_seat(g.centroid, seeds, SEED_CAP)
            # 路-省白名单：受限路只收本省地级（如黔中路仅贵州 52），避免新设路的
            # 种子把邻省地级吸走（泸州→成都府路、昭通/曲靖→大理），越界即视为未命中。
            if hit is not None:
                lim = CIRCUIT_PROV_LIMIT.get(hit[0])
                if lim and str(f["properties"].get("adcode", ""))[:2] not in lim:
                    hit = None
            if hit is None:   # 超种子半径：FORCE_CIRCUIT 兜底，再取该路内最近治所
                forced = FORCE_CIRCUIT.get(f["properties"].get("name", ""))
                if forced is None:
                    continue
                back = _nearest_seat(g.centroid, [s for s in seeds if s[2] == forced])
                hit = (forced, back[1] if back else "")
            cname, sname = hit
            info = CIRCUIT_INFO.get(cname, {})
            feats.append({
                "type": "Feature",
                "properties": {
                    "kind": "circuit",
                    "name": cname,
                    "type": info.get("type", ""),
                    "seat": info.get("seat", ""),     # 路治所（路级语义，勿改）
                    "unit_seat": sname,               # 本块地级所隶治所（州/府级归属）
                    "game_unit": info.get("game_unit"),
                    "member_count": len(info.get("members", [])),
                    "prefecture": f["properties"].get("name", ""),
                },
                "geometry": mapping(g),
            })
    # 省级整体直挂（台湾省→福建路·台湾府等）：直接补入清单，随下游
    # by(路级)/by_seat(州府级) 聚合，不参与种子归属判定。
    if PROVINCE_WHOLE_SEAT:
        for pf in _load_raw("datav_100000_full.json")["features"]:
            tgt = PROVINCE_WHOLE_SEAT.get(pf["properties"].get("name", ""))
            if not tgt:
                continue
            cname, sname = tgt[0], tgt[1]
            g = shape(pf["geometry"]).buffer(0)
            if g.is_empty:
                continue
            info = CIRCUIT_INFO.get(cname, {})
            feats.append({
                "type": "Feature",
                "properties": {
                    "kind": "circuit",
                    "name": cname,
                    "type": info.get("type", ""),
                    "seat": info.get("seat", ""),
                    "unit_seat": sname,
                    "game_unit": info.get("game_unit"),
                    "member_count": len(info.get("members", [])),
                    "prefecture": pf["properties"].get("name", ""),
                },
                "geometry": mapping(g),
            })

    # 将同一路下的所有地级碎片合并为完整大省板块(消除地级碎缝与锯齿台阶)
    by = {}
    by_info = {}
    by_prefectures = {}
    # 州/府级：同一次归属按治所再切一刀（(路名, 治所名) → 地级几何）
    by_seat = {}
    by_seat_prefs = {}
    for f in feats:
        p = f["properties"]
        name = p["name"]
        geom = shape(f["geometry"]).buffer(0)
        by.setdefault(name, []).append(geom)
        by_info[name] = p
        by_prefectures.setdefault(name, []).append(p.get("prefecture", ""))
        skey = (name, p.get("unit_seat") or p.get("seat") or name)
        by_seat.setdefault(skey, []).append(geom)
        by_seat_prefs.setdefault(skey, []).append(p.get("prefecture", ""))

    # 治所权威坐标（CIRCUIT_INFO.members）→ 州/府标签点位
    seat_at = {}
    for cname, info in CIRCUIT_INFO.items():
        for m in info.get("members", []):
            seat_at.setdefault((cname, m[0]), [m[2], m[3]])
    # 省级整体直挂块无 members 种子：用表内显式标签位（如台湾府）
    for _pname, _t in PROVINCE_WHOLE_SEAT.items():
        seat_at.setdefault((_t[0], _t[1]), list(_t[2]))

    road_features = []
    border_features = []

    for name, geoms in by.items():
        u = unary_union(geoms).buffer(0)
        # 闭微缝自愈合(约 +-150m), 消除相邻省市及外接政权交界处的发丝缝隙与锯齿
        u = u.buffer(0.0015).buffer(-0.0015)
        at = u.representative_point()
        p_info = by_info[name]

        # 1. circuits.geojson: 20 大省完整板块
        road_features.append({
            "type": "Feature",
            "properties": {
                "kind": "circuit",
                "name": name,
                "type": p_info.get("type", ""),
                "seat": p_info.get("seat", ""),
                "game_unit": name,
                "member_count": p_info.get("member_count", 0),
                "prefecture": "、".join(x for x in by_prefectures.get(name, []) if x),
                "label_at": [round(at.x, 4), round(at.y, 4)],
            },
            "geometry": mapping(u),
        })

        # 2. circuit_borders.geojson: 连续平滑省界描边线
        boundary = u.boundary
        if boundary.geom_type == "MultiLineString":
            boundary = linemerge(boundary)
        border_features.append({
            "type": "Feature",
            "properties": {
                "kind": "circuit_border",
                "name": name,
                "type": p_info.get("type", ""),
                "label_at": [round(at.x, 4), round(at.y, 4)],
            },
            "geometry": mapping(boundary),
        })

    _save_web("circuits.geojson",
              {"type": "FeatureCollection", "features": road_features})
    _save_web("circuit_borders.geojson",
              {"type": "FeatureCollection", "features": border_features})

    # 3. 州/府级（prefectures.geojson / prefecture_borders.geojson）
    #    同一归属切到治所粒度：每治所一块，州/府可单独选中、单独改名。
    seat_units: list[tuple[str, str, object, list[float]]] = []
    seat_border_features = []
    for (cname, sname), geoms in by_seat.items():
        u = unary_union(geoms).buffer(0)
        u = u.buffer(0.0015).buffer(-0.0015)
        at = seat_at.get((cname, sname))
        if at is None or not u.contains(Point(at[0], at[1])):
            rp = u.representative_point()
            at = [round(rp.x, 4), round(rp.y, 4)]
        seat_units.append((cname, sname, u, [round(at[0], 4), round(at[1], 4)]))

    # 人口经济摊派：路级总量(PREFECTURE_INFO) × 州府块面积占比 × 史实锚点
    # → 拆到每一治所（Σ守恒；尾差并入最大块）。构建期注入属性，运行时不依赖 raw。
    from content.demography import split_circuit_demog
    circ_areas: dict[str, dict[str, float]] = {}
    for cname, sname, u, _at in seat_units:
        circ_areas.setdefault(cname, {})[sname] = u.area
    demog_by = {cname: split_circuit_demog(cname, amap)
                for cname, amap in circ_areas.items()}

    seat_features = []
    for cname, sname, u, at in seat_units:
        props: dict[str, object] = {
            "kind": "prefecture",
            "name": sname,
            "circuit": cname,
            "type": CIRCUIT_INFO.get(cname, {}).get("type", ""),
            "label_at": at,
            "member_count": len(by_seat[(cname, sname)]),
            "prefecture": "、".join(
                x for x in by_seat_prefs.get((cname, sname), []) if x),
        }
        d = demog_by.get(cname, {}).get(sname)
        if d:
            for k, v in d.items():
                if k not in ("name", "circuit"):
                    props[k] = v
        seat_features.append({
            "type": "Feature",
            "properties": props,
            "geometry": mapping(u),
        })
        sb = u.boundary
        if sb.geom_type == "MultiLineString":
            sb = linemerge(sb)
        seat_border_features.append({
            "type": "Feature",
            "properties": {
                "kind": "prefecture_border",
                "name": sname,
                "circuit": cname,
                "label_at": [round(at[0], 4), round(at[1], 4)],
            },
            "geometry": mapping(sb),
        })
    _save_web("prefectures.geojson",
              {"type": "FeatureCollection", "features": seat_features})
    _save_web("prefecture_borders.geojson",
              {"type": "FeatureCollection", "features": seat_border_features})


def main() -> int:
    os.makedirs(WEB, exist_ok=True)
    build_land()
    build_rivers()
    build_lakes()
    build_circuits()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
