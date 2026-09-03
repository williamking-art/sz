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
from content.geo_admin import (
    CIRCUIT_INFO,
    MAP_VIEW,
    REGIME_CITIES,
    REGIME_COLORS,
    REGIME_GEO,
    REGIME_PARTS,
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
    return features


def build_regime_borders() -> dict[str, object]:
    """辽五京道、西夏各道的省道界线层(kind=regime_border),与宋路界线同级细描边。"""
    from shapely.geometry import mapping, shape
    from shapely.ops import linemerge, unary_union

    raw_dir = os.path.join(MAP_DIR, "raw")
    prov_path = os.path.join(raw_dir, "datav_100000_full.json")
    with open(prov_path, encoding="utf-8") as f:
        by_name = {p["properties"]["name"]: p for p in json.load(f)["features"]}

    features: list[dict[str, object]] = []
    for key, spec in REGIME_PARTS.items():
        if not spec.get("borders"):
            continue
        sub_roads = spec.get("sub_roads")
        if sub_roads:
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
                if geoms:
                    u = unary_union(geoms).buffer(0.0015).buffer(-0.0015)
                    b = u.boundary
                    if b.geom_type == "MultiLineString":
                        b = linemerge(b)
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(b),
                        "properties": {"kind": "regime_border", "name": key, "province": rname},
                    })
    return {"type": "FeatureCollection", "features": features}


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
    outputs: dict[str, dict[str, object]] = {
        "regimes.geojson": build_regimes(),
        "regime_borders.geojson": build_regime_borders(),
        "cities.geojson": build_cities(),
        "view.json": build_view(),
    }
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