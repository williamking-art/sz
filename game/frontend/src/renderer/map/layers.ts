// 图层定义：政区/边界/城市/河流/湖泊/势力 —— 对齐现有 map_app.js 的图层方案
// 离线无 glyphs：几何用 fill/line/circle 层，标签全部走 HTML Marker。

export const THEME = {
  paper: "#f1e5c8", // 地图底（比 HUD 宣纸略深）
  ink: "#2b1d12",
  inkLight: "#5a4a3a",
  red: "#8a2b22",
  gold: "#caa24a",
  goldDark: "#8f6e28",
  // 路（宋行政区划）三型底色
  cJijing: "#efd9a8", // 京畿
  cFuli: "#f3e7c6", // 腹里
  cYanbian: "#eddfba", // 沿边
  cRegime: "#d8cbaa", // 境外政权
  cRegimeOff: "#e3dbc8", // 未兴（金开局 inactive）
  cLineRegime: "#6b5b45",
  cCitySeat: "#a04a3c",   // 府治圆点：淡化朱红（弱化视觉权重）
  cCityTown: "#6b5c48",   // 州县圆点：淡墨褐（不再深黑刺眼）
  // 底图（真实地理）：海面 / 陆地晕染 / 河湖
  sea: "#b0bfb6",
  landGold: "#e3c27f",
  river: "#4f7f8e"
} as const;

// 标签显隐档位（zoom 阈值）
export const TIER = {
  regime: 0,
  sub: 3.2,
  jingfu: 3.0,
  seat: 3.4,
  circuit: 4.0,
  town: 4.6
} as const;

/** 地形晕渲瓦片开关（P1-2 处置方案 B）。
 *
 * `frontend/public/map/tiles/hill/` **目录不存在**（不是"空目录"），而
 * `mapController` 仍声明 `${MAP_BASE_URL}/tiles/hill/{z}/{x}/{y}.png`：
 * 开发版与安装版（`app://songzuo/map/...` → 404）都会**每一块瓦片持续 404**。
 *
 * 现状选择"禁用图层 + 消除 404"（可逆、零资源/授权风险）：
 *   · 恢复瓦片需联网跑 `game/fetch_hillshade.py`（ESRI World Hillshade，再分发条款未核），
 *     且脚本只产 z5–7 而源声明 z4–8（z4/z8 仍会 404），还须把瓦片变成可复现构建产物；
 *   · 缺此层仅失去地形晕渲（`frontend/README.md` 已明示其余功能不受影响）。
 * 若日后瓦片入库，把本常量改回 `true` 即可恢复（source 与 layer 同时受其控制）。
 */
export const HILL_TILES_ENABLED = false;

/**
 * 府级（州府）边界线开关（P1-2 接入）。
 *
 * 数据来自权威生成产物 `game/assets/map/web/prefecture_borders.geojson`（127 块，
 * 与路级同一次闭合、同批次），构建期拓扑化为 `public/map/prefecture_borders.topojson`
 * （**独立文件**，不并入 `regions.topojson`，避免推高首帧 `JSON.parse` 成本）。
 *
 * 口径（为什么不与路界抢视觉）：
 *   · **只加线、不加填充**——不加府级 fill 层，避免叠色与命中竞争（填色仍按路）；
 *   · 线宽/色阶低于路界（`TIER`/`inkLight`、`minzoom 5.2`），路界仍为主导层级；
 *   · **不注册 click**，故政区详情/命中测试行为与接入前完全一致。
 *
 * 已知限制：137 个治所中有 11 个（含荆湖北路·澧州）在现代地级质心最近邻判定下
 * 未获独立块 → 该处无府界可绘。修它需改生成算法（`build_map_basemap.py` 归属判定），
 * 会改变逐府人口/田亩/月税摊派，属核心模拟改动，留待设计确认后单独处理。
 */
export const PREFECTURE_BORDERS_ENABLED = true;

/** 府界可见/加载的最低 zoom（单一来源：图层 `minzoom` 与 MapView 懒加载门槛共用）。 */
export const PREFECTURE_BORDERS_MIN_ZOOM = 5.2;

export const LAYER_IDS = {
  land: "land",
  hill: "hill",
  lakes: "lakes",
  rivers: "rivers",
  circuits: "circuits",
  circuitBorders: "circuit-borders",
  prefectureBorders: "prefecture-borders",
  regimes: "regimes",
  regimeBorders: "regime-borders",
  cities: "cities",
  selected: "selected"
} as const;

// 图层定义（MapLibre addLayer 参数）
export function buildLayerDefs() {
  return [
    // 陆地（真实地形晕染）
    {
      id: LAYER_IDS.land,
      type: "fill" as const,
      source: "land",
      paint: { "fill-color": THEME.landGold, "fill-opacity": 0.55 }
    },
    // 地形晕渲（山脉立体感，半透明叠于陆地之上、政区之下）
    // 开关见 `HILL_TILES_ENABLED`：瓦片目录缺失时**整层不建**（连 source 也不声明），
    // 否则每一块瓦片都会向 app://songzuo/map/tiles/hill/… 发一次 404。
    ...(HILL_TILES_ENABLED ? [{
      id: LAYER_IDS.hill,
      type: "raster" as const,
      source: "hill",
      paint: { "raster-opacity": 0.42 }
    }] : []),
    // 湖泊
    {
      id: LAYER_IDS.lakes,
      type: "fill" as const,
      source: "lakes",
      paint: { "fill-color": THEME.sea, "fill-opacity": 0.9 }
    },
    // 河流
    {
      id: LAYER_IDS.rivers,
      type: "line" as const,
      source: "rivers",
      paint: { "line-color": THEME.river, "line-width": 1.2, "line-opacity": 0.8 }
    },
    // 政区（路）底色：全境统一使用古典宣纸米黄色，内部仅以描金界线分隔
    {
      id: LAYER_IDS.circuits,
      type: "fill" as const,
      source: "circuits",
      paint: {
        "fill-color": THEME.cFuli,
        "fill-opacity": 0.75
      }
    },
    // 政区边界（路级粗界，实界并集）
    {
      id: LAYER_IDS.circuitBorders,
      type: "line" as const,
      source: "borders",
      paint: { "line-color": THEME.goldDark, "line-width": 1.1, "line-opacity": 0.55 }
    },
    // 府级（州府）边界：**细于路界、压在其下**（本数组顺序 = z-order，故排在此处即低于
    // 上述路界）。只在 zoom ≥ 5.2 显现，避免全览时线网过密；数据懒加载（见 MapView）。
    ...(PREFECTURE_BORDERS_ENABLED ? [{
      id: LAYER_IDS.prefectureBorders,
      type: "line" as const,
      source: "prefecture_borders",
      minzoom: 5.2,
      paint: {
        "line-color": THEME.inkLight,
        "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.35, 8, 0.8],
        "line-opacity": 0.45
      }
    }] : []),
    // 境外势力
    {
      id: LAYER_IDS.regimes,
      type: "fill" as const,
      source: "regimes",
      paint: {
        // 政权专属色由构建期烘焙进要素(fill 属性),数据驱动直读;
        // 布尔 case 表达式在 topojson 解码路径上会被 MapLibre 求值失败回退默认黑。
        "fill-color": ["coalesce", ["get", "fill"], THEME.cRegime],
        "fill-opacity": 0.6
      }
    },
    // 逐省政权的省界线(内部结构,消除"大简单几何体"观感)
    {
      id: LAYER_IDS.regimeBorders,
      type: "line" as const,
      source: "regime_borders",
      paint: { "line-color": THEME.goldDark, "line-width": 1.1, "line-opacity": 0.55 }
    },
    // 城市（治所/属城）
    {
      id: LAYER_IDS.cities,
      type: "circle" as const,
      source: "cities",
      filter: ["!=", ["get", "kind"], "river"],
      paint: {
        "circle-radius": [
          "case",
          ["get", "is_seat"], 2.8,
          2.0
        ],
        "circle-color": [
          "case",
          ["get", "is_seat"],
          THEME.cCitySeat,
          THEME.cCityTown
        ],
        "circle-opacity": 0.72,
        "circle-stroke-color": THEME.gold,
        "circle-stroke-width": 0.4,
        "circle-stroke-opacity": 0.6
      }
    }
  ];
}