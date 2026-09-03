import { useGameStore } from "../store/gameStore";

// 回合推演结果面板：叙事报告 + 事件列表 + 日志
export default function AdvancePanel({ props }: { props?: Record<string, unknown> }) {
  const report = typeof props?.report === "string" ? props.report : "";
  const events = Array.isArray(props?.events) ? props.events : [];
  const log = Array.isArray(props?.log) ? props.log : [];
  const error = typeof props?.error === "string" ? props.error : "";
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  // 推演失败（多因未接入 AI）：显式提示，不静默
  if (error) {
    return (
      <div className="rounded-lg border border-red/40 bg-red/5 p-4">
        <p className="font-kai text-[15px] leading-relaxed text-red-dark">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
          <h3 className="mb-2 font-kai text-base tracking-widest text-red">朝报</h3>
          <ul className="space-y-1 rounded-lg bg-paper/50 p-3">
            {log.map((line, i) => (
              <li key={i} className="text-xs leading-relaxed text-ink-light">{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}