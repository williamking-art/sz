import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import PlanReadoutPanel from "../PlanReadoutPanel";

/**
 * 计划/工程因果回看（规格 decree-action-chain 任务 6）的前端回归。
 *
 * 断言的是**显示纪律**（这是本组件的全部职责）：
 *   ① 四层级各自成块、互不混写；
 *   ② 「待支持」单列且**不得**出现在「工程告成」里；
 *   ③ 读数缺失时如实说明，**不以空白冒充"无工程"**；
 *   ④ 进度/产能/产出直接取后端下发值，前端不重算。
 */
const h = vi.hoisted(() => ({ readouts: null as unknown }));

vi.mock("../../store/gameStore", () => ({
  useGameStore: (sel: (s: unknown) => unknown) => sel({ readouts: h.readouts }),
}));

const PLAN = {
  phase_labels: {
    accepted: "旨意受理",
    advancing: "执行推进",
    completed: "工程告成",
    effective: "效果生效",
  },
  phases: {
    accepted: [{ kind: "project", title: "海塘", route: "两浙路", note: "已立项待拨款" }],
    advancing: [
      { kind: "project", title: "海塘", route: "两浙路", progress: 40, note: "营建中" },
    ],
    completed: [],
    effective: [],
  },
  projects: [
    {
      pid: "bp:两浙路:dyn:abc",
      name: "海塘",
      route: "两浙路",
      status: "building",
      status_label: "营建中",
      progress: 40,
      capacity: 0,
      dynamic: true,
      output: {},
      runtime: {},
      effects: [],
      source_blueprint: "dyn:abc",
    },
  ],
  unsupported_tasks: [{ name: "兴修水利三年", turn: 5, reason: "无程序侧落点" }],
  counts: {},
};

describe("PlanReadoutPanel", () => {
  it("四层级各自成块（标签取自后端，不由前端自造）", () => {
    h.readouts = { plan: PLAN };
    render(<PlanReadoutPanel />);
    for (const label of ["旨意受理", "执行推进", "工程告成", "效果生效"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it("「待支持」单列，且不在「工程告成」块内", () => {
    h.readouts = { plan: PLAN };
    render(<PlanReadoutPanel />);
    expect(screen.getByText(/待支持（1）/)).toBeTruthy();
    expect(screen.getByText("兴修水利三年：无程序侧落点")).toBeTruthy();
    // 告成块必须为空（该事务**没有**告成）——取整块容器（含计数与条目列表）
    const completedBlock = screen.getByText("工程告成").closest("div.rounded");
    expect(completedBlock?.textContent).toContain("（无）");
    expect(completedBlock?.textContent).not.toContain("兴修水利三年");
  });

  it("工程台账直接显示后端下发的进度与状态", () => {
    h.readouts = { plan: PLAN };
    render(<PlanReadoutPanel />);
    expect(screen.getByText("营建中")).toBeTruthy();
    expect(screen.getByText("40%")).toBeTruthy();
    expect(screen.getByText("旨意")).toBeTruthy(); // 动态蓝图标记
  });

  it("读数缺失时如实说明，不以空白冒充「无工程」", () => {
    h.readouts = null;
    render(<PlanReadoutPanel />);
    expect(screen.getByText(/计划读数未下发/)).toBeTruthy();
    expect(screen.getByText(/不以空白冒充/)).toBeTruthy();
  });

  it("已运行工程显示产能与运行期产出（带 /月 后缀）", () => {
    h.readouts = {
      plan: {
        ...PLAN,
        projects: [
          {
            ...PLAN.projects[0],
            status: "operating",
            status_label: "运行",
            progress: 100,
            capacity: 0.75,
            output: { granary_cap_add: 50000 },
            runtime: { wine_coin_add: 20000 },
          },
        ],
      },
    };
    render(<PlanReadoutPanel />);
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByText("granary_cap_add、wine_coin_add/月")).toBeTruthy();
  });

  it("可按 route 过滤（只显示该路工程）", () => {
    h.readouts = {
      plan: {
        ...PLAN,
        projects: [
          PLAN.projects[0],
          { ...PLAN.projects[0], pid: "p2", name: "汴河堤", route: "京畿路" },
        ],
      },
    };
    render(<PlanReadoutPanel route="京畿路" />);
    expect(screen.getByText(/汴河堤/)).toBeTruthy();
    expect(screen.queryByText(/两浙路·海塘/)).toBeNull();
  });
});
