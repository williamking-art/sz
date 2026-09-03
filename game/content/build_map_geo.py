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
    REGIME_GEO,
    REGIME_SUBDIVISIONS,
    active_regimes,
    all_city_points,
    validate_geo,
)

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
    """周边政权疆域层：active=False 者前端默认不渲染，待 timeline break 激活。

    母政权 feature 之后追加分路 feature（kind="sub"，properties.parent=政权id）：
    分路自持 owner（初始=母政权，可单独易主），随 feature 输出；
    active=False 的母政权（如金）不输出其分路。
    """
    features: list[dict[str, object]] = []
    for key, geo in REGIME_GEO.items():
        features.append(_polygon_feature(key, geo["polygon"], {
            "kind": "regime",
            "display_name": geo.get("name", key),
            "owner": geo.get("owner", key),
            "active": bool(geo.get("active")),
            "always_show": key in EXTERNAL_ALWAYS_SHOW,
            "label_at": geo.get("label_at"),
            "note": geo.get("note", ""),
        }))
        if not geo.get("active"):
            continue  # 未兴政权（金）：分路随母政权一并隐藏
        for sub in REGIME_SUBDIVISIONS.get(key, []):
            features.append(_polygon_feature(sub["name"], sub["polygon"], {
                "kind": "sub",
                "parent": key,
                "owner": sub.get("owner", key),
                "seat": sub.get("seat", ""),
                "seat_at": sub.get("seat_at"),
                "label_at": sub.get("label_at"),
            }))
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
    return {"type": "FeatureCollection", "features": features}


def build_view() -> dict[str, object]:
    """MapLibre 初始视野（fitBounds 用四至 + 中心点）。"""
    return {
        "bounds": [MAP_VIEW["west"], MAP_VIEW["south"],
                   MAP_VIEW["east"], MAP_VIEW["north"]],
        "center": [(MAP_VIEW["west"] + MAP_VIEW["east"]) / 2,
                   (MAP_VIEW["south"] + MAP_VIEW["north"]) / 2],
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