import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Flame, Loader2 } from "lucide-react";
import { getApiClient, type RegionBriefResult, type RegionRoute, type SituationItem } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";
import constants from "../data/constants.json";

// 州县治理 —— 三视图（列表 / 单路详情 / 田亩户籍总览）。
// 派生读数来自 /api/readouts::regions（core/region_brief.py 为单一权威源）：
// 到账后月税、驻军月饷、粮储安全垫、风险分与原因 —— 前端只展示，不复制算法。
// 后端读数不可用时回落 state.prefectures（保证面板不空、不假造派生值）。
type Dict = Record<string, unknown>;

const PREFECTURE_LIST = constants.prefecture_list as string[];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function pnum(p: Dict, key: string, def = 0): number {
  const v = p[key];
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

/** 真实进度条（替代旧 ASCII 条 █▓▒░）：tone 表语义，红色=需要处置。 */
function Bar({ value, tone = "ink", max = 100 }: { value: number; tone?: "good" | "warn" | "bad" | "ink"; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = { good: "bg-emerald-600", warn: "bg-amber-500", bad: "bg-red", ink: "bg-ink/60" }[tone];
  return (
    <span className="inline-block h-1.5 w-20 overflow-hidden rounded-full bg-ink/10 align-middle">
      <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
    </span>
  );
}

const RISK_BADGE: Record<string, string> = {
  安: "bg-emerald-600/85 text-paper",
  警: "bg-amber-500/90 text-paper",
  危: "bg-red text-paper"
};
const toneOf = (v: number, goodHigh = true): "good" | "warn" | "bad" =>
  goodHigh ? (v >= 60 ? "good" : v >= 40 ? "warn" : "bad") : (v <= 30 ? "good" : v <= 55 ? "warn" : "bad");

/** 后端不可用时的最小回落行（不做任何派生，缺的字段留空） */
function fallbackRows(prefectures: Dict): RegionRoute[] {
  return PREFECTURE_LIST.map((name) => {
    const p = asDict(prefectures[name]);
    const support = pnum(p, "public_support", pnum(p, "mood", 50));
    const unrest = pnum(p, "unrest", 0);
    return {
      name,
      display_name: String(p.name ?? name),
      controlled_by: String(p.controlled_by ?? "宋"),
      households: pnum(p, "households"),
      population: pnum(p, "population"),
      land: pnum(p, "land"),
      hidden_land: pnum(p, "hidden_land"),
      mood: pnum(p, "mood"),
      govern: pnum(p, "govern"),
      public_support: support,
      gentry_resistance: pnum(p, "gentry_resistance", 30),
      city_defense: pnum(p, "city_defense", 40),
      unrest,
      fiscal: pnum(p, "fiscal", 50),
      literacy: typeof p.literacy === "number" ? (p.literacy as number) : null,
      grain_year: pnum(p, "grain"),
      grain_stock: pnum(p, "storage") + pnum(p, "changping_stock"),
      grain_months: null,
      tax_month: 0,
      tax_share: 0,
      army_cash_month: 0,
      army_grain_month: 0,
      risk_score: -1,
      risk_label: "警",
      risk_hints: ["读数未就绪（后端 /api/readouts 不可用）"]
    };
  });
}

export default function PrefecturePanel({ props }: { props?: { picked?: string } }) {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [brief, setBrief] = useState<RegionBriefResult | null>(null);
  const [sits, setSits] = useState<SituationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "detail" | "land">("list");
  const [sortKey, setSortKey] = useState<"risk" | "support" | "unrest" | "tax">("risk");
  const [selected, setSelected] = useState<string | null>(props?.picked ?? null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (!alive) return;
        if (res.regions && Array.isArray(res.regions.routes) && res.regions.routes.length) {
          setBrief(res.regions);
        } else {
          setErr("州路读数为空，已回落本地快照");
        }
        // 本路局势（core/situations.py 派生）：州路与局势**双向联动**（§12 第 10 项）
        setSits(res.situations?.items ?? []);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // 与 `props.picked` 同步（从局势面板「跳州路」打开时定位到该路详情）
  useEffect(() => {
    if (props?.picked) {
      setSelected(props.picked);
      setView("detail");
    }
  }, [props?.picked]);

  const prefectures = asDict(pick(state, "prefectures", {}));
  const rows: RegionRoute[] = useMemo(
    () => brief?.routes ?? fallbackRows(prefectures),
    [brief, prefectures]
  );
  const sorted = useMemo(() => {
    const key = sortKey;
    return [...rows].sort((a, b) => {
      if (key === "risk") return b.risk_score - a.risk_score;
      if (key === "support") return a.public_support - b.public_support;
      if (key === "unrest") return b.unrest - a.unrest;
      return b.tax_month - a.tax_month;
    });
  }, [rows, sortKey]);

  // ---- 视图三：田亩户籍总览（读数 + 本地汇总） ----
  if (view === "land") {
    const land = asDict(pick(state, "land", {}));
    const population = pick<number>(state, "population", 0);
    let wealth = 0;
    let grain = 0;
    for (const name of PREFECTURE_LIST) {
      for (const pop of Object.values(asDict(asDict(prefectures[name]).pops))) {
        wealth += pnum(asDict(pop), "wealth");
        grain += pnum(asDict(pop), "grain");
      }
    }
    return (
      <div className="space-y-4">
        <button
          onClick={() => setView("list")}
          className="flex items-center gap-1.5 rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          <ArrowLeft size={14} /> 返回州县列表
        </button>
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <p className="mb-2 font-kai text-[15px] font-bold tracking-[0.3em] text-red">田 亩 户 籍 总 览</p>
          <div className="space-y-1 text-[13px] leading-relaxed text-ink">
            <p>全国垦田：{wan(pnum(land, "cultivated"), "亩")}（隐漏率 {Math.round(pnum(land, "hidden_rate") * 100)}%）</p>
            <p>在籍户数：{wan(pnum(land, "households"), "户")}　约 {wan(population, "口")}</p>
            <p>荒闲田土：{wan(pnum(land, "wasteland"), "亩")}　亩产系数：{pnum(land, "yield", 1).toFixed(2)}</p>
            <p>民间 POP 汇总：持钱 {wan(wealth, "贯")}　存粮 {wan(grain, "石")}</p>
          </div>
        </div>
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <p className="mb-2 font-kai text-sm tracking-widest text-red">诸路 POP 人口（万：农/绅/工/商/官/兵）</p>
          <div className="max-h-64 overflow-y-auto text-[13px] leading-relaxed text-ink">
            {PREFECTURE_LIST.map((name) => {
              const pops = asDict(asDict(prefectures[name]).pops);
              const w = (v: number) => (v >= 1e4 ? `${Math.round(v / 1e4)}` : String(v));
              const pop = (k: string) => asDict(pops[k]);
              return (
                <p key={name}>
                  {name}：农{w(pnum(pop("农"), "size"))} 绅{w(pnum(pop("士绅"), "size"))} 工{w(pnum(pop("工匠"), "size"))}{" "}
                  商{w(pnum(pop("商人"), "size"))} 官{w(pnum(pop("官僚"), "size"))} 兵{w(pnum(pop("兵"), "size"))}
                </p>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // ---- 视图二：单路详情（含派生解释） ----
  if (view === "detail" && selected) {
    const r = rows.find((x) => x.name === selected);
    if (!r) return <p className="py-10 text-center text-dim">该路读数不可用。</p>;
    const blocks: { title: string; items: [string, React.ReactNode][] }[] = [
      {
        title: "户口与田亩",
        items: [
          ["户数", wan(r.households, "户")],
          ["人口", wan(r.population, "口")],
          ["垦田", `${wan(r.land, "亩")}（隐田 ${wan(r.hidden_land, "亩")}）`]
        ]
      },
      {
        title: "民生",
        items: [
          ["民情", <>{<Bar value={r.mood} tone={toneOf(r.mood)} />} {r.mood.toFixed(1)}</>],
          ["治理", <>{<Bar value={r.govern} tone={toneOf(r.govern)} />} {r.govern.toFixed(1)}</>],
          ["民心", <>{<Bar value={r.public_support} tone={toneOf(r.public_support)} />} {r.public_support.toFixed(1)}</>],
          // 识字率（各地各类 POP 自有值按人口加权派生）：政令"写得下去、读得懂"的弱关联项
          ["识字率", r.literacy === null || r.literacy === undefined
            ? <span className="text-xs italic text-dim">未定义</span>
            : <>{<Bar value={r.literacy} tone={toneOf(r.literacy)} />} {r.literacy.toFixed(1)}</>],
          ["士绅阻力", <>{<Bar value={r.gentry_resistance} tone={toneOf(r.gentry_resistance, false)} />} {r.gentry_resistance.toFixed(1)}</>],
          ["城防", <>{<Bar value={r.city_defense} tone={toneOf(r.city_defense)} />} {r.city_defense.toFixed(1)}</>],
          ["动乱", <>{<Bar value={r.unrest} tone={toneOf(r.unrest, false)} />} {r.unrest.toFixed(1)}</>]
        ]
      },
      {
        title: "粮储与财政",
        items: [
          ["粮产", `${wan(r.grain_year, "石")}/年`],
          ["存粮", `${wan(r.grain_stock, "石")}${r.grain_months !== null ? `　可支 ${r.grain_months.toFixed(2)} 月` : ""}`],
          ["到账月税", r.tax_month > 0 ? `${wan(r.tax_month, "贯")}　占全国 ${(r.tax_share * 100).toFixed(1)}%` : "—"],
          ["驻军月饷", r.army_cash_month > 0 ? wan(r.army_cash_month, "贯") : "—"],
          ["驻军月粮", r.army_grain_month > 0 ? `${wan(r.army_grain_month, "石")}` : "—"],
          ["财政档", <>{<Bar value={r.fiscal} tone={toneOf(r.fiscal)} />} {r.fiscal.toFixed(1)}</>]
        ]
      },
      { title: "归属", items: [["控制势力", r.controlled_by]] }
    ];
    return (
      <div className="space-y-3">
        <button
          onClick={() => setView("list")}
          className="flex items-center gap-1.5 rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          <ArrowLeft size={14} /> 返回州县列表
        </button>
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="font-kai text-lg font-bold text-ink">{r.display_name}</p>
            <span className={`rounded px-2 py-0.5 text-xs ${RISK_BADGE[r.risk_label] ?? ""}`}>
              {r.risk_label}
              {r.risk_score >= 0 ? `　风险 ${r.risk_score.toFixed(0)}` : ""}
            </span>
          </div>
          {r.risk_score >= 0 && (
            <p className="mb-2 text-xs text-ink-light">
              风险成因：{r.risk_hints.join("；")}
            </p>
          )}
          {blocks.map((blk) => (
            <div key={blk.title} className="mb-2">
              <p className="mb-0.5 font-kai text-sm tracking-widest text-red">{blk.title}</p>
              {blk.items.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 py-0.5 text-sm">
                  <span className="shrink-0 text-ink-light">{k}</span>
                  <span className="text-ink">{v}</span>
                </div>
              ))}
            </div>
          ))}

          {/* 本路局势：把与本地相关的长期目标并列出来（一望可知"这里正在出什么事"） */}
          {(() => {
            const local = sits.filter((x) => x.region_hint === r.name);
            if (local.length === 0) return null;
            return (
              <div className="mb-2 border-t border-gold/30 pt-2">
                <p className="mb-0.5 font-kai text-sm tracking-widest text-red">本路局势</p>
                {local.map((x) => (
                  <div key={x.id} className="py-0.5 text-sm text-ink">
                    <span className="mr-1 rounded bg-red/85 px-1 text-[11px] text-paper">危急 {x.severity}</span>
                    {x.title}
                    <span className="ml-1 text-ink-light">
                      {x.bar_value === null ? "（无进度）" : `（${x.bar_value}/100）`}
                    </span>
                    {x.execution_channels?.note ? (
                      <span className="block text-[11px] text-dim">{x.execution_channels.note}</span>
                    ) : null}
                  </div>
                ))}
                <button
                  onClick={() => pushOverlay({ kind: "situation", title: "局势" })}
                  className="mt-1 flex items-center gap-1 rounded border border-gold/60 bg-paper/60 px-2 py-1 text-[12px] text-ink transition hover:bg-gold-light"
                >
                  <Flame size={13} /> 打开局势面板（含六类心气与集团⊆POP）
                </button>
              </div>
            );
          })()}
        </div>
        <p className="px-1 text-xs leading-relaxed text-dim">
          到账月税＝本路二税折色实收（已乘到账率）；存粮可支月数＝（州仓＋常平仓）÷ 各路 POP 月耗。
          地方之政（劝农、赈灾、平盗、减税）请经「拟旨」施行，效果由中枢推演落地。
        </p>
      </div>
    );
  }

  // ---- 视图一：州县列表（可按 风险/民心/动乱/税入 排序） ----
  const nation = brief?.nation;
  return (
    <div className="space-y-3">
      <p className="px-1 text-sm leading-relaxed text-dim">
        诸路安则社稷安。默认按<b>风险</b>降序——最可能出事的路排在最前。
      </p>

      {nation && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3 text-[13px] text-ink">
          <p className="text-ink-light">
            二十路合计：户 {wan(nation.households, "户")}　存粮 {wan(nation.grain_stock, "石")}　
            到账月税 {wan(nation.tax_month, "贯")}　驻军月饷 {wan(nation.army_cash_month, "贯")}　
            全国民心（人口加权）{nation.public_support_weighted.toFixed(1)}
          </p>
          <p className="mt-1">
            风险分布：
            <span className="ml-1 rounded bg-emerald-600/85 px-1.5 text-paper">安 {nation.risk_counts.安}</span>
            <span className="ml-1 rounded bg-amber-500/90 px-1.5 text-paper">警 {nation.risk_counts.警}</span>
            <span className="ml-1 rounded bg-red px-1.5 text-paper">危 {nation.risk_counts.危}</span>
          </p>
        </div>
      )}

      {brief?.readout_status === "partial" && (
        <p className="rounded border border-red/50 bg-red/5 px-2 py-1 text-xs text-red">
          读数不完整（{(brief.readout_errors ?? []).join("；") || "核心派生失败"}）——
          相关数字已回落为 0，请勿据此判定"无税入/无驻军"。
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 px-1 text-xs">
        <span className="text-dim">排序：</span>
        {([["risk", "风险"], ["support", "民心↑"], ["unrest", "动乱"], ["tax", "税入"]] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setSortKey(k)}
            className={`rounded border px-2 py-0.5 transition ${
              sortKey === k ? "border-red bg-red text-paper" : "border-gold/60 text-ink hover:bg-gold-light"
            }`}
          >
            {label}
          </button>
        ))}
        {loading && <Loader2 size={13} className="animate-spin text-dim" />}
      </div>

      <div className="rounded-lg border border-gold/40 bg-paper/60 p-2">
        {sorted.map((r) => (
          <button
            key={r.name}
            onClick={() => { setSelected(r.name); setView("detail"); }}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[13px] text-ink transition hover:bg-gold-light"
          >
            <span className={`w-6 shrink-0 rounded text-center text-[11px] text-paper ${RISK_BADGE[r.risk_label] ?? ""}`}>
              {r.risk_label}
            </span>
            <span className="w-20 shrink-0 truncate">{r.display_name}</span>
            <span className="shrink-0 text-ink-light">民心</span>
            <Bar value={r.public_support} tone={toneOf(r.public_support)} />
            <span className="shrink-0 text-ink-light">动乱</span>
            <Bar value={r.unrest} tone={toneOf(r.unrest, false)} />
            <span className="ml-auto shrink-0 text-right text-ink-light">
              {wan(r.households, "户")}　税 {r.tax_month > 0 ? wan(r.tax_month, "贯") : "—"}
            </span>
          </button>
        ))}
      </div>

      {err && <p className="px-1 text-xs text-dim">{err}</p>}

      <div className="flex justify-center gap-3">
        <button
          onClick={() => setView("land")}
          className="rounded-lg border border-gold/60 bg-paper/60 px-5 py-2 font-kai text-sm tracking-widest text-ink transition hover:bg-gold-light"
        >
          田 亩 户 籍 总 览
        </button>
      </div>
    </div>
  );
}
