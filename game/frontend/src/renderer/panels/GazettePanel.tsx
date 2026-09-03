import { useMemo } from "react";
import { useGameStore, pick } from "../store/gameStore";

// 朝报 —— 对齐 game/ui/panels_govern.py::_panel_daily_log（L1629）
// 只读降级：Tk 正文取运行时内存缓冲 self._log_lines（gui.py L201，最近 200 条，不经 HTTP），
// React 版降级为快照 settlement_log（逐月结算日志 list[list[str]]）+ short_term_log
// （行为日志 list<{turn,kind,title,note,year,month}>）重建统一时间线。
type Dict = Record<string, unknown>;

interface ShortTermEntry {
  turn: number;
  kind: string;
  title: string;
  note: string;
  year: number;
  month: number;
}

interface MonthBlock {
  year: number;
  month: number;
  lines: string[];
}

export default function GazettePanel() {
  const state = useGameStore((s) => s.state);

  const blocks = useMemo<MonthBlock[]>(() => {
    if (!state) return [];
    const year = pick<number>(state, "year", 0);
    const month = pick<number>(state, "month", 1);
    const settlement = pick<unknown[]>(state, "settlement_log", []);
    const shortTerm = pick<unknown[]>(state, "short_term_log", []);

    // 月份倒推：长度 L，块 i 对应当前月减 (L-i) 月
    const blocks: MonthBlock[] = settlement.map((lines, i) => {
      const back = settlement.length - i;
      let y = year;
      let m = month - back;
      while (m <= 0) {
        m += 12;
        y -= 1;
      }
      return {
        year: y,
        month: m,
        lines: Array.isArray(lines) ? lines.map(String) : [String(lines)]
      };
    });
    // 当前月块始终存在（对齐 Tk 头）
    if (blocks.length === 0 || blocks[blocks.length - 1].month !== month || blocks[blocks.length - 1].year !== year) {
      blocks.push({ year, month, lines: [] });
    }

    // short_term 条目按自带 year/month 归块
    const kindMark: Record<string, string> = { decree: "诏", edict: "谕" };
    for (const raw of shortTerm) {
      const e = raw as Partial<ShortTermEntry>;
      if (typeof e.year !== "number" || typeof e.month !== "number") continue;
      let blk = blocks.find((b) => b.year === e.year && b.month === e.month);
      if (!blk) {
        blk = { year: e.year, month: e.month, lines: [] };
        blocks.push(blk);
        blocks.sort((a, b) => a.year * 12 + a.month - (b.year * 12 + b.month));
      }
      const mark = kindMark[String(e.kind ?? "")] ?? "记";
      blk.lines.push(`〔${mark}〕${String(e.title ?? "")} —— ${String(e.note ?? "")}`);
    }
    return blocks;
  }, [state]);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无朝报可览。</p>;
  }

  const total = blocks.reduce((a, b) => a + b.lines.length, 0);
  if (total === 0) {
    return (
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-6">
        <p className="text-center font-kai text-base text-dim">— 暂无朝报 —</p>
        <p className="mt-2 text-center text-xs leading-relaxed text-dim">
          每月回合推演后，朝廷大事将记入邸报。
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gold/40 bg-card p-4">
      <p className="mb-2 text-center font-kai text-base tracking-[0.3em] text-red">大 宋 邸 报</p>
      <div className="max-h-[52vh] space-y-3 overflow-y-auto">
        {blocks.map((b, i) => (
          <div key={`${b.year}-${b.month}-${i}`}>
            <p className="font-kai text-sm font-bold text-ink">〔{b.year}年{b.month}月〕</p>
            {b.lines.length === 0 ? (
              <p className="pl-3 text-xs text-dim">（本月无事可记）</p>
            ) : (
              b.lines.map((l, j) => (
                <p key={j} className="py-0.5 pl-3 text-sm leading-relaxed text-ink">· {l}</p>
              ))
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
