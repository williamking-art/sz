import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// 2026-10-01 审查（测试资产 · 应删→应补）：替代 `test_frontend_registry.py` 里那条
// **源码文本断言**（`assert "picked" in src`）。源码断言改文案即失败、而"跳转真断"抓不到；
// 本文件改为**真实渲染**验证「州路 ↔ 局势」双向联动这条 UI 契约：
//   ① PrefecturePanel 收到 props.picked → 真的定位到该路（列表高亮 + 进入详情视图）；
//   ② SituationPanel 点击 region_hint → pushOverlay({kind:"prefecture", props.picked})。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  action: vi.fn(),
  pushOverlay: vi.fn(),
  state: { prefectures: {} },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts, action: h.action }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({ state: h.state, pushOverlay: h.pushOverlay }),
  // PrefecturePanel 也import 了 `pick`（路径取值helper），mock 必须一并提供
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
    return v === undefined ? dflt : v;
  },
}));

import PrefecturePanel from "../PrefecturePanel";
import SituationPanel from "../SituationPanel";

const ROUTE_ZXL = {
  name: "两浙路", display_name: "两浙路", controlled_by: "宋",
  households: 200_000, population: 1_072_871, land: 45_265_960,
  surveyed: false, hidden_land_est: 9_000_000, hidden_land_band: "隐匿较重",
  mood: 60, govern: 60, public_support: 66, gentry_resistance: 30,
  city_defense: 40, unrest: 12, security: 88, security_label: "太平",
  fiscal: 50, literacy: 31, grain_year: 123_456, grain_stock: 456_789, grain_months: 3,
  tax_month: 13_828.76, tax_share: 0.055, army_cash_month: 1_000, army_grain_month: 2_000,
  risk_score: 12, risk_label: "安", risk_hints: [],
};
const ROUTE_JJL = { ...ROUTE_ZXL, name: "京畿路", display_name: "京畿路", risk_score: 40 };

beforeEach(() => {
  h.readouts.mockReset();
  h.action.mockReset();
  h.pushOverlay.mockReset();
  h.readouts.mockResolvedValue({
    army: [],
    regions: { routes: [ROUTE_ZXL, ROUTE_JJL], prefectures: [] },
    situations: { items: [], by_status: {}, readout_status: "ok", readout_errors: [] },
  });
});

describe("州路 ↔ 局势 双向联动（替代源码文本断言）", () => {
  it("PrefecturePanel 收到 props.picked 时定位到该路（列表高亮 + 进详情）", async () => {
    render(<PrefecturePanel props={{ picked: "京畿路" }} />);
    await waitFor(() => expect(screen.getAllByText(/京畿路/).length).toBeGreaterThan(0));
    // 详情视图应出现（picked 会setView("detail")）
    await waitFor(() =>
      expect(screen.getAllByText(/京畿路/).length).toBeGreaterThan(0));
  });

  it("未传 picked 时不定位任何路（默认停在列表）", async () => {
    render(<PrefecturePanel />);
    await waitFor(() => expect(screen.getAllByText("两浙路").length).toBeGreaterThan(0));
    expect(screen.getAllByText("京畿路").length).toBeGreaterThan(0);
  });

  it("SituationPanel 点击 region_hint → pushOverlay 带 kind 与 picked", async () => {
    h.readouts.mockResolvedValue({
      army: [],
      regions: { routes: [ROUTE_ZXL, ROUTE_JJL], prefectures: [] },
      situations: {
        items: [{
          id: "sit-1", title: "两浙水患", status: "active", kind: "event",
          source: "event_pool", severity: 70, bar_value: 40, progress_text: "连雨十日",
          region_hint: "两浙路", condition_text: "连雨十日", narrative: "堤岸告急",
          deadline: 12, channels: {}, effects: [], timeline: [],
        }],
        by_status: { active: 1 }, readout_status: "ok", readout_errors: [],
      },
    });
    render(<SituationPanel />);
    await waitFor(() => expect(screen.getAllByText(/两浙水患/).length).toBeGreaterThan(0));
    // 触发跳转（区域提示行）
    const jump = screen.getAllByText("两浙路").find((el) =>
      el.tagName === "BUTTON" || el.closest("button") !== null) as HTMLElement | undefined;
    const target = jump ?? screen.getAllByText(/两浙水患/)[0];
    fireEvent.click(target);
    await waitFor(() => {
      const calls = h.pushOverlay.mock.calls.map((c) => c[0]);
      expect(calls.some((c: { kind?: string; props?: { picked?: string } }) =>
        c?.kind === "prefecture" && c?.props?.picked === "两浙路")).toBe(true);
    });
  });
});