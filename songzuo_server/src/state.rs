//! GameState —— 游戏核心状态（与 Python 端 save_load.py 的 JSON 字段一一对齐）。
//!
//! 设计目标：Rust 后端的 GameState 序列化后的 JSON 能被 Python 端 load_game 读取，
//! 反之亦然（字段名、类型尽量一致）。Python 端缺省字段用 serde(default) 兜底，
//! 保证旧存档 / 部分字段缺失时不崩溃。

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// 难度预设（与 Python DIFFICULTY_PRESETS 对应）。
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DifficultyPreset {
    pub prestige_start: i64,
    pub arrival_base: f64,
    #[serde(default)]
    pub treasury_start: i64,
    #[serde(default)]
    pub imperial_treasury_start: i64,
}

/// 派系运行态。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FactionState {
    pub influence: i64,
    pub satisfaction: i64,
    #[serde(default)]
    pub cohesion: i64,
    pub leader: String,
    #[serde(default)]
    pub net_support: f64,
    #[serde(default)]
    pub decree_stance: i64,
    #[serde(default)]
    pub last_decree_comment: String,
}

/// 外部势力。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalForce {
    #[serde(default)]
    pub attitude: i64,
    #[serde(default)]
    pub power: i64,
    #[serde(default)]
    pub invasion_will: i64,
}

/// 军队。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Army {
    #[serde(default)]
    pub strength: i64,
    #[serde(default)]
    pub morale: i64,
    #[serde(default)]
    pub location: String,
}

/// 防线。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DefenseLine {
    #[serde(default)]
    pub level: i64,
    #[serde(default)]
    pub garrison: i64,
}

/// 诏令 / 密旨 / 中旨。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Decree {
    pub title: String,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub is_secret: bool,
    #[serde(default)]
    pub is_direct: bool,
    #[serde(default)]
    pub is_zhongzhi: bool,
    #[serde(default = "default_turn")]
    pub turn_issued: i64,
    #[serde(default)]
    pub faction_stances: HashMap<String, i64>,
    #[serde(default)]
    pub secret_loyalty: f64,
    #[serde(default)]
    pub effects: serde_json::Value,
    #[serde(default = "default_one")]
    pub duration: i64,
    #[serde(default)]
    pub targets: Vec<String>,
    #[serde(default)]
    pub desc: String,
    #[serde(default)]
    pub org_hint: String,
}

fn default_turn() -> i64 { 0 }
fn default_one() -> i64 { 1 }

/// 长期政务任务（公开 / 密令）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LongTermTask {
    #[serde(default)]
    pub task_name: String,
    #[serde(default = "default_twelve")]
    pub months: i64,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub params: serde_json::Value,
    #[serde(default)]
    pub minister: String,
    #[serde(default)]
    pub progress: i64,
    #[serde(default)]
    pub last_log: String,
}

fn default_twelve() -> i64 { 12 }

/// 诏草（待会签）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdictDraft {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub body: String,
    #[serde(default)]
    pub effects: serde_json::Value,
    #[serde(default)]
    pub org_hint: String,
    #[serde(default)]
    pub source_minister: String,
}

/// 事件。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GameEvent {
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub desc: String,
    #[serde(default)]
    pub choices: Vec<serde_json::Value>,
}

/// 中央机构运行态（权限随职位）。
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CentralOrg {
    #[serde(default)]
    pub loyalty: f64,
    #[serde(default)]
    pub authority: f64,
}

/// 主状态。所有字段对齐 Python save_load.save_game 的 data 字典。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GameState {
    // 版本 / 元信息
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub save_time_str: String,
    #[serde(default = "default_slot")]
    pub slot: i64,

    // 时间
    #[serde(default = "default_year")]
    pub year: i64,
    #[serde(default = "default_month")]
    pub month: i64,
    #[serde(default)]
    pub turn: i64,
    #[serde(default)]
    pub era_name: String,
    #[serde(default)]
    pub difficulty: String,

    // 皇帝
    #[serde(default)]
    pub emperor_name: String,
    #[serde(default = "default_health")]
    pub emperor_health: i64,
    #[serde(default = "default_true")]
    pub emperor_alive: bool,
    #[serde(default = "default_false")]
    pub is_abdicated: bool,
    #[serde(default)]
    pub abdication_reason: String,
    #[serde(default)]
    pub art_mastery: i64,
    #[serde(default)]
    pub tech: serde_json::Value,        // 科技树（含 level，默认 50）
    #[serde(default)]
    pub taoism_leaning: i64,
    #[serde(default)]
    pub pleasure_leaning: i64,

    // 皇威 / 到账率
    #[serde(default)]
    pub prestige: i64,
    #[serde(default)]
    pub arrival_rate_base: f64,

    // 国库 / 内帑
    #[serde(default)]
    pub treasury: i64,
    #[serde(default)]
    pub imperial_treasury: i64,
    // 内帑（甲口径）：imperial_treasury = 国库净结余抽成 + 榷酒课，与国库分理

    // 仓廪（经济全浮动重构：太仓本色粮，万石）
    #[serde(default)]
    pub granary: f64,             // 太仓现储（万石）
    #[serde(default)]
    pub granary_cap: f64,         // 太仓容量（万石）

    // 加俸预算（厚禄养廉，逐月摊还驱动 pay_ratio）
    #[serde(default)]
    pub payraise_budget: i64,
    // 监察力度 oversight（0~1，越高贪腐扣减越低）
    #[serde(default)]
    pub oversight: f64,

    // 派系
    #[serde(default)]
    pub factions: HashMap<String, FactionState>,

    // 外部势力 / 军事
    #[serde(default)]
    pub external: HashMap<String, ExternalForce>,
    #[serde(default)]
    pub armies: HashMap<String, Army>,
    #[serde(default)]
    pub defense_lines: HashMap<String, DefenseLine>,

    // 诏令
    #[serde(default = "default_bandwidth")]
    pub decree_bandwidth: i64,
    #[serde(default)]
    pub direct_decree_used: i64,
    #[serde(default)]
    pub wolf_count: i64,
    #[serde(default)]
    pub pending_decrees: Vec<Decree>,
    #[serde(default)]
    pub pending_secret_decrees: Vec<Decree>,
    #[serde(default)]
    pub pending_public_decrees: Vec<Decree>,
    #[serde(default)]
    pub active_decrees: Vec<Decree>,
    #[serde(default)]
    pub edict_drafts: Vec<EdictDraft>,
    #[serde(default)]
    pub council_reviews: HashMap<String, serde_json::Value>,

    // 施政
    #[serde(default)]
    pub personal_action: String,
    #[serde(default)]
    pub major_policy: String,
    #[serde(default)]
    pub major_policy_target: String,

    // 事件
    #[serde(default)]
    pub active_events: Vec<GameEvent>,
    #[serde(default)]
    pub event_pressure: HashMap<String, i64>,
    #[serde(default)]
    pub event_history: Vec<String>,

    // 人口 / 民生
    #[serde(default = "default_pop")]
    pub population: i64,
    #[serde(default = "default_sat")]
    pub population_satisfaction: i64,
    #[serde(default)]
    pub refugee_count: i64,

    // 灾荒
    #[serde(default)]
    pub disaster_severity: i64,
    #[serde(default)]
    pub disaster_region: String,

    // 难度系数 / 统计
    #[serde(default)]
    pub diff_params: serde_json::Value,
    #[serde(default)]
    pub statistics: HashMap<String, i64>,

    // 锦衣卫
    #[serde(default)]
    pub spy_network: HashMap<String, f64>,

    // 记录
    #[serde(default)]
    pub settlement_log: Vec<Vec<String>>,
    #[serde(default = "default_false")]
    pub game_over: bool,
    #[serde(default)]
    pub game_result: String,
    #[serde(default = "default_false")]
    pub victory: bool,

    // 六部衙门 / 州县 / 外部政权
    #[serde(default)]
    pub yamen: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub prefectures: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub external_regimes: HashMap<String, serde_json::Value>,

    // 长期政务
    #[serde(default)]
    pub longterm_public: Vec<LongTermTask>,
    #[serde(default)]
    pub longterm_secret: Vec<LongTermTask>,

    // 大臣记忆 / 状态
    #[serde(default)]
    pub minister_memory: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub player_minister_status: HashMap<String, String>,

    // 后台隐藏态
    #[serde(default)]
    pub loyalty: HashMap<String, f64>,
    #[serde(default)]
    pub corruption: HashMap<String, f64>,
    #[serde(default)]
    pub central_orgs: HashMap<String, CentralOrg>,
    #[serde(default)]
    pub authority_matters: HashMap<String, serde_json::Value>,

    // 扩展维度
    #[serde(default)]
    pub land: serde_json::Value,
    #[serde(default)]
    pub jiaozi: serde_json::Value,
    #[serde(default)]
    pub maritime: serde_json::Value,
    #[serde(default)]
    pub coin: serde_json::Value,
    #[serde(default)]
    pub bank: serde_json::Value,
    #[serde(default)]
    pub standard: serde_json::Value,

    // 财政口径强类型字段（对齐 Python game_state.finance_readout / settlement）
    #[serde(default = "default_commerce_tax_rate")]
    pub commerce_tax_rate: f64,        // 工商征率（0.05~0.40）
    #[serde(default)]
    pub waste_reform: serde_json::Value,   // 变法节流 {savings: i64}
    #[serde(default)]
    pub pay_system: serde_json::Value,     // 折色俸禄 {cash_ratio: f64, mode: String}
    #[serde(default)]
    pub economy_knowledge: serde_json::Value, // 认知层（滞后奏报）{grain_price: f64}
    #[serde(default = "default_money_supply")]
    pub money_supply: f64,              // 货币有效供给（贯）
    #[serde(default = "default_price_level")]
    pub price_level: f64,               // 物价水平（钱/物之比）

    // 对话历史 / 上次召见
    #[serde(default)]
    pub dialogue_history: Vec<(String, String)>,
    #[serde(default)]
    pub last_audience: String,
}

// ---- 默认值 ----
fn default_slot() -> i64 { 1 }
fn default_year() -> i64 { 1101 }
fn default_month() -> i64 { 1 }
fn default_health() -> i64 { 75 }
fn default_true() -> bool { true }
fn default_false() -> bool { false }
fn default_bandwidth() -> i64 { 3 }
fn default_pop() -> i64 { 80_000_000 }
fn default_sat() -> i64 { 55 }
fn default_commerce_tax_rate() -> f64 { 0.15 }
fn default_money_supply() -> f64 { 200_000_000.0 }
fn default_price_level() -> f64 { 1.0 }

impl Default for GameState {
    fn default() -> Self {
        GameState {
            version: "0.1.0".into(),
            // schema_version（经济 v2）由 save.rs 写入；此处默认初始不写入存档
            save_time_str: String::new(),
            slot: 1,
            year: 1101,
            month: 1,
            turn: 0,
            era_name: "建中靖国".into(),
            difficulty: "史实".into(),
            emperor_name: "赵佶".into(),
            emperor_health: 75,
            emperor_alive: true,
            is_abdicated: false,
            abdication_reason: String::new(),
            art_mastery: 50,
            tech: serde_json::json!({"level": 50}),
            taoism_leaning: 50,
            pleasure_leaning: 50,
            prestige: 55,
            arrival_rate_base: 0.45,
            treasury: 5_000_000,
            imperial_treasury: 1_000_000,
            granary: 1500.0,
            granary_cap: 2000.0,
            payraise_budget: 0,
            oversight: 0.30,
            factions: HashMap::new(),
            external: HashMap::new(),
            armies: HashMap::new(),
            defense_lines: HashMap::new(),
            decree_bandwidth: 3,
            direct_decree_used: 0,
            wolf_count: 0,
            pending_decrees: vec![],
            pending_secret_decrees: vec![],
            pending_public_decrees: vec![],
            active_decrees: vec![],
            edict_drafts: vec![],
            council_reviews: HashMap::new(),
            personal_action: String::new(),
            major_policy: String::new(),
            major_policy_target: String::new(),
            active_events: vec![],
            event_pressure: HashMap::new(),
            event_history: vec![],
            population: 80_000_000,
            population_satisfaction: 55,
            refugee_count: 0,
            disaster_severity: 0,
            disaster_region: String::new(),
            diff_params: serde_json::Value::Null,
            statistics: {
                let mut m = HashMap::new();
                m.insert("total_income".into(), 0);
                m.insert("total_expenditure".into(), 0);
                m.insert("total_decrees".into(), 0);
                m.insert("total_wars".into(), 0);
                m.insert("total_disasters".into(), 0);
                m
            },
            spy_network: HashMap::new(),
            settlement_log: vec![],
            game_over: false,
            game_result: String::new(),
            victory: false,
            yamen: HashMap::new(),
            prefectures: crate::constants::default_prefectures(),
            external_regimes: HashMap::new(),
            longterm_public: vec![],
            longterm_secret: vec![],
            minister_memory: HashMap::new(),
            player_minister_status: HashMap::new(),
            loyalty: HashMap::new(),
            corruption: HashMap::new(),
            central_orgs: HashMap::new(),
            authority_matters: HashMap::new(),
            land: serde_json::Value::Null,
            jiaozi: serde_json::Value::Null,
            maritime: serde_json::Value::Null,
            coin: serde_json::Value::Null,
            bank: serde_json::Value::Null,
            standard: serde_json::Value::Null,
            commerce_tax_rate: 0.15,
            waste_reform: serde_json::json!({"savings": 0}),
            pay_system: serde_json::json!({"cash_ratio": 0.5, "mode": "分发"}),
            economy_knowledge: serde_json::json!({}),
            money_supply: 200_000_000.0,
            price_level: 1.0,
            dialogue_history: vec![],
            last_audience: String::new(),
        }
    }
}

impl GameState {
    /// 新建一局游戏（对应 Python new_game）。
    pub fn new_game(difficulty: &str) -> Self {
        let mut s = GameState::default();
        // 显式注入 12 路州县初始数据（与 Default 一致，避免外部构造漏填）
        s.prefectures = crate::constants::default_prefectures();
        if !difficulty.is_empty() {
            s.difficulty = difficulty.to_string();
        }
        s
    }

    /// 古意纪年字符串（与 Python _refresh_hud 展示一致）。
    #[allow(dead_code)]
    pub fn era_label(&self) -> String {
        let season = match self.month {
            12 | 1 | 2 => "冬",
            3 | 4 | 5 => "春",
            6 | 7 | 8 => "夏",
            _ => "秋",
        };
        format!("{} {}年·{}·{}月朔日", self.era_name, self.year, season, self.month)
    }

    /// 朝局摘要（供前端展示 / 将来 AI 调用）。
    #[allow(dead_code)]
    pub fn summary(&self) -> serde_json::Value {
        serde_json::json!({
            "time": format!("{} {}年{}月", self.era_name, self.year, self.month),
            "prestige": self.prestige,
            "treasury": self.treasury,
            "imperial_treasury": self.imperial_treasury,
            "population_satisfaction": self.population_satisfaction,
            "factions": self.factions,
            "turn": self.turn,
            "game_over": self.game_over,
        })
    }
}
