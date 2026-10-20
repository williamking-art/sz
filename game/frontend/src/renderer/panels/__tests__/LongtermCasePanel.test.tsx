import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 长期旨案卷：读数缺失一律显示「未定义」，不得回落 0；
// 案卷不可读时明确报错（不假装空案卷）。
const h = vi.hoisted(() => ({ readouts: vi.fn() }));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts }),
}));

import LongtermCasePanel from "../LongtermCasePanel";

const CASE = {
  case_no: "#426",
  title: "南直隶倭寇犯江浙",
  kind: "边事",
  status: "进行中",
  severity: 95,
  source_ref: "disaster_wokou_1630_07",
  opened_turn: 34,
  last_advance_turn: 36,
  linked_region: "nanzhili",
  linked_factions: ["农民", "户部"],
  cancellable: false,
  handler: { name: "郑芝龙", org: "闽浙总兵", stats: { loyalty: 0.42, corruption: 0.31, role: "闽浙总兵", rank: "正二品", faction: "主战", traits: "果敢" } },
  authorization: { budget_total: 50, budget_remaining: 30, pool: "treasury", monthly_cost: 2, discretion: true },
  progress: { percent: 82, phase: "终前", target: 100 },
  monthly_effects: [{ key: "prestige", amount: -1 }],
  progress_log: [
    { turn: 36, narrative: "增烽堠八、墩台二", applied: [{ key: "prestige", amount: -1 }] },
  ],
  outcome_effects: [{ key: "prestige", amount: 9 }],
  fail_effects: [],
};

describe("LongtermCasePanel 案卷渲染", () => {
  beforeEach(() => h.readouts.mockReset());

  it("渲染案卷关键字段（标题/承办人/专款/阶段/影响/日志/达成）", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: CASE } });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);

    expect(await screen.findByText("南直隶倭寇犯江浙")).toBeTruthy();
    expect(screen.getByText(/郑芝龙/)).toBeTruthy();
    // 本项目大臣只有 loyalty/corruption 两项数值（0–1），按百分比显示；没有六维
    expect(screen.getByText("42%")).toBeTruthy();
    expect(screen.getByText("31%")).toBeTruthy();
    expect(screen.getByText(/现有专款/)).toBeTruthy();
    expect(screen.getByText(/终前/)).toBeTruthy();
    expect(screen.getByText(/皇威 -1/)).toBeTruthy();
    expect(screen.getByText(/增烽堠八、墩台二/)).toBeTruthy();
    expect(screen.getByText(/皇威 \+9/)).toBeTruthy();
  });

  it("读数缺该案卷：明确报错，不显示空案卷", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: {} });
    render(<LongtermCasePanel props={{ id: "missing" }} />);
    expect(await screen.findByText(/案卷读数为空/)).toBeTruthy();
  });
});
