import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { feature } from "topojson-client";
import { MapController, MAP_BASE_URL, type MapView as MapViewData } from "./mapController";
import { MarkerManager } from "./markers";
import { deriveMapState } from "./state";
import { useGameStore } from "../store/gameStore";

const DEFAULT_VIEW: MapViewData = {
  bounds: [60, -44, 150, 56],
  center: [108, 31],
  east: 150,
  north: 56,
  south: -44,
  west: 60,
  zoom: 4.0
};

interface GeoData {
  circuits: GeoJSON.FeatureCollection;
  regimes: GeoJSON.FeatureCollection;
  regime_borders: GeoJSON.FeatureCollection;
  cities: GeoJSON.FeatureCollection;
  land: GeoJSON.FeatureCollection;
  rivers: GeoJSON.FeatureCollection;
  lakes: GeoJSON.FeatureCollection;
  borders: GeoJSON.FeatureCollection;
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<MapController | null>(null);
  const markersRef = useRef<MarkerManager | null>(null);
  const dataRef = useRef<GeoData | null>(null);
  const debounceRef = useRef<number | null>(null);
  const state = useGameStore((s) => s.state);
  const setSelected = useGameStore((s) => s.setSelected);
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  // 初始化舆图
  useEffect(() => {
    if (!containerRef.current) return;
    const controller = new MapController({
      container: containerRef.current,
      view: DEFAULT_VIEW,
      onSelect: (sel) => {
        setSelected(sel);
        // 1. 高亮朱红描边
        if (controllerRef.current) {
          controllerRef.current.highlightSelected(sel.feature ?? null);
        }
        // 2. 治所/城池激发朱红呼吸光环
        if (markersRef.current && sel.coordinate) {
          markersRef.current.pulseAt(sel.coordinate);
        }
        // 3. 弹出全属性详情卡 (props.props 完整透传)
        pushOverlay({
          kind: "detail",
          title: sel.name,
          props: {
            kind: sel.kind,
            name: sel.name,
            props: sel.props || {},
          },
        });
      },
      onMapReady: () => {
        controllerRef.current = controller;
        markersRef.current = new MarkerManager(controller.getMap()!);
        loadGeoData();
      }
    });
    controller.init();
    return () => {
      controller.destroy();
      controllerRef.current = null;
      markersRef.current = null;
      dataRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadGeoData() {
    const controller = controllerRef.current;
    if (!controller) return;
    try {
      const loadGeo = async (name: string) => {
        const res = await fetch(`${MAP_BASE_URL}/${name}.geojson`);
        if (!res.ok) throw new Error(`${name} → HTTP ${res.status}`);
        return (await res.json()) as GeoJSON.FeatureCollection;
      };
      // regions.topojson：构建期由 circuits/regimes/circuit_borders 拓扑化而来
      const loadTopo = async () => {
        const res = await fetch(`${MAP_BASE_URL}/regions.topojson`);
        if (!res.ok) throw new Error(`regions.topojson → HTTP ${res.status}`);
        return (await res.json()) as TopoJSON.Topology;
      };

      const [land, lakes, rivers, cities, topo] = await Promise.all([
        loadGeo("land"), loadGeo("lakes"), loadGeo("rivers"),
        loadGeo("cities"), loadTopo()
      ]);
      // TopoJSON → GeoJSON 解码（共享弧，体积已降）
      const circuits = feature(topo, topo.objects.circuits) as GeoJSON.FeatureCollection;
      const regimes = feature(topo, topo.objects.regimes) as GeoJSON.FeatureCollection;
      const borders = feature(topo, topo.objects.circuit_borders) as GeoJSON.FeatureCollection;
      const regime_borders_fc = feature(topo, topo.objects.regime_borders) as GeoJSON.FeatureCollection;

      const data: GeoData = { land, lakes, rivers, circuits, regimes, regime_borders: regime_borders_fc, cities, borders };
      // 预分配稳定 feature id（feature-state 依赖）
      for (const fc of [circuits, regimes, regime_borders_fc, cities, land, rivers, lakes, borders]) {
        fc.features.forEach((f, j) => { f.id = j; });
      }
      dataRef.current = data;
      // 政权几何全精度注入(不再按 zoom 分档简化):精确国界/省界被简化
      // 会在中低缩放退化为直线多边形
      controller.setData(data);
      buildLabels();
      const map = controller.getMap()!;
      // 视口稳定后标签显隐避让(防抖)
      map.on("moveend", () => {
        if (debounceRef.current) window.clearTimeout(debounceRef.current);
        debounceRef.current = window.setTimeout(() => {
          markersRef.current?.refresh(map.getZoom());
          markersRef.current?.avoid();
        }, 120);
      });

      // 点击地图空白海域/无要素处: 清除高亮与光环
      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, {
          layers: ["cities", "circuits", "regimes"],
        });
        if (hits.length === 0) {
          controller.highlightSelected(null);
          markersRef.current?.clearPulse();
        }
      });
    } catch (e) {
      console.error("[map] 数据加载失败", e);
    }
  }

  function buildLabels() {
    const data = dataRef.current;
    const markers = markersRef.current;
    const controller = controllerRef.current;
    if (!data || !markers || !controller) return;
    const map = controller.getMap()!;

    // 1. 宏观政权标签 (zoom: 0, 全国视野可见)
    const seenRegimes = new Set<string>();
    for (const f of data.regimes.features) {
      const p = f.properties as Record<string, unknown>;
      if (p.kind !== "regime" && p.kind !== "part") continue;
      const nm = String(p.name || "");
      if (!nm) continue; // 中立省份无名
      if (seenRegimes.has(nm)) continue;
      seenRegimes.add(nm);

      const at = (p.label_at as [number, number]) || centerOf(f);
      const on = !!p.active;
      markers.addLabel(
        at,
        nm,
        `lbl-regime${on ? "" : " off"}`,
        0,
        on,
        () => selectFeature("regime", nm),
        { kind: "regime", name: nm }
      );
    }

    // 2. 辽五京道、西夏各道历史省道标签 (zoom: 3.6, 与宋路同级显现)
    // 严格白名单机制：绝对杜绝现代区划字样(省/市/自治区/盟/州/县等)
    const VALID_HISTORICAL_ROADS = new Set([
      "南京道", "西京道", "中京道", "东京道", "上京道",
      "兴庆府直辖", "河西走廊", "河南地",
    ]);

    const seenRoads = new Set<string>();
    for (const f of data.regimes.features) {
      const p = f.properties as Record<string, unknown>;
      const prov = String(p.province || "");
      if (!VALID_HISTORICAL_ROADS.has(prov)) continue;
      if (seenRoads.has(prov)) continue;
      seenRoads.add(prov);

      const at = (p.label_at as [number, number]) || centerOf(f);
      markers.addLabel(
        at,
        prov,
        "lbl-circuit",
        3.6,
        true,
        () => selectFeature("circuit", prov)
      );
    }
    // 路标签
    for (const f of data.borders.features) {
      const p = f.properties as Record<string, unknown>;
      markers.addLabel(
        (p.label_at as [number, number]) || centerOf(f),
        String(p.name),
        "lbl-circuit",
        4.0,
        true,
        () => selectFeature("circuit", String(p.name))
      );
    }
    // 治所与江河水系标签
    for (const f of data.cities.features) {
      const p = f.properties as Record<string, unknown>;
      const geom = f.geometry;
      if (geom.type !== "Point") continue;
      const coord = geom.coordinates as [number, number];

      // 著名古江河水系注记
      if (p.kind === "river") {
        markers.addLabel(coord, String(p.name), "lbl-river", 4.0, true);
        continue;
      }

      // 城市与府州治所
      const seat = !!p.is_seat;
      const cls = `lbl-city${seat ? " seat" : ""}${p.level === "京府" ? " jingfu" : ""}`;
      const tier = p.level === "京府" ? 3.0 : seat ? 3.4 : 4.6;
      markers.addLabel(
        coord,
        String(p.name),
        cls,
        tier,
        true,
        () => selectFeature("city", String(p.name))
      );
    }
    markers.refresh(map.getZoom());
  }

  function selectFeature(kind: string, name: string) {
    const data = dataRef.current;
    let foundFeature: GeoJSON.Feature | undefined;
    let foundProps: Record<string, unknown> = {};
    let foundCoord: [number, number] | undefined;

    if (data) {
      if (kind === "city") {
        const f = data.cities.features.find((c) => c.properties?.name === name);
        if (f) {
          foundFeature = f;
          foundProps = (f.properties || {}) as Record<string, unknown>;
          const g = f.geometry as any;
          if (g && g.type === "Point" && Array.isArray(g.coordinates)) {
            foundCoord = [g.coordinates[0], g.coordinates[1]];
          }
        }
      } else if (kind === "circuit") {
        // 先查宋路
        let f = data.circuits.features.find((c) => c.properties?.name === name);
        // 再查辽道/夏道
        if (!f) {
          f = data.regimes.features.find((r) => r.properties?.province === name);
        }
        if (f) {
          foundFeature = f;
          foundProps = (f.properties || {}) as Record<string, unknown>;
          foundCoord = centerOf(f);
        }
      } else if (kind === "regime") {
        const f = data.regimes.features.find((r) => r.properties?.name === name);
        if (f) {
          foundFeature = f;
          foundProps = (f.properties || {}) as Record<string, unknown>;
          foundCoord = centerOf(f);
        }
      }
    }

    const sel = {
      kind,
      name,
      props: foundProps,
      feature: foundFeature,
      coordinate: foundCoord,
    };

    setSelected(sel);
    if (controllerRef.current) {
      controllerRef.current.highlightSelected(foundFeature ?? null);
    }
    if (markersRef.current && foundCoord) {
      markersRef.current.pulseAt(foundCoord);
    }
    pushOverlay({
      kind: "detail",
      title: name,
      props: { kind, name, props: foundProps },
    });
  }

  // 状态同步：active/hidden/sub_owners/markers/focus/select
  useEffect(() => {
    const controller = controllerRef.current;
    const markers = markersRef.current;
    const data = dataRef.current;
    if (!controller || !markers || !data) return;
    const ms = deriveMapState(state);
    const map = controller.getMap()!;

    // 政权显隐
    const activeSet = new Set(ms.activeRegimes);
    const hiddenSet = new Set(ms.hiddenRegimes);
    const regimeOn: Record<string, boolean> = {};
    for (const f of data.regimes.features) {
      const p = f.properties as Record<string, unknown>;
      if (p.kind === "sub") continue;
      const name = String(p.name);
      regimeOn[name] = (!!p.active || activeSet.has(name)) && !hiddenSet.has(name);
    }
    markers.refreshRegimeLabels(regimeOn, (parent, owner) => {
      return regimeOn[parent] || owner === "宋" || !!regimeOn[owner];
    });

    // 自定义标注
    markers.applyCustom(ms.markers);

    // 视角聚焦
    if (ms.focus) {
      if (ms.focus.bounds) {
        const b = ms.focus.bounds;
        map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 70, maxZoom: 6.5, duration: 620 });
      } else if (ms.focus.lng != null && ms.focus.lat != null) {
        map.flyTo({ center: [ms.focus.lng, ms.focus.lat], zoom: ms.focus.zoom || 4.6, duration: 620 });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  // 监听详情卡下发的平滑下钻聚焦事件 (sz:map-focus)
  useEffect(() => {
    const handleFocus = (ev: Event) => {
      const customEv = ev as CustomEvent<{ name: string; kind: string; props: Record<string, unknown> }>;
      const { name, kind, props } = customEv.detail || {};
      const controller = controllerRef.current;
      const data = dataRef.current;
      if (!controller || !data) return;
      const map = controller.getMap();
      if (!map) return;

      if (kind === "city") {
        const f = data.cities.features.find((c) => c.properties?.name === name);
        if (f && f.geometry.type === "Point") {
          const [lng, lat] = f.geometry.coordinates as [number, number];
          map.flyTo({ center: [lng, lat], zoom: 6.2, duration: 800 });
          markersRef.current?.pulseAt([lng, lat]);
          controller.highlightSelected(f);
        }
      } else if (kind === "circuit" || kind === "sub") {
        const f = data.circuits.features.find((c) => c.properties?.name === name) ||
                  data.regimes.features.find((r) => r.properties?.province === name);
        if (f) {
          controller.highlightSelected(f);
          const c = centerOf(f);
          if (c) {
            map.flyTo({ center: c, zoom: 5.4, duration: 800 });
            markersRef.current?.pulseAt(c);
          }
        }
      } else if (kind === "regime") {
        const f = data.regimes.features.find((r) => r.properties?.name === name);
        if (f) {
          controller.highlightSelected(f);
          const c = centerOf(f);
          if (c) {
            map.flyTo({ center: c, zoom: 4.8, duration: 800 });
          }
        }
      }
    };

    window.addEventListener("sz:map-focus", handleFocus);
    return () => window.removeEventListener("sz:map-focus", handleFocus);
  }, []);

  return <div ref={containerRef} className="absolute inset-0" />;
}

// ---- 工具 ----
function bboxOfRing(ring: number[][]): [number, number, number, number] {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  for (const p of ring) {
    if (p[0] < x0) x0 = p[0];
    if (p[0] > x1) x1 = p[0];
    if (p[1] < y0) y0 = p[1];
    if (p[1] > y1) y1 = p[1];
  }
  return [x0, y0, x1, y1];
}

function centerOf(feature: GeoJSON.Feature): [number, number] {
  const g = feature.geometry;
  if (g.type === "Point") return g.coordinates as [number, number];
  const rings: number[][][] = [];
  if (g.type === "Polygon") rings.push(g.coordinates[0]);
  else if (g.type === "MultiPolygon") {
    for (const poly of g.coordinates) rings.push(poly[0]);
  }
  let best: [number, number, number, number] | null = null;
  let bestArea = -1;
  for (const r of rings) {
    const b = bboxOfRing(r);
    const a = (b[2] - b[0]) * (b[3] - b[1]);
    if (a > bestArea) { bestArea = a; best = b; }
  }
  return best ? [(best[0] + best[2]) / 2, (best[1] + best[3]) / 2] : [0, 0];
}