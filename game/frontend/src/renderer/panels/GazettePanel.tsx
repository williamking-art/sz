import { useMemo } from "react";
import { useGameStore, pick } from "../store/gameStore";

// 朝报 —— 批 3 月度奏章八章（明末经验）：诏书核销 / 指令核销 / 长期局势 / 密令动向 /
// 讣闻登场 / 人物历练 / 军事 / 邦交 + 章末七言联 + ▲▼ 差值摘要。
// 后端 core/monthly_gazette.py 为组装权威；无八章数据时回落旧版 settlement_log 时间线。
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

interface GazetteChapter {
  title: string;
  lines: string[];
  /** ⑤ 八章+分幕合并：各章分幕小剧场 */
  scenes?: { scene: string; text: string }[];
}

interface GazetteRecord {
  year: number;
  month: number;
  chapters: GazetteChapter[];
  couplet: string;
  diff_summary: string[];
}

const CHAPTER_TONE: Record<string, string> = {
  诏书核销: "border-l-red",
  指令核销: "border-l-amber-600",
  长期局势: "border-l-red-dark",
  密令动向: "border-l-ink/70",
  讣闻登场: "border-l-ink/50",
  人物历练: "border-l-emerald-700",
  军事: "border-l-red",
  邦交: "border-l-amber-700",
};

function ChapterBlock({ ch }: { ch: GazetteChapter }) {
  const tone = CHAPTER_TONE[ch.title] ?? "border-l-gold";
  return (
    <div className={`border-l-2 ${tone} pl-2.5`}>
      <p className="font-kai text-[13px] font-bold tracking-[0.2em] text-red">{ch.title}</p>
      {ch.lines.length === 0 ? (
        <p className="py-0.5 text-xs text-dim">（本月无事）</p>
      ) : (
        ch.lines.map((l, i) => (
          <p key={i} className="py-0.5 text-sm leading-relaxed text-ink">· {l}</p>
        ))
      )}
      {/* ⑤ 分幕小剧场 */}
      {(ch.scenes?.length ?? 0) > 0 && (
        <div className="mt-1 space-y-1 border-t border-gold/20 pt-1">
          {ch.scenes!.map((s, i) => (
            <div key={i} className="pl-2">
              <span className="font-kai text-[11px] text-dim">【{s.scene}】</span>
              <span className="ml-1 text-xs leading-relaxed text-ink-light">{s.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GazetteMonthCard({ g }: { g: GazetteRecord }) {
  return (
    <div className="rounded-lg border border-gold/40 bg-card p-3">
      <div className="mb-1.5 flex items-baseline justify-between">
        <p className="font-kai text-sm font-bold text-ink">〔{g.year}年{g.month}月〕</p>
        {g.diff_summary.length > 0 && (
          <p className="text-[11px] text-ink-light">{g.diff_summary.join("　")}</p>
        )}
      </div>
      <div className="space-y-1.5">
        {g.chapters.map((ch) => <ChapterBlock key={ch.title} ch={ch} />)}
      </div>
      {g.couplet && (
        <p className="mt-2 text-center font-kai text-sm tracking-[0.15em] text-ink-light">
          {g.couplet}
        </p>
      )}
    </div>
  );
}

export default function GazettePanel() {
  const state = useGameStore((s) => s.state);
  const uiLogs = useGameStore((s) => s.uiLogs);
  const uiLogBlock = uiLogs.length > 0 ? (
    <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
      <p className="font-kai text-sm font-bold tracking-widest text-red">近 日 机 务 回 执</p>
      <div className="mt-1 max-h-40 space-y-0.5 overflow-y-auto">
        {uiLogs.slice(-20).reverse().map((l, i) => (
          <p key={i} className="text-xs leading-relaxed text-ink-light">· {l}</p>
        ))}
      </div>
    </div>
  ) : null;

  // 批 3：八章奏章（后端 monthly_gazette 权威）
  const gazettes = useMemo<GazetteRecord[]>(() => {
    if (!state) return [];
    const raw = pick<unknown[]>(state, "monthly_gazette", []);
    return (Array.isArray(raw) ? raw : [])
      .filter((x): x is GazetteRecord => {
        const d = x as unknown as Partial<GazetteRecord> | null;
        return !!d && typeof d === "object" && Array.isArray(d.chapters);
      })
      .slice()
      .reverse(); // 最新在上
  }, [state]);

  // 旧版回落：settlement_log + short_term_log 时间线
  const blocks = useMemo<MonthBlock[]>(() => {
    if (!state || gazettes.length > 0) return [];
    const year = pick<number>(state, "year", 0);
    const month = pick<number>(state, "month", 1);
    const settlement = pick<unknown[]>(state, "settlement_log", []);
    const shortTerm = pick<unknown[]>(state, "short_term_log", []);

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
    if (blocks.length === 0 || blocks[blocks.length - 1].month !== month || blocks[blocks.length - 1].year !== year) {
      blocks.push({ year, month, lines: [] });
    }

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
  }, [state, gazettes.length]);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无朝报可览。</p>;
  }

  const total = gazettes.length > 0
    ? gazettes.reduce((a, g) => a + g.chapters.reduce((b, c) => b + c.lines.length, 0), 0)
    : blocks.reduce((a, b) => a + b.lines.length, 0);

  if (total === 0 && gazettes.length === 0) {
    return (
      <div className="space-y-3">
        {uiLogBlock}
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-6">
          <p className="text-center font-kai text-base text-dim">— 暂无朝报 —</p>
          <p className="mt-2 text-center text-xs leading-relaxed text-dim">
            每月回合推演后，朝廷大事将记入邸报（八章：诏书/指令/局势/密令/讣闻/人物/军事/邦交）。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {uiLogBlock}
      <div className="rounded-lg border border-gold/40 bg-card p-4">
        <p className="mb-2 text-center font-kai text-base tracking-[0.3em] text-red">大 宋 邸 报</p>
        <p className="mb-2 text-center text-[11px] text-dim">
          八章：诏书核销 · 指令核销 · 长期局势 · 密令动向 · 讣闻登场 · 人物历练 · 军事 · 邦交
        </p>
        <div className="max-h-[52vh] space-y-3 overflow-y-auto">
          {gazettes.length > 0
            ? gazettes.map((g, i) => <GazetteMonthCard key={`${g.year}-${g.month}-${i}`} g={g} />)
            : blocks.map((b, i) => (
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
    </div>
  );
}
