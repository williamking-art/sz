import { useEffect, useState } from "react";
import { Scroll, Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 新朝开局：难度择定 → POST /api/new_game
// 难度键与 game/content/data.py::DIFFICULTY_PRESETS 一致
const DIFFICULTIES: { key: string; label: string; desc: string }[] = [
  { key: "史实", label: "史实", desc: "依宋徽宗朝旧例，外患渐起，人事如常。" },
  { key: "轻松", label: "轻松", desc: "事件压力减半，民心易附，宜初习朝政。" },
  { key: "艰难", label: "艰难", desc: "内忧外患交迫，金人崛起更速，宜老手。" }
];

export default function StartPanel() {
  const [diff, setDiff] = useState("史实");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);
  const popOverlay = useGameStore((s) => s.popOverlay);
  const backendReady = useGameStore((s) => s.backendReady);

  // 后端未就绪时轮询等待，就绪后自动可开局
  useEffect(() => {
    if (!backendReady) setErr(null);
  }, [backendReady]);

  async function start() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await getApiClient().newGame(diff);
      setState(res.state);
      popOverlay();
    } catch (e) {
      console.error("[new_game]", e);
      setErr("开局失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-lg border border-gold/50 bg-paper/60 p-4">
        <Scroll size={28} className="shrink-0 text-red" />
        <div>
          <div className="font-kai text-lg tracking-widest text-ink">新朝开局</div>
          <p className="mt-0.5 text-xs leading-relaxed text-dim">
            建中靖国元年，帝赵佶践祚。择定难度，以承大统。
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {DIFFICULTIES.map((d) => (
          <button
            key={d.key}
            onClick={() => setDiff(d.key)}
            className={`flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left transition ${
              diff === d.key
                ? "border-red bg-red/5 shadow-paper"
                : "border-border bg-paper/50 hover:bg-gold-light"
            }`}
          >
            <span
              className={`mt-1 h-3 w-3 shrink-0 rounded-full border-2 ${
                diff === d.key ? "border-red bg-red" : "border-dim"
              }`}
            />
            <span className="flex-1">
              <span className="block font-kai text-base tracking-widest text-ink">{d.label}</span>
              <span className="mt-0.5 block text-xs leading-relaxed text-dim">{d.desc}</span>
            </span>
          </button>
        ))}
      </div>

      {err && (
        <div className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red-dark">
          {err}
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={start}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-60"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          {busy ? "开局中…" : "承 统"}
        </button>
      </div>
    </div>
  );
}