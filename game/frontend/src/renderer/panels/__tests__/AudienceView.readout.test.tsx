import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// R-UI-6（2026-10-20 全审）：召对面板「五维」原先由**人名 seed 伪随机**生成并直渲染
// （P1-27 只修了一半）。现改为**只渲染后端 readouts.ministers 下发的真值**
// （单一来源 content/ministers/stats.py），缺失一律「未定义」，不得出现 60–99 伪值。
const h = vi.hoisted(() => ({
  memory: vi.fn(),
  action: vi.fn(),
  readouts: { current: null as unknown },
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ memory: h.memory, action: h.action }),
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) =>
    sel({
      state: { era_name: "建中靖国", year: 1101, month: 1, turn: 1, prefectures: {}, central_orgs: {}, factions: {} },
      readouts: h.readouts.current,
      popOverlay: vi.fn(),
      setState: vi.fn(),
    }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
    return v === undefined ? dflt : v;
  },
}));

import AudienceView from "../AudienceView";

const ATTRS = {
  governance: 82, finance: 70, military: 45, strategy: 78, reputation: 88,
};
const POTENTIAL = {
  governance: 88, finance: 78, military: 55, strategy: 84, reputation: 92,
};
const ATTR_NAMES = {
  governance: "政略", finance: "财计", military: "军略", strategy: "谋断", reputation: "风望",
};

function readoutsWith(attrs: unknown, potential: unknown = POTENTIAL, attr_names: unknown = ATTR_NAMES) {
  return {
    army: [],
    granary: {},
    defense_lines: {},
    ministers: { 韩忠彦: { age: 50, role: "尚书左仆射", attrs, potential, attr_names } },
  };
}

describe("AudienceView 五维属性（R-UI-6）", () => {
  beforeEach(() => {
    h.memory.mockReset();
    h.memory.mockResolvedValue({ sessions: [], dialogues: [] });
    h.action.mockReset();
    h.readouts.current = null;
  });

  it("渲染后端下发的真实五维（含潜质上限），不再是伪随机值", async () => {
    h.readouts.current = readoutsWith(ATTRS);
    render(<AudienceView props={{}} />);
    await waitFor(() => expect(screen.getAllByText("政略").length).toBeGreaterThan(0));
    // 五个中文标签全部来自后端 attr_names（本作口径五维）
    for (const label of ["政略", "财计", "军略", "谋断", "风望"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    // 数值 == readout 下发值（潜质上限以 /上限 形式并列）
    expect(screen.getByText("82")).toBeTruthy();
    expect(screen.getByText("/88")).toBeTruthy();
    expect(screen.getByText("88")).toBeTruthy();   // 风望 88 与 政略潜质 /88 各一处
  });

  it("readouts 未下发五维 ⇒ 全部显示「未定义」，不回落伪值", async () => {
    h.readouts.current = null;
    render(<AudienceView props={{}} />);
    await waitFor(() => expect(screen.getAllByText("政略").length).toBeGreaterThan(0));
    expect(screen.getAllByText("未定义").length).toBeGreaterThanOrEqual(5);
  });

  it("部分维度缺失 ⇒ 该维「未定义」，其余仍显示真值", async () => {
    h.readouts.current = readoutsWith({ governance: 82, finance: null, military: null, strategy: 78, reputation: null });
    render(<AudienceView props={{}} />);
    await waitFor(() => expect(screen.getAllByText("82").length).toBeGreaterThan(0));
    // 3 个缺失维（财计/军略/风望）+ 潜质缺失 → 至少 3 处「未定义」
    expect(screen.getAllByText("未定义").length).toBeGreaterThanOrEqual(3);
  });
});
