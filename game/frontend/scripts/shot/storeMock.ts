// 截图台的 store mock（**仅 dev 用**）。
// 为什么这里仍要 alias 换模块：面板需要一份**有数据的 state**，而 state 由真实 store 从后端流程装配，
// 截图台不跑那套流程 → 只能在模块层给一份 fixture。**只 mock 这一个模块**（导出面小且稳定）。
import { STATE } from "./fixtures";

type Sel = (s: unknown) => unknown;

function baseState() {
  return STATE;
}

/** 与真实 `useGameStore` 同形：callable selector + 常用静态方法（防面板用到 getState）。
 *  ⚠️ 必须传 **store 对象** `{state, pushOverlay}`，不是 state 本身：
 *     写成 `sel(baseState())` 会让面板的 `s.state` 全为 undefined（各面板静默走"尚未开局"分支，
 *     截图台看起来像"面板没数据"，实为 mock 自身错误）。 */
export const useGameStore = Object.assign(
  (sel: Sel) => sel({ state: baseState(), pushOverlay: () => undefined }),
  {
    getState: () => ({ state: baseState(), pushOverlay: () => undefined }),
    setState: () => undefined,
    subscribe: () => () => undefined
  }
);

/** 与真实实现同义的路径取值（`prefectures.<路>` 等）。 */
export function pick<T>(obj: Record<string, unknown>, path: string, dflt: T): T {
  const v = path.split(".").reduce<unknown>(
    (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
  return (v === undefined ? dflt : v) as T;
}

export default useGameStore;
