import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// 2026-09-27 新增：地方档案 / 省级军政 两个面板的**首个前端回归网**（此前前端零用例）。
// 手法：mock 掉 api/client 与 store，喂入**确定的读数**，断言面板暴露的关键口径：
//   ① 治安正极性（显示的是后端 security，不是 unrest）；② 未清丈只显**约值**（不显"已清丈"）；
//   ③ 在地阶级 7 类齐全；④ 军令按钮：5 键可点、3 键（拆分/合并/换帅）禁用；
//   ⑤ 点「整编」确实发出 issue_military_order（带选中编制单位 unit_id）。
const h = vi.hoisted(() => ({
  readouts: vi.fn(),
  action: vi.fn(),
  pushOverlay: vi.fn(),
  state: {
    prefectures: {
      "两浙路": {
        controlled_by: "宋",
        population: 1_072_871,
        govern: 60,
        buildings: { 农田: 2, 市舶司: 1 },
        pops: {
          农: { size: 500_000, hidden: 120_000, 自耕农: 300_000, 富农: 50_000, 贫农: 100_000, 佃农: 50_000, ding: 80_000, kou: 120_000 },
          士绅: { size: 9_000 },
          工匠: { size: 110_000 },
          商人: { size: 220_000 },
          官僚: { size: 40_000 },
          兵: { size: 220_000 }
        }
      }
    },
    army_units: [
      {
        unit_id: "u1", name: "两浙路·殿前第15军", army_name: "殿前第15军", tier: "禁军",
        station: "两浙路", defense_line: "沿海", branches: { 轻步兵: 20_000, 弓弩手: 5_000 },
        morale: 55, training: 30, arrears: 0, org_arm: "殿前司"
      },
      {
        unit_id: "u2", name: "两浙路·厢军造船", army_name: "造船厢军", tier: "厢军",
        station: "两浙路", defense_line: "", branches: { 轻步兵: 8_000 },
        morale: 40, training: 10, arrears: 1_200, org_arm: ""
      },
      {
        unit_id: "u9", name: "京畿路·殿前第1军", army_name: "殿前第1军", tier: "禁军",
        station: "京畿路", defense_line: "", branches: { 重骑兵: 9_000 },
        morale: 60, training: 50, arrears: 0, org_arm: "殿前司"
      }
    ]
  }
}));

vi.mock("../api/client", () => ({
  getApiClient: () => ({ readouts: h.readouts, action: h.action })
}));

vi.mock("../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) => sel({ state: h.state, pushOverlay: h.pushOverlay }),
  pick: (obj: Record<string, unknown>, path: string, dflt: unknown) => {
    const v = path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined), obj);
    return v === undefined ? dflt : v;
  }
}));

import LocalArchivePanel from "./LocalArchivePanel";
import ProvinceMilitaryPanel from "./ProvinceMilitaryPanel";

const ROUTE = {
  name: "两浙路", display_name: "两浙路", controlled_by: "宋",
  households: 200_000, population: 1_072_871, land: 45_265_960,
  surveyed: false, hidden_land_est: 9_000_000, hidden_land_band: "隐匿较重",
  mood: 60, govern: 60, public_support: 66, gentry_resistance: 30,
  city_defense: 40, unrest: 12, security: 88, security_label: "太平",
  fiscal: 50, literacy: 31, grain_year: 123_456, grain_stock: 456_789, grain_months: 3,
  tax_month: 13_828.76, tax_share: 0.055, army_cash_month: 1_000, army_grain_month: 2_000,
  risk_score: 12, risk_label: "安", risk_hints: []
};

const PREFECTURES = [
  { name: "台州", circuit: "两浙", route: "两浙路", population: 1_072_871, households: 200_000,
    land: 45_265_960, grain_year: 123_456, tax_month: 13_828.76, share: 1.0 }
];

const MILITARY = {
  route: null,
  routes: [
    { route: "两浙路", units: 2, troops: 33_000, morale_weighted: 51.4, arrears: 1_200,
      cash_month: 1_000, grain_month: 2_000, city_defense: 40, security: 88,
      security_label: "太平", controlled_by: "宋" }
  ],
  nation: { routes: 1, units: 2, troops: 33_000, arrears: 1_200, cash_month: 1_000, grain_month: 2_000 }
};

beforeEach(() => {
  h.readouts.mockReset();
  h.action.mockReset();
  h.readouts.mockResolvedValue({ regions: { routes: [ROUTE], prefectures: PREFECTURES, military: MILITARY } });
  h.action.mockResolvedValue({ message: "批红：禁军·殿前第15军·整编（档 3）已饬行。", state: h.state });
});

describe("地方档案（州府级/省级）", () => {
  it("显示治安（正极性，来自后端 security）而非动乱，并标注动乱原值", async () => {
    render(<LocalArchivePanel props={{ kind: "circuit", name: "两浙路" }} />);
    await waitFor(() => expect(screen.getByText(/88（太平）/)).toBeTruthy());
    expect(screen.getAllByText("88").length).toBeGreaterThan(0);          // 治安值
    expect(screen.getByText(/动乱 12/)).toBeTruthy();              // 原值仅作注解
  });

  it("未清丈只显隐田约值与档位词，不出现「已清丈」与真值", async () => {
    render(<LocalArchivePanel props={{ kind: "circuit", name: "两浙路" }} />);
    await waitFor(() => expect(screen.getByText(/隐匿较重/)).toBeTruthy());
    expect(screen.queryByText("已清丈")).toBeNull();
    expect(screen.getAllByText(/约/).length).toBeGreaterThan(0);
  });

  it("在地阶级为 7 类：六类 + 隐户", async () => {
    render(<LocalArchivePanel props={{ kind: "circuit", name: "两浙路" }} />);
    await waitFor(() => expect(screen.getByText(/在地阶级 · 7 类/)).toBeTruthy());
    for (const c of ["农", "士绅", "工匠", "商人", "官僚", "兵", "隐户"]) {
      expect(screen.getAllByText(c).length).toBeGreaterThan(0);
    }
  });

  it("州府名册来自 regions.prefectures（Σ府 == 路级）", async () => {
    render(<LocalArchivePanel props={{ kind: "circuit", name: "两浙路" }} />);
    await waitFor(() => expect(screen.getByText("台州")).toBeTruthy());
    expect(screen.getByText(/所属州府 · 1/)).toBeTruthy();
  });
});

describe("省级军政（编制单位 + 军令）", () => {
  it("按编制单位列出（番号/军籍/兵额），且只列本路", async () => {
    render(<ProvinceMilitaryPanel props={{ route: "两浙路" }} />);
    await waitFor(() => expect(screen.getAllByText("殿前第15军").length).toBeGreaterThan(0));
    expect(screen.getAllByText("造船厢军").length).toBeGreaterThan(0);
    expect(screen.queryAllByText("殿前第1军").length).toBe(0);            // 京畿路的单位不该出现
  });

  it("军令按钮：5 键可施行、3 键待契约（禁用）", async () => {
    render(<ProvinceMilitaryPanel props={{ route: "两浙路" }} />);
    await waitFor(() => expect(screen.getAllByText("殿前第15军").length).toBeGreaterThan(0));
    for (const a of ["整编", "扩编", "地图调度", "裁撤", "改名"]) {
      expect((screen.getByRole("button", { name: a }) as HTMLButtonElement).disabled).toBe(false);
    }
    for (const a of ["拆分", "合并", "换帅"]) {
      expect((screen.getByRole("button", { name: a }) as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("点「整编」发出 issue_military_order，并带上选中的编制单位", async () => {
    render(<ProvinceMilitaryPanel props={{ route: "两浙路" }} />);
    await waitFor(() => expect(screen.getAllByText("殿前第15军").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "整编" }));
    await waitFor(() => expect(h.action).toHaveBeenCalledWith(
      "issue_military_order",
      expect.objectContaining({ unit_id: "u1", button: "整编" })
    ));
    expect(await screen.findByText(/已饬行/)).toBeTruthy();   // /批红/ 会命中页脚说明，故用回执专有词
  });

  it("全国总览页签给出编制单位/兵额/欠饷合计", async () => {
    render(<ProvinceMilitaryPanel props={{ route: "两浙路" }} />);
    await waitFor(() => expect(screen.getAllByText("殿前第15军").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "全国总览" }));
    await waitFor(() => expect(screen.getByText("全国军政总览")).toBeTruthy());
    expect(screen.getAllByText(/33,000|3\.3万|33万/).length).toBeGreaterThan(0);
  });
});
