// 截图台 fixture（**仅 dev 用**）：一份确定的 state 与 readouts，喂给两个面板。
// 数据刻意覆盖关键口径：未清丈（隐田/隐户只该显约值）、治安正极性、多编制单位、跨路单位。
import type { Dict } from "./types";

export const STATE: Dict = {
  // M293：**必须置于 STATE 顶层**（此前误插进 2 空格缩进的嵌套块 —— 由截图台探针证得
  //   `fixtures.STATE.statistics === undefined`）；值取自真实后端 state.statistics（seed=20261013 + 6 月结算）
  statistics: {"total_income": 16329544, "total_expenditure": 17414649, "total_decrees": 0, "total_wars": 0, "total_disasters": 0},
  prefectures: {
    两浙路: {
      controlled_by: "宋",
      population: 1_072_871,
      households: 210_000,
      govern: 62,
      buildings: { 农田: 3, 市舶司: 1, 造船场: 2 },
      pops: {
        农: {
          size: 500_000, hidden: 120_000,
          自耕农: 300_000, 富农: 50_000, 贫农: 100_000, 佃农: 50_000,
          ding: 80_000, kou: 120_000, wealth: 120_000, grain: 800_000
        },
        士绅: { size: 9_000, wealth: 900_000, grain: 400_000 },
        工匠: { size: 110_000, wealth: 80_000, grain: 50_000 },
        商人: { size: 220_000, wealth: 260_000, grain: 90_000 },
        官僚: { size: 40_000, wealth: 60_000, grain: 40_000 },
        兵: { size: 33_000, wealth: 30_000, grain: 120_000 }
      }
    },
    京畿路: {
      controlled_by: "宋",
      population: 1_371_000,
      households: 268_000,
      govern: 70,
      buildings: { 农田: 5, 军营: 4 },
      pops: {
        农: { size: 620_000, hidden: 60_000, 自耕农: 400_000, 富农: 80_000, 贫农: 90_000, 佃农: 50_000, ding: 90_000, kou: 150_000, wealth: 180_000, grain: 1_050_000 },
        士绅: { size: 20_000, wealth: 1_600_000, grain: 700_000 },
        工匠: { size: 130_000, wealth: 95_000, grain: 60_000 },
        商人: { size: 180_000, wealth: 210_000, grain: 70_000 },
        官僚: { size: 60_000, wealth: 90_000, grain: 55_000 },
        兵: { size: 60_000, wealth: 55_000, grain: 220_000 }
      }
    }
  },
  land: {
    cultivated: 45_265_960, hidden_rate: 0.32, wasteland: 3_200_000,
    hidden_households: 480_000, rem: 0
  },
  granary: {
    stock: 1_013_000,
    changping: 400_000, capacity: 3_000_000
  },
  treasury: 1_250_000,
  imperial_treasury: 320_000
};

// 2026-10-01 审查 M8：编制单位**不在** STATE 里 —— 生产 `/api/state` 经
//   `_state_to_dict` 会剔除 `army_units`（ArmyUnit 为对象、不可JSON 序列化），
//   单位级数据只由 `/api/readouts::army` 下发。把 army_units 塞进 STATE 会让
//   「面板取不到部队 → 军令静默失效」这类缺陷在截图里看不见（假绿）。
export const ARMY: Dict[] = [
  {
    unit_id: "u0001", name: "两浙路·殿前第15军", army_name: "殿前第15军", tier: "禁军",
    station: "两浙路", defense_line: "沿海", org_arm: "殿前司", scale: "军", serial: 15,
    branches: { 重骑兵: 10_500, 轻骑兵: 4_500, 弓弩手: 7_500, 长枪手: 9_000, 轻步兵: 19_350, 器械兵: 3_600, 战船兵: 6_150 },
    equip: { 枪刀: 26_000, 盔甲: 12_000, 战马: 3_000 },
    morale: 55, training: 42, arrears: 0, commander: "吕颐浩"
  },
  {
    unit_id: "u0002", name: "两浙路·厢军造船", army_name: "造船厢军", tier: "厢军",
    station: "两浙路", defense_line: "", org_arm: "", scale: "厢", serial: 3,
    branches: { 轻步兵: 8_000, 器械兵: 2_000 },
    equip: { 枪刀: 6_000 },
    morale: 41, training: 18, arrears: 1_200, commander: ""
  },
  {
    unit_id: "u0003", name: "两浙路·乡兵弓手", army_name: "两浙乡兵弓手", tier: "乡兵",
    station: "两浙路", defense_line: "", org_arm: "", scale: "乡", serial: 7,
    branches: { 弓弩手: 5_000, 轻步兵: 8_000 },
    equip: {},
    morale: 48, training: 12, arrears: 0, commander: ""
  },
  {
    unit_id: "u0011", name: "京畿路·殿前第1军", army_name: "殿前第1军", tier: "禁军",
    station: "京畿路", defense_line: "京畿", org_arm: "殿前司", scale: "军", serial: 1,
    branches: { 重骑兵: 18_000, 轻骑兵: 6_000, 弓弩手: 10_000, 长枪手: 14_000, 轻步兵: 12_000 },
    equip: { 枪刀: 40_000, 盔甲: 24_000, 战马: 6_000 },
    morale: 62, training: 55, arrears: 0, commander: "韩世忠"
  }
];

// 在办长期事务（P1-1 支持模型）：刻意覆盖三种关键状态，供 TodoPanel 截图核对
//   ① 支持/阻力与执行能力齐备、下月可预判（正常在办）
//   ② 吏治读数缺失 → defined=false（必须显式写"未定义"，不得显示成 0/完美）
//   ③ 未命中任何 POP 得失声明 → declared=false（必须写"未声明立场"，不得编造支持者）
//   ④ 密令：走密旨通道，不支持调兵督行
const TASK_SURVEY: Dict = {
  id: "ltp1", task_name: "方田均税·清丈隐田", title: "方田均税·清丈隐田",
  months: 18, progress: 42.5, minister: "章惇", org_hint: "户部", outcome: "在办",
  readout: {
    id: "ltp1", name: "方田均税·清丈隐田",
    goal: "清丈各路隐田、均平赋税，使隐漏稍抑、赋役均平",
    success_condition: "成效满 100%（按月由支持方/阻力方与执行能力推进，非按时间自动完成）",
    org_hint: "户部", minister: "章惇", topic: "land_survey", topic_label: "方田均税（清丈隐田）",
    kind: "民政", stage: "成效渐著", progress: 42.5, months: 18,
    supporters: [{ name: "新党", influence: 34, reason: "户部主责，本派（按 YAMEN_INFO 声明）力主" }],
    opposers: [
      { name: "旧党", influence: 26, reason: "基本盘 士绅 受损（隐田蔽课被括、形势户受损）——按《方田均税（清丈隐田）》POP 得失声明" },
      { name: "中立派", influence: 18, reason: "基本盘 士绅 受损——按《方田均税（清丈隐田）》POP 得失声明" }
    ],
    stance_declared: true, support_net: 0.18, support_bonus: 0.12, stance_mult: 1.09,
    obstruction: {
      defined: true, clerks_mult: 0.86, clerks_quality: "吏胥弄权", civil_mult: 0.92,
      literacy: 18.4, kind: "民政", military_applies: false, army_mult: null,
      blockers: [
        "吏治（强关联）折扣 ×0.86（吏胥弄权）",
        "民心/识字率（弱关联）×0.92",
        "军队不参与（民政事务，未调兵）",
        "旧党 反对（影响力 26）：基本盘 士绅 受损"
      ],
      note: "吏治（强）折扣 ×0.86；民心/识字率（弱）×0.92；军队不参与（民政诏令，未调兵）"
    },
    forecast: {
      advance_pct: 4.83,
      text: "按本月读数，下月约推进 4.83%（基数 5.56% × 难度 1.20 × 执行 0.79 × 立场 1.09）"
    },
    last_change: "本月推进 4.83%（37.7% → 42.5%）：执行 ×0.79（吏治 ×0.86 · 民心/识字率 ×0.92）"
      + " × 立场 ×1.09（净支持 +0.18；支持方 新党，阻力方 旧党、中立派）",
    decree_history: [{
      turn: 3, title: "督行「方田均税·清丈隐田」", kind: "督行", target: "章惇",
      executed: true, rate: 0.71, support_delta: 0.12,
      note: "督行诏已施行（执行率 71%），支持 +0.12"
    }],
    decree_count: 1, stall_months: 0, outcome: "在办"
  }
};

const TASK_UNDEFINED: Dict = {
  id: "ltp2", task_name: "修葺河堤", title: "修葺河堤", months: 12, progress: 8.0,
  minister: "郑居中", org_hint: "工部", outcome: "在办",
  readout: {
    id: "ltp2", name: "修葺河堤", goal: "修葺黄河堤防，免决口之患",
    success_condition: "成效满 100%", org_hint: "工部", minister: "郑居中",
    topic: null, topic_label: null, kind: "民政", stage: "推行中", progress: 8.0, months: 12,
    supporters: [], opposers: [], stance_declared: false,
    stance_note: "未声明立场：本事务未命中任何既有 POP 得失声明（不编造支持者），仅按官场配合度与执行能力推进",
    support_net: 0.0, support_bonus: 0.0, stance_mult: 1.0,
    obstruction: {
      defined: false, clerks_mult: null, clerks_quality: null, civil_mult: null,
      literacy: null, kind: "民政", military_applies: false, army_mult: null,
      blockers: ["吏治读数缺失（未定义）→ 政令无法评估执行能力", "军队不参与（民政事务，未调兵）"],
      note: "吏治读数缺失"
    },
    forecast: { advance_pct: null, text: "吏治读数缺失（未定义）→ 无法预判，本月不推进（不伪造）" },
    last_change: "吏治读数缺失（未定义）→ 本月不推进，成效未变（不伪造）",
    decree_history: [], decree_count: 0, stall_months: 2, outcome: "在办"
  }
};

const TASK_SECRET: Dict = {
  id: "lts1", task_name: "密查诸路截留", title: "密查诸路截留", months: 10, progress: 20.0,
  minister: "李纲", outcome: "在办",
  readout: {
    id: "lts1", name: "密查诸路截留", goal: "密查各路漕粮截留情弊",
    success_condition: "成效满 100%", org_hint: "政府", minister: "李纲",
    topic: null, topic_label: null, kind: "民政", stage: "推行中", progress: 20.0, months: 10,
    supporters: [{ name: "皇党集团", influence: 8, reason: "承办大臣 李纲 出身该派（按 MINISTERS 声明）" }],
    opposers: [], stance_declared: true,
    stance_note: "支持/阻力取自既有声明表（FACTION_POP_BASIS / REFORM_POP_BASIS / YAMEN_INFO）",
    support_net: 0.08, support_bonus: 0.0, stance_mult: 1.04,
    obstruction: {
      defined: true, clerks_mult: 0.9, clerks_quality: "吏习其事", civil_mult: 0.93,
      literacy: 17.2, kind: "民政", military_applies: false, army_mult: null,
      blockers: ["吏治（强关联）折扣 ×0.90（吏习其事）", "军队不参与（民政事务，未调兵）"], note: ""
    },
    forecast: { advance_pct: 9.1, text: "按本月读数，下月约推进 9.10%" },
    last_change: "本月推进 9.10%（10.9% → 20.0%）",
    decree_history: [], decree_count: 0, stall_months: 0, outcome: "在办"
  }
};

STATE.longterm_public = [TASK_SURVEY, TASK_UNDEFINED];
STATE.longterm_secret = [TASK_SECRET];

const ROUTE_ZXL = {
  name: "两浙路", display_name: "两浙路", controlled_by: "宋",
  households: 210_000, population: 1_072_871, land: 45_265_960,
  surveyed: false, hidden_land_est: 9_000_000, hidden_land_band: "隐匿较重", hidden_pop_est: 120_000,
  mood: 63, govern: 62, public_support: 66, gentry_resistance: 34,
  city_defense: 45, unrest: 12, security: 88, security_label: "太平",
  fiscal: 58, literacy: 31, grain_year: 3_100_000, grain_stock: 1_013_000, grain_months: 5.2,
  tax_month: 190_000, tax_share: 0.09, army_cash_month: 42_000, army_grain_month: 36_000,
  risk_score: 12.5, risk_label: "安", risk_hints: []
};

const ROUTE_JJL = {
  name: "京畿路", display_name: "京畿路", controlled_by: "宋",
  households: 268_000, population: 1_371_000, land: 52_800_000,
  surveyed: false, hidden_land_est: 8_500_000, hidden_land_band: "隐匿较重", hidden_pop_est: 60_000,
  mood: 70, govern: 70, public_support: 72, gentry_resistance: 28,
  city_defense: 68, unrest: 8, security: 92, security_label: "太平",
  fiscal: 66, literacy: 38, grain_year: 4_200_000, grain_stock: 1_800_000, grain_months: 6.1,
  tax_month: 420_000, tax_share: 0.19,
  // M275：`GovernanceHub` 的「税入构成」读 **state.tax_breakdown**（store 通道）
  tax_breakdown: {"commerce": 1116720, "poll": 390470, "tax_color": null, "salt": null},
  risk_score: 8.2, risk_label: "安", risk_hints: []
};

export const READOUTS = {
  army: ARMY,
  regions: {
    routes: [ROUTE_ZXL, ROUTE_JJL],
    prefectures: [
      { name: "杭州", circuit: "两浙", route: "两浙路", population: 420_000, households: 82_000, land: 18_100_000, grain_year: 1_240_000, tax_month: 76_000, share: 0.39 },
      { name: "苏州", circuit: "两浙", route: "两浙路", population: 360_000, households: 70_000, land: 15_200_000, grain_year: 1_060_000, tax_month: 65_000, share: 0.34 },
      { name: "越州", circuit: "两浙", route: "两浙路", population: 292_871, households: 58_000, land: 11_965_960, grain_year: 800_000, tax_month: 49_000, share: 0.27 },
      { name: "开封府", circuit: "京畿", route: "京畿路", population: 820_000, households: 160_000, land: 31_000_000, grain_year: 2_500_000, tax_month: 250_000, share: 0.6 },
      { name: "河南府", circuit: "京畿", route: "京畿路", population: 551_000, households: 108_000, land: 21_800_000, grain_year: 1_700_000, tax_month: 170_000, share: 0.4 }
    ],
    military: {
      route: null,
      routes: [
        { route: "两浙路", units: 3, troops: 71_600, morale_weighted: 50.4, arrears: 1_200, cash_month: 42_000, grain_month: 36_000, city_defense: 45, security: 88, security_label: "太平", controlled_by: "宋" },
        { route: "京畿路", units: 1, troops: 60_000, morale_weighted: 62.0, arrears: 0, cash_month: 78_000, grain_month: 64_000, city_defense: 68, security: 92, security_label: "太平", controlled_by: "宋" }
      ],
      nation: { routes: 2, units: 4, troops: 131_600, arrears: 1_200, cash_month: 120_000, grain_month: 100_000 }
    }
  }
};
