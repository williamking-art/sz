// 图层定义：政区/边界/城市/河流/湖泊/势力 —— 宋代青绿山水水墨风骨与舆图四态
// 离线无 glyphs：几何用 fill/line/circle 层，标签全部走 HTML Marker。

export const THEME = {
  paper: "#f3e8cf", // 典雅宋代宣纸底色
  ink: "#22170f",   // 焦墨
  inkLight: "#4e3f31", // 浓墨/松烟
  red: "#9e2a2b",   // 朱砂红印
  gold: "#caa24a",  // 泥金
  goldDark: "#7d5d21", // 古铜金
  // 路（宋行政区划）三型底色（青绿山水水墨风骨）
  cJijing: "#ecd59e", // 京畿金褐御制色
  cFuli: "#f4eacc",   // 腹里温润宣纸色
  cYanbian: "#e2d2ab", // 沿边关防古金铜
  cRegime: "#cfc3a5", // 境外政权古拙灰褐
  cRegimeOff: "#ded6c5", // 未兴（金开局 inactive）
  cLineRegime: "#5f4f3c",
  cCitySeat: "#9e2a2b",   // 府治圆点：典雅朱砂（如盖印金石）
  cCityTown: "#665846",   // 州县圆点：淡墨松烟
  // 底图（青绿山水真容）：海面 / 陆地晕染 / 河湖
  sea: "#98ada8",      // 远海：烟波微茫温润浅碧
  landGold: "#dfc68b", // 陆地金赭晕染底
  river: "#3a6d7c"     // 江河：青绿山水矿物石青/石绿
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

export const HILL_TILES_ENABLED = false;
export const PREFECTURE_BORDERS_ENABLED = true;
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

/** 民怨池是否有**可判定**的数据：必须是对象且至少一个有限数值。
 *  - 空对象/缺失/全为非数值 ⇒ false（调用方据此显示「无数据」，不得伪造警戒色）。
 *  - 有 0 值也算有数据（真实治平），与「缺失」区分。 */
export function hasUnrestData(state?: unknown): boolean {
  const stats = (state as Record<string, unknown> | undefined)?.statistics as Record<string, unknown> | undefined;
  const pool = stats?.organic_unrest_pool;
  if (!pool || typeof pool !== "object" || Array.isArray(pool)) return false;
  return Object.values(pool as Record<string, unknown>).some(
    (v) => typeof v === "number" && Number.isFinite(v),
  );
}

/**
 * 派生二十一路动态着色表达式（支持舆图四态：政区态、物候态、民怨态、边备态）。
 */
export function getCircuitFillExpression(mode: string, state?: unknown): any {
  if (mode === "climate") {
    // 九州物候态：丰稔青碧、寻常米黄、旱歉焦赭
    const lush = "#a4c297";
    const normal = "#eddba6";
    const dry = "#cb885c";
    return [
      "match",
      ["get", "name"],
      ["两浙路", "江南东路", "江南西路", "成都府路", "荆湖南路", "荆湖北路", "福建路"],
      lush,
      ["河北东路", "河北西路", "河东路", "永兴军路", "秦凤路"],
      dry,
      normal
    ];
  }

  if (mode === "unrest") {
    // 海内生计态：根据 state.statistics.organic_unrest_pool 动态标色。
    // 🔴 缺失≠0≠危机：池为空/缺失时**不得**伪造任何路的警戒色，
    //   统一返回 calm 平色，并由调用方（MapView）显示「民怨读数未定义」。
    const stats = (state as Record<string, unknown> | undefined)?.statistics as Record<string, unknown> | undefined;
    const unrestPool = (stats?.organic_unrest_pool as Record<string, unknown> | undefined) || {};
    const alertHigh = "#b83a2c"; // 严重民怨/起义濒发（朱砂赤红）
    const alertMid = "#dca156";  // 中度民怨（焦黄警戒）
    const calm = "#e9e5d4";      // 治平海清（清白温润）

    if (!hasUnrestData(state)) return calm;

    const matches: any[] = ["match", ["get", "name"]];
    const highCircuits: string[] = [];
    const midCircuits: string[] = [];

    for (const [circuit, val] of Object.entries(unrestPool)) {
      // 非数值/非有限值不是 0，直接跳过；否则会把"读不到"画成"治平"。
      if (typeof val !== "number" || !Number.isFinite(val)) continue;
      if (val >= 70) highCircuits.push(circuit);
      else if (val >= 30) midCircuits.push(circuit);
    }

    if (highCircuits.length > 0) {
      matches.push(highCircuits, alertHigh);
    }
    if (midCircuits.length > 0) {
      matches.push(midCircuits, alertMid);
    }
    matches.push(calm);
    return matches.length > 3 ? matches : calm;
  }

  if (mode === "military") {
    // 关防烽燧态：沿边帅司与边塞重镇金铜军防，海防浅翠，腹里温润
    const frontier = "#bd8f46"; // 边防帅司
    const coast = "#7fa89f";    // 海防要津
    const inland = "#ebe1c8";   // 腹里州郡
    return [
      "match",
      ["get", "name"],
      ["河北东路", "河北西路", "河东路", "永兴军路", "秦凤路", "鄜延路", "环庆路", "泾原路", "熙河路"],
      frontier,
      ["两浙路", "福建路", "广南东路"],
      coast,
      inland
    ];
  }

  // 默认政区态（中原疆宇）
  return [
    "match",
    ["get", "name"],
    ["京畿路"],
    THEME.cJijing,
    ["河北东路", "河北西路", "河东路", "永兴军路", "秦凤路"],
    THEME.cYanbian,
    THEME.cFuli
  ];
}

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
    // 地形晕渲
    ...(HILL_TILES_ENABLED ? [{
      id: LAYER_IDS.hill,
      type: "raster" as const,
      source: "hill",
      paint: { "raster-opacity": 0.42 }
    }] : []),
    // 湖泊（千顷澄碧）
    {
      id: LAYER_IDS.lakes,
      type: "fill" as const,
      source: "lakes",
      paint: { "fill-color": THEME.sea, "fill-opacity": 0.95 }
    },
    // 河流（矿物石青石绿）
    {
      id: LAYER_IDS.rivers,
      type: "line" as const,
      source: "rivers",
      paint: { "line-color": THEME.river, "line-width": 1.4, "line-opacity": 0.85 }
    },
    // 政区（路）底色：二十一路青绿水墨风骨与舆图四态
    {
      id: LAYER_IDS.circuits,
      type: "fill" as const,
      source: "circuits",
      paint: {
        "fill-color": getCircuitFillExpression("political"),
        "fill-opacity": 0.80
      }
    },
    // 政区边界（路级粗界，实界并集）
    {
      id: LAYER_IDS.circuitBorders,
      type: "line" as const,
      source: "borders",
      paint: { "line-color": THEME.goldDark, "line-width": 1.2, "line-opacity": 0.65 }
    },
    // 府级（州府）边界
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
        "fill-color": ["coalesce", ["get", "fill"], THEME.cRegime],
        "fill-opacity": 0.62
      }
    },
    // 逐省政权的省界线
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
          ["get", "is_seat"], 3.0,
          2.0
        ],
        "circle-color": [
          "case",
          ["get", "is_seat"],
          THEME.cCitySeat,
          THEME.cCityTown
        ],
        "circle-opacity": 0.80,
        "circle-stroke-color": THEME.gold,
        "circle-stroke-width": 0.5,
        "circle-stroke-opacity": 0.75
      }
    }
  ];
}