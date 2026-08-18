//! 存档读写 —— 与 Python 端 core/save_load.py 共享同一 saves/ 目录与 slot_{n}.json 格式。
//!
//! Rust 写出的 JSON 包含 Python load_game 读取的全部字段（用 serde 默认对齐），
//! 因此 Python 端可直接读 Rust 存的档；Rust 读 Python 档时忽略未知字段（core 可玩）。

use crate::state::GameState;
use std::env;
use std::path::PathBuf;

/// 存档目录：优先用环境变量 SONGZUO_SAVE_DIR 覆盖；云托管默认容器内持久卷 /data/saves，
/// 不可用 Windows 绝对路径（容器内为 Linux）。挂载持久卷后存档才会跨重启保留。
pub fn save_dir() -> PathBuf {
    if let Ok(d) = env::var("SONGZUO_SAVE_DIR") {
        PathBuf::from(d)
    } else {
        // 云托管持久卷默认挂载点；与 Python content.data.SAVE_DIR 仅在本地演示时对齐
        PathBuf::from("/data/saves")
    }
}

/// 写存档（对应 Python save_game）。
pub fn save_game(state: &GameState, slot: i64) -> Result<(), String> {
    let dir = save_dir();
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(format!("slot_{}.json", slot));
    let mut value = serde_json::to_value(state).map_err(|e| e.to_string())?;
    if let Some(obj) = value.as_object_mut() {
        obj.insert("version".into(), serde_json::json!("0.1.0"));
        obj.insert("schema_version".into(), serde_json::json!(2));  // 经济全浮动 v2：废弃 imperial_treasury
        obj.insert("slot".into(), serde_json::json!(slot));
        obj.insert("save_time_str".into(), serde_json::json!(chrono_now()));
        // Python load_game 读取但 Rust 结构未显式建模的字段，补默认值保证兼容
        obj.entry(String::from("exam")).or_insert(serde_json::json!({"talent_pool": 50, "schools": 30}));
        obj.entry(String::from("tech")).or_insert(serde_json::json!({"level": 30, "gunpowder": 20}));
        obj.entry(String::from("diplomacy_log")).or_insert(serde_json::json!([]));
        obj.insert("alliance_jin_liao".to_string(), serde_json::json!(false));
    }
    let s = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
    std::fs::write(&path, s).map_err(|e| e.to_string())?;
    Ok(())
}

/// 读存档（对应 Python load_game）。
pub fn load_game(slot: i64) -> Result<GameState, String> {
    let dir = save_dir();
    let path = dir.join(format!("slot_{}.json", slot));
    if !path.exists() {
        return Err(format!("存档槽 {} 不存在", slot));
    }
    let s = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let state: GameState = serde_json::from_str(&s).map_err(|e| e.to_string())?;
    Ok(state)
}

fn chrono_now() -> String {
    // 避免引入 chrono 依赖，用简单格式
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("t{}", secs)
}
