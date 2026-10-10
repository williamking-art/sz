import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// 州路档案（左侧多页面抽屉）+ 单军档案的首个前端回归网。
//
// 断言的是**面板纪律**，不是像素：
//   ① 多页面：默认概览，切「军政」不改变当前选中的路（同一对象 + 页签）；
//   ② 层级：点州府走既有「地方档案」下钻，不在抽屉里另造府级口径；
//   ③ 军队标签 → 单军档案，且**月军饷/月粮**按后端读数显示；
//   ④ 缺失 ≠ 0：读数为 null 时显示「未定义」，不得显示 0。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  action: vi.fn(),
  pushOverlay: vi.fn(),
  setSelected: vi.fn(),
  selected: { kind: "circuit", name: "两浙路", props: {} } as unknown,
  state: {
    prefectures: {
      "两浙路": {
        controlled_by: "宋",
        local_treasury: 12345,
        buildings: { 农田: 3, 市舶司: 1 },
        pops: {
          农: { size: 500_000, hidden: 120_000 },
          士绅: { size: 9_000 },
          工匠: { size: 110_000 },
          商人: { size: 220_000 },
          官僚: { size: 40_000 },
          兵: { size: 220_000 }
        }
      }
    }
  }
}));

vi.mock("../../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts, action: h.action })
}));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) => sel({
    state: h.state,
    selected: h.selected,
    setSelected: h.setSelected,
    pushOverlay: h.pushOverlay
  }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
    return v === undefined ? dflt : v;
  }
}));

import ProvinceArchivePanel from "../ProvinceArchivePanel";
import ArmyDossier from "../../components/ArmyDossier";

const ROUTE = {
  name: "两浙路", display_name: "两浙路", controlled_by: "宋",
  households: 200_000, population: 1_072_871, land: 45_265_960,
  surveyed: true, hidden_land: 9_000_000,
  mood: 60, govern: 60, public_support: 66, gentry_resistance: 30,
  city_defense: 40, unrest: 12, security: 88, security_label: "太平",
  fiscal: 50, literacy: 31, grain_year: 123_456, grain_stock: 456_789, grain_months: 3,
  tax_month: 13_828.76, tax_share: 0.055, army_cash_month: 1_000, army_grain_month: 2_000,
  risk_score: 12, risk_label: "安", risk_hints: []
};

const PREFECTURES = [
  { name: "台州", circuit: "两浙", route: "两浙路", population: 1_000_000, households: 190_000,
    land: 40_000_000, grain_year: 100_000, tax_month: 12_000, share: 0.9 },
  { name: "明州", circuit: "两浙", route: "两浙路", population: 72_871, households: 10_000,
    land: 5_265_960, grain_year: 23_456, tax_month: 1_828.76, share: 0.1 }
];

const MILITARY = {
  route: null,
  routes: [
    { route: "两浙路", units: 1, troops: 20_000, morale_weighted: 55, arrears: 0,
      cash_month: 1_000, grain_month: 2_000, city_defense: 40, security: 88,
      security_label: "太平", controlled_by: "宋" }
  ],
  nation: { routes: 1, units: 1, troops: 20_000, arrears: 0, cash_month: 1_000, grain_month: 2_000 }
};

const ARMY = [
  {
    unit_id: "u1", name: "两浙路·殿前第15军", army_name: "殿前第15军", tier: "禁军",
    station: "两浙路", defense_line: "沿海", branches: { 轻步兵: 20_000 },
    morale: 55, training: 30, arrears: 0, org_arm: "殿前司", scale: "军", serial: 15,
    equip_rate: 0.8, equip: { 枪刀: 20_000 },
    monthly_pay: 35_400, monthly_grain: 30_000
  }
];

const PLAN = { projects: [{ pid: "p1", name: "两浙水利", route: "两浙路", status: "advancing", status_label: "推进中", progress: 40 }] };

function mockReadouts(over: Record<string, unknown> = {}) {
  h.readouts.mockResolvedValue({
    army: ARMY,
    plan: PLAN,
    regions: { routes: [ROUTE], prefectures: PREFECTURES, military: MILITARY },
    ...over
  });
}

beforeEach(() => {
  h.readouts.mockReset();
  h.action.mockReset();
  h.pushOverlay.mockReset();
  h.setSelected.mockReset();
  h.selected = { kind: "circuit", name: "两浙路", props: {} };
  mockReadouts();
});

describe("州路档案（左侧多页面抽屉）", () => {
  it("默认停在概览：显示关键指标与所属州府（Σ府 == 路级）", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    expect(screen.getByText("明州")).toBeTruthy();
    expect(screen.getByText("州路档案")).toBeTruthy();
    // 关键指标格（参考图口径：人口 / 民心 / 动乱 / 月税实收）
    for (const k of ["人口", "民心", "动乱", "月税实收"]) {
      expect(screen.getAllByText(k).length).toBeGreaterThan(0);
    }
  });

  it("多页面切换：切到「军政」不改变当前选中的路", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "军政" }));
    await waitFor(() => expect(screen.getAllByText("本路驻军").length).toBeGreaterThan(0));
    // 选中的路仍是同一条（页签只换内容，不换对象）
    expect(screen.getAllByText("两浙路").length).toBeGreaterThan(0);
    expect(screen.getByText("殿前第15军")).toBeTruthy();
  });

  it("层级纪律：点州府下钻到既有「地方档案」，不在此另造府级口径", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    fireEvent.click(screen.getByText("台州"));
    await waitFor(() => expect(h.pushOverlay).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "localarchive", props: expect.objectContaining({ kind: "city", name: "台州" }) })
    ));
  });

  it("军队标签 → 单军档案：兵种/人员/月军饷/月粮按后端读数显示", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "军政" }));
    await waitFor(() => expect(screen.getByText("殿前第15军")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /查看殿前第15军档案/ }));
    await waitFor(() => expect(screen.getByText("军伍档案")).toBeTruthy());
    // 断言**限定在档案浮层内**：抽屉的军政页也有「月军饷」标签，全局查询会撞车
    const dlg = within(screen.getByRole("dialog"));
    expect(dlg.getByText("轻步兵")).toBeTruthy();
    expect(dlg.getByText("20,000人")).toBeTruthy();
    expect(dlg.getByText(/月\s*军\s*饷/)).toBeTruthy();
    expect(dlg.getByText("3.5万贯")).toBeTruthy();
    expect(dlg.getByText("3万石")).toBeTruthy();
  });


  it("营建页列出本路建筑与在办工程（读数来自后端）", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "营建" }));
    await waitFor(() => expect(screen.getByText("两浙水利")).toBeTruthy());
    expect(screen.getByText("市舶司")).toBeTruthy();
  });

  it("财赋页展示本路月税/驻军月饷/粮储安全垫", async () => {
    render(<ProvinceArchivePanel />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "财赋" }));
    await waitFor(() => expect(screen.getByText("粮储安全垫")).toBeTruthy());
    expect(screen.getByText("3.00 月")).toBeTruthy();
  });
});

describe("单军档案：缺失 ≠ 0", () => {
  it("月军饷/月粮缺失时显示「未定义」，不显示 0", () => {
    const unit = { ...ARMY[0], monthly_pay: null, monthly_grain: undefined } as never;
    render(<ArmyDossier unit={unit} onClose={() => {}} />);
    expect(screen.getByText("军伍档案")).toBeTruthy();
    // 缺失字段各自呈现「未定义」（月军饷、月粮消耗至少各一处）
    expect(screen.getAllByText("未定义").length).toBeGreaterThanOrEqual(2);
  });

  it("单位为空时不渲染（避免空壳浮层）", () => {
    const { container } = render(<ArmyDossier unit={null} onClose={() => {}} />);
    expect(container.textContent).toBe("");
  });
});
