import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";
import { EFFECT_NAME } from "../utils/effects";
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

// 蓝图 effect dict → 中文串（键表与 content/data.py::TECH_EFFECT_LABELS 对齐；
// 前端保留少量既有别名译名）。
// 修复：原表仅 12 键，granary_cap / workshop_output / decree_speed / exam_talent /
// epidemic_risk 等未覆盖 → 面板直接把**原始键名**显示给玩家。
const EFFECT_LABELS: Record<string, string> = {
  // —— 既有译名（保持不变）——
  yield_bonus: "粮产", trade_income: "贸易收入", production: "制造",
  build_speed: "营造速度", build_cost: "营造成本", defense_bonus: "城防",
  flood_risk: "水患", canal_efficiency: "漕运", army_power: "军力",
  commerce: "商税", pop_growth: "人口", tech_speed: "研习速度",
  // —— 补全（对齐 content/data.py::TECH_EFFECT_LABELS）——
  mining_income: "矿冶收入", training: "操练", equipment: "武备", morale: "士气",
  epidemic_risk: "疫病风险", prestige: "皇威", prestige_gain: "皇威增益",
  exam_talent: "科举才俊", granary_cap: "扩仓容", workshop_output: "增作坊产出",
  decree_speed: "政令速率", bandwidth_bonus: "圣裁带宽", treasury: "国库",
  tax: "税入", grain: "粮储", unrest: "民乱", loyalty: "忠诚",
  satisfaction: "满意度", influence: "势力", power: "实力", population: "人口",
  ship_capacity: "舟运运力", naval_power: "水师", firepower: "火力",
  fortification: "城防工事", garrison: "驻军", art_gain: "艺术造诣",
  health_cost: "健康消耗", taoism_gain: "道术造诣", pleasure_gain: "逸乐",
  clergy_satisfaction: "僧道满意度"
};

function effectText(eff: unknown): string {
  // 本表（更细）优先 → 统一词表兜底 → 皆无登记则返回空串，绝不直出英文键名
  if (typeof eff === "string") return EFFECT_LABELS[eff] ?? EFFECT_NAME[eff] ?? "";
  if (eff && typeof eff === "object") {
    return Object.entries(asDict(eff))
      .map(([k, v]) => {
        const label = EFFECT_LABELS[k] ?? EFFECT_NAME[k];
        if (!label) return "";
        if (typeof v === "boolean") return `${label}${v ? "行" : "止"}`;
        if (typeof v === "number" && v !== 0) {
          const pct = Math.abs(v) < 2 ? `${v > 0 ? "+" : ""}${Math.round(v * 100)}%` : `${v > 0 ? "+" : ""}${v}`;
          return `${label}${pct}`;
        }
        return `${label}${String(v)}`;
      })
      .filter(Boolean)
      .join("、");
  }
  if (typeof eff === "number") return String(eff);
  return "";
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
