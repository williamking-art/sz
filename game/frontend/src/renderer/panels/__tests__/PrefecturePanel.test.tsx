import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 州路面板：读数失败时**不得**伪造 50/30/40/0 或 risk_label「警」；
// 缺失字段（如亩产系数）必须显示「未定义」，并保留失败原因/重试入口。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  pushOverlay: vi.fn(),
  state: { prefectures: {}, land: {} as Record<string, unknown> },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) => sel({ state: h.state, pushOverlay: h.pushOverlay }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      obj,
    );
    return v === undefined || v === null ? dflt : v;
  },
}));

import PrefecturePanel from "../PrefecturePanel";

const ROUTE = {
  name: "两浙路",
  display_name: "两浙路",
  controlled_by: "宋",
  households: 200_000,
  population: 1_072_871,
  land: 45_265_960,
  surveyed: false,
  hidden_land_est: 9_000_000,
  hidden_land_band: "隐匿较重",
  mood: 60,
  govern: 60,
  public_support: 66,
  gentry_resistance: 30,
  city_defense: 40,
  unrest: 12,
  security: 88,
  security_label: "太平",
  fiscal: 50,
  literacy: 31,
  grain_year: 123_456,
  grain_stock: 456_789,
  grain_months: 3,
  tax_month: 13_828.76,
  tax_share: 0.055,
  army_cash_month: 1_000,
  army_grain_month: 2_000,
  risk_score: 12,
  risk_label: "安",
  risk_hints: [],
};

function mockReadoutsOk() {
  h.readouts.mockResolvedValue({
    regions: { routes: [ROUTE] },
    situations: { items: [] },
  });
}

describe("PrefecturePanel 缺失值纪律", () => {
  beforeEach(() => {
    h.readouts.mockReset();
    h.pushOverlay.mockReset();
  });

  it("读数失败：显示失败原因与重试，不渲染伪造的州路行/警戒词", async () => {
    h.readouts.mockRejectedValueOnce(new Error("后端断线"));
    render(<PrefecturePanel />);

    expect(await screen.findByText(/州路读数不可用/)).toBeTruthy();
    expect(screen.getByText(/后端断线/)).toBeTruthy();
    expect(screen.queryByText("两浙路")).toBeNull();
    expect(screen.queryByText("警")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(h.readouts).toHaveBeenCalledTimes(2));
  });

  it("亩产系数缺失显示「未定义」，不显示 1.00", async () => {
    mockReadoutsOk();
    h.state.land = {};
    render(<PrefecturePanel />);
    await screen.findByText("两浙路");

    fireEvent.click(screen.getByRole("button", { name: "田 亩 户 籍 总 览" }));
    expect(screen.getByText(/亩产系数：未定义/)).toBeTruthy();
    expect(screen.queryByText(/亩产系数：1\.00/)).toBeNull();
  });
});
