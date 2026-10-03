import { resolve } from "path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src/renderer"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["src/renderer/**/*.{test,spec}.{ts,tsx}"],
    // 2026-10-01（DSH 全审批次 9 期间实测）：本机（Windows 沙箱）用默认 **forks**（子进程）
    // 池跑全量时，worker 会被系统杀掉 → `ERR_IPC_CHANNEL_CLOSED` / "Worker exited unexpectedly"，
    // 表现为「Test Files 8→6→5→3 随机变少、Errors 2~3 个」，但**逐个文件单跑全部通过**
    // （8 文件 / 66 例），且与断言无关。改用 **threads** 池后稳定 8/8、66/66、零 error。
    // 仅影响测试运行器，不改任何测试语义与被测代码；若换到资源更充足的环境可去掉。
    pool: "threads",
    deps: {
      // 避免 react 等 ESM 包在 vitest 2.x 下的重复实例问题
      optimizer: {
        web: {
          include: ["react", "react-dom", "react/jsx-runtime"],
        },
      },
    },
  },
});
