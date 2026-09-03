import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { buildLayerDefs, LAYER_IDS, THEME } from "./layers";
import type { Selected } from "../store/gameStore";

// 舆图数据资产基址（构建期从 game/assets/map/web/ 平移）
export const MAP_BASE_URL = import.meta.env.BASE_URL + "map";

export interface MapView {
  bounds: [number, number, number, number];
  center: [number, number];
  east: number;
  north: number;
  south: number;
  west: number;
  /** 玩家默认视野级别；缺省回退 3.2（全览） */
  zoom?: number;
}

export interface MapControllerOptions {
  container: HTMLElement;
  view: MapView;
  onSelect: (sel: Selected) => void;
  onMapReady?: () => void;
}

export class MapController {
  private map: maplibregl.Map | null = null;
  private container: HTMLElement;
  private view: MapView;
  private onSelect: (sel: Selected) => void;
  private onMapReady?: () => void;
  private selectedLayer: maplibregl.GeoJSONSource | null = null;

  constructor(opts: MapControllerOptions) {
    this.container = opts.container;
    this.view = opts.view;
    this.onSelect = opts.onSelect;
    this.onMapReady = opts.onMapReady;
  }

  init(): void {
    const [w, s, e, n] = this.view.bounds;
    this.map = new maplibregl.Map({
      container: this.container,
      style: {
        version: 8,
        sources: {},
        layers: []
      },
      center: this.view.center,
      zoom: this.view.zoom ?? 3.2,
      maxBounds: [[w, s], [e, n]],
      minZoom: 2,
      maxZoom: 9,
      attributionControl: false,
      fadeDuration: 0
    });

    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    this.map.addControl(new maplibregl.ScaleControl({ maxWidth: 120 }), "bottom-right");

    this.map.on("load", () => {
      this.addSources();
      this.addLayers();
      this.bindEvents();
      // 初始视野 = center/zoom（东亚重心）；bounds 全览仅经 fitBounds() 显式触发
      this.onMapReady?.();
    });
  }

  private addSources(): void {
    if (!this.map) return;
    const src = (id: string) =>
      this.map!.addSource(id, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });

    // 数据源由 setData 一次性填充（含 TopoJSON 解码结果）
    src("land");
    src("lakes");
    src("rivers");
    src("circuits");
    src("regimes");
    src("regime_borders");
    src("cities");
    src("borders");
    // 地形晕渲（山脉立体感）：ESRI World Hillshade，构建期平移至 map/tiles/hill
    this.map.addSource("hill", {
      type: "raster",
      tiles: [`${MAP_BASE_URL}/tiles/hill/{z}/{x}/{y}.png`],
      tileSize: 256,
      minzoom: 4,
      maxzoom: 8
    });
    this.map.addSource("selected", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] }
    });
  }

  private addLayers(): void {
    if (!this.map) return;
    for (const def of buildLayerDefs()) {
      this.map.addLayer(def as maplibregl.LayerSpecification);
    }
    // 选中高亮层（朱红描边）
    this.map.addLayer({
      id: LAYER_IDS.selected,
      type: "line",
      source: "selected",
      paint: { "line-color": THEME.red, "line-width": 2.5, "line-opacity": 0.95 }
    });
  }

  private bindEvents(): void {
    if (!this.map) return;
    this.map.on("click", LAYER_IDS.circuits, (e) => {
      const f = e.features?.[0];
      if (f) this.onSelect({ kind: "circuit", name: String(f.properties?.name ?? ""), id: String(f.id ?? "") });
    });
    this.map.on("click", LAYER_IDS.regimes, (e) => {
      const f = e.features?.[0];
      if (f) this.onSelect({ kind: "regime", name: String(f.properties?.name ?? ""), id: String(f.id ?? "") });
    });
    this.map.on("click", LAYER_IDS.cities, (e) => {
      const f = e.features?.[0];
      if (f) this.onSelect({ kind: "city", name: String(f.properties?.name ?? ""), id: String(f.id ?? "") });
    });
    // 光标
    this.map.on("mouseenter", LAYER_IDS.circuits, () => this.map!.getCanvas().style.cursor = "pointer");
    this.map.on("mouseleave", LAYER_IDS.circuits, () => this.map!.getCanvas().style.cursor = "");
    this.map.on("mouseenter", LAYER_IDS.cities, () => this.map!.getCanvas().style.cursor = "pointer");
    this.map.on("mouseleave", LAYER_IDS.cities, () => this.map!.getCanvas().style.cursor = "");
  }

  // 一次性注入全部图层数据（由 MapView 加载/解码后调用）
  setData(data: {
    land: GeoJSON.FeatureCollection;
    lakes: GeoJSON.FeatureCollection;
    rivers: GeoJSON.FeatureCollection;
    circuits: GeoJSON.FeatureCollection;
    regimes: GeoJSON.FeatureCollection;
    regime_borders: GeoJSON.FeatureCollection;
    cities: GeoJSON.FeatureCollection;
    borders: GeoJSON.FeatureCollection;
  }): void {
    if (!this.map) return;
    const set = (name: string, fc: GeoJSON.FeatureCollection) => {
      const src = this.map!.getSource(name) as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(fc);
    };
    set("land", data.land);
    set("lakes", data.lakes);
    set("rivers", data.rivers);
    set("circuits", data.circuits);
    set("regimes", data.regimes);
    set("regime_borders", data.regime_borders);
    set("cities", data.cities);
    set("borders", data.borders);
  }

  // 运行时按 zoom 档位重设单个图层几何（TopoJSON 动态简化后注入）
  setLayerData(name: string, fc: GeoJSON.FeatureCollection): void {
    if (!this.map) return;
    const src = this.map.getSource(name) as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(fc);
  }

  fitBounds(): void {
    if (!this.map) return;
    const [w, s, e, n] = this.view.bounds;
    this.map.fitBounds([[w, s], [e, n]], { padding: 20, duration: 0 });
  }

  // 视角下钻：聚焦某要素（层层递进）
  flyToFeature(bbox: [number, number, number, number], zoom?: number): void {
    if (!this.map) return;
    this.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
      padding: 60,
      maxZoom: zoom ?? 7,
      duration: 800
    });
  }

  resetView(): void {
    this.fitBounds();
  }

  highlightSelected(feature: GeoJSON.Feature | null): void {
    if (!this.map) return;
    const src = this.map.getSource("selected") as maplibregl.GeoJSONSource;
    if (!src) return;
    src.setData(feature ? { type: "FeatureCollection", features: [feature] } : { type: "FeatureCollection", features: [] });
  }

  getMap(): maplibregl.Map | null {
    return this.map;
  }

  destroy(): void {
    this.map?.remove();
    this.map = null;
  }
}