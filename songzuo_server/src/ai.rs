//! AI 叙事层 —— 方案 a 阶段：离线兜底（不联网）。
//!
//! 返回结构化兜底文本，前端据此展示；将来接 LLM 时只需在此模块内替换实现，
//! 对外接口（每月报告 / 事件叙事 / 召对建言 / 结局评定）保持不变。

/// AI 是否可用（离线阶段恒为 false）。
pub const AI_AVAILABLE: bool = false;

/// 月度朝报（丞相月折）离线兜底。
pub fn monthly_report(year: i64, month: i64, era: &str) -> serde_json::Value {
    serde_json::json!({
        "report": format!("〔{} {}年{}月 · 离线月度简报〕\n天下粗安，诸事尚可。待接 AI 后呈详细奏对。",
            era, year, month),
        "scenes": [],
    })
}

/// 事件叙事离线兜底。
pub fn event_narrative(title: &str) -> String {
    format!("（离线叙事）{}之事，朝野议论不一，且听陛下圣裁。", title)
}

/// 召对建言离线兜底。
pub fn advice() -> String {
    "（离线建言）此事可从权，亦当审时度势。".into()
}

/// 结局评定离线兜底。
pub fn final_eval(year: i64) -> String {
    format!("（离线评定）至 {} 年，国祚仍在，功过留与后人评说。", year)
}
