import { Loader2, RefreshCw, X, BookOpen } from "lucide-react";
import type { MemoryResult, MemoryDialogueRow, MemoryRelation } from "../api/client";

// 记忆库（会话视角）—— 嵌在「御前召对」面板右侧的抽屉，随会话大臣收窄。
// 与独立面板 MemoryPanel（全局视角，Dock「记忆」入口）的分工：
//   · 本抽屉：{大臣} 的会话原文流 + 其按期纪要 + 涉其近关系（外加全局史略/留痕）；
//   · MemoryPanel：全局记忆库 → 实体计数、全量概要、全量召对纪要、变更留痕。
// 数据源同一只读端点 /api/memory（此处带 minister 参数）。
// 语义：主库（slot_N.db）存「史」——实体/关系/概要；对话库（slot_N_dialogue.db）存召对。
// 归档旧史（w_eff 低于阈值）不再参与 AI 注入，但仍在库中可查证。
//
// 注：RTYPE_CN/KIND_CN/ENTITY_CN 与 MemoryPanel 中的同名映射一致（该文件属他人未提交
// 改动范围，暂不抽出公共模块以免踩踏；两处均只做中文展示名映射，不承载业务口径）。
const RTYPE_CN: Record<string, string> = {
  supports: "支持",
  opposes: "反对",
  involves: "涉",
  produces: "促成",
  progresses: "推进",
  promises: "许诺",
  stance: "态度",
  governs: "主政"
};

const KIND_CN: Record<string, string> = {
  summary: "六回合概要",
  period_summary: "十二回合史略"
};

const ENTITY_CN: Record<string, string> = {
  minister: "大臣",
  event: "事件",
  decision: "决策",
  task: "事务",
  org: "机构",
  institution: "制度",
  external_power: "外邦",
  summary: "概要",
  period_summary: "史略"
};

export type MemoryTab = "digest" | "stream" | "relations" | "history" | "audit";

const TAB_LABEL: Record<MemoryTab, string> = {
  digest: "召对纪要",
  stream: "会话原文",
  relations: "相关关系",
  history: "史略概要",
  audit: "变更留痕"
};

export default function MemoryDrawer({
  minister,
  data,
  busy,
  msg,
  tab,
  onTab,
  onClose,
  onRefresh
}: {
  minister: string;
  data: MemoryResult | null;
  busy: boolean;
  msg: string | null;
  tab: MemoryTab;
  onTab: (t: MemoryTab) => void;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const dialogues = data?.dialogues ?? [];
  const digest = data?.dialogue_summaries ?? [];
  const relOwn = data?.minister_relations ?? [];
  const drift = data ? data.turn !== data.state_turn : false;

  return (
    <aside className="relative z-10 flex h-full w-[380px] shrink-0 flex-col overflow-hidden rounded-[4px] border border-gold/60 bg-[#f7f1e2]/95 shadow-2xl animate-card-in">
      {/* 抽屉题头 */}
      <div className="flex items-center justify-between border-b border-gold/50 bg-[#efe4c9] px-3.5 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <BookOpen size={16} className="shrink-0 text-red" />
          <div className="min-w-0">
            <p className="truncate font-kai text-[15px] font-bold tracking-widest text-red">
              记忆库 · {minister}
            </p>
            <p className="truncate text-[10.5px] text-dim">
              朝廷所记之「史」· 只读回看
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={onRefresh}
            disabled={busy}
            title="重新读取记忆库"
            className="rounded border border-gold/50 bg-paper p-1.5 text-ink transition hover:bg-gold-light disabled:opacity-50"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
          <button
            onClick={onClose}
            title="收起记忆库"
            className="rounded border border-gold/50 bg-paper p-1.5 text-ink transition hover:bg-gold-light"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* 水位条 */}
      <div className="border-b border-gold/40 bg-paper/70 px-3.5 py-2 text-[11.5px] text-ink">
        {data ? (
          <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>
                记忆水位 <strong className="font-kai">第 {data.turn} 回合</strong>
              </span>
              <span className="text-dim">主存档 第 {data.state_turn} 回合</span>
              <span className="text-dim">
                关系 {data.relation_total}（归档 {data.relation_archived}）
              </span>
            </div>
            {drift && (
              <p className="mt-1 text-[10.5px] leading-relaxed text-goldDark">
                记忆水位与主存档不一致：多为主存档未更新（记忆库每回合落盘），读档后已按存档水位对齐检索。
              </p>
            )}
            <div className="mt-1.5 flex flex-wrap gap-1">
              {Object.entries(data.entity_counts ?? {}).length === 0 ? (
                <span className="text-[10.5px] text-dim">库中暂无实体。</span>
              ) : (
                Object.entries(data.entity_counts).map(([k, v]) => (
                  <span
                    key={k}
                    className="rounded border border-gold/40 bg-card px-1.5 py-0.5 text-[10.5px] text-ink"
                  >
                    {ENTITY_CN[k] ?? k} {v}
                  </span>
                ))
              )}
            </div>
          </>
        ) : (
          <span className="text-dim">尚未读到记忆库（未开局或记忆库为空）。</span>
        )}
      </div>

      {msg && (
        <p className="border-b border-red/30 bg-red/5 px-3.5 py-1.5 text-[11.5px] text-red">
          {msg}
        </p>
      )}

      {/* 分栏开关 */}
      <div className="flex shrink-0 gap-1 border-b border-gold/40 bg-[#efe4c9]/80 px-2 py-1.5">
        {(Object.keys(TAB_LABEL) as MemoryTab[]).map((t) => {
          const n =
            t === "digest" ? digest.length
              : t === "stream" ? dialogues.length
                : t === "relations" ? relOwn.length
                  : t === "history" ? (data?.summaries.length ?? 0)
                    : (data?.change_log.length ?? 0);
          const active = tab === t;
          return (
            <button
              key={t}
              onClick={() => onTab(t)}
              className={`flex items-center gap-1 rounded px-2 py-1 text-[11.5px] font-bold transition ${
                active
                  ? "bg-red text-paper shadow-sm"
                  : "border border-gold/50 bg-paper text-ink hover:bg-gold-light"
              }`}
            >
              {TAB_LABEL[t]}
              <span className={`text-[9.5px] ${active ? "text-gold-light" : "text-dim"}`}>
                {n}
              </span>
            </button>
          );
        })}
      </div>

      {/* 分栏内容 */}
      <div className="flex-1 overflow-y-auto px-3.5 py-3">
        {tab === "digest" && (
          <DigestTab rows={digest} />
        )}
        {tab === "stream" && (
          <StreamTab rows={dialogues} minister={minister} />
        )}
        {tab === "relations" && (
          <RelationsTab own={relOwn} recent={data?.recent ?? []} />
        )}
        {tab === "history" && (
          <HistoryTab rows={data?.summaries ?? []} />
        )}
        {tab === "audit" && (
          <AuditTab rows={data?.change_log ?? []} />
        )}
      </div>

      <p className="shrink-0 border-t border-gold/40 bg-paper/70 px-3.5 py-1.5 text-[10.5px] leading-relaxed text-dim">
        侧栏为已落库的会话流（含陛下之言）：关掉面板再召对，旧话仍在此。归档旧史不再注入大臣言谈，但留档可查。
      </p>
    </aside>
  );
}

function Empty({ hint }: { hint: string }) {
  return <p className="py-6 text-center text-[12px] leading-relaxed text-dim">{hint}</p>;
}

function DigestTab({ rows }: { rows: MemoryResult["dialogue_summaries"] }) {
  if (rows.length === 0) {
    return (
      <Empty hint="尚无召对纪要：对话库每 3 回合总结去重一次。推演一回合（或跨过 3 的倍数回合）后即自动生成。" />
    );
  }
  return (
    <div className="space-y-2">
      {rows.map((d, i) => (
        <div key={i} className="rounded border border-gold/40 bg-card p-2">
          <p className="text-[11.5px] font-bold text-ink">
            {d.minister}
            <span className="ml-2 font-normal text-dim">
              第{d.start_turn}–{d.end_turn}回合 · 归并 {d.ref_count} 条
            </span>
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-light">{d.content}</p>
        </div>
      ))}
    </div>
  );
}

function StreamTab({ rows, minister }: { rows: MemoryDialogueRow[]; minister: string }) {
  if (rows.length === 0) {
    return (
      <Empty hint={`尚无 ${minister} 的会话原文。召对一次即落库，此后随时可回看（含陛下之言）。`} />
    );
  }
  // 按回合分组：同回合的「朕言 → 回奏」成对呈现
  const groups: { turn: number; rows: MemoryDialogueRow[] }[] = [];
  for (const r of rows) {
    const last = groups[groups.length - 1];
    if (last && last.turn === r.turn) last.rows.push(r);
    else groups.push({ turn: r.turn, rows: [r] });
  }
  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={`${g.turn}-${g.rows[0]?.id ?? 0}`}>
          <p className="mb-1 border-b border-gold/30 pb-0.5 text-[10.5px] tracking-widest text-dim">
            第 {g.turn} 回合
            {g.rows[0]?.topic ? ` · ${g.rows[0].topic}` : ""}
          </p>
          <div className="space-y-1">
            {g.rows.map((r) => {
              const isEmperor = r.speaker === "朕";
              return (
                <p key={r.id} className="text-[12px] leading-relaxed">
                  <span
                    className={`mr-1 font-bold ${isEmperor ? "text-red" : "text-goldDark"}`}
                  >
                    {isEmperor ? "朕" : r.speaker}：
                  </span>
                  <span className="text-ink">{r.text}</span>
                  {r.summarized && (
                    <span className="ml-1 text-[10px] text-dim">（已入纪要）</span>
                  )}
                </p>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function RelationsTab({
  own,
  recent
}: {
  own: MemoryRelation[];
  recent: MemoryResult["recent"];
}) {
  return (
    <div className="space-y-3">
      <div className="rounded border border-gold/40 bg-card p-2">
        <p className="mb-1 text-[11.5px] font-bold tracking-widest text-red">涉此人近关系</p>
        {own.length === 0 ? (
          <p className="text-[11.5px] text-dim">
            近 24 回合无涉此人的关系。关系由召对、诏令推演写入，机关未动则无事可记。
          </p>
        ) : (
          own.map((r, i) => (
            <p key={i} className="text-[12px] leading-relaxed">
              <span className="text-ink-light">{r.src}</span>
              <span className="mx-1 text-red">{RTYPE_CN[r.rtype] ?? r.rtype}</span>
              <span className="text-ink-light">{r.dst}</span>
              {r.note && <span className="ml-1 text-[10.5px] text-dim">（{r.note}）</span>}
            </p>
          ))
        )}
      </div>
      <div className="rounded border border-gold/40 bg-paper/60 p-2">
        <p className="mb-1 text-[11.5px] font-bold tracking-widest text-red">朝廷近关系（近 24 回合）</p>
        {recent.length === 0 ? (
          <p className="text-[11.5px] text-dim">近年无事可记。</p>
        ) : (
          recent.map((r, i) => (
            <p key={i} className="text-[12px] leading-relaxed">
              <span className="text-ink-light">{r.src}</span>
              <span className="mx-1 text-red">{RTYPE_CN[r.rtype] ?? r.rtype}</span>
              <span className="text-ink-light">{r.dst}</span>
              {r.note && <span className="ml-1 text-[10.5px] text-dim">（{r.note}）</span>}
            </p>
          ))
        )}
      </div>
    </div>
  );
}

function HistoryTab({ rows }: { rows: MemoryResult["summaries"] }) {
  if (rows.length === 0) {
    return <Empty hint="尚未到压缩期（每 6 回合概要、每 12 回合史略）。" />;
  }
  return (
    <div className="space-y-2">
      {rows.map((s) => (
        <div key={s.eid} className="rounded border border-gold/40 bg-card p-2">
          <p className="font-kai text-[12.5px] font-bold text-red">
            {s.name}
            <span className="ml-2 text-[10.5px] font-normal text-dim">
              {KIND_CN[s.kind] ?? s.kind}
              {s.period !== null && s.period !== undefined ? ` · 第${s.period}期` : ""}
              {` · 第${s.turn}回合`}
            </span>
          </p>
          {s.highlights.length > 0 ? (
            <p className="mt-1 text-[11.5px] leading-relaxed text-ink-light">
              {s.highlights.join("；")}
            </p>
          ) : (
            <p className="mt-1 text-[11.5px] text-dim">（本期无显著关系）</p>
          )}
        </div>
      ))}
    </div>
  );
}

function AuditTab({ rows }: { rows: MemoryResult["change_log"] }) {
  if (rows.length === 0) {
    return <Empty hint="尚无写盘/压缩/归档记录。" />;
  }
  return (
    <div className="space-y-1">
      {rows.map((c, i) => (
        <p key={i} className="text-[11.5px] leading-relaxed text-dim">
          第{c.turn}回合 · {c.action} · {c.detail}
        </p>
      ))}
    </div>
  );
}
