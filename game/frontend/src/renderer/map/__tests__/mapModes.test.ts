import { describe, expect, it } from "vitest";
import { MAP_MODES } from "../MapModesControl";
import { getCircuitFillExpression, THEME } from "../layers";

describe("MapModes & Layer Palette", () => {
  it("舆图四态完整定义：包含政区、物候、民怨、边备四种模式", () => {
    expect(MAP_MODES).toHaveLength(4);
    const ids = MAP_MODES.map((m) => m.id);
    expect(ids).toEqual(["political", "climate", "unrest", "military"]);
  });

  it("政区态（中原疆宇）：京畿路与沿边路正确分类着色", () => {
    const expr = getCircuitFillExpression("political");
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("match");
    // 包含京畿色
    expect(expr).toContain(THEME.cJijing);
    expect(expr).toContain(THEME.cYanbian);
    expect(expr).toContain(THEME.cFuli);
  });

  it("物候态（九州物候）：江南鱼米诸路呈现丰稔青碧", () => {
    const expr = getCircuitFillExpression("climate");
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("match");
    // 丰稔青碧色
    expect(expr).toContain("#a4c297");
  });

  it("民怨态（海内生计）：高危民怨池呈现朱砂赤红色警戒", () => {
    const mockState = {
      statistics: {
        organic_unrest_pool: {
          两浙路: 85.0,
          京东东路: 45.0,
          成都府路: 10.0,
        },
      },
    };
    const expr = getCircuitFillExpression("unrest", mockState);
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("match");
    // 严重警戒色
    expect(expr).toContain("#b83a2c");
    // 中度警戒色
    expect(expr).toContain("#dca156");
  });

  it("边备态（关防烽燧）：沿边帅司呈现金铜军防色", () => {
    const expr = getCircuitFillExpression("military");
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("match");
    expect(expr).toContain("#bd8f46");
    expect(expr).toContain("#7fa89f");
  });

  it("民怨池为空/缺失时不得伪造警戒色（缺失≠0≠危机）", () => {
    for (const state of [undefined, { statistics: {} }, { statistics: { organic_unrest_pool: {} } }]) {
      const expr = getCircuitFillExpression("unrest", state);
      expect(expr).toBe("#e9e5d4");
      expect(expr).not.toContain("#b83a2c");
      expect(expr).not.toContain("#dca156");
    }
  });

  it("民怨池含非数值项时跳过该项，不按 0 分级", () => {
    const expr = getCircuitFillExpression("unrest", {
      statistics: { organic_unrest_pool: { 两浙路: "not-a-number" } },
    });
    expect(expr).toBe("#e9e5d4");
  });
});
