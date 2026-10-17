import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 治务枢纽 · 纪事页：准奏/留中失败必须给玩家可见反馈，且不得改动本地 state。
const h = vi.hoisted(() => ({
  action: vi.fn(),
  setState: vi.fn(),
  pushUiLog: vi.fn(),
  state: {
    memorials: [
      { title: "请修水利疏", body: "乞修两浙水利。", source_tag: "通进银台司进呈" },
    ],
  },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ action: h.action }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({ state: h.state, setState: h.setState, pushUiLog: h.pushUiLog }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      obj,
    );
    return v === undefined || v === null ? dflt : v;
  },
  getTreasuryDetail: () => ({
    title: "国库月度收支",
    totalIn: null,
    totalOut: null,
    net: null,
    incomes: [],
    expenses: [],
  }),
}));

import GovernanceHub from "../GovernanceHub";

function openChronicle() {
  render(<GovernanceHub />);
  fireEvent.click(screen.getByText("纪 事 · 奏 折"));
}

describe("GovernanceHub 奏折批红失败反馈", () => {
  beforeEach(() => {
    h.action.mockReset();
    h.setState.mockReset();
    h.pushUiLog.mockReset();
  });

  it("准奏失败：显示可见错误，不提交本地 state", async () => {
    h.action.mockRejectedValueOnce(new Error("网络中断"));
    openChronicle();
    fireEvent.click(screen.getByText("准 奏"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("准奏未成");
    expect(alert.textContent).toContain("网络中断");
    expect(h.setState).not.toHaveBeenCalled();
    expect(h.pushUiLog).not.toHaveBeenCalled();
  });

  it("留中失败：显示可见错误，不提交本地 state", async () => {
    h.action.mockRejectedValueOnce(new Error("后端 500"));
    openChronicle();
    fireEvent.click(screen.getByText("留 中"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("留中未成");
    expect(alert.textContent).toContain("后端 500");
    await waitFor(() => expect(h.setState).not.toHaveBeenCalled());
  });
});
