import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { feature } from "topojson-client";
import { MapController, type MapView as MapViewData } from "./mapController";
import { MarkerManager } from "./markers";
import { deriveMapState } from "./state";
import { SimplifyCache, tierForZoom } from "./simplify";
import { useGameStore } from "../store/gameStore";

// 舆图数据资产基址（构建期从 game/assets/map/web/ 平移）
const MAP_BASE_URL = import.meta.env.BASE_URL + "map";

const DEFAULT_VIEW: MapViewData = {
  bounds: [46.5, -44, 150, 56],
  center: [108, 31],
  east: 150,
  north: 56,
  south: -44,
  west: 46.5,
  zoom: 4.0
};

interface GeoData {
  circuits: GeoJSON.FeatureCollection;
  regimes: GeoJSON.FeatureCollection;
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
  const topoRef = useRef<SimplifyCache | null>(null);
  const tierRef = useRef<number>(-1);
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
        // 点选治所/路/政权 → 弹出详情卡
        pushOverlay({ kind: "detail", title: sel.name, props: { ...sel } });
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

      const data: GeoData = { land, lakes, rivers, circuits, regimes, cities, borders };
      // 预分配稳定 feature id（feature-state 依赖）
      for (const fc of [circuits, regimes, cities, land, rivers, lakes, borders]) {
        fc.features.forEach((f, j) => { f.id = j; });
      }
      dataRef.current = data;
      topoRef.current = new SimplifyCache(topo);
      controller.setData(data);
      buildLabels();
      const map = controller.getMap()!;
      // 首帧按当前 zoom 落一次简化档位 + 标签避让
      applyTier(map.getZoom());
      markersRef.current?.avoid();

      // 视口稳定后（移动/缩放结束）按档位重简化 + 标签显隐避让（防抖）
      map.on("moveend", () => {
        if (debounceRef.current) window.clearTimeout(debounceRef.current);
        debounceRef.current = window.setTimeout(() => {
          applyTier(map.getZoom());
          markersRef.current?.refresh(map.getZoom());
          markersRef.current?.avoid();
        }, 120);
      });
    } catch (e) {
      console.error("[map] 数据加载失败", e);
    }
  }

  /**
   * 按 zoom 切换几何简化档位（TopoJSON 运行时动态简化）。
   * 档位未变时 SimplifyCache 直接命中缓存，不重复解码。
   */
  function applyTier(zoom: number) {
    const controller = controllerRef.current;
    const topo = topoRef.current;
    const data = dataRef.current;
    if (!controller || !topo || !data) return;
    if (tierRef.current === tierForZoom(zoom)) return;
    tierRef.current = tierForZoom(zoom);
    for (const layer of ["circuits", "regimes", "circuit_borders"] as const) {
      const fc = topo.get(layer, zoom);
      fc.features.forEach((f, j) => { f.id = j; });
      controller.setLayerData(layer === "circuit_borders" ? "borders" : layer, fc);
    }
  }

  function buildLabels() {
    const data = dataRef.current;
    const markers = markersRef.current;
    const controller = controllerRef.current;
    if (!data || !markers || !controller) return;
    const map = controller.getMap()!;

    // 政权标签
    for (const f of data.regimes.features) {
      const p = f.properties as Record<string, unknown>;
      if (p.kind === "sub") continue;
      const at = (p.label_at as [number, number]) || centerOf(f);
      const on = !!p.active;
      markers.addLabel(
        at,
        String(p.display_name || p.name),
        `lbl-regime${on ? "" : " off"}`,
        0,
        on,
        () => selectFeature("regime", String(p.name)),
        { kind: "regime", name: String(p.name) }
      );
    }
    // 分路标签
    for (const f of data.regimes.features) {
      const p = f.properties as Record<string, unknown>;
      if (p.kind !== "sub") continue;
      const at = (p.label_at as [number, number]) || centerOf(f);
      const mk = markers.addLabel(
        at,
        String(p.name),
        "lbl-circuit",
        3.2,
        true,
        () => selectFeature("sub", String(p.name)),
        { kind: "sub", name: String(p.name), parent: String(p.parent), owner: String(p.owner) }
      );
      const el = mk.getElement();
      el.style.fontSize = "10.5px";
      el.style.letterSpacing = "1.5px";
      el.style.color = "#6b5b45";
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
    // 治所标签
    for (const f of data.cities.features) {
      const p = f.properties as Record<string, unknown>;
      const seat = !!p.is_seat;
      const cls = `lbl-city${seat ? " seat" : ""}${p.level === "京府" ? " jingfu" : ""}`;
      const tier = p.level === "京府" ? 3.0 : seat ? 3.4 : 4.6;
      const geom = f.geometry;
      if (geom.type !== "Point") continue;
      markers.addLabel(
        geom.coordinates as [number, number],
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
    setSelected({ kind, name });
    pushOverlay({ kind: "detail", title: name, props: { kind, name } });
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