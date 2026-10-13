import { describe, expect, it } from "vitest";

import { hubRowText } from "../ReadoutHubPanel";

// P5 第一片（M84）：统一读数索引面板的**唯一展示映射点**。
// 🔴 契约（前端 AGENTS.md 禁区 + 根 §3-3）：**缺失一律显式呈现「未定义」，不得回落 0**。
describe("ReadoutHubPanel.hubRowText", () => {
  it("有值 ⇒ 原样透传后端给的值字符串（不重算）", () => {
    expect(hubRowText({ display: "1850540" })).toBe("1850540");
    expect(hubRowText({ display: "capacity_shortage" })).toBe("capacity_shortage");
  });

  it("不可读（后端 display===\"undefined\"）⇒ 显示「未定义」，绝不显示 0", () => {
    const t = hubRowText({ display: "undefined" });
    expect(t).toBe("未定义");
    expect(t).not.toBe("0");
  });

  it("值为 0 时**照实显示 0**（真 0 与缺失必须区分）", () => {
    expect(hubRowText({ display: "0" })).toBe("0");
  });
});
