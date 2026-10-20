import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";

/** 长期旨案卷（数据来自后端 /api/readouts → longterm_cases；口径单点在 core）。 */
interface CaseEffect { key: string; amount: number | null }
interface CaseLog { turn: number | null; narrative: string; applied?: CaseEffect[]; blocked?: string | null }
interface CaseReadout {
  case_no: string | null;
  title: string | null;
  kind: string | null;
  status: string | null;
  severity: number | null;
  source_ref: string | null;
  opened_turn: number | null;
  last_advance_turn: number | null;
  linked_region: string | null;
  linked_factions: string[];
  cancellable: boolean;
  handler: { name: string | null; org: string | null; stats: Record<string, number | null> | null };
  authorization: {
    budget_total: number | null;
    budget_remaining: number | null;
    pool: string | null;
    monthly_cost: number | null;
    discretion: boolean;
  };
  progress: { percent: number | null; phase: string; target: number };
  monthly_effects: CaseEffect[];
  progress_log: CaseLog[];
  outcome_effects: CaseEffect[];
  fail_effects: CaseEffect[];
}

// 本项目大臣只有 loyalty/corruption 两项数值（0–1）；没有「六维」，不得臆造。
const STAT_LABEL: Record<string, string> = {
  loyalty: "忠诚",
  corruption: "贪腐",
  role: "差遣",
  rank: "官阶",
  faction: "派系",
  traits: "特质",
};
const POOL_LABEL: Record<string, string> = { treasury: "国库", imperial_treasury: "内帑" };
const EFFECT_LABEL: Record<string, string> = {
  prestige: "皇威",
  treasury: "国库",
  population_satisfaction: "民心",
};

function def(v: unknown, fallback = "未定义"): string {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

function EffectLine({ eff }: { eff: CaseEffect }) {
  const label = EFFECT_LABEL[eff.key] ?? eff.key;
  const amt = eff.amount;
  const text = amt === null || amt === undefined ? "未定义" : `${amt > 0 ? "+" : ""}${amt}`;
  return (
    <span className="rounded border border-gold/50 px-2 py-0.5 text-xs">
      {label} {text}
    </span>
  );
}

export default function LongtermCasePanel({ props }: { props?: { id?: string } }) {
  const [data, setData] = useState<CaseReadout | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const res = (await getApiClient().readouts()) as unknown as {
          longterm_cases?: Record<string, CaseReadout>;
        };
        if (!alive) return;
        const id = String(props?.id ?? "");
        const c = res.longterm_cases?.[id];
        if (c) setData(c);
        else setErr("案卷读数为空（后端未返回该案卷，或该事务未案卷化）");
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [props?.id]);

  const pct = useMemo(() => {
    const p = data?.progress?.percent;
    if (p === null || p === undefined) return null;
    return Math.max(0, Math.min(100, p));
  }, [data]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-dim">
        <Loader2 size={14} className="animate-spin" /> 载入案卷…
      </div>
    );
  }
  if (err || !data) {
    return (
      <div className="rounded border border-red/50 bg-red/5 p-3 text-sm text-red">
        {err ?? "案卷不可读"}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header className="border-b border-gold/40 pb-2">
        <p className="text-xs text-dim">时局案卷 · {def(data.case_no, "无案号")}</p>
        <h2 className="font-kai text-2xl font-bold text-ink">{def(data.title)}</h2>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <span className="rounded border border-gold/60 px-2 py-0.5">{def(data.kind)}</span>
          <span className="rounded border border-gold/60 px-2 py-0.5">严重度 {def(data.severity)}</span>
          <span className="rounded border border-gold/60 px-2 py-0.5">{def(data.status)}</span>
          {data.linked_region && (
            <span className="rounded border border-gold/60 px-2 py-0.5">地区 {data.linked_region}</span>
          )}
          {data.linked_factions?.length > 0 && (
            <span className="rounded border border-gold/60 px-2 py-0.5">
              派系 {data.linked_factions.join("、")}
            </span>
          )}
        </div>
      </header>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">承办人</p>
        <div className="rounded border border-gold/40 p-3">
          <p className="font-bold text-ink">{def(data.handler?.name)}</p>
          <p className="text-xs text-dim">{def(data.handler?.org, "衙署未定义")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(STAT_LABEL).map(([k, label]) => {
              const v = data.handler?.stats?.[k];
              const text =
                v === null || v === undefined
                  ? "未定义"
                  : (k === "loyalty" || k === "corruption")
                    ? `${Math.round(Number(v) * 100)}%`
                    : def(v);
              return (
                <span key={k} className="rounded border border-gold/40 px-2 py-0.5 text-xs">
                  {label} <b className="text-ink">{text}</b>
                </span>
              );
            })}
          </div>
        </div>
      </section>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">承办人授权</p>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <span className="text-dim">现有专款</span>
          <span className="text-right">{def(data.authorization?.budget_total)} 万两（{POOL_LABEL[String(data.authorization?.pool)] ?? def(data.authorization?.pool)}）</span>
          <span className="text-dim">专款余额</span>
          <span className="text-right">{def(data.authorization?.budget_remaining)}</span>
          <span className="text-dim">逐月自理</span>
          <span className="text-right">{def(data.authorization?.monthly_cost)} / 月</span>
          <span className="text-dim">赐专断之权</span>
          <span className="text-right">{data.authorization?.discretion ? "已授" : "未授"}</span>
        </div>
      </section>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">当前阶段</p>
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink">{data.progress?.phase}</span>
          <span className="ml-auto text-sm">
            {pct === null ? "未定义" : Math.round(pct)} / {data.progress?.target ?? 100}
          </span>
        </div>
        <div className="mt-1 h-2 w-full rounded bg-gold-light">
          <div
            className="h-2 rounded bg-red"
            style={{ width: pct === null ? "0%" : `${pct}%` }}
            title={pct === null ? "未定义" : `${Math.round(pct)}%`}
          />
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-dim">当前影响</span>
        {(data.monthly_effects?.length ?? 0) > 0 ? (
          data.monthly_effects.map((e, i) => <EffectLine key={i} eff={e} />)
        ) : (
          <span className="text-xs text-dim">无（未定义）</span>
        )}
      </section>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">案卷底册</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <span className="text-dim">来源引据</span>
          <span>{def(data.source_ref)}</span>
          <span className="text-dim">立项回合</span>
          <span>{def(data.opened_turn)}</span>
          <span className="text-dim">最近推进</span>
          <span>{def(data.last_advance_turn)}</span>
          <span className="text-dim">可撤性</span>
          <span>{data.cancellable ? "可撤" : "不可撤"}</span>
        </div>
      </section>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">推进日志（{data.progress_log?.length ?? 0}）</p>
        {(data.progress_log?.length ?? 0) === 0 ? (
          <p className="text-xs text-dim">暂无推进记录</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {[...(data.progress_log ?? [])].reverse().map((l, i) => (
              <li key={i} className="flex gap-2">
                <span className="w-20 shrink-0 text-dim">{def(l.turn, "—")} 月</span>
                <span className="min-w-0">
                  {l.blocked ? <span className="text-red">{l.blocked}　</span> : null}
                  {l.narrative || "（无叙事）"}
                  {(l.applied?.length ?? 0) > 0 && (
                    <span className="ml-1 text-xs text-dim">
                      落账：{l.applied!.map((e) => `${EFFECT_LABEL[e.key] ?? e.key}${e.amount ?? ""}`).join("、")}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid grid-cols-2 gap-3">
        <div className="rounded border border-gold/40 p-2">
          <p className="text-sm font-bold text-ink">达成后的目标</p>
          <div className="mt-1 flex flex-wrap gap-1">
            {(data.outcome_effects?.length ?? 0) > 0
              ? data.outcome_effects.map((e, i) => <EffectLine key={i} eff={e} />)
              : <span className="text-xs text-dim">未定义</span>}
          </div>
        </div>
        <div className="rounded border border-gold/40 p-2">
          <p className="text-sm font-bold text-ink">失败后的代价</p>
          <div className="mt-1 flex flex-wrap gap-1">
            {(data.fail_effects?.length ?? 0) > 0
              ? data.fail_effects.map((e, i) => <EffectLine key={i} eff={e} />)
              : <span className="text-xs text-dim">无直接数值影响</span>}
          </div>
        </div>
      </section>
    </div>
  );
}
