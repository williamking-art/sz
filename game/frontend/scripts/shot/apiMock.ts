// 截图台：api/client mock（**仅 dev 用**）。
//
// 设计要点（两次踩坑后的定稿）：
//   · 先「整体 alias 成只含 getApiClient 的 mock」→ **错**：面板还会用别的导出
//     （`AdvancePanel` 要 `subscribeRichPoll`），构建直接失败。
//   · 再「不换模块、只拦 window.fetch」→ **也错**：真实 client 在浏览器里构造就抛错，
//     面板反而崩（截图台看到【面板渲染失败】）。
//   · 定稿：**转发真实模块的全部导出 + 只覆盖 `getApiClient`**。
//     ESM 里显式本地导出会**遮蔽** `export *` 的同名导出，故不会重复。
import * as real from "../../src/renderer/api/client";
import { READOUTS } from "./fixtures";

export * from "../../src/renderer/api/client";

export function getApiClient() {
  let base: Record<string, unknown> = {};
  try {
    base = (real.getApiClient() ?? {}) as unknown as Record<string, unknown>;
  } catch {
    base = {};   // 真实 client 依赖浏览器外的东西时不要连累面板
  }
  return {
    ...base,
    readouts: () => Promise.resolve(READOUTS),
    action: () => Promise.resolve({
      message: "批红：禁军·殿前第15军·整编（档 3）已饬行。", state: null
    })
  };
}
