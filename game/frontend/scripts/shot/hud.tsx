// 宋祚 · HUD 截图台（**dev-only**，不进产品构建）
//   ?empty=1 清空在办事务（拍"事务空状态"场景）
//
// 为什么需要它（P2-1）：审查任务书要求核对"底部横向功能栏 / 右侧纵向入口 / 顶部资源状态 /
// 左上事务面板"在**常见窗口尺寸与较小窗口**下的占位、可读性、遮挡与操作密度，
// 而 `panel.html` 只渲染单个面板、不含 HUD。此处把四个 HUD 组件按真实层级叠在一张
// "舆图占位"上，用不同 `--window-size` 截图即可验证"是否被裁/是否互相遮挡"。
//
// 刻意**不渲染 maplibre**：截图台无 WebGL 保证（地图几何另有
// `_dev_tools/game-dev/tests/test_map_prefecture_geometry.py` 做数据级回归）。
import { createRoot } from "react-dom/client";
import "../../src/renderer/styles/theme.css";
import { STATE } from "./fixtures";
import TopBar from "../../src/renderer/hud/TopBar";
import LeftTodo from "../../src/renderer/hud/LeftTodo";
import RightStrip from "../../src/renderer/hud/RightStrip";
import Dock from "../../src/renderer/hud/Dock";

const q = new URLSearchParams(location.search);
if (q.get("empty") === "1") {
  STATE.longterm_public = [];
  STATE.longterm_secret = [];
}

function Hud() {
  // ⚠️ 外壳**必须用内联样式**：Tailwind 的 content 只扫 `src/**`（截图台刻意不进产品构建），
  //    故 `h-screen/w-screen/overflow-hidden` 这类只出现在本文件的类**不会被生成** →
  //    根 div 高度塌成 0，`overflow-hidden` 再把绝对定位的 HUD 全裁掉，截图只剩一片底色
  //    （2026-09-27 实测：首版即如此，3304 字节的纯色 PNG）。HUD 组件自身的类在 src/ 内，正常生成。
  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden", background: "#cfd9c8" }}>
      {/* 舆图占位（仅用于看清 HUD 的占位与遮挡关系） */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "repeating-linear-gradient(0deg, rgba(90,74,58,.06) 0 1px, transparent 1px 48px)," +
            "repeating-linear-gradient(90deg, rgba(90,74,58,.06) 0 1px, transparent 1px 48px)," +
            "radial-gradient(120% 90% at 50% 40%, #e9e2cc 0%, #cfd9c8 100%)"
        }}
      />
      <p
        style={{
          position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)",
          fontFamily: "var(--font-kai, serif)", fontSize: 15, letterSpacing: "0.2em",
          color: "rgba(43,29,18,.35)"
        }}
      >
        舆图占位（HUD 占位核对用）
      </p>
      <TopBar />
      <LeftTodo />
      <RightStrip />
      <Dock />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<Hud />);
