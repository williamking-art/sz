import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 长期旨案卷：读数缺失一律显示「未定义」，不得回落 0；
// 案卷不可读时明确报错（不假装空案卷）。
const h = vi.hoisted(() => ({ readouts: vi.fn(), action: vi.fn() }));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts, action: h.action }),
}));

import { fireEvent } from "@testing-library/react";
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
  handler: {
    name: "郑芝龙",
    org: "闽浙总兵",
    stats: {
      attrs: { governance: 72, finance: 65, military: 92, strategy: 84, reputation: 88 },
      potential: { governance: 78, finance: 70, military: 96, strategy: 90, reputation: 92 },
      attr_names: { governance: "政略", finance: "财计", military: "军略", strategy: "谋断", reputation: "风望" },
      loyalty: 0.42,
      corruption: 0.31,
      traits: ["军略", "果敢"],
      faction: "主战",
    },
  },
  authorization: { budget_total: 50, budget_remaining: 30, pool: "treasury", monthly_cost: 2, discretion: true },
  progress: { percent: 82, phase: "终前", target: 100 },
  monthly_effects: [{ key: "prestige", amount: -1 }],
  progress_log: [
    { turn: 36, narrative: "增烽堠八、墩台二", applied: [{ key: "prestige", amount: -1 }] },
  ],
  outcome_effects: [{ key: "prestige", amount: 9 }],
  fail_effects: [],
  advance: {
    stage: "将成",
    progress: 82,
    forecast: { advance_pct: 7.31, text: "按本月读数，下月约推进 7.31%（基数 5.56% × 难度 1.20 × 执行 0.88 × 立场 1.25）" },
    blockers: ["吏治（强关联）折扣 ×0.96（案牍清明）", "军队不参与（民政事务，未调兵）"],
    supporters: [{ name: "主战", influence: 45, reason: "承办大臣出身该派" }],
    opposers: [{ name: "户部", influence: 30, reason: "专款占用" }],
    support_net: 0.5,
    support_bonus: 0.12,
    stance_mult: 1.25,
    decree_count: 1,
    stall_months: 0,
    months: 18,
    outcome: "在办",
  },
};

describe("LongtermCasePanel 案卷渲染", () => {
  beforeEach(() => h.readouts.mockReset());

  it("渲染案卷关键字段（标题/承办人/专款/阶段/影响/日志/达成）", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: CASE } });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);

    expect(await screen.findByText("南直隶倭寇犯江浙")).toBeTruthy();
    expect(screen.getByText(/郑芝龙/)).toBeTruthy();
    // 本作口径：五维（政略/财计/军略/谋断/风望）+ 潜质上限 + 忠诚/贪腐（0–1，按百分比）
    expect(screen.getByText(/政略/)).toBeTruthy();
    expect(screen.getAllByText(/军略/).length).toBeGreaterThan(0);   // 五维标签 + 特质各一处
    expect(screen.getByText("42%")).toBeTruthy();
    expect(screen.getByText("31%")).toBeTruthy();
    // 本作特色：推进算式 + 阻碍 + 圣意支持
    expect(screen.getByText(/下月约推进 7.31%/)).toBeTruthy();
    expect(screen.getByText(/吏治（强关联）折扣/)).toBeTruthy();
    expect(screen.getByText(/圣旨支持/)).toBeTruthy();
    expect(screen.getByText(/主战（45）/)).toBeTruthy();
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

  it("颁授权：把专款/出库/逐月自理/专断交给后端并刷新", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: CASE } });
    h.action.mockResolvedValue({ message: "已授权：专款 50 万两（treasury）", state: {} });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);

    await screen.findByText("南直隶倭寇犯江浙");
    fireEvent.change(screen.getByLabelText("专款"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("逐月自理"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("赐专断之权"));
    fireEvent.click(screen.getByRole("button", { name: "颁授权" }));

    expect(await screen.findByText(/已授权/)).toBeTruthy();
    expect(h.action).toHaveBeenCalledWith("authorize_case", {
      task_id: "ltp1", budget: 50, pool: "treasury", discretion: true, monthly_cost: 2,
    });
  });
});
