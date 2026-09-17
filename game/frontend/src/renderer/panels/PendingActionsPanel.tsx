import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Loader2, ScrollText, Swords, Landmark } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";

// AI 待批行动队列 —— 对齐 core/commands.approve_ai_action / reject_ai_action
// 严格模式：AI 只有提议权，批红前不落地（密令/施政/军令）

type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

const KIND_META: Record<string, { label: string; icon: React.ReactNode; tone: string }> = {
  secret_order: {
    label: "密令",
    icon: <ScrollText size={14} />,
    tone: "border-red/40 bg-red/5 text-red-dark",
  },
  propose_governance: {
    label: "施政条陈",
    icon: <Landmark size={14} />,
    tone: "border-goldDark/50 bg-gold-light/40 text-ink",
  },
  military_dispatch: {
    label: "军令",
    icon: <Swords size={14} />,
    tone: "border-emerald-600/40 bg-emerald-500/10 text-emerald-800",
  },
};

export default function PendingActionsPanel() {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const all = asArr(pick(state, "ai_pending_actions", []));
  const pending = all.filter((a) => asDict(a).status === "pending");
  const handled = all
    .filter((a) => asDict(a).status !== "pending")
    .slice()
    .reverse()
    .slice(0, 12);

  useEffect(() => {
    if (!msg) return;
    const t = window.setTimeout(() => setMsg(null), 4000);
    return () => window.clearTimeout(t);
  }, [msg]);

  async function decide(actionId: string, approve: boolean) {
    if (busyId) return;
    setBusyId(actionId);
    setError(null);
    try {
      const res = await getApiClient().action(
        approve ? "approve_ai_action" : "reject_ai_action",
        { action_id: actionId },
      );
      if (res.state) setState(res.state);
      setMsg(res.message || (approve ? "已批红" : "已驳回"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <span className="font-kai text-sm font-bold tracking-widest text-red">
          朱 批 待 阅
        </span>
        <span className="font-kai text-xs text-dim">
          AI 仅有提议权 · 批红前不落地 · 待批 {pending.length} 件
        </span>
      </div>

      {msg && (
        <p className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 font-kai text-sm text-emerald-800">
          {msg}
        </p>
      )}
      {error && (
        <p className="rounded border border-red/40 bg-red/10 px-3 py-2 font-kai text-sm text-red-dark">
          {error}
        </p>
      )}

      {pending.length === 0 ? (
        <div className="flex flex-col items-center py-8">
          <img src="/images/empty_scroll.jpg" alt="" className="sz-empty-art" />
          <p className="mt-3 font-kai text-sm text-dim">
            — 枢密拟呈暂无待批条目 —
          </p>
          <p className="mt-1 font-kai text-xs text-dim/80">
            召对中大臣所拟密令 / 施政 / 军令将汇于此，俟陛下朱批
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((raw) => {
            const a = asDict(raw);
            const kind = asStr(a.kind, "");
            const meta = KIND_META[kind] ?? {
              label: kind || "条陈",
              icon: <ScrollText size={14} />,
              tone: "border-gold/40 bg-paper text-ink",
            };
            const id = asStr(a.id);
            const payload = asDict(a.payload);
            return (
              <div
                key={id}
                className={`rounded-lg border p-3 shadow-paper ${meta.tone}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {meta.icon}
                    <span className="font-kai text-sm font-bold">{meta.label}</span>
                    <span className="font-kai text-[13px] font-bold text-ink">
                      「{asStr(a.title, "无题")}」
                    </span>
                  </div>
                  <span className="shrink-0 font-sans text-[11px] text-dim">
                    {asStr(a.proposer, "枢密")} · 回合 {String(a.turn ?? "—")}
                  </span>
                </div>
                <p className="mt-1.5 font-kai text-xs leading-relaxed text-ink-light">
                  {asStr(a.summary, "（无详述）")}
                </p>
                {kind === "military_dispatch" && (
                  <p className="mt-1 font-sans text-[11px] text-dim">
                    军籍 {asStr(payload.army)} · 动作 {asStr(payload.action)}
                    {payload.target ? ` · 赴 ${asStr(payload.target)}` : ""} · 档{" "}
                    {String(payload.scale ?? 3)}
                  </p>
                )}
                {kind === "secret_order" && payload.longterm === true && (
                  <p className="mt-1 font-sans text-[11px] text-dim">长期在办密令</p>
                )}
                <div className="mt-2.5 flex justify-end gap-2">
                  <button
                    onClick={() => decide(id, false)}
                    disabled={busyId === id}
                    className="sz-btn-ghost flex items-center gap-1 rounded px-3 py-1 text-xs disabled:opacity-50"
                  >
                    {busyId === id ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <XCircle size={13} />
                    )}
                    驳 回
                  </button>
                  <button
                    onClick={() => decide(id, true)}
                    disabled={busyId === id}
                    className="sz-btn-primary flex items-center gap-1 rounded px-4 py-1 text-xs font-bold disabled:opacity-50"
                  >
                    {busyId === id ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <CheckCircle2 size={13} />
                    )}
                    批 红
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {handled.length > 0 && (
        <div className="border-t border-gold/30 pt-3">
          <p className="mb-2 font-kai text-xs font-bold tracking-widest text-dim">
            近 期 已 处
          </p>
          <div className="space-y-1">
            {handled.map((raw) => {
              const a = asDict(raw);
              const ok = asStr(a.status) === "approved";
              return (
                <p
                  key={asStr(a.id)}
                  className="font-kai text-xs text-ink-light"
                >
                  <span className={ok ? "text-emerald-700" : "text-dim"}>
                    {ok ? "准" : "驳"}
                  </span>
                  　{asStr(a.title)}　<span className="text-dim">{asStr(a.proposer)}</span>
                </p>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
