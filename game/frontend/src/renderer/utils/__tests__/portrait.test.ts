import { afterEach, describe, expect, it } from "vitest";
import { portraitSrc, setPortraitBase } from "../portrait";

describe("portraitSrc（未注入后端 base 时：保持原行为）", () => {
  afterEach(() => setPortraitBase(""));

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

describe("portraitSrc（注入后端 base 后：app:// 打包态相对路径会落到应用源 → 必须拼绝对 URL）", () => {
  afterEach(() => setPortraitBase("")); // 用例间隔离

  it("受控路由拼成后端绝对 URL", () => {
    setPortraitBase("http://127.0.0.1:8080");
    expect(portraitSrc("/api/portrait/zhao_pu.png")).toBe(
      "http://127.0.0.1:8080/api/portrait/zhao_pu.png",
    );
  });

  it("base 末尾斜杠会被规整", () => {
    setPortraitBase("http://127.0.0.1:8080/");
    expect(portraitSrc("/api/portrait/a.png")).toBe(
      "http://127.0.0.1:8080/api/portrait/a.png",
    );
  });

  it("绝对 URL 不受 base 影响", () => {
    setPortraitBase("http://127.0.0.1:8080");
    expect(portraitSrc("https://cdn.example.com/a.png")).toBe("https://cdn.example.com/a.png");
  });

  it("前端静态资产仍走 ./portraits/", () => {
    setPortraitBase("http://127.0.0.1:8080");
    expect(portraitSrc("general.png")).toBe("./portraits/general.png");
  });

  it("清空 base 后回到原行为", () => {
    setPortraitBase("http://127.0.0.1:8080");
    setPortraitBase("");
    expect(portraitSrc("/api/portrait/a.png")).toBe("/api/portrait/a.png");
  });
});
