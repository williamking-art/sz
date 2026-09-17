import { humanizeCoin } from "./format";

// 事件 effects → 中文描述 / 吉凶判定
// 迁移自 Tk game/ui/gui_common.py::format_effects（L148）与 _judge_effects（L176）；
// 供 EventPanel 选项预览（〔推演效果〕+ 吉/凶朱批色）使用。

/** 效果键 → 中文名（对齐 gui_common._NAME_MAP，并补齐 core/content 侧全部可落地键）。
 *
 * 铁律：内部键名（snake_case 英文、`_` 前缀内部指令）绝不直出玩家界面。
 * 未登记的键在 formatEffects 中被跳过，而不是回落成原键名。
 * 注意：不登记 corruption（隐藏维度），避免隐值经效果预览外泄。
 */
export const EFFECT_NAME: Record<string, string> = {
  // ---- 国力/财计 ----
  prestige: "皇威",
  prestige_gain: "威望",
  treasury: "国帑(贯)",
  imperial_treasury: "内帑(贯)",
  finance: "财利(贯)",
  hoard: "积储",
  tax: "税入",
  commerce_tax: "工商征率",
  trade_income: "商税",
  maritime_income: "市舶",
  mining_income: "矿课",
  curtail_waste: "省浮费",
  reduce_office: "裁汰冗员",
  // ---- 民生 ----
  population_satisfaction: "民心",
  satisfaction: "民心",
  relief: "赈济",
  he_mi: "和籴",
  grain_stabilize: "常平",
  settle_refugees: "安置流民",
  land_survey: "方田均税",
  unrest: "民乱",
  population: "户口",
  grain: "粮储",
  granary_cap: "仓容",
  // ---- 军事 ----
  defense_bonus: "城防",
  army: "军力",
  army_strength: "军力",
  army_power: "战力",
  military_supply: "军需",
  training: "训练",
  equipment: "装备",
  morale: "士气",
  ship_capacity: "运力",
  // ---- 外事 ----
  external_jin: "金态度",
  external_liao: "辽态度",
  external_xixia: "西夏态度",
  influence: "影响",
  power: "实力",
  // ---- 制度/人事 ----
  reform: "改制",
  talent: "人才",
  exam_talent: "科举得才",
  anti_corruption: "惩贪",
  factions_prestige: "派系威望",
  single_whip: "役法",
  pay_reform: "支给",
  granary_reform: "仓法",
  decree_speed: "政令效率",
  influence_office: "事权",
  loyalty: "忠诚",
  // ---- 御躬 ----
  emperor_health: "圣躬",
  pleasure_leaning: "逸乐",
  taoism_leaning: "崇道",
  bandwidth_bonus: "精力",
  art_mastery: "艺文",
  // ---- 营建/科技 ----
  tech: "科技",
  canal_dredge: "漕渠疏浚",
  canal_efficiency: "漕运",
  build_speed: "营造速度",
  build_cost: "营造耗费",
  workshop_output: "作院产出",
  production: "产出",
  yield_bonus: "田产",
  flood_risk: "水患",
  epidemic_risk: "疫病",
  calendar_bonus: "历法",
};

/** 档位词里的减益义（数值以外的表达，如「大减」「停」） */
const REDUCE_WORDS = ["减", "降", "无", "停", "损", "衰", "免"];

/** 单条效果的增益方向：1 增益 / -1 减益 / 0 中性 */
export function effectDeltaSign(v: unknown): number {
  if (typeof v === "number" && Number.isFinite(v)) {
    return v > 0 ? 1 : v < 0 ? -1 : 0;
  }
  if (typeof v === "string") {
    return REDUCE_WORDS.some((w) => v.includes(w)) ? -1 : 1;
  }
  return 0;
}

/** 效果字典 → 一句中文描述（无显著影响时给出明确文案） */
export function formatEffects(effects: unknown): string {
  if (!effects || typeof effects !== "object") return "（无显著影响）";
  const e = effects as Record<string, unknown>;
  const parts: string[] = [];
  for (const [k, v] of Object.entries(e)) {
    if (k === "faction_change" && v && typeof v === "object") {
      for (const [fn, fd] of Object.entries(v as Record<string, unknown>)) {
        const sign = effectDeltaSign(fd) >= 0 ? "+" : "";
        parts.push(`${fn}${sign}${String(fd)}`);
      }
      continue;
    }
    // 内部指令键（如下发控制用的 _confirm_break / _dismiss_break）不属玩家可见效果
    if (k.startsWith("_")) continue;
    const label = EFFECT_NAME[k];
    // 未登记键一律跳过：宁可少显示，也不把英文键名当文案直出
    if (!label) continue;
    if (typeof v === "boolean") {
      parts.push(`${label}${v ? "行" : "止"}`);
    } else if (k === "commerce_tax" && typeof v === "number") {
      parts.push(`工商征率${(v * 100).toFixed(0)}%`);
    } else if ((k === "treasury" || k === "imperial_treasury") && typeof v === "number") {
      parts.push(`${label}${v >= 0 ? "+" : ""}${humanizeCoin(v)}`);
    } else if (typeof v === "number") {
      parts.push(`${label}${v >= 0 ? "+" : ""}${v}`);
    } else {
      parts.push(`${label}${String(v)}`);
    }
  }
  return parts.length ? parts.join("，") : "（无显著影响）";
}

/** 统计增益/减益条目数（供选项朱批色：吉/凶高亮） */
export function judgeEffects(effects: unknown): { good: number; bad: number } {
  if (!effects || typeof effects !== "object") return { good: 0, bad: 0 };
  let good = 0;
  let bad = 0;
  for (const [k, v] of Object.entries(effects as Record<string, unknown>)) {
    if (k === "faction_change" && v && typeof v === "object") {
      for (const fd of Object.values(v as Record<string, unknown>)) {
        const s = effectDeltaSign(fd);
        if (s > 0) good += 1;
        else if (s < 0) bad += 1;
      }
      continue;
    }
    const s = effectDeltaSign(v);
    if (s > 0) good += 1;
    else if (s < 0) bad += 1;
  }
  return { good, bad };
}
