import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";

/** 长期旨案卷（数据来自后端 /api/readouts → longterm_cases；口径单点在 core）。 */
interface CaseEffect { key: string; amount: number | null }
interface CaseLog { turn: number | null; narrative: string; applied?: CaseEffect[]; blocked?: string | null }
interface StanceRow { name: string; influence: number | null; reason: string }
interface HandlerStats {
  attrs: Record<string, number | null> | null;
  potential: Record<string, number | null> | null;
  attr_names: Record<string, string> | null;
  loyalty: number | null;
  corruption: number | null;
  traits: string[];
  faction: string | null;
}
interface AdvanceReadout {
  stage: string | null;
  progress: number | null;
  forecast: { advance_pct: number | null; text: string } | null;
  blockers: string[];
  supporters: StanceRow[];
  opposers: StanceRow[];
  support_net: number | null;
  support_bonus: number | null;
  stance_mult: number | null;
  decree_count: number | null;
  stall_months: number | null;
  months: number | null;
  outcome: string | null;
}
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
  handler: { name: string | null; org: string | null; stats: HandlerStats | null };
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
  /** 推进可解释读数（本作特色：基数×难度×吏治×立场×军队 + 阻碍 + 圣意支持） */
  advance: AdvanceReadout | null;
  timeline?: { turn: number; kind: string; text: string }[];
}

// 本作口径：承办人是「五维」（政略/财计/军略/谋断/风望）+ 潜质上限 + 忠诚/贪腐（0–1）+ 特质；
// **没有**参考图那套「六维」，不得臆造字段（缺失一律「未定义」）。
const ATTR_LABEL: Record<string, string> = {
  governance: "政略",
  finance: "财计",
  military: "军略",
  strategy: "谋断",
  reputation: "风望",
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
function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "未定义";
  return `${Math.round(Number(v) * 100)}%`;
}
function signed(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return "未定义";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;
}

/** 五维条：实心=当前，虚线=潜质上限（成长空间可见）。 */
function AttrBar({ label, value, potential }: { label: string; value: number | null; potential: number | null }) {
  const w = value === null ? 0 : Math.max(0, Math.min(100, value));
  const p = potential === null ? null : Math.max(0, Math.min(100, potential));
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-dim">{label}</span>
        <span className="text-ink">
          {value === null ? "未定义" : Math.round(w)}
          {p !== null && <span className="text-dim"> / {Math.round(p)}</span>}
        </span>
      </div>
      <div className="relative mt-0.5 h-1.5 w-full rounded bg-gold-light">
        <div className="absolute inset-y-0 left-0 rounded bg-red" style={{ width: `${w}%` }} />
        {p !== null && (
          <div className="absolute inset-y-0 border-r border-dashed border-ink/50" style={{ left: `${p}%` }} />
        )}
      </div>
    </div>
  );
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

  const [budgetInput, setBudgetInput] = useState("0");
  const [pool, setPool] = useState("treasury");
  const [discretion, setDiscretion] = useState(false);
  const [monthlyCost, setMonthlyCost] = useState("0");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async (alive = true) => {
    setLoading(true);
    try {
      const res = (await getApiClient().readouts()) as unknown as {
        longterm_cases?: Record<string, CaseReadout>;
      };
      if (!alive) return;
      const id = String(props?.id ?? "");
      const c = res.longterm_cases?.[id];
      if (c) { setData(c); setErr(null); }
      else setErr("案卷读数为空（后端未返回该案卷，或该事务未案卷化）");
    } catch (e) {
      if (alive) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      if (alive) setLoading(false);
    }
  }, [props?.id]);

  useEffect(() => {
    let alive = true;
    void load(alive);
    return () => { alive = false; };
  }, [load]);

  async function submitAuthorize() {
    const id = String(props?.id ?? "");
    if (!id) return;
    setSubmitting(true);
    setMsg(null);
    try {
      const res = await getApiClient().action("authorize_case", {
        task_id: id,
        budget: Number(budgetInput || 0),
        pool,
        discretion,
        monthly_cost: Number(monthlyCost || 0),
      });
      setMsg(res.message || "已授权");
      await load(true);   // 刷新专款余额与授权状态
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const adv = data?.advance ?? null;
  const barPct = useMemo(() => {
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
          <div className="mt-2 grid grid-cols-5 gap-2">
            {Object.entries(ATTR_LABEL).map(([k, label]) => (
              <AttrBar
                key={k}
                label={label}
                value={data.handler?.stats?.attrs?.[k] ?? null}
                potential={data.handler?.stats?.potential?.[k] ?? null}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded border border-gold/40 px-2 py-0.5">
              忠诚 <b className="text-ink">{pct(data.handler?.stats?.loyalty)}</b>
            </span>
            <span className="rounded border border-gold/40 px-2 py-0.5">
              贪腐 <b className="text-ink">{pct(data.handler?.stats?.corruption)}</b>
            </span>
            {(data.handler?.stats?.traits?.length ?? 0) > 0 && (
              <span className="flex flex-wrap gap-1">
                {data.handler!.stats!.traits.map((t) => (
                  <span key={t} className="rounded border border-gold/40 bg-gold-light px-2 py-0.5">
                    {t}
                  </span>
                ))}
              </span>
            )}
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
        {/* 授权入口（2026-10-20）：批专款 + 出库 + 逐月自理 + 赐专断之权；专款真实扣减（后端守恒） */}
        <div className="mt-2 rounded border border-gold/30 p-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-1">
              专款
              <input
                aria-label="专款"
                className="w-20 rounded border border-gold/50 bg-transparent px-1 py-0.5 text-right"
                value={budgetInput}
                onChange={(e) => setBudgetInput(e.target.value)}
              />
              万两
            </label>
            <label className="flex items-center gap-1">
              出库
              <select
                aria-label="出库"
                className="rounded border border-gold/50 bg-transparent px-1 py-0.5"
                value={pool}
                onChange={(e) => setPool(e.target.value)}
              >
                <option value="treasury">国库</option>
                <option value="imperial_treasury">内帑</option>
              </select>
            </label>
            <label className="flex items-center gap-1">
              逐月自理
              <input
                aria-label="逐月自理"
                className="w-16 rounded border border-gold/50 bg-transparent px-1 py-0.5 text-right"
                value={monthlyCost}
                onChange={(e) => setMonthlyCost(e.target.value)}
              />
            </label>
            <label className="flex items-center gap-1">
              <input
                aria-label="赐专断之权"
                type="checkbox"
                checked={discretion}
                onChange={(e) => setDiscretion(e.target.checked)}
              />
              赐专断之权
            </label>
            <button
              type="button"
              className="ml-auto rounded border border-red bg-red px-3 py-1 text-paper disabled:opacity-50"
              disabled={submitting}
              onClick={() => void submitAuthorize()}
            >
              {submitting ? "授权中…" : "颁授权"}
            </button>
          </div>
          <p className="mt-1 text-xs text-dim">
            批专款后承办人逐月自理，不必再下旨；专款从所选库房真实扣减，府库不足则拒批。
          </p>
          {msg && <p className="mt-1 text-xs text-ink">{msg}</p>}
        </div>
      </section>

      <section>
        <p className="mb-1 font-kai text-lg text-ink">当前阶段</p>
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink">{data.progress?.phase}</span>
          <span className="ml-auto text-sm">
            {barPct === null ? "未定义" : Math.round(barPct)} / {data.progress?.target ?? 100}
          </span>
        </div>
        <div className="mt-1 h-2 w-full rounded bg-gold-light">
          <div
            className="h-2 rounded bg-red"
            style={{ width: barPct === null ? "0%" : `${barPct}%` }}
            title={barPct === null ? "未定义" : `${Math.round(barPct)}%`}
          />
        </div>
        {/* 本作特色：推进不靠"感觉"，给出算式与工期/停滞预警 */}
        {adv && (
          <div className="mt-2 rounded border border-gold/30 px-2 py-1 text-xs text-dim">
            {adv.forecast?.text ?? "本月推进读数缺失（未定义）"}
            {adv.months !== null && <span className="ml-2">预计工期 {def(adv.months)} 月</span>}
            {adv.stall_months !== null && adv.stall_months > 0 && (
              <span className="ml-2 text-red">已连续 {adv.stall_months} 月无实质推进</span>
            )}
          </div>
        )}
      </section>

      {/* 阻碍诊断（参考图只写"需推动"，我们给原因） */}
      <section>
        <p className="mb-1 font-kai text-lg text-ink">推进受阻于</p>
        {(adv?.blockers?.length ?? 0) === 0 ? (
          <p className="text-xs text-dim">无记录（未定义）</p>
        ) : (
          <ul className="list-inside list-disc text-sm">
            {adv!.blockers.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        )}
      </section>

      {/* 圣意与立场（本作特色：旨意要连着下才有效，逐月衰减） */}
      <section>
        <p className="mb-1 font-kai text-lg text-ink">圣意与立场</p>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded border border-gold/40 px-2 py-0.5">
            圣旨支持 <b className="text-ink">{signed(adv?.support_bonus)}</b>
          </span>
          <span className="rounded border border-gold/40 px-2 py-0.5">
            已施行旨意 {def(adv?.decree_count)}
          </span>
          <span className="rounded border border-gold/40 px-2 py-0.5">
            立场系数 <b className="text-ink">{signed(adv?.stance_mult)}</b>
          </span>
        </div>
        {(adv?.supporters?.length ?? 0) > 0 && (
          <p className="mt-1 text-xs text-dim">
            支持：{adv!.supporters.map((s) => `${s.name}（${def(s.influence)}）`).join("、")}
          </p>
        )}
        {(adv?.opposers?.length ?? 0) > 0 && (
          <p className="mt-1 text-xs text-red">
            反对：{adv!.opposers.map((s) => `${s.name}（${def(s.influence)}）`).join("、")}
          </p>
        )}
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