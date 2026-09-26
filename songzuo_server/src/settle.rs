//! 月度结算 —— 对应 Python core/settlement.run_monthly_settlement 的简化自洽版。
//!
//! 覆盖核心 12 步中的关键项：诏令执行、派系、经济、财政、国库、军事、民生、皇帝。
//! 高级维度（科举/科技/外交曲线/田赋隐漏等）留 TODO，后期按需补齐，保证数值可推进。

use crate::state::*;
use crate::constants::*;
use rand::Rng;
use serde_json::Value;

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

// ---- 官俸计价口径（子池付款权数；对齐 Python core/officialdom.py）----

/// 本路**官·付款权数**（官俸/官禄的真正乘数）—— 对应 Python
/// `core/officialdom.py:route_pay_units`（**Python 为权威**）。
///
/// 取值优先级：
///   ① `p["official_units"]`：Python `sync_legacy_mirror()` 写入的等价付款权数镜像
///      （officialdom.py:479）。字段存在且为**数字、有限、非负**时直接采用 ——
///      这是权威值，已经含了待阙 0.35 / 祠禄 0.4 的折算。
///   ② 无镜像则由子池推算：`pops["官僚"]` 的
///      `on_post*1.0 + waiting*WAITING_PAY_RATIO + sinecure*SINECURE_PAY_RATIO`
///      （与 Python route_pay_units L299-301 同式；三字段**任一存在**即视为有新口径子池）。
///      若子池缺失但 POP 有 `officials`，按 Python `route_officials` 的「POP 优先」回落到它。
///   ③ 否则回退人头 `p["officials"] * ON_POST_PAY_RATIO`（旧存档 / AI 直改场景的稳健兜底，
///      与 Python「旧档无子池：按全部在岗计价」一致）。
fn route_pay_units(p: &Value) -> f64 {
    // ① Python 镜像（权威）
    if let Some(u) = p.get("official_units").and_then(|v| v.as_f64()) {
        if u.is_finite() && u >= 0.0 {
            return u;
        }
    }
    // ② 由子池推算
    if let Some(pop) = p
        .get("pops")
        .and_then(|v| v.get(POP_CLASS))
        .and_then(|v| v.as_object())
    {
        if ["on_post", "waiting", "sinecure"]
            .iter()
            .any(|k| pop.contains_key(*k))
        {
            let pool = |k: &str| pop.get(k).and_then(|v| v.as_f64()).unwrap_or(0.0).max(0.0);
            return pool("on_post") * ON_POST_PAY_RATIO
                + pool("waiting") * WAITING_PAY_RATIO
                + pool("sinecure") * SINECURE_PAY_RATIO;
        }
        if let Some(o) = pop.get("officials").and_then(|v| v.as_f64()) {
            return o.max(0.0);
        }
    }
    // ③ 回退人头镜像（旧档全俸）
    p.get("officials")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0)
        .max(0.0)
        * ON_POST_PAY_RATIO
}

/// 本路官俸**折色**月支（万贯/月）＝ 付款权数 × 官月俸。
/// 与 Python `calc_official_cash`（game_state_econ.py:584 用 route_pay_units）同口径。
fn official_cash_pay(p: &Value) -> f64 {
    route_pay_units(p) * OFFICIAL_PAY_PER_MONTH / 10000.0
}

/// 本路官禄**本色**月支（万石/月）＝ 付款权数 × 官月禄。
/// 与 Python `calc_official_grain`（game_state_econ.py:574 用 route_pay_units）同口径。
fn official_grain_pay(p: &Value) -> f64 {
    route_pay_units(p) * OFFICIAL_GRAIN_PER_MONTH / 10000.0
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
    // D 修复：savings 无上限时 `expenditure = BASE - savings` 可为负 → 支出为负、
    // 国库反增。按「不超过经常性开支基数」封顶（与 Python 侧同口径）。
    let waste_savings = state
        .waste_reform
        .get("savings")
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
        .clamp(0, MONTHLY_EXP_CIVIL_BASE);

    // ---- 折色俸禄兜底（旧口径兼容）----
    let pay_ratio = state.pay_system.get("cash_ratio").and_then(|v| v.as_f64()).unwrap_or(0.5);
    let cash_out = (PAY_CASH_BASE as f64 * pay_ratio) as i64;

    // ============ 全浮动支出科目（对齐 calc_*）============
    let strength_factor = 1.0_f64; // Rust 无 armies.strength 表，回退 1.0
    // 各路口径合计：官额应得 due 与缺口 gap = max(0, due - 地方财力)（pay_ratio 加俸摊还占比基准）
    let mut share_due_total = 0.0_f64;
    let mut share_gap_total = 0.0_f64;
    for (_, p) in state.prefectures.iter() {
        let cle = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        // 官 component 取**付款权数**（子池折俸）—— 对齐 Python calc_pay_ratio L596-598；
        // 吏 component 仍按人头（本次不改）。
        let due = official_cash_pay(p) + cle * CLERK_PAY_PER_MONTH / 10000.0;
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

        let clerks = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);

        // 官俸折色：按**付款权数**（在岗 1.0 / 待阙 0.35 / 祠禄 0.4）计价，不再按人头全俸。
        // 对齐 Python calc_official_cash（game_state_econ.py:584）。
        official_cash += official_cash_pay(p);

        // 吏俸：pay_ratio = clamp((local_finance + payraise_budget*share/10000)/due, 0, 1)
        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = official_cash_pay(p) + clerks * CLERK_PAY_PER_MONTH / 10000.0;
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
        if let Some(v) = p.get_mut("storage") {
            if let Some(s) = v.as_f64() {
                *v = serde_json::json!(s + inflow);
            }
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
        let cle = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        // 官 component 取**付款权数**（与现金侧同一口径）；吏 component 仍按人头。
        let due = official_cash_pay(p) + cle * CLERK_PAY_PER_MONTH / 10000.0;
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

        let clerks = p.get("clerks").and_then(|v| v.as_f64()).unwrap_or(0.0);
        // 官禄本色：按**付款权数**计价（与现金侧同一乘数）。
        // 对齐 Python calc_official_grain（game_state_econ.py:574）。
        official_grain += official_grain_pay(p);

        let local = p.get("local_finance").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let due = official_cash_pay(p) + clerks * CLERK_PAY_PER_MONTH / 10000.0;
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

    // 田赋本色入：settle_land_local 已在 settle_turn 的 Step 3.5 把本色粮写入
    // 各路 storage（州仓），太仓只通过下方漕运汇聚接收（对齐 Python L456→L628-646）。
    // B2 修复：原此处再次 `let _grain_in = settle_land_local(state, log);` —— 该
    // 函数**带副作用**（会再向各路 storage 累加一次当月 inflow），而返回值本就
    // 未被使用（`_grain_in`），导致本色粮单月被双计。故删除该调用（仅保留注释）。

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
            if let Some(v) = p.get_mut("storage") {
                if let Some(s) = v.as_f64() {
                    *v = serde_json::json!((s - take).max(0.0));
                }
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

    // 恒等断言：Δ太仓 == 月出 − 漕运汇入。
    // 修复（2026-09-27）：原式写成 `(Δ) as i64 == (canal - out) as i64` —— ① 符号写反
    // （太仓是"加漕运、减月出"，Δ = out − canal）；② 浮点转 i64 截断，|值| ≥ 1 的非整数
    // 会左 1 右 −1 而误报（实测 `Δ=1.2726 canal=0 out=1.2726` 直接 panic，debug 构建下
    // 真实对局必炸）。现改为**容差比较**，并在触及仓容上下限（clamp 生效）时豁免。
    let _granary_delta = granary_before - state.granary;
    let _granary_expect = grain_out - canal;
    let _granary_clamped = state.granary <= 0.0 || state.granary >= state.granary_cap;
    debug_assert!(
        (_granary_delta - _granary_expect).abs() < 1e-6 || _granary_clamped,
        "太仓恒等断裂：Δ={} 月出={} 漕运={}", _granary_delta, grain_out, canal
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

// ============================================================
// 官俸付款权数（子池折俸）测试
//   权威口径：Python game/core/officialdom.py:route_pay_units
//             （在岗 1.0 / 待阙 WAITING_PAY_RATIO / 祠禄 SINECURE_PAY_RATIO）
// ============================================================
#[cfg(test)]
mod official_pay_units_tests {
    use super::*;
    use serde_json::json;

    /// 折色（现金）单位：万贯/月；本色（粮）单位：万石/月。
    const EPS: f64 = 1e-12;

    /// ① 有 `official_units` 镜像（Python 权威派生）：直接按权数计价，**不看人头**。
    #[test]
    fn mirror_official_units_drives_both_cash_and_grain() {
        // 官 100 人、子池折后权数 70
        let p = json!({"officials": 100.0, "clerks": 8.0, "official_units": 70.0});

        assert!((route_pay_units(&p) - 70.0).abs() < EPS, "镜像权数未被采用");

        // 现金路径：70 × OFFICIAL_PAY_PER_MONTH / 10000
        let cash_expect = 70.0 * OFFICIAL_PAY_PER_MONTH / 10000.0;
        assert!(
            (official_cash_pay(&p) - cash_expect).abs() < EPS,
            "官俸折色应 == 70×单价，实得 {}",
            official_cash_pay(&p)
        );
        // 粮路径：70 × OFFICIAL_GRAIN_PER_MONTH / 10000
        let grain_expect = 70.0 * OFFICIAL_GRAIN_PER_MONTH / 10000.0;
        assert!(
            (official_grain_pay(&p) - grain_expect).abs() < EPS,
            "官禄本色应 == 70×单价，实得 {}",
            official_grain_pay(&p)
        );

        // 反证：确实低于人头全俸（100 人），即折俸机制生效
        let headcount_cash = 100.0 * OFFICIAL_PAY_PER_MONTH / 10000.0;
        let headcount_grain = 100.0 * OFFICIAL_GRAIN_PER_MONTH / 10000.0;
        assert!(official_cash_pay(&p) < headcount_cash);
        assert!(official_grain_pay(&p) < headcount_grain);
        // 且恰为 70/100
        assert!((official_cash_pay(&p) / headcount_cash - 0.7).abs() < EPS);
        assert!((official_grain_pay(&p) / headcount_grain - 0.7).abs() < EPS);
    }

    /// ② 无镜像但有子池：按 1.0 / 0.35 / 0.4 推算（对齐 Python route_pay_units L299-301）。
    #[test]
    fn subpool_fallback_uses_waiting_and_sinecure_ratios() {
        let pop = |on_post: i64, waiting: i64, sinecure: i64| {
            json!({
                "officials": on_post + waiting + sinecure,
                "clerks": 8,
                "pops": {"官僚": {
                    "size": on_post + waiting + sinecure + 8,
                    "officials": on_post + waiting + sinecure,
                    "clerks": 8,
                    "on_post": on_post, "waiting": waiting, "sinecure": sinecure
                }}
            })
        };

        // 单一子池：逐一钉死三个权数常量
        assert!((route_pay_units(&pop(100, 0, 0)) - 100.0 * ON_POST_PAY_RATIO).abs() < EPS);
        assert!((route_pay_units(&pop(0, 100, 0)) - 100.0 * WAITING_PAY_RATIO).abs() < EPS);
        assert!((route_pay_units(&pop(0, 0, 100)) - 100.0 * SINECURE_PAY_RATIO).abs() < EPS);
        // 显式断言常量值本身（防止有人改常量后测试仍"自洽"通过）
        assert!((WAITING_PAY_RATIO - 0.35).abs() < EPS, "须与 data_constants.py:118 一致");
        assert!((SINECURE_PAY_RATIO - 0.4).abs() < EPS, "须与 data_constants.py:120 一致");

        // 混合子池 on_post=60 / waiting=30 / sinecure=10
        //   60×1.0 + 30×0.35 + 10×0.4 = 60 + 10.5 + 4 = 74.5
        // 注：任务书示例写"→ 权数 70.0"系笔误；按权威常量算应为 74.5（此处以常量为准）。
        let p = pop(60, 30, 10);
        assert!((route_pay_units(&p) - 74.5).abs() < EPS, "实得 {}", route_pay_units(&p));

        // 现金与粮两条路径同时断言
        assert!((official_cash_pay(&p) - 74.5 * OFFICIAL_PAY_PER_MONTH / 10000.0).abs() < EPS);
        assert!((official_grain_pay(&p) - 74.5 * OFFICIAL_GRAIN_PER_MONTH / 10000.0).abs() < EPS);
    }

    /// ③ 三者皆无（镜像/子池/人头子池都缺）：回退 `officials` 人头全俸。
    #[test]
    fn headcount_fallback_when_no_units_and_no_subpools() {
        let p = json!({"officials": 100.0, "clerks": 8.0});
        assert!((route_pay_units(&p) - 100.0).abs() < EPS);
        assert!(
            (official_cash_pay(&p) - 100.0 * OFFICIAL_PAY_PER_MONTH / 10000.0).abs() < EPS,
            "旧存档应回退人头全俸（现金）"
        );
        assert!(
            (official_grain_pay(&p) - 100.0 * OFFICIAL_GRAIN_PER_MONTH / 10000.0).abs() < EPS,
            "旧存档应回退人头全俸（粮）"
        );

        // 极端稳健：完全没有字段 → 0，不 panic
        let empty = json!({});
        assert_eq!(route_pay_units(&empty), 0.0);
        assert_eq!(official_cash_pay(&empty), 0.0);
        assert_eq!(official_grain_pay(&empty), 0.0);
    }

    /// 优先级与健壮性：镜像 ① > 子池 ② > 人头 ③；非法镜像值不当真。
    #[test]
    fn priority_order_and_robustness() {
        // 镜像优先于子池（official_units 已是权威派生值）
        let both = json!({
            "officials": 100.0, "official_units": 42.0,
            "pops": {"官僚": {"officials": 100, "on_post": 100, "waiting": 0, "sinecure": 0}}
        });
        assert!((route_pay_units(&both) - 42.0).abs() < EPS);

        // 镜像非法（负 / 字符串）→ 忽略，退回子池
        for bad in [json!(-1.0), json!("70"), json!(null), json!({"v": 70})] {
            let p = json!({
                "officials": 100.0, "official_units": bad,
                "pops": {"官僚": {"officials": 100, "on_post": 60, "waiting": 30, "sinecure": 10}}
            });
            assert!(
                (route_pay_units(&p) - 74.5).abs() < EPS,
                "非法镜像 {:?} 应被忽略",
                p.get("official_units")
            );
        }

        // 子池存在时优先于人头镜像 officials（否则"养更多官一分钱不多花"的双账复活）
        let subpool_beats_headcount = json!({
            "officials": 100.0,
            "pops": {"官僚": {"officials": 100, "on_post": 70, "waiting": 0, "sinecure": 0}}
        });
        assert!((route_pay_units(&subpool_beats_headcount) - 70.0).abs() < EPS);

        // 无子池但有 POP officials → 按 POP 人头（对齐 Python route_officials 的 POP 优先）
        let pop_headcount = json!({"officials": 1.0, "pops": {"官僚": {"officials": 250}}});
        assert!((route_pay_units(&pop_headcount) - 250.0).abs() < EPS);

        // 子池三键齐备但全 0（"全在待阙且已裁空"）→ 权数 0，不回退人头
        //   （与 Python `any(k in pop ...)` 判定一致：有键即按子池）
        let zero_subpools = json!({
            "officials": 100.0,
            "pops": {"官僚": {"officials": 100, "on_post": 0, "waiting": 0, "sinecure": 0}}
        });
        assert_eq!(route_pay_units(&zero_subpools), 0.0);

        // 负子池被夹到 0
        let negative_subpool = json!({
            "officials": 100.0,
            "pops": {"官僚": {"on_post": -5, "waiting": 10, "sinecure": 0}}
        });
        assert!((route_pay_units(&negative_subpool) - 10.0 * WAITING_PAY_RATIO).abs() < EPS);
    }

    /// 粮路径端到端：走真实 `settle_granary`，断言太仓支出按**付款权数**而非人头。
    #[test]
    fn settle_granary_subtracts_official_grain_by_units() {
        let mut state = GameState::new_game("");
        let routes = state.prefectures.len() as f64;
        assert!(routes > 0.0, "初始 12 路应非空");

        // 构造无干扰环境：每路 officials=1000 人头但 official_units=100（折俸后权数）；无兵、无吏、
        // 无地方财力、无州仓储粮（漕运为 0）、监察满格（贪腐损耗归零）、粮价平稳（不触发常平）。
        // 量级刻意取到 **月出 ≥ 1 万石**：settle_granary 的恒等断言原先用
        // `(Δ) as i64 == (canal - out) as i64`，符号写反且浮点截断，此量级必 panic
        // —— 2026-09-27 已改容差比较，本用例即为该回归的守卫。
        for p in state.prefectures.values_mut() {
            let obj = p.as_object_mut().expect("prefecture 应为 object");
            obj.insert("officials".into(), json!(1000.0));
            obj.insert("official_units".into(), json!(100.0));
            obj.insert("clerks".into(), json!(0.0));
            obj.insert("local_finance".into(), json!(0.0));
            obj.insert("garrisons".into(), json!({}));
            obj.insert("storage".into(), json!(0.0));
            obj.remove("pops");
        }
        state.oversight = 1.0;
        state.payraise_budget = 0;
        state.price_level = 1.0;
        state.granary = 100_000.0;
        state.granary_cap = 1_000_000.0;

        let units_total = 100.0 * routes;
        let official_grain = units_total * OFFICIAL_GRAIN_PER_MONTH / 10000.0;
        // 吏/兵为 0，贪腐项被 oversight=1 归零，故只余官禄 + 雀鼠耗
        let expect_out = official_grain * (1.0 + SPARROW_RAT);
        let expect_headcount_out = 1000.0 * routes * OFFICIAL_GRAIN_PER_MONTH / 10000.0
            * (1.0 + SPARROW_RAT);
        assert!(expect_out >= 1.0, "用量级须 ≥ 1 万石以覆盖截断回归：{}", expect_out);

        let before = state.granary;
        let mut log: Vec<String> = vec![];
        settle_granary(&mut state, &mut log);
        let spent = before - state.granary;

        assert!(
            (spent - expect_out).abs() < 1e-9,
            "太仓月出应 == 权数口径 {}，实得 {}",
            expect_out,
            spent
        );
        assert!(
            (spent - expect_headcount_out).abs() > 1e-9,
            "太仓月出仍等于人头口径 {}，折俸未生效",
            expect_headcount_out
        );
    }
}
