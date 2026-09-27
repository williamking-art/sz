// 截图台的 store mock（**仅 dev 用**）：面板需要一个有数据的 state，而 state 由真实 store 从后端流程装配。
// ⚠️ 必须**忠实反映真实 store 的字段面**：面板会读 `s.uiLogs / s.readouts / s.overlays / s.inGame ...`，
//    少一个字段就可能让某个面板崩（2026-09-27 实测：只给 state+pushOverlay 时 GazettePanel 崩）。
//    字段清单来自 `grep "useGameStore((s) => s." src/renderer/panels`（12 个）。
import { READOUTS } from "./fixtures";
import { STATE } from "./fixtures";

type Sel = (s: unknown) => unknown;

const noop = () => undefined;
const noopReturns = <T,>(v: T) => () => v;

function store() {
  return {
    state: STATE,
    uiLogs: [] as string[],
    readouts: READOUTS,
    overlays: [] as unknown[],
    inGame: true,
    backendReady: true,
    pushOverlay: noop,
    popOverlay: noop,
    popTo: noop,
    clearOverlays: noop,
    setState: noop,
    setInGame: noop,
    getState: () => store(),
    subscribe: noopReturns(noop)
  };
}

/** 与真实 `useGameStore` 同形：callable selector + 常用静态方法。
 *  ⚠️ 必须传 **store 对象**，不是 state 本身：`sel(baseState())` 会让面板的 `s.state` 全 undefined，
 *     各面板静默走"尚未开局"分支，看起来像"面板没数据"，实为 mock 自身错误。 */
export const useGameStore = Object.assign(
  (sel: Sel) => sel(store()),
  {
    getState: () => store(),
    setState: noop,
    subscribe: noop
  }
);

/** 与真实实现同义的路径取值（`prefectures.<路>` 等）。 */
export function pick<T>(obj: Record<string, unknown>, path: string, dflt: T): T {
  const v = path.split(".").reduce<unknown>(
    (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
  return (v === undefined ? dflt : v) as T;
}

export default useGameStore;
