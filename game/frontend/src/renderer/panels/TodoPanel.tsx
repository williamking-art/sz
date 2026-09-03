import { useState } from "react";
import { useGameStore, pick } from "../store/gameStore";

// 在办事务 —— 对齐 game/ui/panels_govern.py::_panel_todo（L1583）
// 只读展示：Tk 版页签切换为纯 UI 无后端调用（待后端暴露 action 后可做催办/撤办）。
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

export default function TodoPanel() {
  const state = useGameStore((s) => s.state);
  const [tab, setTab] = useState<"public" | "secret">("public");

  const issues = pick<Dict[]>(state, tab === "public" ? "longterm_public" : "longterm_secret", []);

  return (
    <div className="space-y-4">
      {/* 页签 */}
      <div className="flex gap-2">
        {([["public", "公 开 事 务"], ["secret", "密 令"]] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-lg px-4 py-1.5 font-kai text-sm tracking-widest transition ${
              tab === key ? "bg-red text-paper" : "bg-paper/60 text-red hover:bg-gold-light"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 条目 */}
      {issues.length === 0 ? (
        <p className="py-8 text-center font-kai text-base text-dim">
          — 暂无在办{tab === "public" ? "公开事务" : "密令"} —
        </p>
      ) : (
        <div className="space-y-2.5">
          {issues.map((t, i) => {
            const title = asStr(t.task_name ?? t.title, "事务");
            const progress = Math.round(asNum(t.progress));
            const minister = asStr(t.minister, "—");
            const lastLog = asStr(t.last_log);
            return (
              <div
                key={i}
                className={`rounded-lg border bg-paper/60 p-3 ${
                  tab === "secret" ? "border-[#6b4e16]" : "border-gold/40"
                }`}
              >
                <p className="font-kai text-[15px] font-bold text-ink">{title}</p>
                <div className="mt-1.5 h-2.5 overflow-hidden rounded-full border border-gold/50 bg-[#e0d3b3]">
                  <div className="h-full rounded-full bg-red transition-all" style={{ width: `${progress}%` }} />
                </div>
                <p className="mt-1.5 text-xs text-dim">
                  承办：{minister}　　进度 {progress}%
                </p>
                {lastLog && (
                  <p className="mt-1 text-xs leading-relaxed text-ink-light">{lastLog}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
