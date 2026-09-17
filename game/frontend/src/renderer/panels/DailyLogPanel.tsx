import { useGameStore, pick } from "../store/gameStore";

// 月日志 / 结算流水 —— 对齐 Tk 版结算日志（只读展示）
// 后端 settlement_log 形状为 list[list[str]]：每月一组日志行
// （core/settlement.py 每月 append(log)）。故需按「月」分组渲染，
// 不可当成一维 string[]（否则整月多行会被 React 无分隔挤成一段）。
export default function DailyLogPanel() {
  const state = useGameStore((s) => s.state);
  const log = pick<unknown[]>(state, "settlement_log", []);
  // 归一为 string[][]：兼容旧档/单条字符串
  const months: string[][] = (Array.isArray(log) ? log : []).map((m) =>
    Array.isArray(m) ? m.map((x) => String(x)) : [String(m)]
  );

  return (
    <div className="space-y-3">
      <p className="font-kai text-[15px] font-bold tracking-widest text-red">结 算 流 水</p>
      {months.length === 0 ? (
        <p className="py-8 text-center font-kai text-base text-dim">— 暂无结算流水（推演后生成）—</p>
      ) : (
        <div className="max-h-[62vh] space-y-2 overflow-y-auto pr-1">
          {[...months].reverse().map((lines, i) => (
            <div
              key={i}
              className="rounded border border-gold/30 bg-paper/50 px-3 py-1.5"
            >
              {lines.map((line, j) => (
                <p key={j} className="font-kai text-[13px] leading-relaxed text-ink-light">
                  {line}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}