import type { GameState } from "../api/client";
import type { CustomMarker } from "./markers";

// 从游戏快照推导舆图状态（对齐 map_app.js applyStateInner）
export interface MapState {
  activeRegimes: string[];
  hiddenRegimes: string[];
  subOwners: Record<string, string>;
  regimeOwners: Record<string, string>;
  markers: CustomMarker[];
  focus: { bounds?: number[]; lng?: number; lat?: number; zoom?: number; padding?: number; maxZoom?: number } | null;
  select: { kind: string; name: string } | null;
}

export function deriveMapState(state: GameState | null): MapState {
  if (!state) {
    return {
      activeRegimes: [],
      hiddenRegimes: [],
      subOwners: {},
      regimeOwners: {},
      markers: [],
      focus: null,
      select: null
    };
  }
  const arr = (k: string): string[] =>
    Array.isArray(state[k]) ? (state[k] as string[]) : [];
  const obj = (k: string): Record<string, string> =>
    state[k] && typeof state[k] === "object" ? (state[k] as Record<string, string>) : {};

  const markers: CustomMarker[] = [];
  if (Array.isArray(state.markers)) {
    for (const m of state.markers as Array<Record<string, unknown>>) {
      const lng = Number(m.lng);
      const lat = Number(m.lat);
      if (isFinite(lng) && isFinite(lat)) {
        markers.push({
          lng,
          lat,
          label: typeof m.label === "string" ? m.label : undefined,
          kind: m.kind === "warn" ? "warn" : "normal"
        });
      }
    }
  }

  let focus: MapState["focus"] = null;
  if (state.focus && typeof state.focus === "object") {
    const f = state.focus as Record<string, unknown>;
    if (Array.isArray(f.bounds) && f.bounds.length === 4) {
      focus = { bounds: f.bounds as number[] };
    } else if (isFinite(Number(f.lng)) && isFinite(Number(f.lat))) {
      focus = { lng: Number(f.lng), lat: Number(f.lat), zoom: Number(f.zoom) || 4.6 };
    }
  }

  let select: MapState["select"] | null = null;
  if (state.select && typeof state.select === "object") {
    const sel = state.select as Record<string, unknown>;
    if (typeof sel.kind === "string" && typeof sel.name === "string") {
      select = { kind: sel.kind, name: sel.name };
    }
  }

  return {
    activeRegimes: arr("active_regimes"),
    hiddenRegimes: arr("hidden_regimes"),
    subOwners: obj("sub_owners"),
    regimeOwners: obj("regime_owners"),
    markers,
    focus,
    select
  };
}