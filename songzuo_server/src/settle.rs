//! 月度结算 —— 对应 Python core/settlement.run_monthly_settlement 的简化自洽版。
//!
//! 覆盖核心 12 步中的关键项：诏令执行、派系、经济、财政、国库、军事、民生、皇帝。
//! 高级维度（科举/科技/外交曲线/田赋隐漏等）留 TODO，后期按需补齐，保证数值可推进。

use crate::state::*;
use crate::constants::*;
use rand::Rng;

/// 执行月度结算，返回日志。
pub fn settle_turn(state: &mut GameState) -> Vec<String> {
    let mut log: Vec<String> = vec![];

    // ---- Step 1: 诏令执行 ----
    settle_decrees(state, &mut log);

    // ---- Step 2: 派系结算 ----
    settle_factions(state, &mut log);

    // ---- Step 3: 经济 ----
    settle_economy(state, &mut log);

    // ---- Step 3.5: 田亩地方（本色粮入）----
    settle_land_local(state, &mut log);

    // ---- Step 3.6: 仓廪漕运（军粮禄米 + 雀鼠耗 + 常平仓）----
    settle_granary(state, &mut log);

    // ---- Step 4: 财政 ----
    settle_finance(state, &mut log);

    // ---- Step 5: 国库（Step4 已含）----

    // ---- Step 6: 军事 / 外交 ----
    settle_military(state, &mut log);

    // ---- Step 7: 事件压力 ----
    settle_events(state, &mut log);

    // ---- Step 8: 灾荒 ----
    settle_disaster(state, &mut log);

    // ---- Step 9: 皇帝个人 ----
    settle_emperor(state, &mut log);

    // 回合计数与月份推进（结算后推进，保持与 Python 端一致）
    state.turn += 1;
    state.month += 1;
    if state.month > 12 {
        state.month = 1;
        state.year += 1;
    }
    state.settlement_log.push(log.clone());

    // 游戏结束判定（双级，对齐 Python content/data.py）
    //   - 国库 < -500万（TREASURY_CRISIS_LINE）：警告级，库藏空虚危机（仅提示，不强制结束）
    //   - 国库 < -2000万（TREASURY_COLLAPSE_LINE）：崩溃级，强判 game_over
    if state.treasury < -20_000_000 {
        state.game_over = true;
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛".into();
        log.push("[国祚] 国库崩坏至不可复救，社稷倾覆！".to_string());
    } else if state.treasury < -5_000_000 {
        log.push("[民生] 库藏空虚，国用告急，亟需开源节流！".to_string());
    }

    log
}

fn settle_decrees(state: &mut GameState, log: &mut Vec<String>) {
    state.direct_decree_used = 0;
    let mut executed = 0;
    let mut failed = 0;
    let pending = std::mem::take(&mut state.pending_decrees);
    for decree in pending {
        let mut rng = rand::thread_rng();
        let rate = if decree.is_direct { 0.85 } else { 0.75 };
        if rng.gen_bool(rate) {
            apply_decree_effect(state, &decree);
            executed += 1;
            if decree.duration > 0 {
                state.active_decrees.push(decree);
            }
        } else {
            log.push(format!("[诏令] 「{}」执行受阻，部分落实", decree.title));
            failed += 1;
        }
    }
    if executed > 0 {
        log.push(format!("[本月] 诏令执行 {} 项，{} 项受阻", executed, failed));
    }

    // 密旨
    let secrets = std::mem::take(&mut state.pending_secret_decrees);
    for decree in secrets {
        let mut rng = rand::thread_rng();
        if rng.gen_bool(0.8) {
            apply_decree_effect(state, &decree);
            log.push(format!("[密旨] 「{}」暗中推行", decree.title));
        }
    }
}

fn apply_decree_effect(state: &mut GameState, decree: &Decree) {
    let effs = &decree.effects;
    if let Some(obj) = effs.as_object() {
        for (k, v) in obj {
            let val = v.as_i64().unwrap_or(0);
            match k.as_str() {
                "prestige" => state.prestige += val,
                "treasury" => state.treasury += val,
                "population_satisfaction" => {
                    state.population_satisfaction = (state.population_satisfaction + val).max(0).min(100)
                }
                _ => {}
            }
        }
    }
    state.prestige = state.prestige.max(0).min(100);
    state.population_satisfaction = state.population_satisfaction.max(0).min(100);
}

fn settle_factions(state: &mut GameState, log: &mut Vec<String>) {
    let mut rng = rand::thread_rng();
    let mut infs: Vec<i64> = vec![];
    for f in state.factions.values_mut() {
        let cohesion_delta = rng.gen_range(-2..=2);
        f.cohesion = (f.cohesion + cohesion_delta).max(10).min(100);
        if f.satisfaction > 55 {
            f.satisfaction = (f.satisfaction - rng.gen_range(0..=2)).max(50);
        } else if f.satisfaction < 45 {
            f.satisfaction = (f.satisfaction + rng.gen_range(0..=1)).min(50);
        }
        let inf_delta = rng.gen_range(-1..=1);
        f.influence = (f.influence + inf_delta).max(5).min(100);
        infs.push(f.influence);
    }
    if let (Some(&mx), Some(&mn)) = (infs.iter().max(), infs.iter().min()) {
        if mx - mn > 40 {
            log.push("[党争] 朝堂势力悬殊，暗流涌动".into());
            state.prestige = (state.prestige - 1).max(0);
        }
    }
}

fn settle_economy(state: &mut GameState, log: &mut Vec<String>) {
    let mut rng = rand::thread_rng();
    let growth = rng.gen_range(-5000..=15000);
    state.population = (state.population + growth).max(10_000_000);
    state.refugee_count = (state.refugee_count as f64 * 0.95) as i64;
    log.push(format!(
        "[民生] 户数 {} 万，民心 {}", state.population / 10000, state.population_satisfaction
    ));
}

// ---- 财政计算辅助（对齐 Python game_state.calc_* / settlement._settle_finance）----

/// 国内工商经济总量（贯/年）—— 税基同源。
fn calc_commerce(state: &GameState) -> f64 {
    let tech = state.tech.get("level").and_then(|v| v.as_i64()).unwrap_or(50) as f64;
    let tech_mult = 1.0 + (tech - 50.0) / 200.0;          // 50→1.0, 100→1.25
    let art = state.art_mastery as f64;
    let art_mult = 1.0 + (art - 85.0) / 400.0;            // 85→1.0, 100→1.0375
    COMMERCE_BASE * tech_mult * art_mult + (state.population / 10) as f64
}

/// 市舶海外贸易年总额（贯/年），独立税源；未开为 0。
fn calc_maritime_trade(state: &GameState) -> f64 {
    let open = state.maritime.get("open").and_then(|v| v.as_bool()).unwrap_or(false);
    if !open {
        return 0.0;
    }
    let tech = state.tech.get("level").and_then(|v| v.as_i64()).unwrap_or(50) as f64;
    let tech_mult = 1.0 + (tech - 50.0) / 100.0;          // 50→1.0, 100→1.5
    let art = state.art_mastery as f64;
    let art_mult = 1.0 + (art - 85.0) / 400.0;            // 85→1.0, 100→1.0375
    MARITIME_TRADE_BASE * tech_mult * art_mult
}

/// 当月实际到账率（对齐 Python calc_arrival_rate）。
fn calc_arrival_rate(state: &GameState) -> f64 {
    // authority 取自 prestige 档位（简化：prestige/100 近似权威指数，[0,1]）
    let authority = (state.prestige as f64 / 100.0).clamp(0.0, 1.0);
    let audit_effort = 0.5;
    let diversion = 0.35;
    let rate = state.arrival_rate_base + audit_effort * 0.30 + authority * 0.15 - diversion * 0.25;
    rate.max(0.05).min(0.95)
}

fn settle_finance(state: &mut GameState, log: &mut Vec<String>) {
    let arrival = calc_arrival_rate(state);
    let shortage = state.coin.get("shortage").and_then(|v| v.as_f64()).unwrap_or(0.3);
    let tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1.0 - shortage);

    // ---- 收入：工商税 + 役钱 + 市舶抽解（对齐 Python _settle_finance 765-778）----
    let commerce = calc_commerce(state);
    let rate = state.commerce_tax_rate
        .max(COMMERCE_TAX_RATE_MIN)
        .min(COMMERCE_TAX_RATE_MAX);
    let commerce_tax = ((commerce / 12.0) * rate * arrival * tax_coeff) as i64;
    let poll_tax = ((ANNUAL_TAX_BASE as f64 * TAX_POLL_RATIO / 12.0) * arrival * tax_coeff) as i64;
    let maritime_trade = calc_maritime_trade(state);
    let maritime_open = state.maritime.get("open").and_then(|v| v.as_bool()).unwrap_or(false);
    let tariff = state.maritime.get("tariff").and_then(|v| v.as_f64()).unwrap_or(0.10);
    let maritime_tax = if maritime_open {
        ((maritime_trade / 12.0) * tariff * arrival * tax_coeff) as i64
    } else {
        0
    };
    let monthly_tax = commerce_tax + poll_tax + maritime_tax;

    // ---- 经济全浮动重构：二税折色（各路 monthly_tax × arrival × tax_coeff × route_mult）----
    let mut tax_color_total = 0.0_f64;
    for p in state.prefectures.values() {
        let base = p.get("monthly_tax").and_then(|v| v.as_f64()).unwrap_or(0.0);   // 万贯/月 锚
        let rm = p.get("route_mult").and_then(|v| v.as_f64()).unwrap_or(1.0);
        tax_color_total += base * arrival * tax_coeff * rm * TAX_COLOR_RATE;
    }
    // 盐课单列（不进 monthly_tax 既有三分项）；活基准：盐产区产能×动态盐价×食盐人口
    let mut salt_capacity = 0.0_f64;
    let mut total_pop = 0.0_f64;
    for p in state.prefectures.values() {
        salt_capacity += p.get("yields").and_then(|y| y.get("salt")).and_then(|v| v.as_f64()).unwrap_or(0.0);
        total_pop += p.get("population").and_then(|v| v.as_f64()).unwrap_or(0.0);
    }
    let adequacy = if SALT_CAPACITY_BASE > 0.0 { (salt_capacity / SALT_CAPACITY_BASE).min(2.0) } else { 1.0 };
    let mut price_factor = 1.0 + (adequacy - 1.0) * 0.3;
    price_factor = price_factor.max(SALT_PRICE_FLOOR).min(SALT_PRICE_CEIL);
    let pop_scale = if SALT_POP_BASE > 0.0 { total_pop / SALT_POP_BASE } else { 1.0 };
    let salt_coin = (salt_capacity * SALT_COIN_UNIT * price_factor * arrival * pop_scale) as i64;
    // 物资变现（开局 0）
    let material_coin = 0_i64;
    // 全货币月入
    let monthly_tax_full = monthly_tax as f64
        + tax_color_total
        + salt_coin as f64
        + material_coin as f64;

    // ---- 变法节流（省浮费/裁汰冗员）：取 savings 冲减常项 ----
    let waste_savings = state.waste_reform.get("savings").and_then(|v| v.as_i64()).unwrap_or(0);

    // ---- 折色俸禄兜底（旧口径兼容）----
    let pay_ratio = state.pay_system.get("cash_ratio").and_then(|v| v.as_f64()).unwrap_or(0.5);
    let cash_out = (PAY_CASH_BASE as f64 * pay_ratio) as i64;

    // ============ 全浮动支出科目（对齐 calc_*）============
    let strength_factor = 1.0_f64; // Rust 无 armies.strength 表，回退 1.0
    // 各路口径合计：官额应得 due 与缺口 gap = max(0, due - 地方财力)（pay_ratio 加俸摊还占比基准）
    let mut share_due_total = 0.0_f64;
    let mut share_gap_total = 0.0_f64;
    for (_, p) in state.prefectures.iter() {
        let off = p.get("officials").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let cle = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = off * OFFICIAL_PAY_PER_MONTH / 10000.0 + cle * CLERK_PAY_PER_MONTH / 10000.0;
        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        share_due_total += due;
        share_gap_total += (due - local).max(0.0);
    }
    if share_due_total <= 0.0 {
        share_due_total = 1.0; // 避免除零
    }

    let mut army_cash = 0.0_f64;
    let mut official_cash = 0.0_f64;
    let mut clerk_cash = 0.0_f64;
    let mut gap_total = 0.0_f64; // Σ 吏俸缺口（折色，未补发部分）

    for p in state.prefectures.values() {
        // 军饷：Σ兵种 × SOLDIER_PAY_PER_MONTH × 质量因子
        let mut troops = 0.0_f64;
        if let Some(g) = p.get("garrisons").and_then(|v| v.as_object()) {
            for (_, v) in g {
                troops += v.as_f64().unwrap_or(0.0);
            }
        }
        army_cash += troops * SOLDIER_PAY_PER_MONTH * strength_factor;

        let officials = p.get("officials").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let clerks = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);

        // 官俸折色
        official_cash += officials * OFFICIAL_PAY_PER_MONTH / 10000.0;

        // 吏俸：pay_ratio = clamp((local_finance + payraise_budget*share/10000)/due, 0, 1)
        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = officials * OFFICIAL_PAY_PER_MONTH / 10000.0
                + clerks * CLERK_PAY_PER_MONTH / 10000.0;
        let pr = if due <= 0.0 {
            1.0
        } else {
            // 加俸预算全国池按"官额缺口"占比摊还；全国无缺口退化为按官额占比
            let my_gap = (due - local).max(0.0);
            let share = if share_gap_total > 0.0 {
                my_gap / share_gap_total
            } else {
                due / share_due_total
            };
            let financed = local + state.payraise_budget as f64 * share / 10000.0;
            (financed / due).max(0.0).min(1.0)
        };
        clerk_cash += clerks * CLERK_PAY_PER_MONTH / 10000.0 * pr;
        gap_total += due * (1.0 - pr);
    }

    // 贪腐折色扣减：gap × CORRUPTION_MULT × (1-oversight)×(1-BRIBE_FLOOR) + gap×BRIBE_FLOOR×0.3
    let oversight = state.oversight.clamp(0.0, 1.0);
    let corruption_cash_ded = gap_total * CORRUPTION_MULT * (1.0 - oversight) * (1.0 - BRIBE_FLOOR)
        + gap_total * BRIBE_FLOOR * 0.3;

    // 加俸预算消耗
    let payraise_used = (state.payraise_budget as f64)
        .min(gap_total * 10000.0 + 10000.0);
    let payraise_used_i = payraise_used as i64;
    state.payraise_budget = (state.payraise_budget - payraise_used_i).max(0);

    // 岁币/岁赐（Rust 无 external attitude 则用 0）
    let mut sui_gong = 0_i64;
    if state.external.get("辽").map(|e| e.attitude).unwrap_or(50) >= 60 {
        sui_gong += (SUI_GONG_ANNUAL as f64 * 0.6 / 12.0) as i64;
    }
    if state.external.get("西夏").map(|e| e.attitude).unwrap_or(50) >= 60 {
        sui_gong += (SUI_GONG_ANNUAL as f64 * 0.4 / 12.0) as i64;
    }

    let expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings;
    let personnel_cash = (army_cash + official_cash + clerk_cash) as i64;
    let effective_cash_out = cash_out.max(personnel_cash);
    let total_out = expenditure
        + effective_cash_out
        + corruption_cash_ded as i64
        + payraise_used_i
        + sui_gong;
    let net = monthly_tax_full - total_out as f64;

    let treasury_before = state.treasury;

    // 内帑抽成（结余为正时） + 酒课（tech.level 驱动）
    let imp_share = (net.max(0.0) * IMPERIAL_SHARE) as i64;
    let tech_level = state.tech.get("level").and_then(|v| v.as_i64()).unwrap_or(50) as f64;
    let wine_coin = (WINE_COIN_BASE as f64 * (1.0 + 0.01 * (tech_level - 50.0))) as i64;

    state.treasury += (net - imp_share as f64) as i64;
    state.statistics.entry(String::from("total_income")).and_modify(|v| *v += monthly_tax_full as i64).or_insert(monthly_tax_full as i64);
    state.statistics.entry(String::from("total_expenditure")).and_modify(|v| *v += total_out).or_insert(total_out);

    // 内帑（甲口径）：imperial_treasury = 国库净结余抽成 + 榷酒课，与国库分理
    state.imperial_treasury += imp_share + wine_coin;

    // ---- 恒等断言：国库变动 == (月入 - 月出 - 内帑抽成)（容差，因浮点截断）----
    debug_assert!(
        (state.treasury - treasury_before - (net as i64 - imp_share)).abs() <= 1,
        "财政恒等断裂：Δtreasury={} net={} imp={}",
        state.treasury - treasury_before, net, imp_share
    );

    let inc_parts = format!(
        "工商{:.0}+役钱{:.0}+二税折色{:.0}+盐课{:.0}",
        commerce_tax as f64 / 10000.0,
        poll_tax as f64 / 10000.0,
        tax_color_total / 10000.0,
        salt_coin as f64 / 10000.0
    );
    let mut inc_parts = inc_parts;
    if maritime_tax > 0 {
        inc_parts.push_str(&format!("+市舶{:.0}", maritime_tax as f64 / 10000.0));
    }
    if net < 0.0 {
        log.push(format!("[财政] 货币月入 {}万贯（{}） 支 {}万贯 亏空 {}万贯",
            monthly_tax as f64 / 10000.0, inc_parts,
            total_out as f64 / 10000.0, (-net) / 10000.0));
    } else {
        log.push(format!("[财政] 货币月入 {}万贯（{}） 支 {}万贯 结余 {}万贯",
            monthly_tax as f64 / 10000.0, inc_parts,
            total_out as f64 / 10000.0, net / 10000.0));
    }
    if sui_gong > 0 {
        log.push(format!("[岁币] 岁币岁赐 {}万贯，纳贡以安边", sui_gong as f64 / 10000.0));
    }
    if state.treasury < -5_000_000 {
        state.population_satisfaction = (state.population_satisfaction - 2).max(0);
        log.push("[民生] 国库亏空严重，民怨渐起".into());
    }
}

/// 田亩地方演进 + 太仓本色月入（对齐 Python _settle_land_local / calc_monthly_grain）。
/// 改造点①：本色粮**先入各路州仓 storage**（与 Python 一致：州仓→漕运→太仓），
/// 返回的 grain_in 仅用于热力学恒等/统计；漕运汇聚在 settle_granary 中读取 storage。
pub fn settle_land_local(state: &mut GameState, _log: &mut Vec<String>) -> f64 {
    let arrival = calc_arrival_rate(state);
    let hyd = state.tech.get("hydraulics").and_then(|v| v.as_i64()).unwrap_or(40) as f64 / 100.0;
    let hidden = state.land.get("hidden_rate").and_then(|v| v.as_f64()).unwrap_or(0.35);
    let harvest = state.land.get("yield").and_then(|v| v.as_f64()).unwrap_or(1.0);

    // 各路本色粮入 → 先入州仓 storage（漕运阶段再汇聚太仓）
    let mut grain_in = 0.0_f64;
    for p in state.prefectures.values_mut() {
        let gy = p.get("grain_yield").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let inflow = gy / 12.0
            * LAND_TAX_RATE_BENEFIT
            * arrival
            * harvest
            * (1.0 - hidden)
            * (0.8 + 0.4 * hyd);
        grain_in += inflow;
        if let Some(s) = p.get_mut("storage").and_then(|v| v.as_f64().as_mut()) {
            *s += inflow;
        }
    }
    grain_in
}

/// 仓廪漕运 / 军粮禄米 / 雀鼠耗 / 常平仓（对齐 Python _settle_granary 552-720）。
/// Rust 简化：跳过漕运输运细节，直接以全浮动口径计算本色出 + 常平仓平粜。
pub fn settle_granary(state: &mut GameState, log: &mut Vec<String>) {
    let strength_factor = 1.0_f64;

    // 各路口径合计：官额应得 due 与缺口 gap = max(0, due - 地方财力)（pay_ratio 加俸摊还占比基准）
    let mut share_due_total = 0.0_f64;
    let mut share_gap_total = 0.0_f64;
    for (_, p) in state.prefectures.iter() {
        let off = p.get("officials").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let cle = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = off * OFFICIAL_PAY_PER_MONTH / 10000.0 + cle * CLERK_PAY_PER_MONTH / 10000.0;
        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        share_due_total += due;
        share_gap_total += (due - local).max(0.0);
    }
    if share_due_total <= 0.0 {
        share_due_total = 1.0;
    }

    // 军粮 / 官禄 / 吏禄（本色）
    let mut army_grain = 0.0_f64;
    let mut official_grain = 0.0_f64;
    let mut clerk_grain = 0.0_f64;
    let mut gap_total = 0.0_f64;
    for p in state.prefectures.values() {
        let mut troops = 0.0_f64;
        if let Some(g) = p.get("garrisons").and_then(|v| v.as_object()) {
            for (_, v) in g {
                troops += v.as_f64().unwrap_or(0.0);
            }
        }
        army_grain += troops * SOLDIER_GRAIN_PER_MONTH * strength_factor;

        let officials = p.get("officials").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let clerks = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        official_grain += officials * OFFICIAL_GRAIN_PER_MONTH / 10000.0;

        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = officials * OFFICIAL_PAY_PER_MONTH / 10000.0
                + clerks * CLERK_PAY_PER_MONTH / 10000.0;
        let pr = if due <= 0.0 {
            1.0
        } else {
            // 加俸预算全国池按"官额缺口"占比摊还；全国无缺口退化为按官额占比
            let my_gap = (due - local).max(0.0);
            let share = if share_gap_total > 0.0 {
                my_gap / share_gap_total
            } else {
                due / share_due_total
            };
            let financed = local + state.payraise_budget as f64 * share / 10000.0;
            (financed / due).max(0.0).min(1.0)
        };
        clerk_grain += clerks * CLERK_GRAIN_PER_MONTH / 10000.0 * pr;
        gap_total += due * (1.0 - pr);
    }

    let sparrow = (army_grain + official_grain + clerk_grain) * SPARROW_RAT;
    let oversight = state.oversight.clamp(0.0, 1.0);
    let corruption_grain_loss = gap_total * CORRUPTION_MULT * 0.5 * (1.0 - oversight);
    let grain_out = army_grain + official_grain + clerk_grain + sparrow + corruption_grain_loss;

    // 田赋本色入：settle_land_local 已将本色粮写入各路 storage（州仓），
    // 太仓只通过下方漕运汇聚接收（对齐 Python L456→L628-646），绝不再二次加 grain_in。
    let grain_in = settle_land_local(state, log);

    // ── 漕运汇聚（对齐 Python _settle_granary L628-646：州府 storage → 中央太仓）──
    // Rust 简化：固定 canal_eff=CANAL_MONTHLY_RATE（忽略随机 block 演化），
    // 损耗用 CANAL_LOSS_BASE（忽略 corrupt_avg 侵盗放大）。
    let canal_eff = CANAL_MONTHLY_RATE;
    let loss_rate = CANAL_LOSS_BASE;
    let granary_before = state.granary; // 恒等断言基线（漕运前取值）
    let mut canal = 0.0_f64;
    for p in state.prefectures.values_mut() {
        let storage = p.get("storage").and_then(|v| v.as_f64()).unwrap_or(0.0);
        if storage <= 0.0 {
            continue;
        }
        let movable = storage * canal_eff;
        let room = (state.granary_cap - state.granary).max(0.0);
        let take = movable.min(room);
        if take > 0.0 {
            let loss = take * loss_rate;
            let arrive = take - loss;
            // 更新该路 storage
            if let Some(s) = p.get_mut("storage").and_then(|v| v.as_f64().as_mut()) {
                *s -= take;
            }
            state.granary = (state.granary + arrive).clamp(0.0, state.granary_cap);
            canal += arrive;
        }
    }
    if canal > 0.0 {
        log.push(format!("[漕运] 诸路上供输粟 {}万石入太仓", canal.round()));
    }

    // 月出（兵/官/吏禄 + 雀鼠 + 侵盗）统一从太仓扣；本色只经漕运入太仓（不再二次加 grain_in）
    state.granary = (state.granary - grain_out).clamp(0.0, state.granary_cap);

    // 恒等断言：太仓变动 == 漕运汇入 - 月出
    debug_assert!(
        (granary_before - state.granary) as i64 == (canal - grain_out) as i64,
        "太仓恒等断裂：Δ={} canal={} out={}", granary_before - state.granary, canal, grain_out
    );

    // ---- 常平仓平粜籴（修复 audit-qa L698-720 缺陷：先砍量后扣款，籴粜同层中央太仓）----
    // Rust 无区域粮价，近似 price=1.0（处于 CHANGPING_LOW 与 CHANGPING_HIGH 之间，本回合不触发平粜，
    // 但保留结构以便后续接入 price）。
    let price = state.price_level.max(0.4); // 近似区域粮价
    if price < CHANGPING_LOW && state.treasury > 200_000 {
        let mut buy = (6.0_f64).min(state.treasury as f64 / 10000.0 / price);
        let room = state.granary_cap - state.granary;
        buy = buy.min(room).max(0.0);
        if buy > 0.0 {
            state.treasury -= (buy * price * 10000.0) as i64;
            state.granary += buy;
        }
    } else if price > CHANGPING_HIGH && state.granary > 200.0 {
        let sell = (8.0_f64).min(state.granary);
        if sell > 0.0 {
            state.treasury += (sell * price * 10000.0) as i64;
            state.granary -= sell;
        }
    }
}

fn settle_military(state: &mut GameState, log: &mut Vec<String>) {
    let mut rng = rand::thread_rng();
    if let Some(jin) = state.external.get_mut("金") {
        if state.year >= 1115 {
            jin.power = (jin.power + rng.gen_range(1..=2)).min(100);
            jin.invasion_will = (jin.invasion_will + rng.gen_range(1..=2)).min(100);
            log.push("[边事] 金国崛起，势渐张。".into());
        }
    }
    if let Some(liao) = state.external.get_mut("辽") {
        if state.year >= 1110 {
            liao.power = (liao.power - rng.gen_range(1..=2)).max(10);
        }
    }
}

fn settle_events(state: &mut GameState, _log: &mut Vec<String>) {
    // 事件压力自然衰减
    for v in state.event_pressure.values_mut() {
        *v = (*v as f64 * 0.9) as i64;
    }
}

fn settle_disaster(state: &mut GameState, _log: &mut Vec<String>) {
    if state.disaster_severity > 0 {
        state.disaster_severity = (state.disaster_severity as f64 * 0.85) as i64;
    }
}

fn settle_emperor(state: &mut GameState, _log: &mut Vec<String>) {
    // 皇帝健康随年龄/享乐缓慢变化（简化）
    if state.pleasure_leaning > 70 {
        state.emperor_health = (state.emperor_health - 1).max(0);
    } else {
        state.emperor_health = (state.emperor_health + 1).min(100);
    }
    if state.emperor_health <= 0 {
        state.emperor_alive = false;
        state.game_over = true;
    }
}
