//! 游戏命令层 —— 对应 Python core/commands.py 的公开 API。
//!
//! 所有函数操作 `GameState`（后端持有），返回 (消息文本, 可选事件列表)。
//! AI 叙事在 Rust 端暂为占位（report 留空，见 server.rs），将来可在后端直连 LLM。

use crate::state::*;
use rand::Rng;

/// 工具：随机派系立场（与 Python _random_faction_stances 等价）。
fn random_faction_stances(state: &GameState) -> std::collections::HashMap<String, i64> {
    let mut m = std::collections::HashMap::new();
    let mut rng = rand::thread_rng();
    for name in state.factions.keys() {
        let v: i64 = rng.gen_range(-1..=1);
        m.insert(name.clone(), v);
    }
    m
}

fn clamp(v: i64, lo: i64, hi: i64) -> i64 {
    v.max(lo).min(hi)
}

/// 新建游戏。
pub fn new_game(difficulty: &str) -> GameState {
    // TODO: 难度预设（prestige_start / treasury_start 等）从 content.data 移植
    GameState::new_game(difficulty)
}

/// 下达普通诏令 / 御笔直发。
pub fn issue_decree(state: &mut GameState, decree: &DecreeInput) -> String {
    if decree.is_direct {
        if state.direct_decree_used >= 2 {
            return "本月御笔已用尽。".into();
        }
        let full = Decree {
            title: decree.title.clone().unwrap_or_else(|| "御笔诏令".into()),
            category: "御笔".into(),
            is_secret: false,
            is_direct: true,
            is_zhongzhi: false,
            turn_issued: state.turn,
            faction_stances: random_faction_stances(state),
            secret_loyalty: 0.5,
            effects: decree.effects.clone().unwrap_or(serde_json::json!({"prestige": 1})),
            duration: 1,
            targets: vec![],
            desc: decree.desc.clone().unwrap_or_default(),
            org_hint: String::new(),
        };
        let title = full.title.clone();
        state.pending_decrees.push(full);
        state.direct_decree_used += 1;
        state.wolf_count += 1;
        state.statistics.entry(String::from("total_decrees")).and_modify(|v| *v += 1).or_insert(1);
        let warn = if state.wolf_count >= 3 { "（警告：狼来了！密旨公信力下降。）" } else { "" };
        return format!("御笔直发：「{}」{}", title, warn);
    }
    if (state.pending_decrees.len() as i64) >= state.decree_bandwidth {
        return "诏令带宽已满！".into();
    }
    let full = Decree {
        title: decree.title.clone().unwrap_or_else(|| "诏令".into()),
        category: decree.category.clone().unwrap_or_else(|| "财政".into()),
        is_secret: false,
        is_direct: false,
        is_zhongzhi: false,
        turn_issued: state.turn,
        faction_stances: random_faction_stances(state),
        secret_loyalty: 0.5,
        effects: decree.effects.clone().unwrap_or(serde_json::json!({"prestige": 1})),
        duration: 1,
        targets: decree.targets.clone().unwrap_or_default(),
        desc: decree.desc.clone().unwrap_or_default(),
        org_hint: String::new(),
    };
    let title = full.title.clone();
    state.pending_decrees.push(full);
    state.statistics.entry(String::from("total_decrees")).and_modify(|v| *v += 1).or_insert(1);
    format!("已下诏：「{}」", title)
}

/// 下达密旨。
pub fn issue_secret_decree(state: &mut GameState, target: &str, content: &str) -> String {
    if (state.pending_secret_decrees.len() as i64) >= 3 {
        return "密旨已满（上限3道）。".into();
    }
    let d = Decree {
        title: if content.is_empty() { "密旨".into() } else { content.into() },
        category: "密旨".into(),
        is_secret: true,
        is_direct: false,
        is_zhongzhi: false,
        turn_issued: state.turn,
        faction_stances: std::collections::HashMap::new(),
        secret_loyalty: 0.6,
        effects: serde_json::json!({"prestige": 0}),
        duration: 1,
        targets: vec![],
        desc: content.into(),
        org_hint: String::new(),
    };
    state.pending_secret_decrees.push(d);
    state.statistics.entry("total_decrees".into()).and_modify(|v| *v += 1).or_insert(1);
    format!("密旨已下，目标：{}。", target)
}

/// 个人行动。
pub fn do_personal_action(state: &mut GameState, name: &str) -> String {
    state.personal_action = name.into();
    format!("本回合个人行动：{}", name)
}

/// 施政大项。
pub fn choose_major_policy(state: &mut GameState, policy: &str) -> String {
    state.major_policy = policy.into();
    format!("已定施政大项：「{}」", policy)
}

/// 推进一个月（返回需要玩家处理的事件列表）。
pub fn advance_month(state: &mut GameState) -> Vec<GameEvent> {
    // 月份/回合推进统一在 settle_turn 的月度结算之后完成，避免一回合重复计数。
    // TODO: 历史事件触发（get_historical_event）从 content.data 移植；此处随机占位
    let mut events = vec![];
    let mut rng = rand::thread_rng();
    if rng.gen_bool(0.25) {
        let ev = GameEvent {
            title: "地方水患".into(),
            message: "江南连雨，堤防告急，郡县请赈。".into(),
            desc: "江南连雨，堤防告急。".into(),
            // TODO: 事件 effects 数据对齐 Python core/commands.py 的 do_personal_action / 历史触发逻辑，
            //       暂以空 choices 占位，避免保留与 Python 端不对应的假数值。
            choices: vec![],
        };
        events.push(ev.clone());
        state.active_events.push(ev);
    }
    // 游戏结束判定（简化）
    if state.emperor_health <= 0 {
        state.emperor_alive = false;
        state.game_over = true;
    }
    events
}

/// 处理事件选择。
pub fn resolve_event(state: &mut GameState, event_title: &str, choice_idx: usize) -> String {
    // 找到 active 事件
    let mut chosen: Option<GameEvent> = None;
    for ev in &state.active_events {
        if ev.title == event_title {
            chosen = Some(ev.clone());
            break;
        }
    }
    let ev = match chosen {
        Some(e) => e,
        None => return "无此事件。".into(),
    };
    let choice = ev.choices.get(choice_idx).cloned().unwrap_or(serde_json::Value::Null);
    let mut log = vec![];
    if let Some(obj) = choice.as_object() {
        if let Some(effs) = obj.get("effects").and_then(|v| v.as_object()) {
            for (k, v) in effs {
                let val = v.as_i64().unwrap_or(0);
                match k.as_str() {
                    "population_satisfaction" => state.population_satisfaction = clamp(state.population_satisfaction + val, 0, 100),
                    "treasury" => state.treasury += val,
                    "prestige" => state.prestige = clamp(state.prestige + val, 0, 100),
                    "imperial_treasury" => state.imperial_treasury += val,
                    "defense_bonus" => {
                        for line in state.defense_lines.values_mut() {
                            line.garrison = clamp(line.garrison + val, 0, 100);
                        }
                    }
                    "faction_change" => {
                        if let Some(map) = v.as_object() {
                            for (fname, delta) in map {
                                if let (Some(f), Some(d)) = (state.factions.get_mut(fname.as_str()), delta.as_i64()) {
                                    f.satisfaction = clamp(f.satisfaction + d, 0, 100);
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
        log.push(format!("〔{}〕{}", ev.title, obj.get("label").and_then(|l| l.as_str()).unwrap_or("")));
    }
    // 清除在场标记
    state.active_events.retain(|e| e.title != event_title);
    if state.treasury < -2_000_000 {
        state.population_satisfaction = clamp(state.population_satisfaction - 2, 0, 100);
    }
    log.join("\n")
}

/// 客户端传入的诏令输入。
#[derive(Debug, Clone, serde::Deserialize)]
pub struct DecreeInput {
    pub title: Option<String>,
    pub category: Option<String>,
    pub desc: Option<String>,
    pub effects: Option<serde_json::Value>,
    pub targets: Option<Vec<String>>,
    #[serde(default)]
    pub is_direct: bool,
}
