//! HTTP 服务层 —— 用 axum 暴露游戏后端 API。
//!
//! 前端（tkinter 客户端）通过 REST 调用本服务。后端持有 GameState（进程内），
//! 所有逻辑在后端执行，前端只收发 JSON 状态快照。
//!
//! 端点：
//!   POST /api/new_game   {difficulty}                -> {state}
//!   POST /api/action     {action, params}             -> {state, message}
//!   POST /api/advance                              -> {state, log, report, events}
//!   POST /api/resolve_event {title, choice}          -> {state, message}
//!   GET  /api/state                                -> {state}
//!   POST /api/save      {slot}                      -> {ok}
//!   POST /api/load      {slot}                      -> {state}

use crate::commands::*;
use crate::save::*;
use crate::settle;
use crate::state::*;
use axum::{
    extract::State,
    http::StatusCode,
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};

/// 后端全局状态：持有当前游戏（演示用单会话；后期可换 HashMap<session_id, GameState>）。
#[derive(Clone)]
pub struct AppState {
    pub game: Arc<Mutex<Option<GameState>>>,
}

/// 朝报/结算后的统一响应。
#[derive(Serialize)]
pub struct ActionResult {
    pub state: GameState,
    #[serde(default)]
    pub message: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub log: Vec<String>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub report: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub events: Vec<GameEvent>,
}

#[derive(Deserialize)]
pub struct NewGameReq {
    #[serde(default)]
    pub difficulty: String,
}

#[derive(Deserialize)]
pub struct ActionReq {
    pub action: String,
    #[serde(default)]
    pub params: serde_json::Value,
}

#[derive(Deserialize)]
pub struct ResolveEventReq {
    pub title: String,
    #[serde(default)]
    pub choice: usize,
}

#[derive(Deserialize)]
pub struct SlotReq {
    #[serde(default = "default_slot")]
    pub slot: i64,
}
fn default_slot() -> i64 { 1 }

/// 启动 HTTP 服务。
pub async fn serve(addr: &str) {
    let state = AppState {
        game: Arc::new(Mutex::new(None)),
    };
    let app = Router::new()
        .route("/api/new_game", post(new_game_handler))
        .route("/api/action", post(action_handler))
        .route("/api/advance", post(advance_handler))
        .route("/api/resolve_event", post(resolve_event_handler))
        .route("/api/save", post(save_handler))
        .route("/api/load", post(load_handler))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    println!("[songzuo_server] 监听于 http://{}", addr);
    axum::serve(listener, app).await.unwrap();
}

async fn new_game_handler(
    State(st): State<AppState>,
    Json(req): Json<NewGameReq>,
) -> Json<ActionResult> {
    let mut g = st.game.lock().unwrap();
    let gs = new_game(&req.difficulty);
    let snapshot = gs.clone();
    *g = Some(gs);
    Json(ActionResult {
        state: snapshot,
        message: "新朝开局。".into(),
        log: vec![],
        report: String::new(),
        events: vec![],
    })
}

async fn action_handler(
    State(st): State<AppState>,
    Json(req): Json<ActionReq>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    let mut g = st.game.lock().unwrap();
    let gs = g.as_mut().ok_or((StatusCode::BAD_REQUEST, "尚未开局".into()))?;
    let msg = match req.action.as_str() {
        "issue_decree" => {
            let d: DecreeInput = serde_json::from_value(req.params.clone())
                .unwrap_or(DecreeInput { title: None, category: None, desc: None, effects: None, targets: None, is_direct: false });
            issue_decree(gs, &d)
        }
        "issue_secret_decree" => {
            let target = req.params.get("target").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let content = req.params.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string();
            issue_secret_decree(gs, &target, &content)
        }
        "do_personal_action" => {
            let name = req.params.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
            do_personal_action(gs, &name)
        }
        "choose_major_policy" => {
            let p = req.params.get("policy").and_then(|v| v.as_str()).unwrap_or("").to_string();
            choose_major_policy(gs, &p)
        }
        other => return Err((StatusCode::BAD_REQUEST, format!("未知动作: {}", other))),
    };
    let snapshot = gs.clone();
    Ok(Json(ActionResult {
        state: snapshot,
        message: msg,
        log: vec![],
        report: String::new(),
        events: vec![],
    }))
}

async fn advance_handler(
    State(st): State<AppState>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    let mut g = st.game.lock().unwrap();
    let gs = g.as_mut().ok_or((StatusCode::BAD_REQUEST, "尚未开局".into()))?;
    let events = advance_month(gs);
    let log = settle::settle_turn(gs);
    // AI 模块已移除（纯占位，后端未接 LLM，前端不直调后端 AI）；report 留空对齐简化版
    let report = String::new();
    let snapshot = gs.clone();
    Ok(Json(ActionResult {
        state: snapshot,
        message: "回合推演完成。".into(),
        log,
        report,
        events,
    }))
}

async fn resolve_event_handler(
    State(st): State<AppState>,
    Json(req): Json<ResolveEventReq>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    let mut g = st.game.lock().unwrap();
    let gs = g.as_mut().ok_or((StatusCode::BAD_REQUEST, "尚未开局".into()))?;
    let msg = resolve_event(gs, &req.title, req.choice);
    let snapshot = gs.clone();
    Ok(Json(ActionResult {
        state: snapshot,
        message: msg,
        log: vec![],
        report: String::new(),
        events: vec![],
    }))
}

async fn save_handler(
    State(st): State<AppState>,
    Json(req): Json<SlotReq>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let g = st.game.lock().unwrap();
    match g.as_ref() {
        Some(gs) => {
            match save_game(gs, req.slot) {
                Ok(_) => Ok(Json(serde_json::json!({"ok": true}))),
                Err(e) => Err((StatusCode::INTERNAL_SERVER_ERROR, e)),
            }
        }
        None => Err((StatusCode::BAD_REQUEST, "尚未开局".into())),
    }
}

async fn load_handler(
    State(st): State<AppState>,
    Json(req): Json<SlotReq>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    match load_game(req.slot) {
        Ok(gs) => {
            let snapshot = gs.clone();
            *st.game.lock().unwrap() = Some(gs);
            Ok(Json(ActionResult {
                state: snapshot,
                message: "读档成功。".into(),
                log: vec![],
                report: String::new(),
                events: vec![],
            }))
        }
        Err(e) => Err((StatusCode::NOT_FOUND, e)),
    }
}
