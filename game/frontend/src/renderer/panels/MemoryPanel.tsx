import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { getApiClient, type MemoryResult } from "../api/client";

// 记忆库 —— 玩家可见「AI 究竟记住了什么」。
// 数据源 /api/memory（薄壳：主库概要与近关系、变更日志 + 对话记忆库概要），只读展示、不改动记忆。
// 语义：主库（slot_N.db）存「史」——实体/关系/概要；对话库（slot_N_dialogue.db）存召对。
// 已归档旧史（w_eff 低于阈值）不再参与 AI 注入，但仍在库中可查证。
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

export default function MemoryPanel() {
  const [data, setData] = useState<MemoryResult | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setMsg(null);
    try {
      setData(await getApiClient().memory());
    } catch (e) {
      console.error("[memory]", e);
      setMsg("记忆库读取失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().memory();
        if (alive) setData(res);
      } catch (e) {
        console.error("[memory]", e);
        if (alive) setMsg("记忆库读取失败：" + (e instanceof Error ? e.message : String(e)));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!data) {
    return (
      <div className="space-y-3">
        {msg && <p className="rounded border border-red/40 bg-red/5 p-2 text-sm text-red">{msg}</p>}
        <p className="py-10 text-center text-dim">尚无记忆可览（未开局或记忆库为空）。</p>
      </div>
    );
  }

  const counts = Object.entries(data.entity_counts ?? {});
  const drift = data.turn !== data.state_turn;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm leading-relaxed text-dim">
          朝廷所记之「史」——跨回合的实体与关系、按期压缩的概要、召对纪要。
          归档旧史不再注入大臣言谈，但仍留档可查。
        </p>
        <button
          onClick={() => void load()}
          disabled={busy}
          className="sz-btn-secondary flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-xs disabled:opacity-60"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          刷新
        </button>
      </div>

      {msg && <p className="rounded border border-red/40 bg-red/5 p-2 text-sm text-red">{msg}</p>}

      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink">
          <span>记忆水位：<strong>第 {data.turn} 回合</strong></span>
          <span className="text-dim">主存档：第 {data.state_turn} 回合</span>
          <span className="text-dim">
            关系 {data.relation_total} 条（归档 {data.relation_archived}）
          </span>
        </div>
        {drift && (
          <p className="mt-1 text-xs leading-relaxed text-gold-dark">
            记忆水位与主存档不一致：多为主存档未更新（记忆库每回合落盘），读档后已按存档水位对齐检索。
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {counts.length === 0 ? (
            <span className="text-xs text-dim">库中暂无实体。</span>
          ) : (
            counts.map(([k, v]) => (
              <span key={k} className="rounded border border-gold/40 bg-card px-2 py-0.5 text-xs text-ink">
                {ENTITY_CN[k] ?? k} {v}
              </span>
            ))
          )}
        </div>
      </div>

      <Section title="史略与概要" empty={data.summaries.length === 0} emptyHint="尚未到压缩期（每 6 回合概要、每 12 回合史略）。">
        {data.summaries.map((s) => (
          <div key={s.eid} className="rounded border border-gold/30 bg-card p-2">
            <p className="font-kai text-sm font-bold text-red">
              {s.name}
              <span className="ml-2 text-xs font-normal text-dim">
                {KIND_CN[s.kind] ?? s.kind}
                {s.period !== null && s.period !== undefined ? ` · 第${s.period}期` : ""}
                {` · 第${s.turn}回合`}
              </span>
            </p>
            {s.highlights.length > 0 ? (
              <p className="mt-1 text-xs leading-relaxed text-ink-light">
                {s.highlights.join("；")}
              </p>
            ) : (
              <p className="mt-1 text-xs text-dim">（本期无显著关系）</p>
            )}
          </div>
        ))}
      </Section>

      <Section title="近期关系（近 24 回合）" empty={data.recent.length === 0} emptyHint="近年无事可记。">
        {data.recent.map((r, i) => (
          <p key={i} className="text-sm leading-relaxed text-ink">
            <span className="text-ink-light">{r.src}</span>
            <span className="mx-1 text-red">{RTYPE_CN[r.rtype] ?? r.rtype}</span>
            <span className="text-ink-light">{r.dst}</span>
            {r.note && <span className="ml-1 text-xs text-dim">（{r.note}）</span>}
          </p>
        ))}
      </Section>

      <Section title="召对纪要" empty={data.dialogue_summaries.length === 0} emptyHint="尚无召对可记（每 3 回合总结去重）。">
        {data.dialogue_summaries.map((d, i) => (
          <div key={i} className="rounded border border-gold/30 bg-card p-2">
            <p className="text-xs font-bold text-ink">
              {d.minister}
              <span className="ml-2 font-normal text-dim">
                第{d.start_turn}–{d.end_turn}回合 · {d.ref_count} 条
              </span>
            </p>
            <p className="mt-1 text-xs leading-relaxed text-ink-light">{d.content}</p>
          </div>
        ))}
      </Section>

      <Section title="记忆变更留痕（审计）" empty={data.change_log.length === 0} emptyHint="尚无写盘/压缩/归档记录。">
        {data.change_log.map((c, i) => (
          <p key={i} className="text-xs leading-relaxed text-dim">
            第{c.turn}回合 · {c.action} · {c.detail}
          </p>
        ))}
      </Section>
    </div>
  );
}

function Section({
  title,
  empty,
  emptyHint,
  children
}: {
  title: string;
  empty: boolean;
  emptyHint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
      <p className="mb-2 font-kai text-sm font-bold tracking-widest text-red">{title}</p>
      {empty ? (
        <p className="text-xs text-dim">{emptyHint}</p>
      ) : (
        <div className="max-h-56 space-y-1.5 overflow-y-auto">{children}</div>
      )}
    </div>
  );
}
