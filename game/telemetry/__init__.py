# -*- coding: utf-8 -*-
"""宋祚 · 遥测包（A2：SQLite 遥测存储）

默认关闭：设环境变量 SONGZUO_TELEMETRY=1 启用。
启用后 AIClient 的 token 计量与月度快照/事件可落 SQLite，供
dev 侧平衡分析（析微澜席位）离线查询。遥测绝不影响游戏运行。
"""
from telemetry.store import TelemetryStore, get_store  # noqa: F401
