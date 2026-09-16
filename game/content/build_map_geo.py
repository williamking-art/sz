# -*- coding: utf-8 -*-
"""宋祚 · 舆图 GeoJSON 生成器（开发期构建工具）

从 content.geo_admin（单一权威源）生成 MapLibre 舆图消费的静态 GeoJSON，
输出到 assets/map/web/（经 content.data.MAP_DIR 解析，不另立路径常量）：

    circuits.geojson  宋路实界（build_map_basemap.py 由 DataV 地级政区合成，
                      本模块不再产出；circuit_borders/land/rivers/lakes 同源）
    regimes.geojson   周边政权疆域层（REGIME_GEO，含 active 标记）
    cities.geojson    府/州/军治所点层（CIRCUIT_INFO.members 展平）
    view.json         舆图初始视野（MAP_VIEW，west/south/east/north）

用法：
    python -m content.build_map_geo           # 校验 + 生成
    python -m content.build_map_geo --check   # 仅校验，不写文件

约定：
- 输出确定性：sort_keys + 固定缩进 + UTF-8 无 BOM，同输入必同字节（可 diff、可入库）。
- 幂等：内容无变化时跳过写入（保留文件 mtime）。
- 安全失败：validate_geo() 有问题则拒绝生成并返回非零码，绝不静默产出坏数据。
- 坐标系 WGS84；边界为玩法分组示意，非严格历史界（史翰青席位口径）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 允许直接以脚本运行（python game/content/build_map_geo.py）
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content.data import EXTERNAL_ALWAYS_SHOW, MAP_DIR
from content.demography import split_regime_prefecture_demog
from content.geo_admin import (
    CIRCUIT_INFO,
    HISTORICAL_RIVERS,
    MAP_VIEW,
    REGIME_CITIES,
    REGIME_COLORS,
    REGIME_GEO,
    REGIME_PARTS,
    REGIME_PREFECTURES,
    active_regimes,
    all_city_points,
    validate_geo,
)
_DEFAULT_REGIME_COLOR = "#d8cbaa"

OUT_DIR = os.path.join(MAP_DIR, "web")

__all__ = ["OUT_DIR", "build_regimes", "build_cities",
           "build_view", "generate_all"]


# ============================================================
# Feature 组装（GeoJSON RFC 7946：线性环首尾闭合，坐标 [lon, lat]）
# ============================================================
def _closed_ring(ring: list[list[float]]) -> list[list[float]]:
    """线性环须首尾闭合；数据源允许开环，输出前补首点副本（显式规范化）。"""
    if len(ring) >= 3 and ring[0] != ring[-1]:
        return [*ring, ring[0]]
    return ring


def _polygon_feature(name: str, ring: list[list[float]],
                     props: dict[str, object]) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [_closed_ring(ring)]},
        "properties": {"name": name, **props},
    }


def build_regimes() -> dict[str, object]:
    """周边政权疆域层:两类 feature,叠放次序(先=底层)。

      1. part   —— use_parts 政权按 REGIME_PARTS 真实政区(省/地级/NE Admin-1)拼合;
      2. regime —— 其余政权(REGIME_GEO.polygon 手工近似,境外一势力一块)。
    use_parts 且未注册拼合条目者(金与诸部,1101 年无建国)完全不上图;
    分路(五京道/监军司)手工几何已退役,"可单独易主"转由运行时归属改写(P1)承担。
    """
    features: list[dict[str, object]] = []
    for key, geo in REGIME_GEO.items():
        if geo.get("use_parts"):
            continue
        features.append(_polygon_feature(key, geo["polygon"], {
            "kind": "regime",
            "display_name": geo.get("name", key),
            "owner": geo.get("owner", key),
            "active": bool(geo.get("active")),
            "tint": "on" if geo.get("active") else "off",
            "fill": REGIME_COLORS.get(key, _DEFAULT_REGIME_COLOR),
            "always_show": key in EXTERNAL_ALWAYS_SHOW,
            "label_at": geo.get("label_at"),
            "note": geo.get("note", ""),
        }))
        # 分路(五京道/监军司)不再输出手工几何:政权版图已按真实政区拼合,
        # "可单独易主"语义转由运行时归属改写(P1)承担。
    return {"type": "FeatureCollection",
            "features": [*regime_part_features(), *features]}


def regime_part_features() -> list[dict[str, object]]:
    """use_parts 政权按 DataV 省级/地级真实边界拼合(kind="part")。

    每省(或省内地级)一块 feature;properties.name=政权显示名(点击详情按政权
    呈现),province=省/地级名,active/owner 继承政权注册表。原始文件由
    fetch_basemap.py 下载至 assets/map/raw/(datav_100000=省级,datav_{adcode}=地级)。
    """
    raw_dir = os.path.join(MAP_DIR, "raw")
    prov_path = os.path.join(raw_dir, "datav_100000_full.json")
    with open(prov_path, encoding="utf-8") as f:
        by_name = {p["properties"]["name"]: p
                   for p in json.load(f)["features"]}

    features: list[dict[str, object]] = []
    for key, spec in REGIME_PARTS.items():
        geo = REGIME_GEO.get(key, {})
        is_neutral = spec.get("neutral", False)
        base = {
            "kind": "part",
            "display_name": "" if is_neutral else geo.get("name", key),
            "name": "" if is_neutral else geo.get("name", key),
            "owner": "" if is_neutral else geo.get("owner", key),
            "active": False if is_neutral else bool(geo.get("active")),
            "tint": "on" if (not is_neutral and geo.get("active")) else "off",
            "fill": spec.get("fill") or REGIME_COLORS.get(key, _DEFAULT_REGIME_COLOR),
            "always_show": False if is_neutral else (key in EXTERNAL_ALWAYS_SHOW),
            "label_at": None if is_neutral else geo.get("label_at"),
            "note": "" if is_neutral else geo.get("note", ""),
        }

        def emit(src: dict[str, object], label: str) -> None:
            features.append({
                "type": "Feature",
                "geometry": src["geometry"],
                "properties": {**base, "province": label},
            })

        # sub_roads: 辽五京道、西夏各道（如宋分路分省）
        sub_roads = spec.get("sub_roads")
        if sub_roads:
            from shapely.geometry import mapping, shape
            from shapely.ops import unary_union

            for rname, rspec in sub_roads.items():
                geoms = []
                for prov, cities in rspec.get("prefectures", {}).items():
                    adcode = by_name[prov]["properties"]["adcode"]
                    fn = os.path.join(raw_dir, f"datav_{adcode}_full.json")
                    with open(fn, encoding="utf-8") as fh:
                        city_feats = json.load(fh)["features"]
                    for c in city_feats:
                        cnm = str(c["properties"]["name"])
                        if cities == "*" or cnm in cities:
                            geoms.append(shape(c["geometry"]).buffer(0))
                # 若为南京道，将廊坊北三县(三河/大厂/香河)并入辽国幽燕腹心
                if rname == "南京道":
                    hebei_fn = os.path.join(raw_dir, "datav_130000_full.json")
                    with open(hebei_fn, encoding="utf-8") as fh:
                        hbf = json.load(fh)["features"]
                    for c in hbf:
                        if c["properties"].get("name") == "廊坊市":
                            cg = shape(c["geometry"])
                            if cg.geom_type == "MultiPolygon":
                                for poly in cg.geoms:
                                    if poly.centroid.y > 39.62:
                                        geoms.append(poly.buffer(0))
                if geoms:
                    merged = unary_union(geoms).buffer(0)
                    road_base = dict(base)
                    road_base["province"] = rname
                    road_base["display_name"] = rname
                    road_base["seat"] = rspec.get("seat", "")
                    road_base["label_at"] = rspec.get("label_at")
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(merged),
                        "properties": road_base,
                    })
            continue

        # union_external:外部行政区(NE Admin-1)拼合
        # 支持 admin 匹配、target_regime 匹配、sub_admin 匹配
        ext = spec.get("union_external")
        if ext:
            from shapely.geometry import mapping, shape
            from shapely.ops import unary_union

            with open(os.path.join(raw_dir, ext["file"]), encoding="utf-8") as f:
                ext_feats = json.load(f)["features"]
            want_admin = set(ext.get("admin", []))
            want_regime = ext.get("target_regime")
            sub_want = ext.get("sub_admin")
            exclude = set(ext.get("exclude", []))
            geoms = []
            label = ""

            for src in ext_feats:
                p = src["properties"]
                nm = str(p.get("name_local") or p.get("name") or "")
                match = False
                if want_regime and p.get("target_regime") == want_regime:
                    match = True
                elif want_admin and p.get("admin") in want_admin and nm not in exclude:
                    if not sub_want or p.get("sub_admin") == sub_want:
                        match = True
                
                if match:
                    geoms.append((shape(src["geometry"]).buffer(0), nm))
                    label = label or str(want_regime or sub_want or p.get("admin"))

            if geoms:
                if spec.get("merge", True):
                    merged = unary_union([g for g, _ in geoms]).buffer(0)
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(merged),
                        "properties": {**base, "province": label},
                    })
                else:
                    for g, nm in geoms:
                        features.append({
                            "type": "Feature",
                            "geometry": mapping(g),
                            "properties": {**base, "province": nm},
                        })
            if not spec.get("provinces") and not spec.get("prefectures"):
                continue

        for prov in spec.get("provinces", []):
            emit(by_name[prov], prov)
        for prov, cities in spec.get("prefectures", {}).items():
            adcode = by_name[prov]["properties"]["adcode"]
            with open(os.path.join(raw_dir, f"datav_{adcode}_full.json"),
                      encoding="utf-8") as f:
                city_feats = json.load(f)["features"]
            wanted = cities
            for c in city_feats:
                cname = str(c["properties"]["name"])
                if wanted == "*" or cname in wanted:
                    emit(c, cname)

    # ---- 后处理：剪除与宋路重叠的省界浮点带；同政权内道/司按序去重叠 ----
    # 同一地级只归宋或政权一方，重叠仅来自跨省 datav 文件边界浮点；宋路优先。
    from shapely.geometry import mapping, shape
    kept: dict[str, list[object]] = {}
    out: list[dict[str, object]] = []
    for f in features:
        g = _clip_song(shape(f["geometry"]).buffer(0))
        key = str(f["properties"].get("name", ""))
        if key:                       # 中性块(name="")不去重，仅剪宋路
            for prev in kept.get(key, []):
                if g.is_empty:
                    break
                g = g.difference(prev)
        if g.is_empty:
            continue
        if key:
            kept.setdefault(key, []).append(g)
        f["geometry"] = mapping(g)
        out.append(f)
    return out


def build_regime_borders() -> dict[str, object]:
    """辽五京道、西夏各道的省道界线层(kind=regime_border)。

    只保留政权**内部**的省道界线：
    1. 先拼合整个政权的全境外轮廓（total_union）；
    2. 各道边界 = 该道轮廓 ∩ 全政权轮廓并集的非共享段 —— 即从各道 boundary 中
       剔除落在政权总外轮廓 boundary（≈国界/与其他政权交界）附近的部分，
       剩下的才是真正的"省内界线"（消除与国界重描的残余）。
    """
    from shapely.geometry import mapping, shape, MultiLineString
    from shapely.ops import linemerge, unary_union

    raw_dir = os.path.join(MAP_DIR, "raw")
    prov_path = os.path.join(raw_dir, "datav_100000_full.json")
    with open(prov_path, encoding="utf-8") as f:
        by_name = {p["properties"]["name"]: p for p in json.load(f)["features"]}

    def _road_geom(rspec: dict) -> object | None:
        geoms = []
        for prov, cities in rspec.get("prefectures", {}).items():
            adcode = by_name[prov]["properties"]["adcode"]
            fn = os.path.join(raw_dir, f"datav_{adcode}_full.json")
            with open(fn, encoding="utf-8") as fh:
                city_feats = json.load(fh)["features"]
            for c in city_feats:
                cnm = str(c["properties"]["name"])
                if cities == "*" or cnm in cities:
                    geoms.append(shape(c["geometry"]).buffer(0))
        if not geoms:
            return None
        return unary_union(geoms).buffer(0.0015).buffer(-0.0015)

    features: list[dict[str, object]] = []
    for key, spec in REGIME_PARTS.items():
        if not spec.get("borders"):
            continue
        sub_roads = spec.get("sub_roads")
        if not sub_roads:
            continue

        # 1) 全政权总轮廓（用于识别"国界段"）
        road_geoms = []
        road_geoms_raw = []
        for rname, rspec in sub_roads.items():
            g = _road_geom(rspec)
            if g is not None:
                road_geoms.append((rname, g))
                road_geoms_raw.append(g)
        if not road_geoms:
            continue
        total_union = unary_union(road_geoms_raw).buffer(0)
        # 国界缓冲带：落在政权外轮廓附近的线段 = 与他政权/宋接壤段，剔除
        outer_band = total_union.boundary.buffer(0.02)

        # 2) 各道 boundary 减去国界段 → 只剩省内界线
        for rname, g in road_geoms:
            b = g.boundary
            if b.geom_type == "MultiLineString":
                b = linemerge(b)
            # difference 剔除国界附近段（国内省界保留）
            inner = b.difference(outer_band)
            if inner.is_empty:
                continue
            if inner.geom_type == "MultiLineString":
                inner = linemerge(inner)
            if inner.geom_type not in ("LineString", "MultiLineString"):
                continue
            features.append({
                "type": "Feature",
                "geometry": mapping(inner),
                "properties": {"kind": "regime_border", "name": key, "province": rname},
            })
    return {"type": "FeatureCollection", "features": features}


# ============================================================
# 辽/西夏州/府级切分（REGIME_PREFECTURES，仅此两政权；其余政权不下沉）
#   州府块并集恒等于所在道/司（与宋路/州府两级同源语义），生成即面积复核，
#   不满足(重叠/缝隙/越界)抛异常拒绝写盘，绝不静默产出坏数据。
# ============================================================
_SONG_LAND: object | None = None
_SONG_LAND_LOADED = False


def _song_land() -> object | None:
    """宋路并集（circuits.geojson，由 build_map_basemap 先产出）。

    同一地级只归宋或政权一方，剪裁只消省界浮点叠带；文件缺失时返回 None
    （纯校验环境不阻断）。结果驻留内存，避免逐要素重解析。
    """
    global _SONG_LAND, _SONG_LAND_LOADED
    if _SONG_LAND_LOADED:
        return _SONG_LAND
    _SONG_LAND_LOADED = True
    fn = os.path.join(OUT_DIR, "circuits.geojson")
    if not os.path.exists(fn):
        return None
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
        with open(fn, encoding="utf-8") as fh:
            feats = json.load(fh).get("features", [])
        geoms = [shape(f["geometry"]).buffer(0) for f in feats if f.get("geometry")]
        _SONG_LAND = unary_union(geoms).buffer(0) if geoms else None
    except Exception:                       # noqa: BLE001 构建期容错
        _SONG_LAND = None
    return _SONG_LAND


def _clip_song(g: object) -> object:
    """剪除与宋路重叠的省界浮点带（宋路优先：同一地级只属一方）。"""
    land = _song_land()
    if land is None or g is None or g.is_empty:
        return g
    out = g.difference(land)
    return out if not out.is_empty else g.buffer(0)


def _prov_raw(by_name: dict, raw_dir: str, prov: str) -> list[dict[str, object]]:
    """省级名 → 该省 DataV 地级 feature 列表。"""
    if prov not in by_name:
        raise ValueError(f"REGIME_PREFECTURES 未知省级政区: {prov}")
    adcode = by_name[prov]["properties"]["adcode"]
    with open(os.path.join(raw_dir, f"datav_{adcode}_full.json"),
              encoding="utf-8") as fh:
        return json.load(fh)["features"]


def _prefecture_geoms(prov_parts: dict, by_name: dict,
                      raw_dir: str) -> list[object]:
    """州府 parts {省: [地级]|"*"} → 地级政区几何集合（空省跳过）。"""
    from shapely.geometry import shape
    geoms = []
    for prov, cities in prov_parts.items():
        for c in _prov_raw(by_name, raw_dir, prov):
            cnm = str(c["properties"]["name"])
            if cities == "*" or cnm in cities:
                geoms.append(shape(c["geometry"]).buffer(0))
    return geoms


def _langfang_north(raw_dir: str) -> list[object]:
    """廊坊北三县（北纬 > 39.62°，京津之间辽南京道腹心）→ 带走几何。"""
    from shapely.geometry import shape
    with open(os.path.join(raw_dir, "datav_130000_full.json"),
              encoding="utf-8") as fh:
        hbf = json.load(fh)["features"]
    out = []
    for c in hbf:
        if c["properties"].get("name") != "廊坊市":
            continue
        cg = shape(c["geometry"])
        if cg.geom_type == "MultiPolygon":
            for poly in cg.geoms:
                if poly.centroid.y > 39.62:
                    out.append(poly.buffer(0))
    return out


def _regime_prefecture_blocks(reg_key: str, by_name: dict,
                              raw_dir: str) -> list[tuple[str, str, object]]:
    """政权州府块（去重叠）[(州府名, 道/司名, 几何)]，顺序 = 表序。

    跨省共边（不同 datav 文件）存在浮点级重叠：按表序后块让位先块
    （difference 已保留区），保证块间零重叠且并集不变（先算并集与道/司
    并集恒等，再切）。fill 与 borders 两层共用本函数，几何单一来源。
    """
    from shapely.geometry import shape
    from shapely.ops import unary_union
    out: list[tuple[str, str, object]] = []
    kept: list[object] = []
    for rname, prefs in REGIME_PREFECTURES.get(reg_key, {}).items():
        for pname, pspec in prefs.items():
            geoms = _prefecture_geoms(pspec.get("parts", {}), by_name, raw_dir)
            if rname == "南京道" and pname == "析津府":
                geoms += _langfang_north(raw_dir)
            if not geoms:
                continue
            u = _clip_song(unary_union(geoms).buffer(0))
            if kept:
                u = u.difference(unary_union(kept))
            if u.is_empty:
                continue
            out.append((pname, rname, u))
            kept.append(u)
    return out


def build_regime_prefectures() -> dict[str, object]:
    """辽/西夏州/府级实界块层（kind="regime_prefecture"）。

    每州府一块：properties 含 regime/sub_road/seat/label_at/active/owner，
    供前端在道/司之下再下一级选中、改名（宋州/府级同构）。
    """
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    raw_dir = os.path.join(MAP_DIR, "raw")
    with open(os.path.join(raw_dir, "datav_100000_full.json"),
              encoding="utf-8") as f:
        by_name = {p["properties"]["name"]: p for p in json.load(f)["features"]}

    features: list[dict[str, object]] = []
    for reg_key, sub_roads in REGIME_PREFECTURES.items():
        geo = REGIME_GEO.get(reg_key, {})
        blocks = _regime_prefecture_blocks(reg_key, by_name, raw_dir)
        # 人口经济摊派：道/司级总量(REGIME_DEMOG) × 州府块面积占比 × 史实锚点
        # → 拆到每一州府（Σ守恒；尾差并入最大块）。构建期注入属性。
        area_map = {pname: u.area for pname, _r, u in blocks}
        demog_map = split_regime_prefecture_demog(reg_key, area_map)
        for pname, rname, u in blocks:
            geoms_n = len(_prefecture_geoms(
                sub_roads[rname][pname].get("parts", {}), by_name, raw_dir))
            pspec = sub_roads[rname][pname]
            seat_at = pspec.get("seat_at")
            if seat_at and not u.contains(shape(
                    {"type": "Point",
                     "coordinates": [seat_at[0], seat_at[1]]})):
                seat_at = None     # 治所溢出块外时退回代表点（防标签飘走）
            if not seat_at:
                rp = u.representative_point()
                seat_at = [round(rp.x, 4), round(rp.y, 4)]
            props: dict[str, object] = {
                "kind": "regime_prefecture",
                "name": pname,
                "display_name": pname,
                "regime": reg_key,
                "sub_road": rname,
                "seat": pname,
                "owner": geo.get("owner", reg_key),
                "active": bool(geo.get("active")),
                "tint": "on" if geo.get("active") else "off",
                "label_at": seat_at,
                "member_count": geoms_n,
            }
            d = demog_map.get(pname)
            if d:
                for k, v in d.items():
                    if k not in ("name", "regime", "sub_road"):
                        props[k] = v
            features.append({
                "type": "Feature",
                "geometry": mapping(u),
                "properties": props,
            })
        if not blocks:
            continue
        # ---- 面积复核 ----
        # a) sub_roads 式（辽/西夏）：州府并集 == 道/司并集（同构重建，理论零差），
        #    symdiff 超限视为归属遗漏/重叠，拒绝写盘；
        # b) 单层式（州府直接挂政权，如吐蕃·河湟）：州府是政权内局部细化，
        #    只查"无越界"（州府并集 ⊆ 政权领土），不查全覆盖。
        total = unary_union([g for _, _, g in blocks])
        ref = _regime_sub_union(reg_key, by_name, raw_dir)
        ref_area = max(ref.area, 1e-9)
        if all(rn == reg_key for _pn, rn, _g in blocks):
            leak = total.difference(ref)
            if leak.area > 0.05 and leak.area / ref_area > 0.002:
                raise ValueError(
                    f"州府并集越出政权领土 "
                    f"(leak={leak.area:.4f} 度²/政权 {ref_area:.1f} 度², "
                    f"diff bounds={leak.bounds}): {reg_key}")
        else:
            sym = total.symmetric_difference(ref)
            sym_area = sym.area
            if sym_area > 0.05 and sym_area / ref_area > 0.002:
                raise ValueError(
                    f"州府并集与道/司并集偏差过大 "
                    f"(symdiff={sym_area:.4f} 度²/政权 {ref_area:.1f} 度², "
                    f"diff bounds={sym.bounds}): {reg_key}")
    return {"type": "FeatureCollection", "features": features}


def _regime_sub_union(reg_key: str, by_name: dict, raw_dir: str) -> object:
    """按 REGIME_PARTS.sub_roads 重建政权道/司并集（与 regime_part_features
    同构：逐道 union + buffer(0)，含南京道北三县特判；不另做自愈）。"""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    spec = REGIME_PARTS.get(reg_key)
    sub = spec.get("sub_roads") if spec else None
    if not sub:
        # 单层模式（如吐蕃·河湟）：无道/司中间级，重建用 provinces+prefectures
        # 全集（provinces 为省级整块，prefectures 为地级；两者并集=政权领土）。
        if spec and (spec.get("provinces") or spec.get("prefectures")):
            sub = {reg_key: {"provinces": spec.get("provinces", []),
                             "prefectures": spec.get("prefectures", {})}}
        else:
            return shape({"type": "GeometryCollection", "geometries": []})
    parts = []
    for rname, rspec in sub.items():
        geoms = []
        for prov in rspec.get("provinces", []):
            if prov in by_name:
                geoms.append(shape(by_name[prov]["geometry"]).buffer(0))
        for prov, cities in rspec.get("prefectures", {}).items():
            for c in _prov_raw(by_name, raw_dir, prov):
                cnm = str(c["properties"]["name"])
                if cities == "*" or cnm in cities:
                    geoms.append(shape(c["geometry"]).buffer(0))
        if rname == "南京道":
            geoms += _langfang_north(raw_dir)
        if geoms:
            parts.append(_clip_song(unary_union(geoms).buffer(0)))
    if not parts:
        return shape({"type": "GeometryCollection", "geometries": []})
    return _clip_song(unary_union([p for p in parts if not p.is_empty]).buffer(0))


def build_cities() -> dict[str, object]:
    """治所点层：is_seat 标记路治，供前端放大级标签分级。"""
    features: list[dict[str, object]] = []
    for p in all_city_points():
        circuit_info = CIRCUIT_INFO.get(p["circuit"], {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            "properties": {
                "name": p["name"],
                "level": p["level"],
                "circuit": p["circuit"],
                "game_unit": p["game_unit"],
                "is_seat": p["name"] == circuit_info.get("seat"),
            },
        })
    # 辽、西夏与境外重点城市：府级治所赋予 is_seat: True, 享受与宋治所同等待遇
    for regime, cities in REGIME_CITIES.items():
        for nm, lon, lat in cities:
            is_fu = "府" in nm
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": nm,
                    "level": "府" if is_fu else "州",
                    "circuit": regime,
                    "game_unit": None,
                    "is_seat": is_fu,
                    "kind": "regime_city",
                },
            })
    # 著名古江河大川标注 (青水墨色, 仅供标签渲染)
    for nm, lon, lat in HISTORICAL_RIVERS:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "name": nm,
                "level": "水系",
                "circuit": "大川",
                "game_unit": None,
                "is_seat": False,
                "kind": "river",
            },
        })
    return {"type": "FeatureCollection", "features": features}


def build_view() -> dict[str, object]:
    """MapLibre 舆图视野。

    bounds = MAP_VIEW 数据四至（全览/限位用）；center/zoom = 玩家默认视野，
    重心在东亚（宋辽夏核心区）而非数据几何中点。
    """
    return {
        "bounds": [MAP_VIEW["west"], MAP_VIEW["south"],
                   MAP_VIEW["east"], MAP_VIEW["north"]],
        "center": [108.0, 31.0],
        "zoom": 4.0,
        "west": MAP_VIEW["west"], "east": MAP_VIEW["east"],
        "south": MAP_VIEW["south"], "north": MAP_VIEW["north"],
    }


# ============================================================
# 写盘（确定性 + 幂等）
# ============================================================
def _dump_bytes(obj: object) -> bytes:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)
    return (text + "\n").encode("utf-8")


def _write_if_changed(path: str, payload: bytes) -> str:
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if fh.read() == payload:
                return "unchanged"
    with open(path, "wb") as fh:
        fh.write(payload)
    return "written"


# ============================================================
# 主流程：校验 → 组装 → 写盘 → 摘要
# ============================================================
def generate_all(out_dir: str = OUT_DIR) -> int:
    problems = validate_geo()
    if problems:
        print("[build_map_geo] 校验未通过，拒绝生成：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    os.makedirs(out_dir, exist_ok=True)
    try:
        outputs: dict[str, dict[str, object]] = {
            "regimes.geojson": build_regimes(),
            "regime_borders.geojson": build_regime_borders(),
            "regime_prefectures.geojson": build_regime_prefectures(),
            "cities.geojson": build_cities(),
            "view.json": build_view(),
        }
    except ValueError as exc:
        print(f"[build_map_geo] 州/府级数据校验未通过，拒绝生成：{exc}",
              file=sys.stderr)
        return 2
    counts: dict[str, tuple[str, int]] = {}
    for fname, obj in outputs.items():
        status = _write_if_changed(os.path.join(out_dir, fname), _dump_bytes(obj))
        feats = obj.get("features")
        n = len(feats) if isinstance(feats, list) else 0
        counts[fname] = (status, n)
        print(f"[build_map_geo] {fname:<18} {status:<9} features={n}")

    total = sum(n for _, n in counts.values())
    print(f"[build_map_geo] 完成：{len(counts)} 个文件，共 {total} 个要素 → {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="宋祚舆图 GeoJSON 生成器")
    parser.add_argument("--check", action="store_true",
                        help="仅运行一致性校验，不写任何文件")
    parser.add_argument("--out", default=OUT_DIR, help="输出目录（默认 assets/map/web）")
    args = parser.parse_args(argv)

    problems = validate_geo()
    if problems:
        print("[build_map_geo] 校验未通过：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    print(f"[build_map_geo] 校验通过（{len(CIRCUIT_INFO)} 路 / "
          f"{len(active_regimes())} 活跃政权）")
    if args.check:
        return 0
    return generate_all(args.out)


if __name__ == "__main__":
    raise SystemExit(main())