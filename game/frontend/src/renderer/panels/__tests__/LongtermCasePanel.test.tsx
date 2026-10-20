import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 长期旨案卷：读数缺失一律显示「未定义」，不得回落 0；
// 案卷不可读时明确报错（不假装空案卷）。
// 2026-10-20 全审补：R-UI-2（已授权禁用按钮）/ R-UI-3（单位=贯，万贯走 wan）/
// R-UI-4（未授权 authorization=null ⇒ 「未授权/未定义」，绝不显示「0 贯」）/
// R-UI-7（按后端 ok 渲染失败态）。
const h = vi.hoisted(() => ({ readouts: vi.fn(), action: vi.fn() }));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts, action: h.action }),
}));

import { fireEvent } from "@testing-library/react";
import LongtermCasePanel from "../LongtermCasePanel";

const CASE = {
  case_no: "LT-034-01",
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
  // 单位口径：贯（300,000 贯 = 30万贯）
  authorization: { budget_total: 300000, budget_remaining: 100000, pool: "treasury", monthly_cost: 20000, discretion: true },
  progress: { percent: 82, phase: "终前", target: 100 },
  monthly_effects: [{ key: "prestige", amount: -1 }],
  progress_log: [
    { turn: 36, narrative: "增烽堠八、墩台二", applied: [{ key: "prestige", amount: -1 }] },
    { turn: 37, narrative: "工料未到", applied: [{ key: "treasury", amount: null }] },
  ],
  outcome_effects: [{ key: "prestige", amount: 9 }],
  fail_effects: [],
  resolve_condition_text: "成效满 100%（按月由支持方/阻力方与执行能力推进）",
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

/** 未授权口径（C-4）：后端整块回 null，前端不得显示 0。 */
const UNAUTHORIZED = { ...CASE, case_no: null, authorization: null };

describe("LongtermCasePanel 案卷渲染", () => {
  beforeEach(() => {
    h.readouts.mockReset();
    h.action.mockReset();
  });

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
    // R-UI-3：专款/余额/月费统一「贯」，万以上走 wan()（30万贯/10万贯/2万贯）
    expect(screen.getByText("专款额度")).toBeTruthy();
    expect(screen.getByText(/30万贯/)).toBeTruthy();
    expect(screen.getByText(/10万贯/)).toBeTruthy();
    expect(screen.getByText(/2万贯 \/ 月/)).toBeTruthy();
    expect(screen.queryByText(/万两/)).toBeNull();
    // 怎么算赢：达成条件来自事务自身声明（不是编造）
    expect(screen.getByText(/成效满 100%/)).toBeTruthy();
    expect(screen.getByText(/终前/)).toBeTruthy();
    // 「皇威 -1」同时出现在「当前影响」与「推进日志落账」两处
    expect(screen.getAllByText(/皇威 -1/).length).toBeGreaterThan(0);
    expect(screen.getByText(/增烽堠八、墩台二/)).toBeTruthy();
    expect(screen.getByText(/皇威 \+9/)).toBeTruthy();
    // 日志落账缺值 ⇒ 「未定义」（不再是空白串）
    expect(screen.getByText(/国库 未定义/)).toBeTruthy();
  });

  it("读数缺该案卷：明确报错，不显示空案卷", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: {} });
    render(<LongtermCasePanel props={{ id: "missing" }} />);
    expect(await screen.findByText(/案卷读数为空/)).toBeTruthy();
  });

  it("未授权（authorization=null）：显示「未授权/未定义」，绝不出现 0 贯；按钮可点", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: UNAUTHORIZED } });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);
    expect(await screen.findByText(/本卷尚未授权/)).toBeTruthy();
    expect(screen.queryByText(/0 贯/)).toBeNull();
    expect(screen.queryByText(/0 万两/)).toBeNull();
    const btn = screen.getByRole("button", { name: "颁授权" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it("已授权：按钮禁用并显示「已授权」（R-UI-2）", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: CASE } });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);
    await screen.findByText("南直隶倭寇犯江浙");
    const btn = screen.getByRole("button", { name: "已授权" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect((screen.getByLabelText("专款") as HTMLInputElement).disabled).toBe(true);
  });

  it("颁授权：把专款/出库/逐月自理/专断交给后端并刷新", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: UNAUTHORIZED } });
    h.action.mockResolvedValue({
      ok: true,
      message: "已授权（案号 LT-001-01）：专款 50 贯（国库），逐月自理 2 贯，专断之权 已授",
      state: {},
    });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);

    await screen.findByText("南直隶倭寇犯江浙");
    fireEvent.change(screen.getByLabelText("专款"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("逐月自理"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("赐专断之权"));
    fireEvent.click(screen.getByRole("button", { name: "颁授权" }));

    expect(await screen.findByText(/已授权（案号/)).toBeTruthy();
    expect(screen.getByText(/已准/)).toBeTruthy();
    expect(h.action).toHaveBeenCalledWith("authorize_case", {
      task_id: "ltp1", budget: 50, pool: "treasury", discretion: true, monthly_cost: 2,
    });
  });

  it("授权失败（后端 ok=false，HTTP 200）：渲染失败态且不出现「已准/已授权」（R-UI-7）", async () => {
    h.readouts.mockResolvedValue({ longterm_cases: { ltp1: UNAUTHORIZED } });
    h.action.mockResolvedValue({ ok: false, message: "府库不足，未拨款", state: {} });
    render(<LongtermCasePanel props={{ id: "ltp1" }} />);

    await screen.findByText("南直隶倭寇犯江浙");
    fireEvent.click(screen.getByRole("button", { name: "颁授权" }));

    expect(await screen.findByText(/授权未成：府库不足/)).toBeTruthy();
    expect(screen.queryByText(/已准/)).toBeNull();
    // 未授权状态不变 ⇒ 仍是「颁授权」按钮（不会假显示已授权）
    expect(screen.getByRole("button", { name: "颁授权" })).toBeTruthy();
  });
});
