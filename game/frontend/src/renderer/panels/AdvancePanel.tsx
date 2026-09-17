import { useEffect, useState } from "react";
import { useGameStore } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";

// 回合推演结果面板：本月损益（▲▼）+ 叙事报告 + 事件 + 朝报（逐行揭示，可跳过）
// 迁移补齐：对齐 Tk game/ui/panels_meta.py::_settle_show——
//   ① 结算前后关键指标快照对比（本 Tk 三件套之一）；
//   ② 朝报 220ms 逐行揭示；③ 「跳过演出」/空格键立即全显。
export default function AdvancePanel({ props }: { props?: Record<string, unknown> }) {
  const report = typeof props?.report === "string" ? props.report : "";
  const events = Array.isArray(props?.events) ? props.events : [];
  const log = Array.isArray(props?.log) ? (props.log as string[]) : [];
  const error = typeof props?.error === "string" ? props.error : "";
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  const before = (props?.before ?? null) as Record<string, number> | null;
  const after = (props?.after ?? null) as Record<string, number> | null;

  // 逐行揭示（220ms/行；跳过/空格立即全显）
  const [revealed, setRevealed] = useState(log.length > 0 ? 1 : 0);
  const [skipped, setSkipped] = useState(false);

  useEffect(() => {
    if (skipped || revealed >= log.length) return;
    const t = window.setTimeout(() => setRevealed((n) => Math.min(n + 1, log.length)), 220);
    return () => window.clearTimeout(t);
  }, [revealed, skipped, log.length]);

  useEffect(() => {
    if (skipped) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space" || e.key === " ") {
        e.preventDefault();
        setSkipped(true);
        setRevealed(log.length);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [skipped, log.length]);

  // 推演失败（多因未接入 AI）：显式提示，不静默
  if (error) {
    return (
      <div className="rounded-lg border border-red/40 bg-red/5 p-4">
        <p className="font-kai text-[15px] leading-relaxed text-red-dark">{error}</p>
      </div>
    );
  }

  const deltas =
    before && after
      ? [
          { label: "国库", v: (after.treasury ?? 0) - (before.treasury ?? 0), coin: true },
          { label: "内帑", v: (after.imperial_treasury ?? 0) - (before.imperial_treasury ?? 0), coin: true },
          { label: "民心", v: (after.population_satisfaction ?? 0) - (before.population_satisfaction ?? 0), coin: false },
          { label: "皇威", v: (after.prestige ?? 0) - (before.prestige ?? 0), coin: false }
        ]
      : [];

  return (
    <div className="space-y-4">
      {deltas.length > 0 && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="font-kai text-sm font-bold tracking-widest text-red">本 月 损 益</p>
          <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {deltas.map((d) => {
              const up = d.v > 0;
              const flat = d.v === 0;
              const tone = flat ? "text-dim" : up ? "text-emerald-700" : "text-red";
              const mark = flat ? "—" : up ? "▲" : "▼";
              return (
                <div key={d.label} className="rounded border border-gold/30 bg-card p-2 text-center">
                  <p className="text-xs text-dim">{d.label}</p>
                  <p className={`mt-0.5 font-sans text-sm font-bold ${tone}`}>
                    {mark} {flat ? "持平" : d.coin ? humanizeCoin(Math.abs(d.v)) : Math.abs(d.v).toFixed(0)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {report && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <p className="whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">{report}</p>
        </div>
      )}

      {events.length > 0 && (
        <div>
          <h3 className="mb-2 font-kai text-base tracking-widest text-red">事件</h3>
          <ul className="space-y-2">
            {events.map((ev, i) => {
              const title = typeof ev === "string" ? ev : String((ev as Record<string, unknown>)?.title ?? "");
              return (
                <li key={i}>
                  <button
                    onClick={() => pushOverlay({ kind: "event", title, props: { event: ev } })}
                    className="w-full rounded-lg border border-gold/40 bg-card px-3 py-2 text-left text-sm text-ink transition hover:bg-gold-light"
                  >
                    {title}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {log.length > 0 && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-kai text-base tracking-widest text-red">朝报</h3>
            {revealed < log.length && !skipped && (
              <button
                onClick={() => {
                  setSkipped(true);
                  setRevealed(log.length);
                }}
                className="rounded border border-gold/50 bg-paper/70 px-2 py-0.5 font-kai text-xs text-ink transition hover:bg-gold-light/40"
              >
                跳过演出 ␣
              </button>
            )}
          </div>
          <ul className="space-y-1 rounded-lg bg-paper/50 p-3">
            {log.slice(0, revealed).map((line, i) => (
              <li key={i} className="text-xs leading-relaxed text-ink-light">{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
