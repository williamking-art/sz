//! 全局常量与初始数据 —— 与 Python 端 `content/data.py` 同名对齐。
//!
//! 经济全浮动重构口径：原 `settle.rs` 顶部的旧常量全部迁移至此，
//! 并补齐二税折色 / 盐课 / 贪腐 / 加俸 / 内帑抽成 / 常平仓等项。
//! `settle.rs` 通过 `use crate::constants::*;` 引入，避免双份定义。

use std::collections::HashMap;
use serde_json::json;

// ============================================================
// 初始数值（与 Python DIFFICULTY_PRESETS / Default 初值对齐）
// ============================================================
pub const TREASURY_START: i64 = 5_000_000;       // 国库初值（贯）
pub const INNER_TREASURY_START: i64 = 1_000_000; // 内帑初值（贯）
pub const PRESTIGE_START: i64 = 55;              // 皇威初值
pub const ARRIVAL_BASE: f64 = 0.45;              // 到账率基准
pub const EMPEROR_HEALTH_START: i64 = 75;        // 圣体初值
pub const GRANARY_START: f64 = 1500.0;           // 太仓初储（万石）
pub const GRANARY_START_CAP: f64 = 2000.0;       // 太仓容量（万石）

// ============================================================
// 财政常量（对齐 content/data.py）
// ============================================================
pub const ANNUAL_TAX_BASE: i64 = 80_000_000;     // 年应征基准 ~8000万贯
pub const TAX_POLL_RATIO: f64 = 0.10;            // 丁口(役钱)占一成
pub const COMMERCE_TAX_RATE_MIN: f64 = 0.05;     // 工商征率下限 0.5 成
pub const COMMERCE_TAX_RATE_MAX: f64 = 0.40;     // 工商征率上限 4 成
pub const TAX_COEFF_MIN: f64 = 0.75;             // 纳税系数下限（钱荒税难征）
pub const TAX_COEFF_MAX: f64 = 1.25;             // 纳税系数上限（泉货充裕税易征）
pub const MONTHLY_EXP_CIVIL_BASE: i64 = 1_300_000; // 朝廷经常性货币开支派生基准（废除旧 210 万写死常项）
pub const PAY_CASH_BASE: i64 = 2_000_000;        // 折色月度总盘子（兜底，贯）
pub const PAY_GRANARY_BASE: f64 = 800_000.0;     // 折色粮兜底（万石）
// 盐课（活基准）：盐产区产能 × 动态盐价 × 食盐人口，不再写死月额
pub const SALT_COIN_UNIT: f64 = 3090.0;          // 每单位盐产月折合课利钱（贯/单位/月）
pub const SALT_CAPACITY_BASE: f64 = 231.0;       // 开局 Σ各路 yields["salt"] 基准（产能比分母）
pub const SALT_POP_BASE: f64 = 5065.0;           // 开局总人口基准（万，人口缩放分母）
pub const SALT_PRICE_FLOOR: f64 = 0.6;           // 盐价因子下限
pub const SALT_PRICE_CEIL: f64 = 1.3;            // 盐价因子上限
// 酒课（保底基准）：WINE_COIN_BASE 为无作坊时保底月额，受 tech.level 微扰；
//   玩家建作坊/工程产酒时额外酒课走动态价（见 settle.rs 作坊段 MATERIAL_PRICE_BASE["wine"]）
pub const WINE_COIN_BASE: i64 = 100_000;         // 酒课保底月基准（贯，进内帑）—— 史实酒课~1000万/年取象征性净额12%
pub const SUI_GONG_ANNUAL: i64 = 300_000;        // 岁币岁赐年支出基准（贯）
pub const TAX_COLOR_RATE: f64 = 1.0;             // 二税折色率
pub const LAND_TAX_RATE_BENEFIT: f64 = 0.10;     // 田赋本色率
pub const SPARROW_RAT: f64 = 0.01;               // 雀鼠耗：存粮月自然损耗率（1%）
pub const IMPERIAL_SHARE: f64 = 0.10;            // 内帑抽成比率（结余为正时，plan L148/L207 定稿 0.1）
pub const CHANGPING_HIGH: f64 = 1.6;             // 粮价高于此则常平粜粮抑价
pub const CHANGPING_LOW: f64 = 0.6;              // 粮价低于此则常平籴粮托市

// ============================================================
// 军 / 官 / 吏 人均口径（与 Python calc_* 对齐，单位：万兵/万官/万吏）
// ============================================================
pub const SOLDIER_GRAIN_PER_MONTH: f64 = 2.0;    // 兵/月 本色粮（万石/万兵）
pub const SOLDIER_PAY_PER_MONTH: f64 = 0.5;      // 兵/月 折色饷（贯/万兵）
pub const OFFICIAL_PAY_PER_MONTH: f64 = 30.0;    // 官/月 折色俸（贯/万官）
pub const OFFICIAL_GRAIN_PER_MONTH: f64 = 15.0;  // 官/月 本色禄（万石/万官）
pub const CLERK_PAY_PER_MONTH: f64 = 2.0;        // 吏/月 折色俸（贯/万吏）
pub const CLERK_GRAIN_PER_MONTH: f64 = 1.5;      // 吏/月 本色禄（万石/万吏）
pub const CLERK_PER_OFFICIAL: i64 = 8;           // 吏/官 比（初始锚）

// 贪腐相关（对齐 calc_corruption_deduction）
pub const CORRUPTION_MULT: f64 = 0.8;            // 贪腐放大系数
pub const BRIBE_FLOOR: f64 = 0.2;                // 贿赂下限（顽固部分）

// 经济 / 军事 基准
pub const COMMERCE_BASE: f64 = 350_000_000.0;    // 国内工商经济总量基准（贯/年）
pub const MARITIME_TRADE_BASE: f64 = 20_000_000.0; // 广开市舶基准（贯/年）

// ============================================================
// 12 路初始数据（对齐 Python content/data.py PREFECTURE_INFO 432-571）
// 返回 HashMap<String, serde_json::Value>，键为稳定 ID。
// 数值逐路对齐 Python（households/land/grain/mood/govern/population/unrest/
//   monthly_tax/hidden_land/storage/type/is_capital/grain_yield/route_mult/
//   yields/garrisons/officials/clerks）。
// ============================================================
pub fn default_prefectures() -> HashMap<String, serde_json::Value> {
    let mut m: HashMap<String, serde_json::Value> = HashMap::new();

    m.insert("东京开封府".to_string(), json!({
        "name": "东京开封府",
        "households": 830, "land": 4200, "grain": 980, "mood": 62, "govern": 60,
        "population": 415, "unrest": 12, "monthly_tax": 46, "hidden_land": 620,
        "storage": 540, "local_finance": 540, "type": "京畿要地", "is_capital": true,
        "grain_yield": 11760, "route_mult": 1.05,
        "yields": {"salt":10,"tea":12,"silk":20,"hemp":10,"cane":8,"fruit":15,"timber":12,"stone":15,"iron":12},
        "garrisons": {"禁军":6,"厢军":2,"乡兵":0},
        "officials": 1, "clerks": 8
    }));

    m.insert("京西路".to_string(), json!({
        "name": "京西",
        "households": 540, "land": 3000, "grain": 640, "mood": 60, "govern": 58,
        "population": 270, "unrest": 14, "monthly_tax": 28, "hidden_land": 470,
        "storage": 330, "local_finance": 330, "type": "腹里州路", "is_capital": false,
        "grain_yield": 7680, "route_mult": 1.0,
        "yields": {"salt":6,"tea":10,"silk":10,"hemp":25,"cane":8,"fruit":10,"timber":15,"stone":12,"iron":12},
        "garrisons": {"禁军":1,"禁军_2":0,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("河北路".to_string(), json!({
        "name": "河北",
        "households": 910, "land": 4800, "grain": 720, "mood": 55, "govern": 55,
        "population": 455, "unrest": 24, "monthly_tax": 40, "hidden_land": 700,
        "storage": 380, "local_finance": 380, "type": "缘边重镇", "is_capital": false,
        "grain_yield": 8640, "route_mult": 0.95,
        "yields": {"salt":8,"tea":8,"silk":12,"hemp":12,"cane":6,"fruit":10,"timber":12,"stone":30,"iron":35},
        "garrisons": {"禁军":3,"厢军":2,"乡兵":3},
        "officials": 1, "clerks": 8
    }));

    m.insert("河东".to_string(), json!({
        "name": "河东",
        "households": 600, "land": 3100, "grain": 540, "mood": 58, "govern": 57,
        "population": 300, "unrest": 19, "monthly_tax": 26, "hidden_land": 430,
        "storage": 290, "local_finance": 290, "type": "缘边重镇", "is_capital": false,
        "grain_yield": 6480, "route_mult": 0.95,
        "yields": {"salt":45,"tea":8,"silk":10,"hemp":10,"cane":6,"fruit":10,"timber":35,"stone":40,"iron":45},
        "garrisons": {"禁军":2,"厢军":2,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("陕西路".to_string(), json!({
        "name": "陕西",
        "households": 780, "land": 4500, "grain": 610, "mood": 50, "govern": 52,
        "population": 390, "unrest": 30, "monthly_tax": 32, "hidden_land": 660,
        "storage": 300, "local_finance": 300, "type": "缘边重镇", "is_capital": false,
        "grain_yield": 7320, "route_mult": 0.95,
        "yields": {"salt":12,"tea":12,"silk":12,"hemp":12,"cane":8,"fruit":12,"timber":40,"stone":35,"iron":40},
        "garrisons": {"西军":20,"禁军":2,"厢军":2,"乡兵":2},
        "officials": 1, "clerks": 8
    }));

    m.insert("两浙路".to_string(), json!({
        "name": "两浙",
        "households": 1240, "land": 5200, "grain": 1680, "mood": 66, "govern": 68,
        "population": 620, "unrest": 8, "monthly_tax": 78, "hidden_land": 540,
        "storage": 880, "local_finance": 880, "type": "财赋膏腴", "is_capital": false,
        "grain_yield": 20160, "route_mult": 1.0,
        "yields": {"salt":40,"tea":35,"silk":45,"hemp":12,"cane":12,"fruit":15,"timber":18,"stone":12,"iron":15},
        "garrisons": {"禁军":2,"厢军":2,"乡兵":2},
        "officials": 2, "clerks": 16
    }));

    m.insert("江南东路".to_string(), json!({
        "name": "江南东",
        "households": 1120, "land": 4900, "grain": 1540, "mood": 64, "govern": 65,
        "population": 560, "unrest": 10, "monthly_tax": 70, "hidden_land": 560,
        "storage": 800, "local_finance": 800, "type": "财赋膏腴", "is_capital": false,
        "grain_yield": 18480, "route_mult": 1.0,
        "yields": {"salt":15,"tea":30,"silk":40,"hemp":12,"cane":12,"fruit":15,"timber":15,"stone":12,"iron":15},
        "garrisons": {"禁军":1,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("江南西路".to_string(), json!({
        "name": "江南西",
        "households": 1050, "land": 4700, "grain": 1460, "mood": 63, "govern": 64,
        "population": 525, "unrest": 11, "monthly_tax": 64, "hidden_land": 580,
        "storage": 760, "local_finance": 760, "type": "财赋膏腴", "is_capital": false,
        "grain_yield": 17520, "route_mult": 1.0,
        "yields": {"salt":12,"tea":30,"silk":25,"hemp":12,"cane":10,"fruit":12,"timber":15,"stone":12,"iron":15},
        "garrisons": {"禁军":1,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("荆湖南路".to_string(), json!({
        "name": "荆湖",
        "households": 760, "land": 3600, "grain": 920, "mood": 60, "govern": 56,
        "population": 380, "unrest": 18, "monthly_tax": 36, "hidden_land": 520,
        "storage": 430, "local_finance": 430, "type": "腹里州路", "is_capital": false,
        "grain_yield": 11040, "route_mult": 1.0,
        "yields": {"salt":8,"tea":15,"silk":15,"hemp":30,"cane":10,"fruit":12,"timber":20,"stone":15,"iron":15},
        "garrisons": {"禁军":1,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("福建路".to_string(), json!({
        "name": "福建",
        "households": 700, "land": 2600, "grain": 880, "mood": 61, "govern": 59,
        "population": 350, "unrest": 13, "monthly_tax": 42, "hidden_land": 330,
        "storage": 400, "local_finance": 400, "type": "沿海市舶", "is_capital": false,
        "grain_yield": 10560, "route_mult": 1.0,
        "yields": {"salt":35,"tea":25,"silk":15,"hemp":12,"cane":40,"fruit":35,"timber":20,"stone":12,"iron":15},
        "garrisons": {"禁军":1,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("成都府路".to_string(), json!({
        "name": "川峡",
        "households": 880, "land": 3900, "grain": 1180, "mood": 65, "govern": 66,
        "population": 440, "unrest": 12, "monthly_tax": 52, "hidden_land": 470,
        "storage": 620, "local_finance": 620, "type": "天府沃野", "is_capital": false,
        "grain_yield": 14160, "route_mult": 1.0,
        "yields": {"salt":10,"tea":40,"silk":35,"hemp":12,"cane":25,"fruit":30,"timber":45,"stone":15,"iron":15},
        "garrisons": {"禁军":1,"厢军":2,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m.insert("广南东路".to_string(), json!({
        "name": "广南",
        "households": 580, "land": 2300, "grain": 600, "mood": 58, "govern": 53,
        "population": 290, "unrest": 20, "monthly_tax": 34, "hidden_land": 300,
        "storage": 280, "local_finance": 280, "type": "沿海市舶", "is_capital": false,
        "grain_yield": 7200, "route_mult": 1.0,
        "yields": {"salt":30,"tea":12,"silk":12,"hemp":35,"cane":35,"fruit":40,"timber":18,"stone":12,"iron":12},
        "garrisons": {"禁军":1,"厢军":1,"乡兵":1},
        "officials": 1, "clerks": 8
    }));

    m
}

// ── 漕运常量（对齐 Python data.py:701-707）──
pub const CANAL_MONTHLY_RATE: f64 = 0.90;          // 每月把州府可输存粮的 90% 输往中央仓
pub const CANAL_LOSS_BASE: f64 = 0.04;             // 漕运漂没基础损耗（4%）
pub const CANAL_LOSS_CORRUPT_WEIGHT: f64 = 0.06;   // 漕运侵盗损耗随押运官贪腐放大系数
                                                   // 注：Rust 简化版漕运暂用 CANAL_LOSS_BASE 作固定损耗率，
                                                   // 忽略随机 canal_block 演化与 corrupt_avg 侵盗放大（对拍时此部分为结构性差异，见 diff_bench.py 白名单）。
