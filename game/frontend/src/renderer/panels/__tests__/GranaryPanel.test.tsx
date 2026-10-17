import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 仓廪：后端 granary 派生失败时下发 {}；缺失月入/月出/米价/物价不得显示 0。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  state: {
    granary: 1000,
    granary_cap: 5000,
    pay_system: {},
    single_whip: false,
    prefectures: {},
  },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) => sel({ state: h.state }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      obj,
    );
    return v === undefined || v === null ? dflt : v;
  },
}));

import GranaryPanel from "../GranaryPanel";

describe("GranaryPanel 空读数不显示 0", () => {
  beforeEach(() => {
    h.readouts.mockReset();
  });

  it("granary={} 且米价/漕运/物价缺失：显示未定义，不显示 0石/0", async () => {
    h.readouts.mockResolvedValue({ finance: {}, granary: {} });
    render(<GranaryPanel />);

    expect(await screen.findByText(/太仓月入.*未定义/)).toBeTruthy();
    expect(screen.getByText(/月出（军粮未定义/)).toBeTruthy();
    expect(screen.getByText(/米价约 未定义/)).toBeTruthy();
    expect(screen.getByText(/物价水平：未定义/)).toBeTruthy();
    expect(screen.queryByText(/太仓月入.*0石/)).toBeNull();
  });
});
