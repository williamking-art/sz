import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  getApiClient,
  type ExecutionChannels,
  type FactionBasisRow,
  type PopChannels,
  type SituationItem,
  type SituationReadoutResult
} from "../api/client";
import { useGameStore } from "../store/gameStore";

// 局势 —— 只读投影（core/situations.py 为单一权威源）。
// 三个页签：局势 / 六类 POP 心气 / 集团 ⊆ POP。
// 纪律（对齐规范 §2.2 §3.5 §3.7）：派生值只展示不重算；缺失一律显示"未定义"，不得当 0；
// 执行三通道用于解释"下了诏≠办了事"，数值由后端程序算，前端不伪造。

const SOURCE_LABEL: Record<SituationItem["source"], string> = {
  legacy: "帝国修正",
  focus: "国策",
  free_effect: "长期诏",
  event: "事件"
};
const SOURCE_BADGE: Record<SituationItem["source"], string> = {
  legacy: "bg-red/90 text-paper",
  focus: "bg-emerald-700/90 text-paper",
  free_effect: "bg-amber-600/90 text-paper",
  event: "bg-ink/80 text-paper"
};
const STATUS_LABEL: Record<SituationItem["status"], string> = {
  active: "在办",
  resolved: "已解",
  failed: "已败",
  cancelled: "已罢"
};

function sevTone(sev: number): "good" | "warn" | "bad" {
  return sev >= 80 ? "bad" : sev >= 60 ? "warn" : "good";
}

/** 真实进度条（缺失时不画条，显示"未定义"） */
function Bar({
  value,
  tone = "ink",
  width = "w-24"
}: {
  value: number | null;
  tone?: "good" | "warn" | "bad" | "ink";
  width?: string;
}) {
  if (value === null || !Number.isFinite(value)) {
    return <span className="text-xs italic text-dim">未定义</span>;
  }
  const pct = Math.max(0, Math.min(100, value));
  const color = { good: "bg-emerald-600", warn: "bg-amber-500", bad: "bg-red", ink: "bg-ink/60" }[tone];
  return (
    <span className={`inline-block h-1.5 ${width} overflow-hidden rounded-full bg-ink/10 align-middle`}>
      <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
    </span>
  );
}

function def(v: React.ReactNode, fallback = "未定义") {
  if (v === null || v === undefined || v === "") return <span className="italic text-dim">{fallback}</span>;
  return <>{v}</>;
}

/** 诏令实际效果一行式：吏治（强）× 民心/文书（弱）；军队仅军政类加成 */
function ExecutionLine({ ch }: { ch: ExecutionChannels | null }) {
  if (!ch) return <span className="text-xs italic text-dim">无执行通道（帝修不由诏令执行）</span>;
  const num = (v: number | null, digits = 2) =>
    typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "未定义";
  return (
    <span className="text-xs leading-relaxed text-ink-light">
      吏治（强关联）×{num(ch.clerks_mult)}　民心/识字率（弱关联）×{num(ch.civil_mult)}　<b className="text-red">实际效果 ×{num(ch.combined_mult)}</b>
      <span className="block text-[11px] text-dim">军队：{ch.military_applies ? (ch.military_mult !== null ? `强制施行加成（${ch.kind === "军政" ? "军政类" : "调兵强制"}），军队可靠度 ${num(ch.military_mult)}` : "已参与，但无驻军读数（未计入）") : "民政诏令未调兵（亦可调兵强制施行）"}{ch.official_support?.weighted != null ? `　官场配合度代理 ${ch.official_support.weighted.toFixed(0)}` : ""}</span>
      {ch.note ? <span className="block text-[11px] text-dim">{ch.note}</span> : null}
    </span>
  );
}

function ItemCard({ r }: { r: SituationItem }) {
  const [open, setOpen] = useState(false);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  return (
    <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
      <div className="flex items-center gap-2">
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] ${SOURCE_BADGE[r.source]}`}>
          {SOURCE_LABEL[r.source]}
        </span>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] ${
          sevTone(r.severity) === "bad" ? "bg-red text-paper" : sevTone(r.severity) === "warn" ? "bg-amber-500 text-paper" : "bg-emerald-600 text-paper"
        }`}>
          危急 {r.severity}
        </span>
        <span className="min-w-0 flex-1 truncate font-kai font-bold text-ink">{r.title}</span>
        <span className="shrink-0 text-[11px] text-dim">
          {STATUS_LABEL[r.status]}
          {r.phase ? `　${r.phase}` : ""}
        </span>
        {r.region_hint && (
          <button
            onClick={() => pushOverlay({ kind: "prefecture", title: "州县", props: { picked: r.region_hint } })}
            title={`打开 ${r.region_hint} 州路面板`}
            className="shrink-0 rounded border border-gold/60 px-1.5 py-0.5 text-[11px] text-ink transition hover:bg-gold-light"
          >
            {r.region_hint}
          </button>
        )}
      </div>

      <div className="mt-1 flex items-center gap-2 text-[13px] text-ink">
        <Bar value={r.bar_value} tone={r.bar_value === null ? "ink" : sevTone(100 - r.bar_value)} />
        <span className="text-ink-light">
          {r.bar_value === null ? "无进度" : `${r.bar_value} / 100`}
          {r.progress_text ? `　${r.progress_text}` : ""}
        </span>
      </div>

      <div className="mt-1 space-y-0.5 text-[13px] text-ink">
        <p>达成：{def(r.resolve_condition_text, "未定义（不编造）")}</p>
        {r.fail_condition_text ? <p>失败：{r.fail_condition_text}</p> : null}
        {r.ongoing_text ? <p>持续代价：{r.ongoing_text}</p> : null}
      </div>

      {(r.pop_highlights?.length || r.channel_highlights?.length) ? (
        <div className="mt-1 text-[12px] text-dim">
          {r.pop_highlights?.length ? <p>民力：{r.pop_highlights.join("；")}</p> : null}
          {r.channel_highlights?.length ? <p>心气：{r.channel_highlights.join("；")}</p> : null}
        </div>
      ) : null}

      <div className="mt-1 border-t border-gold/30 pt-1">
        <ExecutionLine ch={r.execution_channels} />
      </div>

      {r.timeline.length > 0 && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="mt-1 text-[11px] text-dim underline decoration-dotted"
        >
          {open ? "收起" : `展开 ${r.timeline.length} 条月报线索`}
        </button>
      )}
      {open && (
        <ul className="mt-1 space-y-0.5 text-[12px] text-ink-light">
          {r.timeline.map((t, i) => (
            <li key={i}>
              <span className="text-dim">第 {t.turn} 月 · {t.kind}（{t.source === "ai" ? "AI" : "程序"}）</span>{" "}
              {t.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 六类 POP 心气：nation（最低/均） + 逐路明细 */
function RouteRow({ name, row }: { name: string; row: Record<string, number | null> }) {
  const cells: [string, number | null][] = [
    ["农", row["农"]],
    ["绅", row["士绅"]],
    ["工", row["工匠"]],
    ["商", row["商人"]],
    ["官", row["官僚"]],
    ["兵", row["兵"]],
    ["吏", row["吏"]]
  ];
  const tone = (k: string, v: number | null): "good" | "warn" | "bad" => {
    if (v === null || !Number.isFinite(v)) return "warn";
    if (k === "吏" || k === "官") return v <= 20 ? "good" : v <= 45 ? "warn" : "bad";
    if (k === "兵" || k === "农") return v >= 60 ? "good" : v >= 40 ? "warn" : "bad";
    return v <= 30 ? "good" : v <= 55 ? "warn" : "bad";
  };
  return (
    <div className="flex items-center gap-1.5 py-0.5 text-[12px] text-ink">
      <span className="w-20 shrink-0 truncate">{name}</span>
      {cells.map(([k, v]) => (
        <span key={k} className="flex w-16 shrink-0 items-center gap-1">
          <span className="text-dim">{k}</span>
          {v === null || !Number.isFinite(v) ? (
            <span className="text-[11px] italic text-dim">—</span>
          ) : (
            <>
              <Bar value={v} tone={tone(k, v)} width="w-6" />
              <span className="tabular-nums">{v.toFixed(0)}</span>
            </>
          )}
        </span>
      ))}
    </div>
  );
}

/** 集团 ⊆ POP：主行展示子集说明与占比，绝不与 POP 并列 */
function FactionRow({ name, row }: { name: string; row: FactionBasisRow }) {
  const b = row.basis_readout;
  const share = b?.share ?? null;
  return (
    <div className="border-b border-gold/25 py-1.5 last:border-b-0">
      <div className="flex items-center gap-2 text-[13px] text-ink">
        <span className="w-20 shrink-0 font-kai font-bold">{name}</span>
        <span className="text-ink-light">
          满意度 {row.satisfaction?.toFixed(0) ?? "未定义"}　影响力 {row.influence?.toFixed(0) ?? "未定义"}
          {row.leader ? `　领袖 ${row.leader}` : ""}
        </span>
      </div>
      {b ? (
        <div className="mt-0.5 flex items-center gap-2 text-[12px] text-ink-light">
          <span>{b.subset_note}</span>
          {share !== null && <Bar value={share * 100} tone="ink" width="w-16" />}
        </div>
      ) : (
        <p className="mt-0.5 text-[12px] italic text-red">未声明 POP 基本盘（势力无源）</p>
      )}
      {row.basis_errors.length > 0 && (
        <p className="text-[11px] text-red">{row.basis_errors.join("；")}</p>
      )}
    </div>
  );
}

export default function SituationPanel({ props }: { props?: { tab?: "items" | "pop" | "faction" } }) {
  const [data, setData] = useState<SituationReadoutResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<"items" | "pop" | "faction">(props?.tab ?? "items");
  const [pickedRoute, setPickedRoute] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (!alive) return;
        const s = res.situations;
        if (s && Array.isArray(s.items)) setData(s);
        else setErr("局势读数为空（后端 /api/readouts 未返回 situations）");
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const items = useMemo(
    () => [...(data?.items ?? [])].sort((a, b) => b.severity - a.severity || a.id.localeCompare(b.id)),
    [data]
  );
  const pop: PopChannels | undefined = data?.pop_channels;
  const routes = useMemo(() => Object.entries(pop?.by_route ?? {}), [pop]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 px-1 text-xs">
        {([["items", "局势"], ["pop", "六类心气"], ["faction", "集团⊆POP"]] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`rounded border px-2.5 py-1 transition ${
              tab === k ? "border-red bg-red text-paper" : "border-gold/60 text-ink hover:bg-gold-light"
            }`}
          >
            {label}
          </button>
        ))}
        {data?.by_status && (
          <span className="ml-auto text-dim">
            {Object.entries(data.by_status).map(([k, v]) => `${STATUS_LABEL[k as SituationItem["status"]] ?? k} ${v}`).join("　")}
          </span>
        )}
        {loading && <Loader2 size={13} className="animate-spin text-dim" />}
      </div>

      {data?.readout_status === "partial" && (
        <p className="rounded border border-red/50 bg-red/5 px-2 py-1 text-xs text-red">
          读数不完整（{(data.readout_errors ?? []).join("；") || "派生失败"}）——缺失项显示"未定义"，请勿当作 0。
        </p>
      )}

      {tab === "items" && (
        <div className="space-y-2">
          <p className="px-1 text-xs leading-relaxed text-dim">
            局势按<b>危急</b>降序。进度与达成/失败条件由程序派生；<b>下了诏 ≠ 办了事</b>——
            下方"执行通道"给出该事本月实际能推得动的折扣（吏治 × 军队督行）。
          </p>
          {items.map((r) => <ItemCard key={r.id} r={r} />)}
          {items.length === 0 && !loading && <p className="px-1 py-6 text-center text-dim">当前无在办局势。</p>}
        </div>
      )}

      {tab === "pop" && (
        <div className="space-y-2">
          <p className="px-1 text-xs leading-relaxed text-dim">
            POP 不止钱粮：<b>六类各有心气</b>（农=民心、士绅=抵抗、工匠/商人=市面与欠缴、官僚=冗官与派系满意度、兵=军心与欠饷），
            外加<b>吏</b>（官僚 POP 的子池，非第 7 类）。逐路取值——各省结构不同，心气不同。
          </p>
          {pop?.nation && (
            <div className="rounded-lg border border-gold/40 bg-paper/60 p-3 text-[12.5px] text-ink">
              <p className="mb-1 font-kai tracking-widest text-red">全国截面</p>
              {Object.entries(pop.nation).map(([cls, vals]) => (
                <p key={cls}>
                  <b>{cls}</b>
                  {pop.channels[cls] ? <span className="text-dim">（{pop.channels[cls].label}）</span> : null}：
                  {Object.entries(vals).map(([k, v]) => {
                    if (v === null || v === undefined) return `　${k} 未定义`;
                    if (typeof v === "object") return `　${k} ${v.最低}~${v.均}`;
                    return `　${k} ${typeof v === "number" ? v.toFixed(0) : v}`;
                  })}
                </p>
              ))}
            </div>
          )}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-2">
            <p className="mb-1 px-1 font-kai text-[12.5px] tracking-widest text-red">
              逐路心气（农/绅/工/商/官/兵/吏；"官/吏"为越低越好，"兵/农"为越高越好）
            </p>
            <div className="max-h-72 overflow-y-auto">
              {routes.map(([name, row]) => (
                <button key={name} onClick={() => setPickedRoute(name === pickedRoute ? null : name)} className="w-full text-left">
                  <RouteRow name={name} row={row} />
                </button>
              ))}
            </div>
          </div>
          {pickedRoute && pop && (
            <div className="rounded-lg border border-gold/40 bg-paper/60 p-3 text-[12px] text-ink-light">
              <div className="mb-1 flex items-center gap-2">
                <button
                  onClick={() => setPickedRoute(null)}
                  className="flex items-center gap-1 rounded bg-paper/60 px-2 py-1 text-ink transition hover:bg-gold-light"
                >
                  <ArrowLeft size={13} /> 返回
                </button>
                <span className="font-kai font-bold text-ink">{pickedRoute}</span>
              </div>
              {Object.entries(pop.channels).map(([cls, ch]) => {
                const v = pop.by_route[pickedRoute]?.[cls];
                return (
                  <p key={cls}>
                    {cls}·{ch.label}：{v === null || v === undefined ? "未定义" : v.toFixed(1)}
                    <span className="text-dim">　（{ch.primary}{ch.secondary ? ` / ${ch.secondary}` : ""}）</span>
                  </p>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === "faction" && (
        <div className="space-y-2">
          <p className="px-1 text-xs leading-relaxed text-dim">
            集团<b>不是与 POP 并列的实体</b>，而是某阶级（某子池、某路域）的<b>子集</b>——
            如西军集团 ⊆ 兵 POP 的路域子集。势力源于人口与财赋；改革会改变 POP 得失，也可能催生新集团。
          </p>
          {data?.faction_channels && !data.faction_channels.declared && (
            <p className="rounded border border-red/50 bg-red/5 px-2 py-1 text-xs text-red">
              有集团未声明 POP 基本盘：{(data.faction_channels.basis_errors ?? []).join("；")}
            </p>
          )}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
            {Object.entries(data?.faction_channels?.factions ?? {}).map(([name, row]) => (
              <FactionRow key={name} name={name} row={row} />
            ))}
          </div>
          {(data?.faction_channels?.emerging?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-gold/40 bg-paper/60 p-3 text-[12.5px] text-ink">
              <p className="mb-1 font-kai tracking-widest text-red">在场改革 → POP 得失 → 可能的新集团</p>
              {data!.faction_channels!.emerging.map((e) => (
                <div key={e.reform} className="mb-1.5 last:mb-0">
                  <p className="font-bold">{e.label}</p>
                  <p className="text-ink-light">
                    受益 POP：{e.gain.map((g) => `${g.class}（${g.why}）`).join("、") || "—"}
                  </p>
                  <p className="text-ink-light">
                    受损 POP：{e.lose.map((l) => `${l.class}（${l.why}）`).join("、") || "—"}
                  </p>
                  {e.emergent.map((f) => (
                    <p key={String(f.name)} className="text-dim">
                      或催生「{f.name}」——{f.desc}
                      {f.basis_errors.length > 0 ? `（⚠ ${f.basis_errors.join("；")}）` : ""}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {err && <p className="px-1 text-xs text-dim">{err}</p>}
    </div>
  );
}
