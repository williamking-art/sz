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

/** 国库收支明细（前端派生，数据源为快照原始字段）。 */
export function hudTreasuryFlow(state: GameState | null): [string, string][] {
  if (!state) return [];
  const stats = pick<Record<string, number>>(state, "statistics", {});
  const tb = pick<Record<string, number>>(state, "tax_breakdown", {});
  const rows: [string, string][] = [];
  for (const [k, v] of Object.entries(tb)) {
    if (typeof v === "number" && v !== 0) rows.push([k, `+${humanizeCoin(v)}`]);
  }
  rows.push(["岁入", humanizeCoin(stats.total_income ?? 0)]);
  rows.push(["岁出", humanizeCoin(stats.total_expenditure ?? 0)]);
  return rows;
}

/** 内帑收支明细。 */
export function hudPrivyFlow(state: GameState | null): [string, string][] {
  if (!state) return [];
  return [
    ["现额", humanizeCoin(hudPrivy(state))],
    ["酒课", humanizeCoin(pick<Record<string, number>>(state, "wine_tax", {}).month_coin ?? 0)]
  ];
}