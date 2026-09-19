// 会话守卫最小自测（本机无 vitest/jsdom，用 Electron 内置 Node + tsx 直接跑）
// 用法：cd game/frontend
//       $env:ELECTRON_RUN_AS_NODE='1'
//       .\node_modules\electron\dist\electron.exe .\node_modules\tsx\dist\cli.mjs src\renderer\panels\sessionGuard.selftest.ts
// 任一断言失败即以非零退出码结束。
//
// 覆盖范围与局限：
//   - 已自动化：SessionGuard 三层隔离判定、竞态时序模拟、展示态分类、ApiClient 取消联动。
//   - 未自动化（前端无 vitest/jsdom、无测试基建）：AudienceView 的 React 接线只能手工复核。
//
// 手工复现步骤（需可运行的本地后端 + 打开 Electron 窗口）：
//   1. 打开「御前召对」，展开右侧「记忆库」，先看一位留档较多的大臣 A；
//   2. A 正在加载/刷新时立刻点名大臣 B —— 中栏应显示 B 的留档或 B 的开场白；
//      待 A 的旧回执返回后，B 的消息列不得出现 A 的内容（不串台）；
//   3. 快速 A→B→A 反复切换：中栏标题与消息列必须始终与左栏高亮大臣一致；
//   4. 停掉后端再切换大臣：中栏应出现「旧档调阅受阻 + 重新调阅」并保持该态，
//      点「重新调阅」能恢复；不得静默回落成正常空会话；
//   5. 选一位无留档的大臣：中栏应提示「本会话尚无留档，以下为开场白」；
//   6. P1-9 调拨串会话：调拨请求在途时名录本就禁用（第一道防线），
//      守卫（第二道防线）保证即便对象变更，回执也只写原会话或丢弃。
import assert from "node:assert/strict";
import {
  SessionGuard,
  isAbortError,
  classifySessionView,
  type RequestTicket
} from "./sessionGuard";
import { ApiClient } from "../api/client";

let passed = 0;
function check(name: string, fn: () => void): void {
  fn();
  passed += 1;
  console.log(`  PASS  ${name}`);
}

console.log("[1] SessionGuard 三层身份隔离");

check("同大臣同通道：最新请求 fresh", () => {
  const g = new SessionGuard();
  const t = g.issue("A", "session");
  assert.equal(g.isFresh(t, "A"), true);
});

check("切换大臣（invalidate 旧会话）后旧回执失效", () => {
  const g = new SessionGuard();
  const t = g.issue("A", "session");
  g.invalidate("A");
  assert.equal(g.isFresh(t, "A"), false);
  assert.equal(g.isFresh(t, "B"), false);
});

check("A→B→A：新纪元生效，旧纪元回执被丢弃", () => {
  const g = new SessionGuard();
  const oldTicket = g.issue("A", "session");
  g.invalidate("A"); // 离开 A
  g.invalidate("A"); // 回到 A 再作废一次，确保全新纪元
  const newTicket = g.issue("A", "session");
  assert.equal(g.isFresh(oldTicket, "A"), false);
  assert.equal(g.isFresh(newTicket, "A"), true);
});

check("同通道连续请求：旧序号被新序号取代", () => {
  const g = new SessionGuard();
  const first = g.issue("A", "sidebar");
  const second = g.issue("A", "sidebar");
  assert.equal(g.isFresh(first, "A"), false);
  assert.equal(g.isFresh(second, "A"), true);
});

check("不同用途互不抢占：侧栏刷新不吃掉在途奏对", () => {
  const g = new SessionGuard();
  const dialogue = g.issue("A", "dialogue");
  const sidebar = g.issue("A", "sidebar");
  assert.equal(g.isFresh(dialogue, "A"), true, "奏对回执不得被刷新作废");
  assert.equal(g.isFresh(sidebar, "A"), true);
});

check("对象已变：跨大臣回执一律丢弃", () => {
  const g = new SessionGuard();
  const t = g.issue("A", "transfer");
  assert.equal(g.isFresh(t, "B"), false);
});

check("凭据身份在 issue 时冻结", () => {
  const g = new SessionGuard();
  g.invalidate("A");
  const t: RequestTicket = g.issue("A", "dialogue");
  assert.deepEqual(
    { minister: t.minister, purpose: t.purpose, epoch: t.epoch },
    { minister: "A", purpose: "dialogue", epoch: 1 }
  );
});

console.log("[2] 竞态时序模拟（旧请求后到，不得覆盖新会话）");

async function simulateRace(): Promise<string> {
  const g = new SessionGuard();
  let current = "A";
  let rendered = "";

  // A 的会话加载（慢）在途
  const aTicket = g.issue("A", "session");
  // 玩家快速切到 B：作废 A 并清空私有数据
  g.invalidate("A");
  rendered = "";
  current = "B";
  const bTicket = g.issue("B", "session");

  // B 回执先到 → 写入 B
  await Promise.resolve("B 的留档").then((v) => {
    if (g.isFresh(bTicket, current)) rendered = v;
  });
  // A 回执后到 → 必须被丢弃
  await Promise.resolve("A 的留档").then((v) => {
    if (g.isFresh(aTicket, current)) rendered = v;
  });
  return rendered;
}

console.log("[3] 展示态分类（loading / error / empty / ready）");

check("加载中", () => {
  assert.equal(classifySessionView({ phase: "loading", archivedCount: 0 }), "loading");
});
check("失败优先于空档", () => {
  assert.equal(classifySessionView({ phase: "error", archivedCount: 0 }), "error");
  assert.equal(classifySessionView({ phase: "error", archivedCount: 5 }), "error");
});
check("拉取成功但无留档 → empty（区别于 error/loading）", () => {
  assert.equal(classifySessionView({ phase: "ready", archivedCount: 0 }), "empty");
});
check("拉取成功且有留档 → ready", () => {
  assert.equal(classifySessionView({ phase: "ready", archivedCount: 3 }), "ready");
});

console.log("[4] 取消错误识别");

check("AbortError 识别", () => {
  const e = new Error("aborted");
  e.name = "AbortError";
  assert.equal(isAbortError(e), true);
  assert.equal(isAbortError(new Error("boom")), false);
  assert.equal(isAbortError(null), false);
  assert.equal(isAbortError(undefined), false);
  assert.equal(isAbortError("AbortError"), false);
});

console.log("[5] ApiClient 取消信号联动（AbortController 真正中断在途拉取）");

async function testAbortPlumbing(): Promise<void> {
  const g = globalThis as unknown as {
    window?: unknown;
    fetch?: unknown;
  } & Record<string, unknown>;
  const prevWindow = g.window;
  const prevFetch = g.fetch;
  try {
    g.window = {
      setTimeout: (fn: () => void, ms: number) => setTimeout(fn, ms),
      clearTimeout: (id: unknown) => clearTimeout(id as ReturnType<typeof setTimeout>)
    };
    let captured: AbortSignal | null = null;
    g.fetch = (_url: string, init: { signal?: AbortSignal }) =>
      new Promise((_resolve, reject) => {
        captured = init.signal ?? null;
        init.signal?.addEventListener("abort", () => {
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        });
      });

    const client = new ApiClient("http://127.0.0.1:0");
    const ctrl = new AbortController();
    const pending = client.memory("甲", { signal: ctrl.signal });
    ctrl.abort();

    let seen = "(resolved)";
    await pending.then(
      () => {
        seen = "(resolved)";
      },
      (e: unknown) => {
        seen = isAbortError(e) ? "AbortError" : `(other: ${String(e)})`;
      }
    );
    assert.equal(seen, "AbortError", "调用方取消应原样上抛 AbortError，不得译成超时文案");
    assert.ok(captured, "fetch 必须被调用且携带 signal");
    const sig = captured as unknown as AbortSignal;
    assert.equal(sig.aborted, true, "外部 abort 应联动内部 controller");
  } finally {
    g.window = prevWindow;
    g.fetch = prevFetch;
  }
}

async function main(): Promise<void> {
  const rendered = await simulateRace();
  assert.equal(rendered, "B 的留档");
  passed += 1;
  console.log("  PASS  旧会话回执不覆盖新会话消息列（异步时序）");

  await testAbortPlumbing();
  passed += 1;
  console.log("  PASS  切换会话 abort 真正中断在途请求（AbortError 原样上抛）");

  console.log(`\nALL PASS (${passed} checks)`);
}

main().catch((e) => {
  console.error("SELFTEST FAILED:", e);
  process.exit(1);
});