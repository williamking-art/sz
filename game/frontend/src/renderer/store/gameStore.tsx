import { createContext, useContext, useEffect, useReducer, type ReactNode } from "react";
import { getApiClient, type GameState, type ReadoutsResult } from "../api/client";
import { formatEra } from "../utils/format";

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
  /** /api/readouts 派生读数（供 TopBar 收支悬浮卡等只读消费，随 state 变更自动刷新）。 */
  readouts: ReadoutsResult | null;
}

type Action =
  | { type: "SET_BACKEND"; url: string; ready: boolean; error: string | null }
  | { type: "SET_STATE"; state: GameState | null }
  | { type: "SET_READOUTS"; readouts: ReadoutsResult | null }
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
  inGame: false,
  readouts: null
};

function reducer(s: StoreShape, a: Action): StoreShape {
  switch (a.type) {
    case "SET_BACKEND":
      return { ...s, backendUrl: a.url, backendReady: a.ready, backendError: a.error };
    case "SET_STATE":
      return { ...s, state: a.state };
    case "SET_READOUTS":
      return { ...s, readouts: a.readouts };
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
  setReadouts: (readouts: ReadoutsResult | null) => void;
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

  // 派生读数自动刷新：每次后端 GameState 快照更新（开局/载档/推演/任意 action 回执）后
  // 重新拉取 /api/readouts，保证 TopBar 收支悬浮卡等消费的是与当前状态同源的 live 数据。
  useEffect(() => {
    if (!state.backendReady || !state.inGame || !state.state) return;
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (alive) dispatch({ type: "SET_READOUTS", readouts: res });
      } catch (e) {
        console.warn("[readouts] 读数刷新失败：", e);
      }
    })();
    return () => {
      alive = false;
    };
  }, [state.backendReady, state.inGame, state.state]);

  const api: GameStoreApi = {
    ...state,
    setBackend: (url, ready, error) => dispatch({ type: "SET_BACKEND", url, ready, error }),
    setState: (st) => dispatch({ type: "SET_STATE", state: st }),
    setReadouts: (readouts) => dispatch({ type: "SET_READOUTS", readouts }),
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
  /** 合计可为 null：读数未就绪/无口径时展示占位，绝不回退硬编码。 */
  totalIn: number | null;
  totalOut: number | null;
  net: number | null;
  subNotice?: string;
  incomes: BudgetCategoryItem[];
  expenses: BudgetCategoryItem[];
  oneTimeItems?: BudgetCategoryItem[];
}

/** 只读 /api/readouts::finance 转数值：非有限数一律 null（未取到 → 展示占位）。 */
function financeNum(fin: Record<string, unknown> | null, key: string): number | null {
  if (!fin) return null;
  const v = fin[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** 深度财政结构化解析：国库月度收支（读数源 /api/readouts::finance，与后端 _settle_finance 同源）。 */
export function getTreasuryDetail(state: GameState | null, finance: Record<string, unknown> | null): BudgetFlowData {
  if (!state) {
    return {
      title: "国库月度收支",
      totalIn: null,
      totalOut: null,
      net: null,
      incomes: [],
      expenses: []
    };
  }

  // 月入分项（后端 finance_readout：commerce/poll/maritime/tax_color/salt_coin）
  const commerce = financeNum(finance, "commerce");
  const poll = financeNum(finance, "poll");
  const maritime = financeNum(finance, "maritime");
  const taxColor = financeNum(finance, "tax_color");
  const salt = financeNum(finance, "salt_coin");
  // 月支分项（expenditure/army_cash/official_cash/clerk_cash/sui_gong）
  const expenditure = financeNum(finance, "expenditure");
  const armyCash = financeNum(finance, "army_cash");
  const officialCash = financeNum(finance, "official_cash");
  const clerkCash = financeNum(finance, "clerk_cash");
  const suiGong = financeNum(finance, "sui_gong");
  // 合计（后端权威总额）
  const totalIn = financeNum(finance, "monthly_in");
  const totalOut = financeNum(finance, "total_out");
  const net = financeNum(finance, "net");

  // 只列读数存在且 >0 的科目，避免 0 值噪音（读数未就绪时全部不列 → 悬浮卡显示占位提示）
  const incomes: BudgetCategoryItem[] = [
    ...(taxColor !== null && taxColor > 0
      ? [{
          name: "两税折色",
          amount: taxColor,
          desc: "二十路夏秋两税折色钱帛直输国库，按田赋隐漏与到账率实收。",
          formula: "夏秋两税折色月实收（× 到账率）"
        }]
      : []),
    ...(commerce !== null && commerce > 0
      ? [{
          name: "工商榷税",
          amount: commerce,
          desc: "两浙、江南等诸路坊郭工商产值抽解，由工匠与行商分纳。",
          formula: "工商月产值 × 现行征率 × 到账率"
        }]
      : []),
    ...(salt !== null && salt > 0
      ? [{
          name: "盐铁官榷",
          amount: salt,
          desc: "解盐、淮盐等诸路榷盐铁利，盐铁司统一钞引，利归公帑。",
          formula: "诸路盐产钞引税月度结算"
        }]
      : []),
    ...(poll !== null && poll > 0
      ? [{
          name: "身丁役钱",
          amount: poll,
          desc: "天下乡村夫役代役钱，农户免役而输钱，充备百司役使用度。",
          formula: "在册农户役率折月实收"
        }]
      : []),
    ...(maritime !== null && maritime > 0
      ? [{
          name: "市舶抽解",
          amount: maritime,
          desc: "泉州、广州、明州市舶司番商番货互市抽解关税。",
          formula: "远洋商舶进港货值 × 抽解率"
        }]
      : [])
  ];

  const expenses: BudgetCategoryItem[] = [
    ...(armyCash !== null && armyCash > 0
      ? [{
          name: "禁厢兵饷",
          amount: armyCash,
          desc: "京师三衙禁军与九边防线折色兵饷钱，战时赏赉另给。",
          formula: "在籍战兵 × 步骑饷额折色月结"
        }]
      : []),
    ...(officialCash !== null && officialCash > 0
      ? [{
          name: "百官俸禄",
          amount: officialCash,
          desc: "中枢诸司与地方各路正印官折色俸钱，依品秩月给。",
          formula: "在职官员 × 俸格折色月结"
        }]
      : []),
    ...(clerkCash !== null && clerkCash > 0
      ? [{
          name: "胥吏食钱",
          amount: clerkCash,
          desc: "诸路各州县案牍吏员月度给食钱，吏俸充足则贪墨少。",
          formula: "各路吏员 × 月实发折钱"
        }]
      : []),
    ...(expenditure !== null && expenditure > 0
      ? [{
          name: "朝廷常支",
          amount: expenditure,
          desc: "六部司署公文纸札、馆阁营造、礼仪祭祀及京畿常例公用。",
          formula: "司署基准用度 - 节流省浮"
        }]
      : []),
    ...(suiGong !== null && suiGong > 0
      ? [{
          name: "岁币和议",
          amount: suiGong,
          desc: "对辽/西夏岁币月摊（依外交态度与协议倍率结算）。",
          formula: "岁币年额 × 协议倍率 ÷ 12"
        }]
      : [])
  ];

  return {
    title: "国库月度收支",
    totalIn,
    totalOut,
    net,
    subNotice: "读数与月结同源：税额随征率/到账率/钱荒动态折算；支合计含吏俸缺口扣减等隐项，以合计为准。",
    incomes,
    expenses
  };
}

/** 深度财政结构化解析：内帑月入读数（/api/readouts::finance；内廷支度不列外朝会计，无分项读数）。 */
export function getPrivyDetail(state: GameState | null, finance: Record<string, unknown> | null): BudgetFlowData {
  if (!state) {
    return {
      title: "内帑月入·酒课",
      totalIn: null,
      totalOut: null,
      net: null,
      incomes: [],
      expenses: []
    };
  }

  const wine = financeNum(finance, "wine_coin");
  const incomes: BudgetCategoryItem[] =
    wine !== null && wine > 0
      ? [{
          name: "榷酒课钱",
          amount: wine,
          desc: "诸路官私酒务榷酒之利直入内帑封桩，酒坊兴建则课额累增。",
          formula: "榷酒课月结（随酒坊产出动态）"
        }]
      : [];

  return {
    title: "内帑月入·酒课",
    totalIn: wine,
    totalOut: null,
    net: null,
    subNotice: "内藏库与户部分理：外朝账册仅见榷酒课月入，其余皇庄贡奉与内廷支度不经外朝、不列读数。",
    incomes,
    expenses: []
  };
}