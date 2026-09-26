import { describe, expect, it } from "vitest";
import { portraitSrc } from "../portrait";

describe("portraitSrc", () => {
  it("空值返回空字符串", () => {
    expect(portraitSrc(undefined)).toBe("");
    expect(portraitSrc(null)).toBe("");
    expect(portraitSrc("")).toBe("");
    expect(portraitSrc("   ")).toBe("");
  });

  it("以 / 开头的服务端路径原样返回", () => {
    expect(portraitSrc("/api/portrait/zhao_pu.png")).toBe("/api/portrait/zhao_pu.png");
  });

  it("http/https 绝对路径原样返回", () => {
    expect(portraitSrc("https://example.com/a.png")).toBe("https://example.com/a.png");
  });

  it("相对文件名拼接到 ./portraits/", () => {
    expect(portraitSrc("general.png")).toBe("./portraits/general.png");
  });

  it("修剪首尾空白", () => {
    expect(portraitSrc("  general.png  ")).toBe("./portraits/general.png");
  });
});
