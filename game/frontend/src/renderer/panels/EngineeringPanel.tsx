import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";
import constants from "../data/constants.json";

// 工程营造 —— 对齐 game/ui/panels_economy.py::_panel_engineering（L1146）
// 可建工程（政府建筑 + 科技蓝图）+ 已开工工程（从在办筛「工程」类）。只读展示。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

// 蓝图 effect dict → 中文串（对齐 Tk _TECH_EFFECT_LABELS 简化）
const EFFECT_LABELS: Record<string, string> = {
  yield_bonus: "粮产", trade_income: "贸易收入", production: "制造",
  build_speed: "营造速度", build_cost: "营造成本", defense_bonus: "城防",
  flood_risk: "水患", canal_efficiency: "漕运", army_power: "军力",
  commerce: "商税", pop_growth: "人口", tech_speed: "研习速度"
};

function effectText(eff: unknown): string {
  if (typeof eff === "string") return EFFECT_LABELS[eff] ?? eff;
  if (eff && typeof eff === "object") {
    return Object.entries(asDict(eff))
      .map(([k, v]) => {
        const label = EFFECT_LABELS[k] ?? k;
        if (typeof v === "number" && v !== 0) {
          const pct = Math.abs(v) < 2 ? `${v > 0 ? "+" : ""}${Math.round(v * 100)}%` : `${v > 0 ? "+" : ""}${v}`;
          return `${label}${pct}`;
        }
        return `${label}${String(v)}`;
      })
      .join("、");
  }
  return String(eff ?? "");
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

export default function EngineeringPanel() {
  const state = useGameStore((s) => s.state);
  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无工程可览。</p>;
  }

  // 可建工程：政府建筑 + 科技蓝图
  const items: { name: string; cost: number; eff: string }[] = [];
  for (const [bname, bcfgRaw] of Object.entries(asDict(constants.building_std))) {
    const bcfg = asDict(bcfgRaw);
    items.push({
      name: bname,
      cost: asNum(bcfg.base_cost),
      eff: effectText(bcfg.effect)
    });
  }
  for (const [bid, bcfgRaw] of Object.entries(asDict(constants.building_blueprints))) {
    const bcfg = asDict(bcfgRaw);
    items.push({
      name: asStr(bcfg.name, bid),
      cost: asNum(asDict(bcfg.cost).silver),
      eff: effectText(bcfg.effect)
    });
  }
  const shown = items.slice(0, 12);

  // 已开工：从在办筛「工程」类
  const opened: Dict[] = [];
  for (const grp of ["longterm_public", "longterm_secret"] as const) {
    for (const it of pick<Dict[]>(state, grp, [])) {
      if (asStr(it.cat).includes("工程") || asStr(it.title).includes("工程")) {
        opened.push(it);
      }
    }
  }

  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        山川城邑，营建之事。凡兴土工役之诏，皆由圣旨推演。
      </p>

      {/* 可建工程 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="可 建 工 程" />
        <div className="mt-1.5">
          {shown.length ? (
            shown.map((it, i) => (
              <p key={i} className="py-0.5 text-sm text-ink">
                · {it.name}（{Math.floor(it.cost / 10000)}万贯）{it.eff}
              </p>
            ))
          ) : (
            <p className="py-1 text-sm text-dim">— 暂无可见工程 —</p>
          )}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-dim">
          （拟诏「营造」某建筑以兴工；工程类诏令经圣旨推演落地）
        </p>
      </div>

      {/* 已开工 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="已 开 工" />
        <div className="mt-1.5">
          {opened.length ? (
            opened.slice(0, 10).map((it, i) => (
              <p key={i} className="py-1 text-sm text-ink">
                · {asStr(it.title, asStr(it.cat, "工程"))}：承办 {asStr(it.owner, "—")}　
                进度 {Math.round(asNum(it.progress))}%
              </p>
            ))
          ) : (
            <p className="py-1 text-sm text-dim">— 暂无开工之役 —</p>
          )}
        </div>
      </div>
    </div>
  );
}
