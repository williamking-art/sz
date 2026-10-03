# -*- coding: utf-8 -*-
"""P1-2 舆图回归保护：黔中—湖南—湖北交界归属与几何连续性 + 府界接入产物。

审查任务书（`game/游戏审查整改实施指南.md` P1-2）验收条件：
> · 重点区域不存在意外空洞、重叠或异常飞线；抽查的相邻府/路归属正确。
> · 目标政区边界在游戏实际地图上可辨认，且缩放、点击、标签和既有路界正常。
> · 缺失瓦片不再造成持续 404，或对应图层按预期关闭。
> · 提供更新前后同范围、同缩放级别的截图或其他可复查证据。

本文件把"可复查证据"固化为**可复跑断言**（截图仍需人工，见报告"未执行项"）：
  ① 归属：黔中/荆湖北路/夔州路 的现代地级市归属，直接读生成产物 `prefectures.geojson`
     的 `prefecture`（成员现代地级市名）+ `circuit`（所属宋路）两个字段——数据驱动，
     不靠人工目视、不依赖 raw DataV 源；
  ② 几何：`circuits.geojson` 在 ROI 内**无大面积空洞 / 无异常重叠 / 无飞线**；
  ③ 接入：府界拓扑产物存在且可解码、体积在预算内；`regions.topojson` 的对象集合
     与首帧预算未被改动（府界刻意独立成文件，见 `scripts/build-topo.ts`）。
  ④ 治所账目：历史治所（`CIRCUIT_INFO.members`）→ 府块 / **省级归入** 的恒等式与守恒
     （用户 2026-09-29 裁决：无府块者按历史数据归入省级，份额留在路级）。

依赖：`shapely`（几何部分）。缺失则**跳过**几何用例，只跑归属与产物用例——
避免把"本机没装可选的几何库"误报成产品缺陷。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

WEB = os.path.join(_GAME_ROOT, "assets", "map", "web")
PUB = os.path.join(_GAME_ROOT, "frontend", "public", "map")

#: 关注区域（黔中—湖南—湖北—夔州交界），与审查任务书点名范围一致
ROI = (102.0, 22.0, 116.0, 34.0)
#: 任务书实证基线（2026-09-28 生成批次实测）。阈值刻意留 3× 余量：
#: 空洞最大 0.000275 平方度（≈1.8 km 见方）、重叠最大 0.00305 平方度。
VOID_MAX_SQ_DEG = 0.001
OVERLAP_MAX_SQ_DEG = 0.01
#: 飞线判据：任一相邻顶点距离不得超过 0.6 度（≈60 km）——实测最长边远小于此
EDGE_MAX_DEG = 0.6
#: 府界拓扑体积预算（量化后实测 2.87 MB；超此说明量化/懒加载策略被破坏）
PREFECTOPO_MAX_BYTES = 6 * 1024 * 1024


def _load(path):
    if not os.path.exists(path):
        pytest.skip(f"缺少生成产物：{path}（需先跑地图生成/构建）")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _prefecture_rows():
    fc = _load(os.path.join(WEB, "prefectures.geojson"))
    rows = []
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        members = p.get("prefecture") or []
        # 生成器把成员现代地级市写成 **顿号分隔的字符串**（如 "邯郸市、邢台市"），
        # 不是数组——按字符串迭代会得到单个汉字（本用例第一版即踩此坑）。
        if isinstance(members, str):
            members = [m for m in members.split("、") if m.strip()]
        rows.append({"seat": str(p.get("name") or ""),
                     "circuit": str(p.get("circuit") or ""),
                     "members": [str(m).strip() for m in members]})
    return rows


# ============================================================
# ① 归属：抽查相邻府/路归属正确（数据驱动，不靠目视）
# ============================================================
def test_roi_prefecture_attribution_is_correct():
    """黔中交界重点城市的归属必须正确（怀化→荆湖北路、秀山→夔州路、黔中各市→黔中路）。

    这些正是审查任务书点名的"此前发现的问题"所在；`prefectures.geojson` 的
    `prefecture` 字段列出该块包含的现代地级市，`circuit` 给出所属宋路。
    """
    rows = _prefecture_rows()
    assert rows, "prefectures.geojson 无要素（生成失败？）"
    idx = {}
    for r in rows:
        for m in r["members"]:
            idx.setdefault(m, set()).add(r["circuit"])

    def _expect(city, circuit, *aliases):
        got = set()
        for name in (city,) + aliases:
            got |= idx.get(name, set())
        assert got == {circuit}, f"{city} 应属 {circuit}，实测 {sorted(got) or '无块'}"

    # 任务书已知现状点名的两处（此前核对为怀化归荆湖北路、秀山归夔州路）
    _expect("怀化市", "荆湖北路")
    _expect("秀山土家族苗族自治县", "夔州路", "秀山")
    # 黔中路主体（贵州各市）
    for city in ("铜仁市", "遵义市", "黔东南苗族侗族自治州", "黔南布依族苗族自治州",
                 "黔西南布依族苗族自治州", "安顺市", "贵阳市", "毕节市", "六盘水市"):
        _expect(city, "黔中路")
    # 邻接路口径
    _expect("湘西土家族苗族自治州", "荆湖北路")
    _expect("恩施土家族苗族自治州", "夔州路")
    _expect("泸州市", "成都府路")
    _expect("邵阳市", "荆湖南路")
    _expect("百色市", "广南西路", "河池市")


def test_no_prefecture_block_claims_two_circuits():
    """同一现代地级市不得被两个路同时认领（生成器"先筛候选治所再匹配"的回归保护）。"""
    rows = _prefecture_rows()
    seen = {}
    for r in rows:
        if not r["circuit"]:
            pytest.fail(f"府块 {r['seat']!r} 缺 circuit 字段")
        for m in r["members"]:
            seen.setdefault(m, set()).add(r["circuit"])
    dup = {m: sorted(cs) for m, cs in seen.items() if len(cs) > 1}
    assert not dup, f"以下地级市被多路重复认领：{dup}"


def test_seat_ledger_identity_and_circuit_attribution():
    """**历史治所账目**（用户 2026-09-29 裁决：无府块者按历史数据归入省级）。

    恒等式与归属，一次全锁：
      · `seats == blocked + merged`（历史席位 = 有府块 + 省级归入）
      · `prefecture_blocks == blocked + offtable_blocks`（府块 = 历史有块 + 表外直挂）
      · 无块的历史席位**恰好**等于台账登记的省级归入集合（不多不少、不重复）
      · 每条省级归入确实属于其所属路的历史治所表，且**没有**独立府块
      · 表外直挂块（台湾省→福建路·台湾府，不在 members 里）单独登记，不混入"有块席位"
    """
    from content.geo_admin import CIRCUIT_INFO
    led = _load(os.path.join(WEB, "circuit_seat_ledger.json"))
    t = led["totals"]
    assert t["seats"] == t["blocked"] + t["merged"], f"席数不守恒：{t}"
    assert t["prefecture_blocks"] == t["blocked"] + t["offtable_blocks"], f"府块数不自洽：{t}"

    blocks = {(r["circuit"], r["seat"]) for r in _prefecture_rows()}
    hist = {(c, str(m[0])) for c, i in CIRCUIT_INFO.items() for m in (i.get("members") or [])}
    assert t["seats"] == len(hist), f"台账席数 {t['seats']} ≠ 历史治所数 {len(hist)}"
    assert len(blocks) == t["prefecture_blocks"]

    merged = {(c, m["name"]) for c, v in led["circuits"].items() for m in v["seats_merged"]}
    off = {(c, m["name"]) for c, v in led["circuits"].items() for m in v["blocks_offtable"]}
    assert merged <= hist, f"省级归入含非历史治所：{merged - hist}"
    assert not (merged & blocks), f"同一条治所既归入省级又有府块：{merged & blocks}"
    assert hist - blocks == merged, \
        f"无块历史席位与台账登记不一致：实际 {sorted(hist - blocks)}，台账 {sorted(merged)}"
    assert off == blocks - hist, f"表外直挂块登记不全：块 {sorted(blocks - hist)}，台账 {sorted(off)}"
    assert len(merged) == t["merged"], "台账 totals 与逐路明细不一致"
    # 任务书点名的 ROI 席位必须在省级归入名单里（否则说明归属又被现代质心牵着走）
    assert ("荆湖北路", "澧州") in merged
    # 每路 seats_total/blocked 与历史表逐条对齐
    for cname, v in led["circuits"].items():
        members = [str(m[0]) for m in (CIRCUIT_INFO.get(cname, {}).get("members") or [])]
        assert v["seats_total"] == len(members), f"{cname} seats_total 与历史表不符"
        assert v["seats_merged_count"] == len(v["seats_merged"])
        assert v["seats_blocked"] == v["seats_total"] - v["seats_merged_count"]


def test_demog_residual_conserves_circuit_totals():
    """**省级残留守恒**：Σ府块 + 省级残留 == 路级总量（逐维 + yields 逐货品）。

    这是"归入省级"的数值落地：收回的份额留在路级（`demog_residual`），
    既没蒸发、也没摊回邻府。
    """
    from content.data import PREFECTURE_INFO
    from content.demography import EXTRA_CIRCUIT_DEMOG

    led = _load(os.path.join(WEB, "circuit_seat_ledger.json"))
    pref = _load(os.path.join(WEB, "prefectures.geojson"))["features"]
    bad = []
    moved = 0
    for cname, v in led["circuits"].items():
        base = PREFECTURE_INFO.get(cname) or EXTRA_CIRCUIT_DEMOG.get(cname) or {}
        res = v.get("demog_residual") or {}
        rows = [f["properties"] for f in pref
                if (f.get("properties") or {}).get("circuit") == cname]
        for dim in ("population", "households", "land", "grain", "monthly_tax"):
            if base.get(dim) is None:
                continue
            s = sum(int(r.get(dim) or 0) for r in rows)
            r_ = int(res.get(dim) or 0)
            if s + r_ != int(base[dim]):
                bad.append((cname, dim, s, r_, int(base[dim])))
            moved += abs(r_)
        for dim, val in (base.get("yields") or {}).items():
            s = sum(int((r.get("yields") or {}).get(dim) or 0) for r in rows)
            r_ = int((res.get("yields") or {}).get(dim) or 0)
            if s + r_ != int(val):
                bad.append((cname, "yields." + dim, s, r_, int(val)))
    assert not bad, f"省级归入后不守恒 {len(bad)} 处：{bad[:5]}"
    assert moved > 0, "无任何份额留在省级——省级归入未生效"
    # 有省级归入的路，其有块席位必须**少于**历史席位数
    for cname, v in led["circuits"].items():
        if v["seats_merged_count"]:
            assert v["seats_blocked"] < v["seats_total"]


# ============================================================
# ② 几何：无大面积空洞 / 无异常重叠 / 无飞线
# ============================================================
def _shapely():
    return pytest.importorskip("shapely", reason="几何核对需要 shapely（可选依赖）")


def _circuit_shapes():
    _shapely()
    from shapely.geometry import shape
    fc = _load(os.path.join(WEB, "circuits.geojson"))
    out = {}
    for f in fc.get("features", []):
        name = str((f.get("properties") or {}).get("name") or "")
        if name:
            out[name] = shape(f["geometry"])
    assert out, "circuits.geojson 无有效要素"
    return out


def test_roi_has_no_large_land_void():
    """ROI 内不得存在大面积空洞（此前"大面积空白"缺陷的回归保护）。

    只查**内部空洞环**（interior ring）——海岸/湖泊/境外未归属区不算空洞：
    实测 ROI 内最大内部空洞 0.000275 平方度（≈1.8 km），远小于阈值。
    """
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    shapes = _circuit_shapes()
    roi = box(*ROI)
    union = unary_union([s.buffer(0) for s in shapes.values()])
    clipped = union.intersection(roi)
    geoms = list(clipped.geoms) if hasattr(clipped, "geoms") else [clipped]
    voids = []
    for g in geoms:
        for ring in g.interiors:
            poly = Polygon(ring)
            if poly.area > 0:
                voids.append(poly.area)
    big = sorted((a for a in voids if a > VOID_MAX_SQ_DEG), reverse=True)
    assert not big, (f"ROI 内出现 {len(big)} 个超阈值空洞，最大 {big[0]:.6f} 平方度"
                     f"（阈值 {VOID_MAX_SQ_DEG}）；总空洞面积 {sum(voids):.5f}")


def test_roi_overlaps_are_negligible():
    """相邻路不得大面积重叠（同色填充下重叠会掩盖错误几何）。"""
    from shapely.geometry import box

    shapes = _circuit_shapes()
    roi = box(*ROI)
    names = sorted(shapes)
    worst = (0.0, "")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = shapes[a].intersection(shapes[b])
            if inter.is_empty:
                continue
            if not inter.intersects(roi):
                continue
            if inter.area > worst[0]:
                worst = (inter.area, f"{a}↔{b}")
    assert worst[0] <= OVERLAP_MAX_SQ_DEG, \
        f"路级重叠过大：{worst[1]} {worst[0]:.6f} 平方度（阈值 {OVERLAP_MAX_SQ_DEG}）"


def test_no_flyline_edges_in_roi():
    """任一相邻顶点距离不得 > `EDGE_MAX_DEG`（飞线/自交的量化判据）。"""
    import math

    shapes = _circuit_shapes()
    worst = 0.0
    where = ""
    for name, g in shapes.items():
        polys = list(g.geoms) if hasattr(g, "geoms") else [g]
        for poly in polys:
            for ring in [poly.exterior, *poly.interiors]:
                pts = list(ring.coords)
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    if not (ROI[0] <= x0 <= ROI[2] and ROI[1] <= y0 <= ROI[3]):
                        continue
                    d = math.hypot(x1 - x0, y1 - y0)
                    if d > worst:
                        worst, where = d, name
    assert worst <= EDGE_MAX_DEG, f"疑似飞线：{where} 存在 {worst:.3f} 度的相邻顶点跨度"


# ============================================================
# ③ 接入产物：府界独立拓扑 + 首帧预算未被破坏 + hill 策略
# ============================================================
def _decode_topology(path, obj_name):
    """最小 TopoJSON 解码（仅取该对象的坐标点），避免为测试引入额外依赖。"""
    topo = _load(path)
    tr = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        pts, x, y = [], 0, 0
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x, y))
        arcs.append(pts)

    def ring_from(indices):
        out = []
        for i in indices:
            seg = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
            if out:
                seg = seg[1:]        # 相邻弧共享端点，去重
            out.extend(seg)
        return out

    def coords(geom):
        t = geom["type"]
        if t == "LineString":
            return ring_from(geom["arcs"])
        if t == "MultiLineString":
            return [ring_from(a) for a in geom["arcs"]]
        if t == "Polygon":
            return [ring_from(a) for a in geom["arcs"]]
        if t == "MultiPolygon":
            return [[ring_from(a) for a in poly] for poly in geom["arcs"]]
        return []

    obj = topo["objects"][obj_name]
    geoms = obj.get("geometries") if obj.get("type") == "GeometryCollection" else [obj]
    out = []
    for g in geoms:
        pts = coords(g)
        flat = []

        def walk(c):
            if c and isinstance(c[0], (int, float)):
                flat.append((c[0], c[1]))
            else:
                for cc in c:
                    walk(cc)
        walk(pts)
        if tr:      # 反量化：先缩放平移，再交给调用方
            sx, sy = tr["scale"]
            tx, ty = tr["translate"]
            flat = [(tx + x * sx, ty + y * sy) for x, y in flat]
        out.append(flat)
    return out


def test_prefecture_border_topology_is_wired_and_within_budget():
    """府界拓扑产物：可解码、127 段、体积在预算内（懒加载 + 量化策略的回归保护）。"""
    path = os.path.join(PUB, "prefecture_borders.topojson")
    if not os.path.exists(path):
        pytest.fail("缺少 frontend/public/map/prefecture_borders.topojson"
                    "——请跑 `npm run build:topo`（府界接入的必要产物）")
    size = os.path.getsize(path)
    assert size <= PREFECTOPO_MAX_BYTES, \
        f"府界拓扑 {size/1048576:.2f} MB 超预算 {PREFECTOPO_MAX_BYTES/1048576:.0f} MB" \
        f"（会拖慢懒加载；检查 build-topo.ts 的 PREFECTURE_QUANTIZATION）"
    lines = _decode_topology(path, "prefecture_borders")
    assert len(lines) == 127, f"府界段数应为 127（生成批次约定），实测 {len(lines)}"
    assert sum(len(x) for x in lines) > 10000, "府界顶点数异常偏少（量化过度？）"
    # 坐标必须落在合理经纬度范围（防量化/平移写错导致飞到几内亚湾）。
    # 纬度下界放宽到 0：广南西路/福建路含**南海诸岛**（三沙市）→ 实测最低 3.84°N。
    xs = [p[0] for x in lines for p in x]
    ys = [p[1] for x in lines for p in x]
    assert 70 < min(xs) and max(xs) < 140, f"府界经度越界：{min(xs)}–{max(xs)}"
    assert -5 < min(ys) and max(ys) < 56, f"府界纬度越界：{min(ys)}–{max(ys)}"


def test_regions_topojson_first_frame_objects_unchanged():
    """府界**独立成文件**，不得混入 regions.topojson（首帧预算保护）。"""
    topo = _load(os.path.join(PUB, "regions.topojson"))
    assert set(topo["objects"]) == {"circuits", "regions_placeholder"} or \
        set(topo["objects"]) >= {"circuits", "regimes", "circuit_borders", "regime_borders"}, \
        f"regions.topojson 对象集合异常：{sorted(topo['objects'])}"
    assert "prefecture_borders" not in topo["objects"], \
        "府界被并入 regions.topojson → 首帧解析成本上升（应独立成文件、前端按 zoom 懒加载）"
    assert os.path.getsize(os.path.join(PUB, "regions.topojson")) < 20 * 1024 * 1024, \
        "regions.topojson 超 20 MB（首帧预算）"


def test_hill_tiles_dir_absence_matches_disabled_layer():
    """hill 处置：瓦片目录不存在时，前端必须**整层关闭**（否则每块瓦片持续 404）。

    本用例只断言"事实"（目录是否存在）并把决策点固定下来：若有人重新生成瓦片，
    这里会失败并提醒把 `layers.HILL_TILES_ENABLED` 打开——反之亦然。
    """
    tiles = os.path.join(PUB, "tiles", "hill")
    layers_ts = os.path.join(_GAME_ROOT, "frontend", "src", "renderer", "map", "layers.ts")
    if not os.path.exists(layers_ts):
        pytest.skip("找不到 layers.ts")
    with open(layers_ts, encoding="utf-8") as f:
        src = f.read()
    enabled = "export const HILL_TILES_ENABLED = true" in src
    disabled = "export const HILL_TILES_ENABLED = false" in src
    assert enabled or disabled, "layers.ts 未声明 HILL_TILES_ENABLED（hill 源/图层开关）"
    has_tiles = os.path.isdir(tiles) and any(
        os.scandir(tiles)) if os.path.isdir(tiles) else False
    if has_tiles:
        assert enabled, ("瓦片目录已存在却仍关闭 hill 图层——请把 HILL_TILES_ENABLED 改回 true；"
                         "并核对 fetch_hillshade.py 的 ZOOMS 与 source 的 minzoom/maxzoom 是否一致")
    else:
        assert disabled, ("瓦片目录缺失却仍启用 hill 图层 → 每块瓦片都会向 "
                          "app://songzuo/map/tiles/hill/… 发一次 404；请设 HILL_TILES_ENABLED=false")
