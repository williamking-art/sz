// 宋祚 · 面板截图台（**dev-only**，不进产品构建）
//   ?panel=<面板文件名>  route=<路/府名>  kind=circuit|city  w=<像素宽>
//
// 设计（2026-09-27 修正）：**只 mock 网络，不替换模块**。
//   先前用 Vite alias 把 `../api/client` 整个换成 mock → 必须穷举该模块的每个导出
//   （`AdvancePanel` 要 `subscribeRichPoll`，当场构建失败）。现改为：
//     · `window.fetch` 拦截 `/api/**` 返回 fixture —— 各面板继续用**真实 client 模块**，导出齐全；
//     · 仅 `store/gameStore` 仍由 alias 换成 mock（面板需要一个有数据的 state，别无他法）。
//   · 面板用 `import.meta.glob` 动态解析；**错误浮层**把渲染异常画进页面（截图即可见）。
import React, { Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "../../src/renderer/styles/theme.css";
import { READOUTS, STATE } from "./fixtures";
import { useGameStore } from "./storeMock";

// ⚠️ 必须排除 *.test.tsx：曾把同目录的测试一并 eager 导入，vitest 在导入期抛错
//    （"Vitest failed to access its internal state"）→ **整页空白**，9 张截图全废。
const PANELS = import.meta.glob(
  ["../../src/renderer/panels/*.tsx", "!../../src/renderer/panels/*.test.tsx"],
  { eager: true }) as
  Record<string, { default?: React.ComponentType<{ props?: Record<string, unknown> }> }>;

const q = new URLSearchParams(location.search);
const rawName = q.get("panel") ?? "LocalArchivePanel";
const name = rawName === "localarchive" ? "LocalArchivePanel"
  : rawName === "provincemilitary" ? "ProvinceMilitaryPanel" : rawName;
const route = q.get("route") ?? "两浙路";
const kind = q.get("kind") ?? "circuit";
// 页签/子视图选择（如 TodoPanel 的 `tab=secret`）——统一经 props 传给真实组件，
// 避免为截图另写一份 mock 视图（那会让截图失去"就是玩家看到的那份组件"这一价值）。
const tab = q.get("tab") ?? undefined;
// `empty=1`：清空在办事务，用于拍**空状态**（P2-1 要求核对的四场景之一）。
// 刻意改的是同一份 fixture 对象，故面板走的仍是真实分支，不是另写的示意视图。
if (q.get("empty") === "1") {
  STATE.longterm_public = [];
  STATE.longterm_secret = [];
}
const width = Number(q.get("w") ?? 920);

// ---- 网络 mock：拦 /api/**，其余原样放行 ----
const FIXTURES: Record<string, unknown> = {
  "/api/readouts": READOUTS,
  "/api/memory": { entries: [] },
  "/api/meter": { total_tokens: 0, calls: 0, by_agent: {} },
  "/api/save_slots": { slots: [] },
  "/api/ai_config": { base_url: "", model: "", has_key: false },
  "/api/military": { routes: [] }
};
const realFetch = window.fetch.bind(window);
window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  const hit = Object.keys(FIXTURES).find((k) => url.includes(k));
  if (hit) {
    return new Response(JSON.stringify(FIXTURES[hit]), {
      status: 200, headers: { "Content-Type": "application/json" }
    });
  }
  if (url.includes("/api/")) {
    // 未登记的读数端点：回空对象（面板应容错显示"—"；若崩了，错误浮层会显示出来）
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  }
  return realFetch(input as RequestInfo, init);
}) as typeof window.fetch;

const entry = PANELS[`../../src/renderer/panels/${name}.tsx`];
const Panel = entry?.default;

// 探针：直接问 store mock 要一次 state，把实况显示在页头——用于区分"mock 没数据"与"面板自身分支"。
const probe = (() => {
  try {
    const s = useGameStore((x: unknown) => (x as { state?: unknown }).state) as unknown;
    return s ? `store ok（state ${Object.keys(s as object).length} 键）` : "store 返回 state=undefined";
  } catch (e) {
    return `store 探针异常：${String((e as Error)?.message ?? e)}`;
  }
})();

class Boundary extends Component<{ children: ReactNode }, { err: string }> {
  state = { err: "" };
  static getDerivedStateFromError(e: unknown) {
    return { err: String((e as Error)?.message ?? e) };
  }
  render() {
    if (this.state.err) {
      return (
        <pre style={{ color: "#a00", whiteSpace: "pre-wrap", fontSize: 13 }}>
          【截图台】面板渲染失败：{name}{"\n"}{this.state.err}
        </pre>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <div className="min-h-screen bg-paper p-5" style={{ width }}>
    <div className="mb-3 font-kai text-[12px] text-dim">
      截图台（dev-only）· panel={name} · route={route} · kind={kind} · {probe}
    </div>
    <Boundary>
      {Panel
        ? <Panel props={{ kind, name: route, route, tab }} />
        : (
          <pre style={{ color: "#a00", fontSize: 13 }}>
            【截图台】无此面板：{name}
            {"\n"}可用：{Object.keys(PANELS).map((k) => k.split("/").pop()).join(", ")}
          </pre>
        )}
    </Boundary>
  </div>
);
