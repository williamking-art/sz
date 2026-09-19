import { useState } from "react";
import { useGameStore, pick } from "../store/gameStore";
import { getApiClient } from "../api/client";
import { humanizeCoin } from "../utils/format";
import { EFFECT_NAME } from "../utils/effects";
import constants from "../data/constants.json";

// 工程营造 —— 可建工程（政府建筑 + 科技蓝图）**支持营建立项**；
// 已开工读 `state.projects`（工程系统的唯一权威，含五态状态机与进度）。
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

const EFFECT_LABELS: Record<string, string> = {
  yield_bonus: "粮产", trade_income: "贸易收入", production: "制造",
  build_speed: "营造速度", build_cost: "营造成本", defense_bonus: "城防",
  flood_risk: "水患", canal_efficiency: "漕运", army_power: "军力",
  commerce: "商税", pop_growth: "人口", tech_speed: "研习速度",
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

// 工程五态（对齐 content/data.py::PROJECT_STATUS_LABELS）
const STATUS_LABEL: Record<string, string> = {
  proposed: "拟议", funded: "已拨款", building: "营建中",
  operating: "运行中", degraded: "降效", abandoned: "作罢"
};

function effectText(eff: unknown): string {
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
  const setState = useGameStore((s) => s.setState);
  const [route, setRoute] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无工程可览。</p>;
  }

  const routes = Object.keys(asDict(pick(state, "prefectures", {})));
  const effRoute = route || routes[0] || "";

  // 可建工程：政府建筑（BUILDING_STD）+ 科技蓝图（BUILDING_BLUEPRINTS）
  const items: { name: string; key: string; cost: number; eff: string; cat: string }[] = [];
  for (const [bname, bcfgRaw] of Object.entries(asDict(constants.building_std))) {
    const bcfg = asDict(bcfgRaw);
    items.push({ name: bname, key: bname, cost: asNum(bcfg.base_cost),
                 eff: effectText(bcfg.effect), cat: asStr(bcfg.category, "政府") });
  }
  for (const [bid, bcfgRaw] of Object.entries(asDict(constants.building_blueprints))) {
    const bcfg = asDict(bcfgRaw);
    items.push({ name: asStr(bcfg.name, bid), key: bid,
                 cost: asNum(asDict(bcfg.cost).silver),
                 eff: effectText(bcfg.effect), cat: asStr(bcfg.category, "科技") });
  }
  const shown = items.slice(0, 16);

  // 已开工：读工程系统唯一权威 `state.projects`
  const opened: Dict[] = Object.entries(asDict(pick(state, "projects", {})))
    .map(([pid, p]) => {
      const d: Dict = asDict(p);
      d.pid = pid;
      return d;
    })
    .filter((p) => asStr(p.status) !== "abandoned");

  async function handleBuild(name: string, key: string) {
    if (busy || !effRoute) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().proposeProject(effRoute, name, key, 1);
      if (res.state) setState(res.state);
      setMsg(res.message || `已为 ${effRoute} 立项「${name}」`);
    } catch (e) {
      setMsg(`立项受阻：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        山川城邑，营建之事。择地立项 → 工部按蓝图核价 → 逐月施工 → 落成生效。
      </p>

      {/* 择地 */}
      <div className="flex items-center gap-2 rounded-lg border border-gold/40 bg-paper/60 px-3 py-2">
        <span className="text-sm text-dim">营建之地</span>
        <select
          className="rounded border border-gold/40 bg-paper px-2 py-0.5 text-sm text-ink"
          value={effRoute}
          onChange={(e) => setRoute(e.target.value)}
        >
          {routes.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        {msg ? <span className="ml-2 text-xs text-red">{msg}</span> : null}
      </div>

      {/* 可建工程 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="可 建 工 程" />
        <div className="mt-1.5">
          {shown.length ? (
            shown.map((it, i) => (
              <div key={i} className="flex items-center justify-between gap-2 py-0.5">
                <span className="text-sm text-ink">
                  · {it.name}〔{it.cat}〕（{Math.max(0, Math.floor(it.cost / 10000))}万贯）{it.eff}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void handleBuild(it.name, it.key)}
                  className="shrink-0 rounded border border-gold/50 px-2 py-0.5 text-xs text-red hover:bg-gold/10 disabled:opacity-40"
                >
                  营建
                </button>
              </div>
            ))
          ) : (
            <p className="py-1 text-sm text-dim">— 暂无可见工程 —</p>
          )}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-dim">
          （立项后由工部逐月施工；科技蓝图须先解锁对应节点，地利不合者不予立项）
        </p>
      </div>

      {/* 已开工 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="已 开 工" />
        <div className="mt-1.5">
          {opened.length ? (
            opened.slice(0, 12).map((it) => (
              <p key={asStr(it.pid)} className="py-1 text-sm text-ink">
                · {asStr(it.name, "工程")}（{asStr(it.route, "—")}）：　
                {STATUS_LABEL[asStr(it.status)] ?? asStr(it.status, "—")}
                {typeof it.progress === "number" ? `　进度 ${Math.round(asNum(it.progress))}%` : ""}
                {it.cost_coin ? `　工款 ${humanizeCoin(asNum(it.cost_coin))}` : ""}
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