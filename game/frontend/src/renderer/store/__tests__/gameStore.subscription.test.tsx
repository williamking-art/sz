import { render, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useRef } from "react";
import {
  GameStoreProvider, useGameStore, __storeApiRebuilds
} from "../gameStore";

// 地基断言（2026-09-27，**实测驱动**）：
//   ① **选择器门槛有效**：只订阅 `pushUiLog`（稳定引用）的组件，在"与它无关的变更"下**不重渲**；
//   ② **合并对象有缓存**：31 个订阅者 × 通知下，合并重建次数远小于"订阅者数 × 通知数"。
// 本文件替代"凭感觉说 store 有双次通知"——旧审计结论已按实测更正（见方案/报告）。
const renders = { action: 0, state: 0 };

function ActionProbe() {
  const pushUiLog = useGameStore((s) => s.pushUiLog);
  const n = useRef(0);
  n.current += 1;
  renders.action = Math.max(renders.action, n.current);
  return <button data-testid="log" onClick={() => pushUiLog("测试回执")}>log</button>;
}

function StateProbe() {
  const st = useGameStore((s) => s.state);
  const n = useRef(0);
  n.current += 1;
  renders.state = Math.max(renders.state, n.current);
  return <span data-testid="state-len">{st ? Object.keys(st).length : 0}</span>;
}

describe("store 订阅地基", () => {
  it("选择器门槛：无关变更不重渲订阅 action 的组件；合并对象被缓存", async () => {
    renders.action = 0;
    renders.state = 0;
    const before = __storeApiRebuilds();

    const { getAllByTestId } = render(
      <GameStoreProvider>
        <StateProbe />
        {Array.from({ length: 30 }, (_, i) => <ActionProbe key={i} />)}
      </GameStoreProvider>
    );

    const actionRendersAfterMount = renders.action;
    const stateRendersAfterMount = renders.state;
    const rebuildsAfterMount = __storeApiRebuilds() - before;

    // 触发一次与 state 无关的变更（写 uiLogs）——31 个订阅者都会收到通知
    await act(async () => {
      fireEvent.click(getAllByTestId("log")[0]);
    });
    await waitFor(() => expect(getAllByTestId("log").length).toBe(30));

    const dAction = renders.action - actionRendersAfterMount;
    const dState = renders.state - stateRendersAfterMount;
    const dRebuilds = __storeApiRebuilds() - before - rebuildsAfterMount;

    // ① 只订阅 action（稳定引用）的组件：**不应重渲**
    expect(dAction).toBe(0);
    // ② 只订阅 state 的组件：state 未变 → 也不应重渲
    expect(dState).toBe(0);
    // ③ 合并对象重建次数受缓存约束：应远小于 31 × 通知数
    expect(dRebuilds).toBeLessThanOrEqual(2);
  });
});
