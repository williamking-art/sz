import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 科技面板：不得在前端复刻 node_status/tech_cost_with_era。
// 后端未下发节点读数时，状态/费用显示「未定义」，立项动作把 silver=0 交给后端权威计算。
const h = vi.hoisted(() => ({
  action: vi.fn(),
  setState: vi.fn(),
  state: {
    year: 1101,
    tech: {
      level: 50,
      hydraulics: 40,
      unlocked: ["M0_plow", "M1_noria"],
      researching: {} as Record<string, unknown>,
    },
  },
  readouts: {} as Record<string, unknown>,
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ action: h.action }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({ state: h.state, setState: h.setState, readouts: h.readouts }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      obj,
    );
    return v === undefined || v === null ? dflt : v;
  },
}));

import TechPanel from "../TechPanel";

describe("TechPanel 只读后端节点读数", () => {
  beforeEach(() => {
    h.action.mockReset();
    h.setState.mockReset();
    h.readouts = {};
    h.action.mockResolvedValue({ message: "已立项", state: h.state });
  });

  it("后端未下发节点读数：状态/费用显示未定义，立项不前端算价（silver=0）", async () => {
    render(<TechPanel />);
    fireEvent.click(screen.getByText("水力大纺车"));

    expect(screen.getByText(/状态：未定义/)).toBeTruthy();
    expect(screen.getByText(/耗帑 未定义/)).toBeTruthy();

    fireEvent.click(screen.getByText("国库拨银（会签）"));
    await waitFor(() => expect(h.action).toHaveBeenCalledTimes(1));
    expect(h.action.mock.calls[0][0]).toBe("start_tech_research");
    expect(h.action.mock.calls[0][1].node_id).toBe("M2_spindle");
    expect(h.action.mock.calls[0][1].silver).toBe(0);
  });

  it("后端下发节点可研/成本字段：只渲染后端值", () => {
    h.readouts = {
      tech: {
        nodes: {
          M2_spindle: { status: "researchable", silver: 120000, months: 9, idea: false },
        },
      },
    };
    render(<TechPanel />);
    fireEvent.click(screen.getByText("水力大纺车"));

    expect(screen.getByText(/状态：可研发/)).toBeTruthy();
    expect(screen.getByText(/耗帑 12万贯/)).toBeTruthy();
    expect(screen.getByText(/工期 9月/)).toBeTruthy();
    expect(screen.getByText("国库拨银（会签）")).toBeTruthy();
  });
});
