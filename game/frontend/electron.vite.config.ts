import { resolve } from "path";
import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: "out/main",
      lib: { entry: "src/main/index.ts" }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: "out/preload",
      lib: { entry: "src/preload/index.ts" }
    }
  },
  renderer: {
    root: "src/renderer",
    publicDir: resolve(__dirname, "public"),
    plugins: [react()],
    resolve: {
      alias: {
        "@": resolve(__dirname, "src/renderer")
      }
    },
    build: {
      outDir: "out/renderer",
      rollupOptions: {
        input: resolve(__dirname, "src/renderer/index.html")
      }
    },
    server: {
      // P2-34：禁止 0.0.0.0（局域网可访问 dev 渲染层）；仅本机回环
      host: "127.0.0.1",
      allowedHosts: ["localhost", "127.0.0.1"]
    }
  }
});