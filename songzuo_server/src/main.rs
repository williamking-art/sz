//! 宋祚后端服务（Rust）
//!
//! 玩家运行前端客户端（tkinter / 将来 Web），游戏逻辑全部在此后端执行。
//! 后端持有 GameState，通过 HTTP（axum）暴露命令接口，前端只收发 JSON 状态快照。
//!
//! **重要定位**：本 Rust 后端是**简化版 MVP**，数值口径与 Python 原型端（`game/`）
//! **不必一致、存档字段也暂不互通**。Python 端有更完整的经济/军事/事件/AI 叙事建模；
//! Rust 端仅实现核心结算骨架（货币、声望、人口满足度、压力衰减），用于独立部署演示。
//! 不要假定两端等价，也不要期望跨端读取同一存档。
//!
//! 后期部署：把本目录整体搬到服务器，编译为 release，`SONGZUO_SAVE_DIR` 指向服务器存档路径，
//! 用 `cargo run --release` 或 systemd/docker 常驻即可。

mod commands;
mod constants;
mod save;
mod server;
mod settle;
mod state;

use server::serve;

#[tokio::main]
async fn main() {
    // 监听地址可用环境变量 SONGZUO_ADDR 覆盖，默认 127.0.0.1:8080（本机演示）。
    // 上线时改为 0.0.0.0:8080 并前置 nginx 反向代理。
    let addr = std::env::var("SONGZUO_ADDR").unwrap_or_else(|_| "127.0.0.1:8080".into());
    println!("[songzuo_server] 宋祚后端启动，存档目录 = {:?}", save::save_dir());
    serve(&addr).await;
}
