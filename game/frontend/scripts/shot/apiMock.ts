// 截图台：API 模拟（**仅 dev 用**）——面板只用到 `readouts()` 与 `action()`。
import { READOUTS } from "./fixtures";

export function getApiClient() {
  return {
    readouts: () => Promise.resolve(READOUTS),
    action: () => Promise.resolve({ message: "批红：禁军·殿前第15军·整编（档 3）已饬行。", state: null })
  };
}
