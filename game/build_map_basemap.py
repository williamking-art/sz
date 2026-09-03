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

归属算法：地级政区质心 → 最近治所（CIRCUIT_INFO members 的经纬度，游戏
真值）所在路；距离 > SEED_CAP 视为游戏未建模区域（如京东东路）不归属。
CIRCUIT_BOUNDS 示意界不再参与生成，渲染的是真政区合并结果。

用法：python build_map_basemap.py
"""
from __future__ import annotations

import json
import math
import os
import sys

from shapely.geometry import box, mapping, shape
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
}

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
    """[(经度, 纬度, 路名)] — 116 治所作为归属种子。"""
    pts = []
    for cname, info in CIRCUIT_INFO.items():
        for m in info.get("members", []):
            pts.append((m[2], m[3], cname))
    return pts


def _nearest_circuit(c, seeds):
    """质心 → 最近治所所在路；超 SEED_CAP 返回 None。"""
    best, bd = None, SEED_CAP
    kx = math.cos(math.radians(c.y))
    for lon, lat, cname in seeds:
        d = math.hypot((lon - c.x) * kx, lat - c.y)
        if d < bd:
            bd, best = d, cname
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
            hit = _nearest_circuit(g.centroid, seeds)
            if hit is None:
                hit = FORCE_CIRCUIT.get(f["properties"].get("name", ""))
            if hit is None:
                continue
            info = CIRCUIT_INFO.get(hit, {})
            feats.append({
                "type": "Feature",
                "properties": {
                    "kind": "circuit",
                    "name": hit,
                    "type": info.get("type", ""),
                    "seat": info.get("seat", ""),
                    "game_unit": info.get("game_unit"),
                    "member_count": len(info.get("members", [])),
                    "prefecture": f["properties"].get("name", ""),
                },
                "geometry": mapping(g),
            })
    # 将同一路下的所有地级碎片合并为完整大省板块(消除地级碎缝与锯齿台阶)
    by = {}
    by_info = {}
    for f in feats:
        name = f["properties"]["name"]
        by.setdefault(name, []).append(shape(f["geometry"]).buffer(0))
        by_info[name] = f["properties"]

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


def main() -> int:
    os.makedirs(WEB, exist_ok=True)
    build_land()
    build_rivers()
    build_lakes()
    build_circuits()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
