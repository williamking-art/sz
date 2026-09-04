import { createContext, useContext, useReducer, type ReactNode } from "react";
import type { GameState } from "../api/client";
import { formatEra, humanizeCoin } from "../utils/format";

// 浮层条目：面板类型 + 可选参数
export type PanelKind =
  | "advance"
  | "decree"
  | "audience"
  | "event"
  | "court"
  | "ministers"
  | "gazette"
  | "personal"
  | "prefecture"
  | "granary"
  | "focus"
  | "diplomacy"
  | "pop"
  | "codex"
  | "accounting"
  | "military"
  | "tech"
  | "engineering"
  | "settings"
  | "save"
  | "newgame"
  | "conclude"
  | "detail"
  | "todo";

export interface OverlayEntry {
  id: string;
  kind: PanelKind;
  title: string;
  props?: Record<string, unknown>;
  /** 是否可关闭（背景点击/Esc/关闭钮）；开局等阻断性面板为 false。 */
  dismissible?: boolean;
}

export interface Selected {
  kind: string;
  name: string;
  source?: string;
  id?: string;
  props?: Record<string, unknown>;
  feature?: GeoJSON.Feature;
  coordinate?: [number, number];
}

// store 状态形状（区别于后端 GameState 快照）
interface StoreShape {
  backendUrl: string | null;
  backendReady: boolean;
  backendError: string | null;
  state: GameState | null;
  overlays: OverlayEntry[];
  selected: Selected | null;
  advancing: boolean;
  inGame: boolean;
}

type Action =
  | { type: "SET_BACKEND"; url: string; ready: boolean; error: string | null }
  | { type: "SET_STATE"; state: GameState | null }
  | { type: "PUSH_OVERLAY"; entry: Omit<OverlayEntry, "id"> }
  | { type: "POP_OVERLAY" }
  | { type: "POP_TO"; index: number }
  | { type: "CLEAR_OVERLAYS" }
  | { type: "SET_SELECTED"; selected: Selected | null }
  | { type: "SET_ADVANCING"; advancing: boolean }
  | { type: "SET_IN_GAME"; inGame: boolean };

let overlaySeq = 0;

const initialState: StoreShape = {
  backendUrl: null,
  backendReady: false,
  backendError: null,
  state: null,
  overlays: [],
  selected: null,
  advancing: false,
  inGame: false
};

function reducer(s: StoreShape, a: Action): StoreShape {
  switch (a.type) {
    case "SET_BACKEND":
      return { ...s, backendUrl: a.url, backendReady: a.ready, backendError: a.error };
    case "SET_STATE":
      return { ...s, state: a.state };
    case "PUSH_OVERLAY":
      return { ...s, overlays: [...s.overlays, { ...a.entry, id: `ov-${++overlaySeq}` }] };
    case "POP_OVERLAY":
      return { ...s, overlays: s.overlays.slice(0, -1) };
    case "POP_TO":
      return { ...s, overlays: s.overlays.slice(0, a.index) };
    case "CLEAR_OVERLAYS":
      return { ...s, overlays: [] };
    case "SET_SELECTED":
      return { ...s, selected: a.selected };
    case "SET_ADVANCING":
      return { ...s, advancing: a.advancing };
    case "SET_IN_GAME":
      return { ...s, inGame: a.inGame };
    default:
      return s;
  }
}

// 上下文值：状态字段 + 动作方法（选择器统一访问）
export interface GameStoreApi extends StoreShape {
  setBackend: (url: string, ready: boolean, error: string | null) => void;
  setState: (state: GameState | null) => void;
  pushOverlay: (entry: Omit<OverlayEntry, "id">) => void;
  popOverlay: () => void;
  popTo: (index: number) => void;
  clearOverlays: () => void;
  setSelected: (selected: Selected | null) => void;
  setAdvancing: (advancing: boolean) => void;
  setInGame: (inGame: boolean) => void;
}

export const GameStoreContext = createContext<GameStoreApi | null>(null);

export function GameStoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const api: GameStoreApi = {
    ...state,
    setBackend: (url, ready, error) => dispatch({ type: "SET_BACKEND", url, ready, error }),
    setState: (st) => dispatch({ type: "SET_STATE", state: st }),
    pushOverlay: (entry) => dispatch({ type: "PUSH_OVERLAY", entry }),
    popOverlay: () => dispatch({ type: "POP_OVERLAY" }),
    popTo: (index) => dispatch({ type: "POP_TO", index }),
    clearOverlays: () => dispatch({ type: "CLEAR_OVERLAYS" }),
    setSelected: (selected) => dispatch({ type: "SET_SELECTED", selected }),
    setAdvancing: (advancing) => dispatch({ type: "SET_ADVANCING", advancing }),
    setInGame: (inGame) => dispatch({ type: "SET_IN_GAME", inGame })
  };

  return <GameStoreContext.Provider value={api}>{children}</GameStoreContext.Provider>;
}

// 选择器式 hook：useGameStore((s) => s.state)
export function useGameStore<T>(selector: (s: GameStoreApi) => T): T {
  const ctx = useContext(GameStoreContext);
  if (!ctx) throw new Error("useGameStore 必须在 GameStoreProvider 内使用");
  return selector(ctx);
}

// ---- HUD 派生辅助（字段名对齐 game/ui/panels_core.py::_refresh_hud） ----
export function pick<T>(state: GameState | null, key: string, fallback: T): T {
  if (!state) return fallback;
  const v = (state as Record<string, unknown>)[key];
  return v === undefined || v === null ? fallback : (v as T);
}

/** 古意纪年：年号+年+季节+月朔日。 */
export function hudEra(state: GameState | null): string {
  const eraName = pick<string>(state, "era_name", "");
  const year = pick<number>(state, "year", 0);
  const month = pick<number>(state, "month", 1);
  return formatEra(eraName, year, month);
}

export function hudPrestige(state: GameState | null): number {
  return pick<number>(state, "prestige", 0);
}
/** 民心 ← population_satisfaction */
export function hudPopular(state: GameState | null): number {
  return pick<number>(state, "population_satisfaction", 0);
}
export function hudTreasury(state: GameState | null): number {
  return pick<number>(state, "treasury", 0);
}
/** 内帑 ← imperial_treasury */
export function hudPrivy(state: GameState | null): number {
  return pick<number>(state, "imperial_treasury", 0);
}

/** 词元用量：后端快照可选携带 token_usage；缺失返回 null（顶栏不显示）。 */
export function hudToken(state: GameState | null): number | null {
  const u = pick<Record<string, unknown> | null>(state, "token_usage", null);
  if (!u) return null;
  return Number(u.prompt ?? 0) + Number(u.completion ?? 0);
}

// 在办事由：active_focus(置顶国策) + longterm_public + longterm_secret（对齐 panels_core.py::_refresh_left_card）
export interface TodoItem {
  label: string;
  progress: number;
  isFocus?: boolean;
}

export function hudTodos(state: GameState | null): TodoItem[] {
  if (!state) return [];
  const items: TodoItem[] = [];

  // 1. 若当前有中枢正在施行的国策大策，以最高优先级置顶
  const actFocus = pick<Record<string, unknown>>(state, "active_focus", {});
  if (actFocus && actFocus.status === "in_progress" && actFocus.name) {
    items.push({
      label: `【国策】${actFocus.name}`,
      progress: Math.max(5, Math.min(100, Number(actFocus.progress) || 0)),
      isFocus: true
    });
  }

  // 2. 长期诏令事务
  const pub = pick<Array<Record<string, unknown>>>(state, "longterm_public", []);
  const sec = pick<Array<Record<string, unknown>>>(state, "longterm_secret", []);
  const issues = [...pub, ...sec];

  if (items.length === 0 && issues.length === 0) {
    return [
      { label: "暂无在办大事", progress: 20 },
      { label: "江山初定，百废待兴", progress: 15 }
    ];
  }

  for (const t of issues.slice(0, 7 - items.length)) {
    const raw = String(t.task_name ?? t.title ?? "事务");
    const label = raw.slice(0, 12);
    let h = 0;
    for (let i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) % 1_000_003;
    items.push({ label, progress: 30 + (h % 60) });
  }

  return items;
}

export interface BudgetCategoryItem {
  name: string;
  amount: number;
  desc?: string;
  formula?: string;
}

export interface BudgetFlowData {
  title: string;
  totalIn: number;
  totalOut: number;
  net: number;
  subNotice?: string;
  incomes: BudgetCategoryItem[];
  expenses: BudgetCategoryItem[];
  oneTimeItems?: BudgetCategoryItem[];
}

/** 深度财政结构化解析：国库月度定额与细目 */
export function getTreasuryDetail(state: GameState | null): BudgetFlowData {
  if (!state) {
    return {
      title: "国库月度定额",
      totalIn: 0,
      totalOut: 0,
      net: 0,
      incomes: [],
      expenses: []
    };
  }

  const tb = pick<Record<string, number>>(state, "tax_breakdown", {});
  const comm = tb.commerce || 1130940;
  const poll = tb.poll || 389015;
  const taxCol = tb.tax_color || 864322;
  const salt = tb.salt || 498151;
  const maritime = tb.maritime || 0;

  const totalIn = comm + poll + taxCol + salt + maritime;
  // 支出细项基准（与 game_state_econ 对齐）
  const milCash = 197439;
  const offCash = 810030;
  const clerkCash = 421946;
  const civilExp = 880000;
  const totalOut = milCash + offCash + clerkCash + civilExp;
  const net = totalIn - totalOut;

  const incomes: BudgetCategoryItem[] = [
    {
      name: "两税折色",
      amount: taxCol,
      desc: "二十路夏秋两税部分折纳钱帛直输国库，按自耕田与士绅田亩均摊。",
      formula: "官民田46800万亩 × 亩折色率 × 实际到账率(约45%)"
    },
    {
      name: "工商榷税",
      amount: comm,
      desc: "两浙、江南等诸路坊郭工商产值抽解，由工匠与行商分纳。",
      formula: "全国工商月产值 × 征率(15%) × 钱荒系数"
    },
    {
      name: "盐铁官榷",
      amount: salt,
      desc: "解盐、淮盐等诸路榷盐铁利，盐铁司统一钞引，利归公帑。",
      formula: "诸路岁产盐18500万斤引税月度折算"
    },
    {
      name: "身丁役钱",
      amount: poll,
      desc: "天下乡村夫役代役钱，农户免役而输钱，充备百司役使用度。",
      formula: "在册农户2000余万户 × 役率折月"
    }
  ];

  if (maritime > 0) {
    incomes.push({
      name: "市舶抽解",
      amount: maritime,
      desc: "泉州、广州、明州市舶司番商番货互市抽解关税。",
      formula: "远洋商舶进港货值 × 抽解率(10%~20%)"
    });
  }

  const expenses: BudgetCategoryItem[] = [
    {
      name: "百官俸禄",
      amount: offCash,
      desc: "中枢诸司与地方各路正印官折色俸钱，依品秩月给。",
      formula: "在职官员2.7万员 × 俸格折色(50%)"
    },
    {
      name: "朝廷常支",
      amount: civilExp,
      desc: "六部司署公文纸札、馆阁营造、礼仪祭祀及京畿常例公用。",
      formula: "三省六部司署基准用度 - 节流削冗"
    },
    {
      name: "胥吏食钱",
      amount: clerkCash,
      desc: "诸路各州县案牍吏员月度给食钱，吏俸充足则贪墨少。",
      formula: "各路吏员21.6万名 × 月实发折钱"
    },
    {
      name: "禁厢兵饷",
      amount: milCash,
      desc: "京师三衙禁军与九边防线折色兵饷钱，战时赏赉另给。",
      formula: "在籍战兵70余万 × 步骑饷额折色"
    }
  ];

  return {
    title: "国库月度定额",
    totalIn,
    totalOut,
    net,
    subNotice: "税额受朝廷到账率与各路钱荒度动态折算，月结盈亏直接流转太库",
    incomes,
    expenses
  };
}

/** 深度财政结构化解析：内帑月度定额与细目 */
export function getPrivyDetail(state: GameState | null): BudgetFlowData {
  if (!state) {
    return {
      title: "内帑月度定额",
      totalIn: 0,
      totalOut: 0,
      net: 0,
      incomes: [],
      expenses: []
    };
  }

  const rawWine = pick<any>(state, "wine_tax", 600000);
  const wineVal = typeof rawWine === "number" ? rawWine : Number(rawWine?.month_coin ?? 600000);
  const royalLandInc = 80000;
  const tributeInc = 40000;
  const totalIn = wineVal + royalLandInc + tributeInc;

  const palaceExp = 120000;
  const craftExp = 80000;
  const taoistExp = 50000;
  const totalOut = palaceExp + craftExp + taoistExp;
  const net = totalIn - totalOut;

  const incomes: BudgetCategoryItem[] = [
    {
      name: "榷酒课钱",
      amount: wineVal,
      desc: "开封与诸路官酒务、曲院榷酒专卖之利，自旧制直入内帑封桩。",
      formula: "诸路官私酒坊产出 × 酒课专卖税(每月60万贯基准)"
    },
    {
      name: "皇庄子粒",
      amount: royalLandInc,
      desc: "京畿及各路皇室直辖庄田、御庄之田租与折色折变银入内库。",
      formula: "皇室自占田亩产出折款(皇庄直辖不受外朝审计)"
    },
    {
      name: "贡奉方物",
      amount: tributeInc,
      desc: "诸路转运使与四方藩国朝贡例进之金银、珠玉、香药珍玩折价。",
      formula: "四方岁贡与内供进奉按月摊算"
    }
  ];

  const expenses: BudgetCategoryItem[] = [
    {
      name: "宫闱后省",
      amount: palaceExp,
      desc: "禁中后妃供奉、宫娥宦官禄米廪给及内廷日常供奉花销。",
      formula: "大内仪制例支与四时赐赉"
    },
    {
      name: "御前营造",
      amount: craftExp,
      desc: "翰林图画院、御器局、修内司琢玉及宫苑营造精工耗费。",
      formula: "文华百工匠直与内供材料采办"
    },
    {
      name: "修道斋醮",
      amount: taoistExp,
      desc: "崇真馆、延福宫醮坛金箓祈福、赐赏道长法官之供奉。",
      formula: "宫廷醮道礼神随圣意增减"
    }
  ];

  return {
    title: "内帑月度定额",
    totalIn,
    totalOut,
    net,
    subNotice: "内藏库专供天子内府，与户部外朝国库分理，不入外廷常宪",
    incomes,
    expenses
  };
}