import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { feature } from "topojson-client";
import { MapController, MAP_BASE_URL, type MapView as MapViewData } from "./mapController";
import { PREFECTURE_BORDERS_ENABLED, PREFECTURE_BORDERS_MIN_ZOOM } from "./layers";
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
  const cancelledRef = useRef(false);
  // P2-3（M10）：地图资源错误必须有**玩家可见**的失败态，不能只 console.error；
  // 且瓦片/几何错误只汇总打印一次，避免 404 刷屏掩盖真实错误。
  const [geoError, setGeoError] = useState<string | null>(null);
  const mapErrLoggedRef = useRef(false);
  const prefLoadStartedRef = useRef(false);
  const prefLoadedRef = useRef(false);
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
      // P1-24：先清 marker（label/custom/pulse），再 destroy map——否则 DOM/监听残留
      markersRef.current?.clearAll();
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      cancelledRef.current = true;
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
    setGeoError(null);
    // 地基（2026-09-27）：**把首帧成本变成产品自己报的数**。
    // 实测（Node/V8，scripts/shot/bench-map.mjs）：regions.topojson 13.0 MB，
    // JSON.parse 130.7 ms + 4 次 feature() 11.5 ms ≈ **142 ms 主线程阻塞/每次挂载**。
    // **⚠ 基线已过期（审查 2026-10-01）**：`frontend/public/map/` 现为 **18.3 MB / 7 文件**
    // （实测，含 topojson 与 geojson），较上述 13.0 MB 增长 **+41%** → 按比例外推，
    // 首次挂载的主线程阻塞量级约 **~200 ms**（未复测，`bench-map.mjs` 可重跑取准确值）。
    // 该量级不做侵入式改造（迁 Worker / 降几何精度会推翻 :121 的"全精度注入"设计），
    // 但必须**可观测**：留 performance mark，并把耗时挂到 window 供基准/诊断读取。
    try { performance.mark("songzuo:geo:start"); } catch { /* 非浏览器环境 */ }
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
      try {
        performance.mark("songzuo:geo:end");
        const m = performance.measure("songzuo:geo", "songzuo:geo:start", "songzuo:geo:end");
        (window as unknown as { __songzuoGeoMs?: number }).__songzuoGeoMs = m.duration;
        if (import.meta.env.DEV) {
          console.info(`[map] 舆图数据就绪：fetch+parse+解码 ${m.duration.toFixed(1)} ms` +
            `（基准参考 142 ms @13.0MB）`);
        }
      } catch { /* performance 不可用则忽略 */ }
      if (cancelledRef.current) return; // 卸载后不再 setData/挂监听
      // 政权几何全精度注入(不再按 zoom 分档简化):精确国界/省界被简化
      // 会在中低缩放退化为直线多边形
      controller.setData(data);
      buildLabels();
      const map = controller.getMap()!;
      // P2-3（M10）：地图资源错误汇总（只打一次）——原先全前端无 error 监听，
      // 缺瓦片/几何时只有满控制台 404，玩家与开发者都无法定位。
      map.on("error", (ev) => {
        if (mapErrLoggedRef.current) return;
        mapErrLoggedRef.current = true;
        const msg = String((ev as unknown as { error?: { message?: string } }).error?.message ?? ev);
        console.warn(`[map] 地图资源错误（同类后续不再重复打印）：${msg}`);
      });
      // 府级边界懒加载：仅在玩家放大到可见档位时才取，避免推高首屏成本。
      void ensurePrefectureData();
      // 视口稳定后标签显隐避让(防抖)
      map.on("moveend", () => {
        if (debounceRef.current) window.clearTimeout(debounceRef.current);
        debounceRef.current = window.setTimeout(() => {
          markersRef.current?.refresh(map.getZoom());
          markersRef.current?.avoid();
          void ensurePrefectureData();
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
      // P2-3（M10）：原实现只 console.error → `onMapReady` 早已触发，玩家看到的是
      // 一张"正常"的空白舆图，无从判断是加载失败还是本就没有要素。
      const msg = e instanceof Error ? e.message : String(e);
      console.error("[map] 数据加载失败", e);
      if (!cancelledRef.current) {
        setGeoError(`舆图数据加载失败：${msg}（路界/政权/城市均未载入）`);
      }
    }
  }

  /** 府级（州府）边界 **懒加载**（P1-2 接入；`PREFECTURE_BORDERS_ENABLED=false` 时直接返回）。
   *
   * 独立文件 `prefecture_borders.topojson`（不并入 regions.topojson，避免推高首帧解析成本）；
   * 只在 zoom ≥ `PREFECTURE_BORDERS_MIN_ZOOM` 时取，失败不影响路界/填充，也**不**阻塞首屏。
   */
  async function ensurePrefectureData() {
    if (!PREFECTURE_BORDERS_ENABLED || prefLoadedRef.current || prefLoadStartedRef.current) return;
    const controller = controllerRef.current;
    const map = controller?.getMap();
    if (!controller || !map) return;
    if ((map.getZoom() ?? 0) < PREFECTURE_BORDERS_MIN_ZOOM) return;
    prefLoadStartedRef.current = true;
    try {
      const res = await fetch(`${MAP_BASE_URL}/prefecture_borders.topojson`);
      if (!res.ok) throw new Error(`prefecture_borders.topojson → HTTP ${res.status}`);
      const topo = (await res.json()) as TopoJSON.Topology;
      const obj = topo.objects.prefecture_borders ?? Object.values(topo.objects)[0];
      const fc = feature(topo, obj) as GeoJSON.FeatureCollection;
      fc.features.forEach((f, j) => { f.id = j; });
      if (cancelledRef.current) return;
      controller.setPrefectureData(fc);
      prefLoadedRef.current = true;
      if (import.meta.env.DEV) {
        console.info(`[map] 府级边界就绪：${fc.features.length} 段（zoom ≥ ${PREFECTURE_BORDERS_MIN_ZOOM}）`);
      }
    } catch (e) {
      // 府界是**可选增强层**：失败只记一次并允许下次 moveend 重试，不污染路界/填充，
      // 也不弹错误遮罩（那是给"整张舆图没数据"用的）。
      prefLoadStartedRef.current = false;
      const msg = e instanceof Error ? e.message : String(e);
      console.warn(`[map] 府级边界未载入（不影响路界与填色）：${msg}`);
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
      // 主次互斥：同屏出现省份/路分名时不显示府名，缩放到一定程度（路名避让落败或档位提高）才现府名
      markers.addLabel(
        coord,
        String(p.name),
        cls,
        tier,
        true,
        () => selectFeature("city", String(p.name)),
        { kind: "city", parent: seat ? String(p.circuit || p.province || "") : "" }
      );
    }
    // 注册主次互斥组：省级路名（macro）优先于府名（micro）——同区域重叠时路名先占位，
    // 府名只有当 zoom 深入、路名隐去或错开后才浮现。
    markers.registerMutualExclusion({
      macro: (lab) => lab.el.classList.contains("lbl-circuit"),
      micro: (lab) => lab.el.classList.contains("lbl-city")
    });
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
          // centerOf 现可能返回 null（几何无环）→ 归一为 undefined（`Selected.coordinate` 是可选配）
          foundCoord = centerOf(f) ?? undefined;
        }
      } else if (kind === "regime") {
        const f = data.regimes.features.find((r) => r.properties?.name === name);
        if (f) {
          foundFeature = f;
          foundProps = (f.properties || {}) as Record<string, unknown>;
          foundCoord = centerOf(f) ?? undefined;
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
    // 2026-09-27（地方档案 P0）：点**府/州** → 开「地方档案」浮层；
    // 2026-10-11：点**路** → 改由左侧「州路档案」多页面抽屉呈现（App 层挂载，读同一 selected），
    //   不再叠加浮层——否则抽屉与浮层会同时出现，且路级信息被挤进小卡。
    // 其余（如政权）仍走 detail。detail（查阅路分账册/诏令）仍可由其它入口打开，未移除。
    if (kind === "city") {
      pushOverlay({ kind: "localarchive", title: name, props: { kind, name, props: foundProps } });
      return;
    }
    if (kind === "circuit") {
      return;
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

  return (
    <>
      <div ref={containerRef} className="absolute inset-0" />
      {/* P2-3（M10）：可观测失败态——原先加载失败只有控制台一行，界面与"空地图"无法区分 */}
      {geoError && (
        <div className="pointer-events-auto absolute left-1/2 top-1/2 z-30 w-[min(420px,86vw)] -translate-x-1/2 -translate-y-1/2 rounded-[3px] border border-red bg-card/95 px-5 py-4 text-center shadow-paper">
          <p className="font-kai text-[16px] font-bold text-red">舆图数据加载失败</p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-light">{geoError}</p>
          <button
            onClick={() => {
              prefLoadedRef.current = false;
              prefLoadStartedRef.current = false;
              markersRef.current?.clearAll();
              void loadGeoData();
            }}
            className="mt-3 rounded border border-gold px-3.5 py-1 font-kai text-[13px] text-ink transition hover:bg-gold-light"
          >
            重试载入
          </button>
        </div>
      )}
    </>
  );
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

function centerOf(feature: GeoJSON.Feature): [number, number] | null {
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
  // 无环几何（缺失/异常）→ 返回 null 让调用方跳过聚焦。
  // P2-3（M10）：原回落 `[0, 0]`（几内亚湾）会让 flyTo/pulseAt **静默飞到错误坐标**，
  // 而调用方 `if (c)` 的判断对数组恒真，等于把"没有中心"伪装成"中心在 0,0"。
  return best ? [(best[0] + best[2]) / 2, (best[1] + best[3]) / 2] : null;
}