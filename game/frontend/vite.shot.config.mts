// 面板截图台的独立 Vite 配置（**不动产品构建**：electron.vite.config.ts 只打 src/{main,preload,renderer}）。
//
// 只 mock 两个模块，且 mock 都**转发真实导出**（见 scripts/shot/apiMock.ts 的踩坑记录）。
// ⚠️ 教训：整体替换一个模块等于承诺穷举它的全部导出——`AdvancePanel` 要 `subscribeRichPoll`，
//    当年用「只含 getApiClient 的 mock」时构建当场失败；不换模块只拦 fetch 又因真实 client 构造抛错而崩面板。
import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: __dirname,
  base: "./",
  publicDir: false,   // 截图台只需面板自身，勿整拷 public/（约 30 MB 舆图与立绘）
  plugins: [react()],
  resolve: {
    alias: [
      { find: /^\.\.\/api\/client$/, replacement: resolve(__dirname, "scripts/shot/apiMock.ts") },
      // 两种写法都覆盖（面板用相对路径；若有 `@/` 别名导入也一并命中）
      { find: /^\.\.\/store\/gameStore$/, replacement: resolve(__dirname, "scripts/shot/storeMock.ts") },
      { find: /^@\/store\/gameStore$/, replacement: resolve(__dirname, "scripts/shot/storeMock.ts") },
    ],
  },
  build: {
    outDir: resolve(__dirname, "_shot-dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        panel: resolve(__dirname, "scripts/shot/panel.html"),
        // P2-1：HUD 四区（顶部资源条/左上在办/右侧入口/底部功能栏）叠在舆图占位上，
        // 用不同 --window-size 截图核对窄窗裁切与小窗遮挡。
        hud: resolve(__dirname, "scripts/shot/hud.html"),
      },
    },
  },
});
