// 截图台：store 模拟（**仅 dev 用**）——按真实 `useGameStore` 的调用形状（selector）返回 fixture。
import { STATE } from "./fixtures";

type Sel = (s: unknown) => unknown;

export function useGameStore(sel: Sel): unknown {
  return sel({ state: STATE, pushOverlay: () => undefined });
}

/** 与真实实现同义的路径取值（`prefectures.<路>` 等）。 */
export function pick<T>(obj: Record<string, unknown>, path: string, dflt: T): T {
  const v = path.split(".").reduce<unknown>(
    (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
  return (v === undefined ? dflt : v) as T;
}
