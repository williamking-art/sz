import { describe, expect, it } from "vitest";
import { formatEra, group, humanizeCoin, seasonName, statusColor, wan } from "../format";

describe("format utils", () => {
  describe("group", () => {
    it("整数千分位", () => {
      expect(group(0)).toBe("0");
      expect(group(1000)).toBe("1,000");
      expect(group(1234567)).toBe("1,234,567");
      expect(group(-1234)).toBe("-1,234");
    });

    it("四舍五入到整数", () => {
      expect(group(1234.4)).toBe("1,234");
      expect(group(1234.6)).toBe("1,235");
    });
  });

  describe("wan", () => {
    it("非法值返回 em dash", () => {
      expect(wan(null)).toBe("—");
      expect(wan(undefined)).toBe("—");
      expect(wan(NaN)).toBe("—");
    });

    it("小于 1 万显示真实数千分位", () => {
      expect(wan(0)).toBe("0");
      expect(wan(500)).toBe("500");
      expect(wan(9999)).toBe("9,999");
      expect(wan(-500)).toBe("-500");
    });

    it("大于等于 1 万以万为单位", () => {
      expect(wan(10000)).toBe("1万");
      expect(wan(12345)).toBe("1.2万");
      expect(wan(123400)).toBe("12.3万");
      expect(wan(1234000)).toBe("123万");
      expect(wan(123450000)).toBe("12345万");
      expect(wan(-12345)).toBe("-1.2万");
    });

    it("可附加单位", () => {
      expect(wan(12345, "贯")).toBe("1.2万贯");
    });
  });

  describe("humanizeCoin", () => {
    it("货币以贯为单位", () => {
      expect(humanizeCoin(12345)).toBe("1.2万贯");
      expect(humanizeCoin(null)).toBe("0贯");
    });
  });

  describe("seasonName", () => {
    it("12/1/2 为冬，3/4/5 为春，6/7/8 为夏，其余为秋", () => {
      expect(seasonName(1)).toBe("冬");
      expect(seasonName(12)).toBe("冬");
      expect(seasonName(4)).toBe("春");
      expect(seasonName(7)).toBe("夏");
      expect(seasonName(9)).toBe("秋");
    });
  });

  describe("formatEra", () => {
    it("拼接古意纪年", () => {
      expect(formatEra("建中靖国", 1, 1)).toBe("建中靖国1年·冬·1月朔日");
      expect(formatEra("政和", 5, 6)).toBe("政和5年·夏·6月朔日");
    });
  });

  describe("statusColor", () => {
    it("按阈值返回状态色", () => {
      expect(statusColor(80)).toBe("#5a7a3c");
      expect(statusColor(65)).toBe("#5a7a3c");
      expect(statusColor(60)).toBe("#8f6e28");
      expect(statusColor(55)).toBe("#8f6e28");
      expect(statusColor(50)).toBe("#caa24a");
      expect(statusColor(45)).toBe("#caa24a");
      expect(statusColor(30)).toBe("#8a2b22");
    });
  });
});
