//! HTTP 服务层 —— 用 axum 暴露游戏后端 API。
//!
//! 前端（game/frontend，Electron + React）通过 REST 调用本服务。后端持有 GameState
//! （进程内），所有逻辑在后端执行，前端只收发 JSON 状态快照。
//!
//! 鉴权：设置 `SONGZUO_SERVER_TOKEN` 后 `/api/*` 需 `Authorization: Bearer <token>`；
//! 未设置时仅接受本机回环来源（见 auth_mw）。
//!
//! 端点（**简化版**：Python 端 `game/backend/server.py` 端点更全，如
//! `/api/state` `/api/readouts` `/api/meter` `/api/council_review`
//! `/api/monthly_report` `/api/decree/*` `/api/ai_config` `/api/save_slots`
//! `/api/conclude` 均**尚未在本 crate 实现**）：
//!   POST /api/new_game   {difficulty}                -> {state}
//!   POST /api/action     {action, params}             -> {state, message}
//!   POST /api/advance                              -> {state, log, report, events}
//!   POST /api/resolve_event {title, choice}          -> {state, message}
//!   POST /api/save      {slot}                      -> {ok}
//!   POST /api/load      {slot}                      -> {state}
//!   GET  /health | /healthz | /                    -> 200（就绪探针）

use crate::commands::*;
use crate::save::*;
use crate::settle;
use crate::state::*;
use axum::{
    extract::{ConnectInfo, Request as AxumRequest, State},
    http::{HeaderValue, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use tower_http::cors::{Any, CorsLayer};
use serde::{Deserialize, Serialize};
use std::net::{IpAddr, SocketAddr};
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

/// 鉴权配置（安全审查 A5）：token 为空时仅放行本机回环来源。
#[derive(Clone)]
struct AuthCfg {
    token: Option<String>,
}

/// 常量时间字符串比较（防 Bearer 时序侧信道）。
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for i in 0..a.len() {
        diff |= a[i] ^ b[i];
    }
    diff == 0
}

fn is_loopback(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => v4.is_loopback(),
        IpAddr::V6(v6) => v6.is_loopback(),
    }
}

/// `/api/*` 鉴权中间件（安全审查 A5）。
///
/// 修复前：Rust 后端完全无鉴权（且默认绑 0.0.0.0），任何网络可达者均可
/// `new_game/advance/save/load`。现规则与 Python 端同构：
///   - 配置了 `SONGZUO_SERVER_TOKEN`：必须携带 `Authorization: Bearer <token>`；
///   - 未配置：仅接受回环来源（本机演示），其余一律 401。
async fn auth_mw(
    State(cfg): State<AuthCfg>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    req: AxumRequest,
    next: Next,
) -> Result<Response, (StatusCode, String)> {
    if req.uri().path().starts_with("/api/") {
        match cfg.token.as_deref() {
            Some(tok) => {
                let got = req
                    .headers()
                    .get(axum::http::header::AUTHORIZATION)
                    .and_then(|v| v.to_str().ok())
                    .unwrap_or("");
                let want = format!("Bearer {}", tok);
                if !constant_time_eq(got.as_bytes(), want.as_bytes()) {
                    return Err((StatusCode::UNAUTHORIZED, "令符不合，未获授权。".into()));
                }
            }
            None => {
                if !is_loopback(addr.ip()) {
                    return Err((
                        StatusCode::UNAUTHORIZED,
                        "服务端未配置 SONGZUO_SERVER_TOKEN，且来源非本机，拒绝访问。".into(),
                    ));
                }
            }
        }
    }
    Ok(next.run(req).await)
}

/// 启动 HTTP 服务。
pub async fn serve(addr: &str) {
    let token = std::env::var("SONGZUO_SERVER_TOKEN")
        .ok()
        .filter(|s| !s.trim().is_empty());
    if token.is_none() {
        println!("[songzuo_server] 未设置 SONGZUO_SERVER_TOKEN：/api/* 仅接受本机回环来源");
    }
    let auth_cfg = AuthCfg { token };

    let state = AppState {
        game: Arc::new(Mutex::new(None)),
    };
    // CORS：默认开放（云托管后端面对浏览器/小程序前端）；生产可设
    //   SONGZUO_CORS_ORIGINS="https://a.example,https://b.example"
    // 收紧来源白名单。安全边界由上方 auth_mw 承担，CORS 仅约束浏览器侧。
    let cors = match std::env::var("SONGZUO_CORS_ORIGINS") {
        Ok(v) if !v.trim().is_empty() => {
            let origins: Vec<HeaderValue> = v
                .split(',')
                .filter_map(|s| s.trim().parse::<HeaderValue>().ok())
                .collect();
            CorsLayer::new()
                .allow_origin(origins)
                .allow_methods(Any)
                .allow_headers(Any)
        }
        _ => CorsLayer::new()
            .allow_origin(Any)
            .allow_methods(Any)
            .allow_headers(Any),
    };

    // 健康检查路由：供云托管 readiness probe 使用，返回 200 即视为就绪。
    async fn healthz() -> StatusCode {
        StatusCode::OK
    }

    let app = Router::new()
        .route("/api/new_game", post(new_game_handler))
        .route("/api/action", post(action_handler))
        .route("/api/advance", post(advance_handler))
        .route("/api/resolve_event", post(resolve_event_handler))
        .route("/api/save", post(save_handler))
        .route("/api/load", post(load_handler))
        .route("/", get(healthz))
        .route("/healthz", get(healthz))
        // 审查修复（D）：Python 端与 Electron checkHealth 都用 /health，
        // Rust 原先只有 /healthz → 指向本后端时健康检查恒失败。补别名。
        .route("/health", get(healthz))
        .layer(middleware::from_fn_with_state(auth_cfg, auth_mw))
        .layer(cors)
        .with_state(state);

    // 审查修复（D）：bind/serve 失败给出明确错误，而非裸 panic。
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("[songzuo_server] 绑定 {} 失败：{}（端口可能被占用）", addr, e);
            std::process::exit(1);
        }
    };
    println!("[songzuo_server] 监听于 http://{}", addr);
    if let Err(e) = axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await
    {
        eprintln!("[songzuo_server] 服务异常退出：{}", e);
    }
}

/// 取游戏状态锁：**中毒不 panic**（审查 P3-18）。
///
/// `Mutex::lock()` 在前次持锁线程 panic 后会返回 `Err(PoisonError)`；原实现
/// `lock().unwrap()` 会把它变成**级联 panic**，令整个后端无诊断信息地不可用。
/// 这里改为返回可读 500，锁定失败也只影响本次请求。
fn lock_game(
    st: &AppState,
) -> Result<std::sync::MutexGuard<'_, Option<GameState>>, (StatusCode, String)> {
    st.game.lock().map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "游戏状态锁已中毒（此前请求发生 panic），请重启后端进程。".to_string(),
        )
    })
}

async fn new_game_handler(
    State(st): State<AppState>,
    Json(req): Json<NewGameReq>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    // 缩短锁范围：新局构造在锁外，锁内只做一次指针替换。
    let gs = new_game(&req.difficulty);
    let snapshot = gs.clone();
    {
        let mut g = lock_game(&st)?;
        *g = Some(gs);
    }
    Ok(Json(ActionResult {
        state: snapshot,
        message: "新朝开局。".into(),
        log: vec![],
        report: String::new(),
        events: vec![],
    }))
}

async fn action_handler(
    State(st): State<AppState>,
    Json(req): Json<ActionReq>,
) -> Result<Json<ActionResult>, (StatusCode, String)> {
    let mut g = lock_game(&st)?;
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
    drop(g); // 缩短锁范围：快照已取，JSON 序列化在锁外
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
    let mut g = lock_game(&st)?;
    let gs = g.as_mut().ok_or((StatusCode::BAD_REQUEST, "尚未开局".into()))?;
    let events = advance_month(gs);
    let log = settle::settle_turn(gs);
    // AI 模块已移除（纯占位，后端未接 LLM，前端不直调后端 AI）；report 留空对齐简化版
    let report = String::new();
    let snapshot = gs.clone();
    drop(g); // 缩短锁范围：快照已取，JSON 序列化在锁外
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
    let mut g = lock_game(&st)?;
    let gs = g.as_mut().ok_or((StatusCode::BAD_REQUEST, "尚未开局".into()))?;
    let msg = resolve_event(gs, &req.title, req.choice);
    let snapshot = gs.clone();
    drop(g); // 缩短锁范围：快照已取，JSON 序列化在锁外
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
    let g = lock_game(&st)?;
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
            {
                let mut g = lock_game(&st)?;
                *g = Some(gs);
            }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_time_eq_matches_and_differs() {
        // 鉴权比较：等值真、异值假、长度不等假（常量时间，不走短路）
        assert!(constant_time_eq(b"Bearer token", b"Bearer token"));
        assert!(!constant_time_eq(b"Bearer token", b"Bearer tokeX"));
        assert!(!constant_time_eq(b"Bearer token", b"Bearer"));
        assert!(constant_time_eq(b"", b""));
    }

    #[test]
    fn poisoned_lock_returns_error_instead_of_panicking() {
        // 审查 P3-18：锁中毒（前次持锁 panic）必须返回可读 500，而不是 unwrap 级联 panic。
        let st = AppState {
            game: Arc::new(Mutex::new(None)),
        };
        let g = st.game.clone();
        let res = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
            let _guard = g.lock().unwrap();
            panic!("simulate poisoned mutex");
        }));
        assert!(res.is_err(), "构造 poison 失败");
        let r = lock_game(&st);
        assert!(r.is_err(), "锁中毒时 lock_game 必须返回 Err");
        let (code, msg) = r.err().unwrap();
        assert_eq!(code, StatusCode::INTERNAL_SERVER_ERROR);
        assert!(msg.contains("中毒"), "错误信息应可读: {}", msg);
    }

    #[test]
    fn healthy_lock_still_works() {
        let st = AppState {
            game: Arc::new(Mutex::new(None)),
        };
        let guard = lock_game(&st).expect("健康锁应可获取");
        assert!(guard.is_none());
    }
}
