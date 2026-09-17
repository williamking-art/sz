import { useGameStore, pick } from "../store/gameStore";

// 月日志 / 结算流水 —— 对齐 Tk 版结算日志（只读展示）
// 读取后端 settlement_log（string[]，月度/事件结算流水，倒序展示最新在前）。
export default function DailyLogPanel() {
  const state = useGameStore((s) => s.state);
  const log = pick<string[]>(state, "settlement_log", []);

  return (
    <div className="space-y-3">
      <p className="font-kai text-[15px] font-bold tracking-widest text-red">结 算 流 水</p>
      {!log || log.length === 0 ? (
        <p className="py-8 text-center font-kai text-base text-dim">— 暂无结算流水（推演后生成）—</p>
      ) : (
        <div className="max-h-[62vh] space-y-1 overflow-y-auto pr-1">
          {[...log].reverse().map((line, i) => (
            <p
              key={i}
              className="rounded border border-gold/30 bg-paper/50 px-3 py-1.5 font-kai text-[13px] leading-relaxed text-ink-light"
            >
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}