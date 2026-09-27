// 截图台 fixture（**仅 dev 用**）：一份确定的 state 与 readouts，喂给两个面板。
// 数据刻意覆盖关键口径：未清丈（隐田/隐户只该显约值）、治安正极性、多编制单位、跨路单位。
import type { Dict } from "./types";

export const STATE: Dict = {
  prefectures: {
    两浙路: {
      controlled_by: "宋",
      population: 1_072_871,
      govern: 62,
      buildings: { 农田: 3, 市舶司: 1, 造船场: 2 },
      pops: {
        农: {
          size: 500_000, hidden: 120_000,
          自耕农: 300_000, 富农: 50_000, 贫农: 100_000, 佃农: 50_000,
          ding: 80_000, kou: 120_000
        },
        士绅: { size: 9_000 },
        工匠: { size: 110_000 },
        商人: { size: 220_000 },
        官僚: { size: 40_000 },
        兵: { size: 33_000 }
      }
    },
    京畿路: {
      controlled_by: "宋",
      population: 1_371_000,
      govern: 70,
      buildings: { 农田: 5, 军营: 4 },
      pops: {
        农: { size: 620_000, hidden: 60_000, 自耕农: 400_000, 富农: 80_000, 贫农: 90_000, 佃农: 50_000, ding: 90_000, kou: 150_000 },
        士绅: { size: 20_000 },
        工匠: { size: 130_000 },
        商人: { size: 180_000 },
        官僚: { size: 60_000 },
        兵: { size: 60_000 }
      }
    }
  },
  army_units: [
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
  ]
};

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
  tax_month: 420_000, tax_share: 0.19, army_cash_month: 78_000, army_grain_month: 64_000,
  risk_score: 8.2, risk_label: "安", risk_hints: []
};

export const READOUTS = {
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
