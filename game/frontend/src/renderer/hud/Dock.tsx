import { Landmark, Users, Newspaper, ScrollText, PenLine, Play, Globe2 } from "lucide-react";
import { useGameStore } from "../store/gameStore";
import { getApiClient } from "../api/client";

// 底部命令 dock：朝堂/群臣/朝报/个人行止/拟旨 + 回合推演
const COMMANDS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "court", label: "朝堂", icon: <Landmark size={20} /> },
  { key: "ministers", label: "群臣", icon: <Users size={20} /> },
  { key: "gazette", label: "朝报", icon: <Newspaper size={20} /> },
  { key: "personal", label: "行止", icon: <ScrollText size={20} /> },
  { key: "diplomacy", label: "邦交", icon: <Globe2 size={20} /> },
  { key: "decree", label: "拟旨", icon: <PenLine size={20} /> }
];

export default function Dock() {
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const advancing = useGameStore((s) => s.advancing);
  const setAdvancing = useGameStore((s) => s.setAdvancing);
  const setState = useGameStore((s) => s.setState);

  async function handleAdvance() {
    if (advancing) return;
    setAdvancing(true);
    try {
      const res = await getApiClient().advance();
      setState(res.state);
      pushOverlay({ kind: "advance", title: "回合推演", props: { events: res.events, log: res.log, report: res.report } });
    } catch (e) {
      console.error("[advance]", e);
      // 推演为全游戏级强制 AI（core/commands.py::settle_turn 拒绝式），
      // 后端未配 AI 时抛 500，此处转为可读提示而非静默失败。
      const raw = e instanceof Error ? e.message : String(e);
      const hint = /^(HTTP 500|Internal Server Error)$/i.test(raw.trim())
        ? "推演需接入 AI：请配置 AI 设置（OpenAI 兼容 API）后重试。"
        : raw;
      pushOverlay({ kind: "advance", title: "推演未成", props: { error: hint } });
    } finally {
      setAdvancing(false);
    }
  }

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end justify-between px-6 pb-5">
      {/* 左：命令钮横排 */}
      <div className="pointer-events-auto flex items-center gap-3">
        {COMMANDS.map((c) => (
          <button
            key={c.key}
            onClick={() => pushOverlay({ kind: c.key as never, title: c.label })}
            className="group flex h-14 w-14 flex-col items-center justify-center rounded-full bg-card/95 shadow-paper backdrop-blur-sm transition hover:bg-gold-light hover:shadow-card border border-gold/40"
          >
            <span className="text-red transition group-hover:scale-110">{c.icon}</span>
            <span className="mt-0.5 text-[11.5px] font-bold text-ink">{c.label}</span>
          </button>
        ))}
      </div>

      {/* 右：回合推演大按钮 */}
      <div className="pointer-events-auto">
        <button
          onClick={handleAdvance}
          disabled={advancing}
          className="group relative flex h-16 w-16 items-center justify-center rounded-full bg-red text-paper shadow-card transition hover:bg-red-dark disabled:opacity-60"
        >
          {!advancing && <span className="absolute inset-0 rounded-full animate-breathe" />}
          <Play size={26} className="relative transition group-hover:scale-110" />
          <span className="absolute -bottom-6 whitespace-nowrap font-kai text-sm tracking-widest text-ink">
            {advancing ? "推演中…" : "回合推演"}
          </span>
        </button>
      </div>
    </div>
  );
}