// 面板截图台的独立 Vite 配置（**不动产品构建**：electron.vite.config.ts 只打 src/{main,preload,renderer}）。
// 关键：把面板里的相对导入 `../api/client`、`../store/gameStore` 别名到截图台的 mock，
// 这样无需 Python 后端、无需打包 exe、无需在产品里加任何 dev 钩子。
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
      { find: /^\.\.\/store\/gameStore$/, replacement: resolve(__dirname, "scripts/shot/storeMock.ts") },
    ],
  },
  build: {
    outDir: resolve(__dirname, "_shot-dist"),
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, "scripts/shot/panel.html") },
  },
});
