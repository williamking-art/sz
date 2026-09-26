import { describe, expect, it } from "vitest";
import { effectDeltaSign, formatEffects, judgeEffects } from "../effects";

describe("effect utils", () => {
  describe("effectDeltaSign", () => {
    it("数值正负", () => {
      expect(effectDeltaSign(5)).toBe(1);
      expect(effectDeltaSign(-3)).toBe(-1);
      expect(effectDeltaSign(0)).toBe(0);
    });

    it("字符串按减义词判定", () => {
      expect(effectDeltaSign("大减")).toBe(-1);
      expect(effectDeltaSign("停罢")).toBe(-1);
      expect(effectDeltaSign("增益")).toBe(1);
    });

    it("其他类型为中性", () => {
      expect(effectDeltaSign(null)).toBe(0);
      expect(effectDeltaSign(undefined)).toBe(0);
      expect(effectDeltaSign({})).toBe(0);
    });
  });

  describe("formatEffects", () => {
    it("空/非法值返回占位", () => {
      expect(formatEffects(null)).toBe("（无显著影响）");
      expect(formatEffects(undefined)).toBe("（无显著影响）");
      expect(formatEffects({})).toBe("（无显著影响）");
    });

    it("注册数值键带正负号", () => {
      expect(formatEffects({ prestige: 5, army: -10 })).toBe("皇威+5，军力-10");
    });

    it("布尔值显示行止", () => {
      expect(formatEffects({ exam_talent: true, single_whip: false })).toBe("科举得才行，役法止");
    });

    it("工商征率转百分比", () => {
      expect(formatEffects({ commerce_tax: 0.15 })).toBe("工商征率15%");
    });

    it("国库/内帑以万贯格式化", () => {
      expect(formatEffects({ treasury: 12345 })).toBe("国帑(贯)+1.2万贯");
      expect(formatEffects({ imperial_treasury: -5000 })).toBe("内帑(贯)-5,000贯");
    });

    it("派系变化嵌套展开", () => {
      expect(formatEffects({ faction_change: { 旧党: 2, 新党: -1 } })).toBe("旧党+2，新党-1");
    });

    it("跳过未注册键与内部指令键", () => {
      expect(formatEffects({ prestige: 5, zz_unknown_key: 1, _confirm_break: true })).toBe("皇威+5");
    });

    it("corruption 隐藏维度不应出现在效果预览", () => {
      expect(formatEffects({ prestige: 3, corruption: 5 })).toBe("皇威+3");
    });
  });

  describe("judgeEffects", () => {
    it("统计增益减益条目数", () => {
      expect(judgeEffects({ prestige: 5, army: -10 })).toEqual({ good: 1, bad: 1 });
    });

    it("派系变化参与统计", () => {
      expect(judgeEffects({ faction_change: { 旧党: 2, 新党: -1 }, treasury: 0 })).toEqual({
        good: 1,
        bad: 1,
      });
    });

    it("非法值返回零", () => {
      expect(judgeEffects(null)).toEqual({ good: 0, bad: 0 });
    });
  });
});
