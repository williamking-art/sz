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
  cCitySeat: "#8a2b22",
  cCityTown: "#4a3a28",
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

export const LAYER_IDS = {
  land: "land",
  hill: "hill",
  lakes: "lakes",
  rivers: "rivers",
  circuits: "circuits",
  circuitBorders: "circuit-borders",
  regimes: "regimes",
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
    {
      id: LAYER_IDS.hill,
      type: "raster" as const,
      source: "hill",
      paint: { "raster-opacity": 0.42 }
    },
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
    // 政区（路）三型底色
    {
      id: LAYER_IDS.circuits,
      type: "fill" as const,
      source: "circuits",
      paint: {
        "fill-color": [
          "match",
          ["get", "type"],
          "京畿", THEME.cJijing,
          "沿边", THEME.cYanbian,
          THEME.cFuli
        ],
        "fill-opacity": 0.75
      }
    },
    // 政区边界（路级粗界，实界并集）
    {
      id: LAYER_IDS.circuitBorders,
      type: "line" as const,
      source: "borders",
      paint: { "line-color": THEME.goldDark, "line-width": 1, "line-opacity": 0.5 }
    },
    // 境外势力
    {
      id: LAYER_IDS.regimes,
      type: "fill" as const,
      source: "regimes",
      paint: {
        // 数据侧烘焙 tint(on/off),前端 match 读取——布尔 case 表达式
        // 在 topojson 解码路径上会被 MapLibre 求值失败并回退默认黑。
        "fill-color": [
          "match",
          ["get", "tint"],
          "off",
          THEME.cRegimeOff,
          THEME.cRegime
        ],
        "fill-opacity": 0.6
      }
    },
    // 城市（治所/属城）
    {
      id: LAYER_IDS.cities,
      type: "circle" as const,
      source: "cities",
      paint: {
        "circle-radius": [
          "case",
          ["get", "is_seat"], 4,
          2.5
        ],
        "circle-color": [
          "case",
          ["get", "is_seat"],
          THEME.cCitySeat,
          THEME.cCityTown
        ],
        "circle-stroke-color": THEME.gold,
        "circle-stroke-width": 0.6
      }
    }
  ];
}