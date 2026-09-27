import { useEffect, useState } from "react";
import { getApiClient, type RegionBriefResult, type RegionPrefecture, type RegionRoute } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";

// 地方档案（州府级 / 省级）—— 点击舆图的府·州·路时弹出。
// 数据来源（**算法单点，前端不复制**）：
//   · 路级读数：/api/readouts::regions（core/region_brief.py::build_region_brief）
//   · 府级底盘：regions.prefectures（region_brief.py::build_prefecture_brief，Σ府==路级）
//   · POP 子池：state.prefectures[路].pops（含 农 的职位/丁口/隐户子池）
// 纪律：
//   ① 路级动态量（治安/城防/民心/士绅抵抗）**只有路级真值** → 面板标注「（全路）」，不假装府级独立；
//   ② 隐田**未清丈只显约值**（band + est），清丈后才显真数（后端已脱敏，前端不得反推）；
//   ③ 治安 = 100 − 动乱（**正极性**，越高越好），由后端单点派生。
type Dict = Record<string, unknown>;

const CLASSES = ["农", "士绅", "工匠", "商人", "官僚", "兵"] as const;
const FARM_POSITIONS = ["自耕农", "富农", "贫农", "佃农"] as const;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function pnum(p: Dict, key: string, def = 0): number {
  const v = p[key];
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function Bar({ value, tone = "ink", max = 100 }: { value: number; tone?: "good" | "warn" | "bad" | "ink"; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = { good: "bg-emerald-600", warn: "bg-amber-500", bad: "bg-red", ink: "bg-ink/60" }[tone];
  return (
    <span className="inline-block h-1.5 w-24 overflow-hidden rounded-full bg-ink/10 align-middle">
      <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
    </span>
  );
}
const toneHigh = (v: number): "good" | "warn" | "bad" => (v >= 60 ? "good" : v >= 40 ? "warn" : "bad");
const toneLow = (v: number): "good" | "warn" | "bad" => (v <= 30 ? "good" : v <= 55 ? "warn" : "bad");

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/40 py-1 last:border-0">
      <span className="shrink-0 font-kai text-[13px] text-dim">{label}</span>
      <span className="text-right font-kai text-[13.5px]">{value}</span>
    </div>
  );
}

export default function LocalArchivePanel({ props }: { props?: Dict }) {
  const selName = String(props?.name ?? "");
  const selKind = String(props?.kind ?? "circuit");
  const state = useGameStore((s) => s.state);
  const [regions, setRegions] = useState<RegionBriefResult | null>(null);
  const [note, setNote] = useState<string>("");

  useEffect(() => {
    let alive = true;
    getApiClient()
      .readouts()
      .then((r) => {
        if (!alive) return;
        const reg = (r as { regions?: RegionBriefResult } | null)?.regions ?? null;
        setRegions(reg);
        if (!reg) setNote("（读数不可用，以下回落 state 原始字段，派生值留空）");
      })
      .catch((e) => {
        if (!alive) return;
        setNote(`（读数不可用：${String((e as Error)?.message ?? e)}；回落 state 原始字段）`);
      });
    return () => {
      alive = false;
    };
  }, [selName]);

  const prefRows: RegionPrefecture[] = regions?.prefectures ?? [];
  const cityRow = prefRows.find((p) => p.name === selName);
  const routeName = selKind === "city" ? cityRow?.route ?? "" : selName;
  const route: RegionRoute | undefined = regions?.routes?.find((r) => r.name === routeName);
  const routePrefs = prefRows.filter((p) => p.route === routeName);
  const p = asDict(pick<Dict>(state, `prefectures.${routeName}`, {}));
  const pops = asDict(p.pops);
  const nong = asDict(pops["农"]);
  // ⚠️ 隐户按原设定「只知约值」：**面板层粗化到 5 万口**再显示（不把真值摆到玩家眼前）。
  //    更彻底的做法是在快照层 `backend/server.py::_state_to_dict` 对 `prefectures.*.pops.农.hidden`
  //    做与 `estate`/`loyalty` 同类的脱敏——**目前快照仍含真值**，此处只是展示层兜底（见方案 §8 待办）。
  const hiddenTrue = Math.round(pnum(nong, "hidden"));
  const hidden = Math.round(hiddenTrue / 50_000) * 50_000;
  const buildings = asDict(p.buildings);
  const buildingCount = Object.keys(buildings).length;

  const title = selKind === "city" ? `${selName}（${routeName || "—"}）` : `${selName || "—"}`;
  const security = route ? route.security : undefined;
  const surveyed = route?.surveyed;

  return (
    <div className="space-y-4">
      <div className="border-b border-border pb-2">
        <div className="font-kai text-[19px] font-bold tracking-[0.28em] text-ink">{title}</div>
        <div className="mt-1 text-[12px] text-dim">
          地方档案 · {selKind === "city" ? "州府" : "路（省）"} · {route?.controlled_by ?? String(p.controlled_by ?? "宋")}
          {note ? `　${note}` : ""}
        </div>
      </div>

      {/* 四格摘要（路级真值；府级面板同样显示"全路"值并标注） */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { k: "人口", v: route ? wan(route.population, "口") : wan(pnum(p, "population"), "口") },
          { k: "民心", v: route ? String(route.public_support) : String(pnum(p, "public_support", 50)) },
          { k: "治安", v: security === undefined ? "—" : `${security}（${route?.security_label ?? ""}）` },
          { k: "月税实收", v: route ? wan(route.tax_month, "贯") : "—" }
        ].map((it) => (
          <div key={it.k} className="rounded border border-border/60 bg-card/60 px-2 py-1.5">
            <div className="text-[11.5px] text-dim">{it.k}</div>
            <div className="font-kai text-[15px]">{it.v}</div>
          </div>
        ))}
      </div>

      {/* 军民要情：城防 / 治安 / 民心 + 杠杆提示 */}
      <section>
        <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">军民要情 <span className="text-[11px] text-dim">（全路）</span></div>
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[13px]">
            <span className="w-14 shrink-0 text-dim">治安</span>
            <Bar value={security ?? 50} tone={toneHigh(security ?? 50)} />
            <span>{security ?? "—"}</span>
            {route ? <span className="text-[11px] text-dim">（动乱 {route.unrest}）</span> : null}
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <span className="w-14 shrink-0 text-dim">城防</span>
            <Bar value={route?.city_defense ?? 40} tone={toneHigh(route?.city_defense ?? 40)} />
            <span>{route?.city_defense ?? "—"}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <span className="w-14 shrink-0 text-dim">民心</span>
            <Bar value={route?.public_support ?? 50} tone={toneHigh(route?.public_support ?? 50)} />
            <span>{route?.public_support ?? "—"}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <span className="w-14 shrink-0 text-dim">士绅抵抗</span>
            <Bar value={route?.gentry_resistance ?? 30} tone={toneLow(route?.gentry_resistance ?? 30)} />
            <span>{route?.gentry_resistance ?? "—"}</span>
          </div>
        </div>
        <div className="mt-1 text-[11.5px] leading-relaxed text-dim">
          杠杆：本路建筑 {buildingCount} 类、治理 {route?.govern ?? pnum(p, "govern", 50)}、识字率{" "}
          {route?.literacy ?? "—"}；高动乱会使工程降效（治安 &lt; 40 ⇔ 动乱 &gt; 60）。
        </div>
      </section>

      {/* 地方底册 */}
      <section>
        <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">地方底册</div>
        <div className="rounded border border-border/60 bg-card/40 px-2 py-1">
          <Row label="在册田亩" value={route ? wan(route.land, "亩") : "—"} />
          <Row
            label="隐田"
            value={
              surveyed === undefined ? "—"
                : surveyed
                  ? <span>{wan(route?.hidden_land ?? 0, "亩")}<span className="ml-1 text-[11px] text-emerald-700">已清丈</span></span>
                  : <span>约 {wan(route?.hidden_land_est ?? 0, "亩")}<span className="ml-1 text-[11px] text-dim">（{route?.hidden_land_band}，未清丈）</span></span>
            }
          />
          <Row label="隐户" value={<span>约 {wan(hidden, "口")}<span className="ml-1 text-[11px] text-dim">（未清丈，据税籍推估）</span></span>} />
          <Row label="粮食年产" value={route ? wan(route.grain_year, "石") : "—"} />
          <Row label="存粮" value={route ? <span>{wan(route.grain_stock, "石")}　<span className="text-[11px] text-dim">可支 {route.grain_months ?? "—"} 月</span></span> : "—"} />
          <Row label="月税实收" value={route ? <span>{wan(route.tax_month, "贯")}　<span className="text-[11px] text-dim">占全国 {((route.tax_share ?? 0) * 100).toFixed(1)}%</span></span> : "—"} />
          <Row label="驻军月饷 / 月粮" value={route ? `${wan(route.army_cash_month, "贯")} / ${wan(route.army_grain_month, "石")}` : "—"} />
        </div>
      </section>

      {/* 在地阶级：六类 + 隐户（第 7 行） */}
      <section>
        <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">
          在地阶级 · {CLASSES.length + 1} 类 <span className="text-[11px] text-dim">（全路）</span>
        </div>
        <div className="space-y-1">
          {CLASSES.map((c) => {
            const slot = asDict(pops[c]);
            return (
              <div key={c} className="rounded border border-border/50 bg-card/40 px-2 py-1">
                <div className="flex items-baseline justify-between">
                  <span className="font-kai text-[13.5px]">{c}</span>
                  <span className="text-[12.5px] text-dim">{wan(pnum(slot, "size"), "口")}</span>
                </div>
                {c === "农" ? (
                  <div className="mt-0.5 text-[11.5px] text-dim">
                    自耕农 {wan(pnum(nong, "自耕农"), "口")}｜富农 {wan(pnum(nong, "富农"), "口")}｜
                    贫农 {wan(pnum(nong, "贫农"), "口")}｜佃农 {wan(pnum(nong, "佃农"), "口")}　
                    丁 {wan(pnum(nong, "ding"), "口")}／口 {wan(pnum(nong, "kou"), "口")}
                  </div>
                ) : null}
              </div>
            );
          })}
          <div className="rounded border border-dashed border-border/60 bg-card/20 px-2 py-1">
            <div className="flex items-baseline justify-between">
              <span className="font-kai text-[13.5px] text-dim">隐户</span>
              <span className="text-[12.5px] text-dim">约 {wan(hidden, "口")}</span>
            </div>
            <div className="mt-0.5 text-[11.5px] text-dim">未在籍；隐田产出七成自留、三成归庇护士绅（清丈后归籍）</div>
          </div>
        </div>
      </section>

      {/* 州府名册（路级面板）/ 该府底盘（州府级面板） */}
      {selKind === "circuit" ? (
        <section>
          <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">
            所属州府 · {routePrefs.length} <span className="text-[11px] text-dim">（Σ府 == 路级，后端守恒）</span>
          </div>
          <div className="max-h-56 overflow-y-auto rounded border border-border/60">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-card/95 text-dim">
                <tr><th className="px-2 py-1 text-left">州府</th><th className="px-2 py-1 text-right">人口</th><th className="px-2 py-1 text-right">在册田亩</th><th className="px-2 py-1 text-right">月税</th></tr>
              </thead>
              <tbody>
                {routePrefs.map((r) => (
                  <tr key={r.name} className="border-t border-border/40">
                    <td className="px-2 py-0.5">{r.name}</td>
                    <td className="px-2 py-0.5 text-right">{wan(r.population, "")}</td>
                    <td className="px-2 py-0.5 text-right">{wan(r.land, "")}</td>
                    <td className="px-2 py-0.5 text-right">{wan(r.tax_month, "")}</td>
                  </tr>
                ))}
                {routePrefs.length === 0 ? (
                  <tr><td className="px-2 py-2 text-dim" colSpan={4}>（州府名册不可用：读数未就绪）</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section>
          <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">该府底盘 <span className="text-[11px] text-dim">（按路级实数分摊，Σ府 == 路级）</span></div>
          <div className="rounded border border-border/60 bg-card/40 px-2 py-1">
            <Row label="所属路" value={cityRow?.route ?? "—"} />
            <Row label="人口" value={cityRow ? wan(cityRow.population, "口") : "—"} />
            <Row label="户数" value={cityRow ? wan(cityRow.households, "户") : "—"} />
            <Row label="在册田亩" value={cityRow ? wan(cityRow.land, "亩") : "—"} />
            <Row label="粮食年产" value={cityRow ? wan(cityRow.grain_year, "石") : "—"} />
            <Row label="月税" value={cityRow ? wan(cityRow.tax_month, "贯") : "—"} />
            <Row label="占本路人口" value={cityRow ? `${((cityRow.share ?? 0) * 100).toFixed(1)}%` : "—"} />
          </div>
        </section>
      )}
    </div>
  );
}
