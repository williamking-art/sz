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
