import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 会计录：后端 finance 派生失败时下发 {}（server.py: finance={}）。
// 空对象不得被 asNum(...,0) 渲染成 0 贯；缺失字段必须显示「未定义」。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  setState: vi.fn(),
  pushOverlay: vi.fn(),
  state: {
    commerce_tax_rate: 0.1,
    treasury: 100,
    imperial_treasury: 50,
    money_supply: 1000,
    price_level: 1,
    payraise_budget: 0,
    waste_reform: {},
  },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({ state: h.state, setState: h.setState, pushOverlay: h.pushOverlay, readouts: null }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      obj,
    );
    return v === undefined || v === null ? dflt : v;
  },
}));

import AccountingPanel from "../AccountingPanel";

describe("AccountingPanel 空读数不显示 0", () => {
  beforeEach(() => {
    h.readouts.mockReset();
  });

  it("finance={}：账面岁入/月应征/净额均显示未定义，不显示 0贯", async () => {
    h.readouts.mockResolvedValue({ finance: {} });
    render(<AccountingPanel />);

    expect(await screen.findByText(/账面岁入.*未定义/)).toBeTruthy();
    expect(screen.getByText(/本月应征.*未定义/)).toBeTruthy();
    expect(screen.getByText(/净额：未定义/)).toBeTruthy();
    expect(screen.queryByText(/账面岁入.*0贯/)).toBeNull();
    expect(screen.queryByText(/本月应征.*0贯/)).toBeNull();
  });
});
