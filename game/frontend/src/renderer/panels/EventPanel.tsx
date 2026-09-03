import { useState } from "react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 事件抉择弹窗：展示事件描述与选项，选择后 resolve_event
export default function EventPanel({ props }: { props?: Record<string, unknown> }) {
  const event = props?.event as Record<string, unknown> | undefined;
  const title = typeof props?.title === "string" ? props.title : String(event?.title ?? "事件");
  const desc = typeof event?.desc === "string" ? event.desc : String(event?.description ?? "");
  const choices = Array.isArray(event?.choices)
    ? (event.choices as Array<Record<string, unknown>>)
    : Array.isArray(event?.options)
      ? (event.options as Array<Record<string, unknown>>)
      : [];

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);
  const popOverlay = useGameStore((s) => s.popOverlay);

  async function choose(idx: number) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await getApiClient().resolveEvent(title, idx);
      setState(res.state);
      setResult(res.message);
    } catch (e) {
      console.error("[resolve_event]", e);
      setResult("抉择处理失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{desc}</p>

      {!result && (
        <div className="space-y-2">
          {choices.map((c, i) => (
            <button
              key={i}
              onClick={() => choose(i)}
              disabled={busy}
              className="w-full rounded-lg border border-gold/50 bg-paper/60 px-4 py-2.5 text-left text-sm text-ink transition hover:bg-gold-light disabled:opacity-60"
            >
              {String(c.label ?? c.text ?? c.option ?? `选项 ${i + 1}`)}
            </button>
          ))}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{result}</p>
          <button
            onClick={popOverlay}
            className="mt-3 rounded-lg bg-red px-4 py-1.5 text-sm text-paper transition hover:bg-red-dark"
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
}