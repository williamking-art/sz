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
import { HUB } from "./hubFixture";
import { SITUATIONS } from "./situationsFixture";

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
    // 🔴 M266：**同时**给出真实契约形状 `{hub}`（`ReadoutHubPanel` 取 `res.hub`，
    //   旧形状 `READOUTS` 无 `hub` 键 ⇒ 面板恒停在「正在读取…」，此前被我误判为
    //   「截图台无后端」。保留 `...READOUTS` 旧形状以免影响其它读 `readouts` 的面板。
    readouts: () => Promise.resolve({ ...READOUTS, hub: HUB, situations: SITUATIONS }),
    action: () => Promise.resolve({
      message: "批红：禁军·殿前第15军·整编（档 3）已饬行。", state: null
    })
  };
}
