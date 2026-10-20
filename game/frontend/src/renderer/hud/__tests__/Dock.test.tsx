import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// R-UI-5（2026-10-20 全审，承接旧 P1-25）：
// Dock 的 round2 富化轮询**必须绑组件生命周期**——卸载时退订 + 清掉 180s 上限计时器，
// 否则「结算中退回主菜单」后回调仍向全局 store pushOverlay，把回合报告弹到主菜单上。
// 原实现 `pollTimerRef` 从未赋值（死代码）、180s setTimeout 也没人持有。
const h = vi.hoisted(() => ({
  advance: vi.fn(),
  subscribeRichPoll: vi.fn(),
  unsubscribe: vi.fn(),
  pushOverlay: vi.fn(),
  pushUiLog: vi.fn(),
  setAdvancing: vi.fn(),
  setState: vi.fn(),
  audio: { playClick: vi.fn(), playSfx: vi.fn() },
  state: {
    turn: 3, era_name: "建中靖国", year: 1101, month: 1,
    treasury: 5_000_000, imperial_treasury: 100_000,
    population_satisfaction: 55, prestige: 60
  }
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ advance: h.advance }),
  subscribeRichPoll: h.subscribeRichPoll
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({
      pushOverlay: h.pushOverlay,
      pushUiLog: h.pushUiLog,
      advancing: false,
      setAdvancing: h.setAdvancing,
      setState: h.setState,
      state: h.state
    })
}));

vi.mock("../../audio/engine", () => ({ audioEngine: h.audio }));

import Dock from "../Dock";

const LIMIT_MS = 180_000;

function advanceResult(turn = 3) {
  return { state: { ...h.state, turn }, events: [], log: [], report: "" };
}

/** 抓 180s 上限计时器的 id（用 spy 证明它被 clearTimeout 清掉，不依赖 fake timer）。 */
function captureLimitTimer(setSpy: {
  mock: { calls: unknown[][]; results: { value: unknown }[] };
}): number {
  const idx = setSpy.mock.calls.findIndex((c) => c[1] === LIMIT_MS);
  expect(idx, "应挂一个 180s 上限计时器").toBeGreaterThanOrEqual(0);
  return setSpy.mock.results[idx].value as number;
}

async function clickAdvanceAndSubscribe() {
  render(<Dock />);
  h.advance.mockResolvedValue(advanceResult());
  fireEvent.click(screen.getByText("推演天下"));
  await waitFor(() => expect(h.subscribeRichPoll).toHaveBeenCalledTimes(1));
  return h.subscribeRichPoll.mock.calls[0][0] as (r: Record<string, unknown>) => void;
}

describe("Dock 轮询生命周期（R-UI-5）", () => {
  beforeEach(() => {
    h.advance.mockReset();
    h.subscribeRichPoll.mockReset();
    h.unsubscribe.mockReset();
    h.pushOverlay.mockReset();
    h.pushUiLog.mockReset();
    h.setAdvancing.mockReset();
    h.setState.mockReset();
    h.audio.playClick.mockReset();
    h.audio.playSfx.mockReset();
    h.subscribeRichPoll.mockReturnValue(h.unsubscribe);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("卸载时退订轮询并清掉 180s 上限计时器（无 timer 残留）", async () => {
    const setSpy = vi.spyOn(window, "setTimeout");
    const clearSpy = vi.spyOn(window, "clearTimeout");
    const { unmount } = render(<Dock />);
    h.advance.mockResolvedValue(advanceResult());
    fireEvent.click(screen.getByText("推演天下"));
    await waitFor(() => expect(h.subscribeRichPoll).toHaveBeenCalledTimes(1));
    expect(h.unsubscribe).not.toHaveBeenCalled();
    const limitId = captureLimitTimer(setSpy);

    unmount();
    expect(h.unsubscribe).toHaveBeenCalledTimes(1);          // 订阅已断
    expect(clearSpy).toHaveBeenCalledWith(limitId);          // 180s 计时器已清
    // 卸载后没有任何新 overlay（原缺陷：退回主菜单后仍会弹「回合报告」）
    const before = h.pushOverlay.mock.calls.length;
    expect(h.pushOverlay.mock.calls.filter(
      (c) => (c[0] as { title?: string }).title === "回合报告").length).toBeLessThanOrEqual(1);
    expect(h.pushOverlay.mock.calls.length).toBe(before);
  });

  it("180 秒仍未就绪：到点自动退订，不无限轮询", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await clickAdvanceAndSubscribe();
    expect(h.unsubscribe).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(LIMIT_MS); });
    expect(h.unsubscribe).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("富化就位：弹「回合报告」并立即退订、清掉上限计时器", async () => {
    const setSpy = vi.spyOn(window, "setTimeout");
    const clearSpy = vi.spyOn(window, "clearTimeout");
    const cb = await clickAdvanceAndSubscribe();
    const limitId = captureLimitTimer(setSpy);

    cb({
      ready: true, settle_error: "", rich_report: "本月月报", rich_civilian: "民间风闻",
      log: [], state: { ...h.state, turn: 3 }
    });
    const titles = h.pushOverlay.mock.calls.map((c) => (c[0] as { title?: string }).title);
    expect(titles).toContain("回合报告");
    expect(h.unsubscribe).toHaveBeenCalledTimes(1);
    expect(clearSpy).toHaveBeenCalledWith(limitId);
  });

  it("结算失败：弹「推演未成」，不弹「回合报告」", async () => {
    const cb = await clickAdvanceAndSubscribe();
    cb({ ready: true, settle_error: "AI 未成", rich_report: "", rich_civilian: "", log: [] });
    const titles = h.pushOverlay.mock.calls.map((c) => (c[0] as { title?: string }).title);
    expect(titles).toContain("推演未成");
    expect(titles).not.toContain("回合报告");
  });
});
