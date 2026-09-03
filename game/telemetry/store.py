# -*- coding: utf-8 -*-
"""宋祚 · 遥测存储（A2：SQLite，标准库 sqlite3，零第三方依赖）

库文件：SAVE_DIR/telemetry.db（与对话记忆库同目录约定，frozen 路径兼容）。
表结构：
  ai_calls(id, ts, method, prompt_tokens, completion_tokens, estimated)
  monthly(id, ts, turn, payload JSON)      —— 月度快照（国库/仓廪/口碑等，键值自由）
  events(id, ts, turn, name, payload JSON) —— 事件触发记录
  meta(k, v)                               —— schema_version 等

设计纪律：
- 线程安全：check_same_thread=False + threading.Lock（AI 调用可能来自工作线程）；
- 失败静默：遥测任何异常都不上抛（绝不影响游戏）；
- 默认关闭：SONGZUO_TELEMETRY=1 才启用（get_store 返回 None 表示未启用）；
- 单一权威源：路径复用 content.data.SAVE_DIR，不重复定义。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Optional

_SCHEMA_VERSION = 1
_lock = threading.Lock()
_store: Optional["TelemetryStore"] = None


def _db_path() -> str:
    from content.data import SAVE_DIR
    return os.path.join(SAVE_DIR, "telemetry.db")


class TelemetryStore:
    """轻量遥测库。所有方法失败静默（返回 False/None），绝不影响游戏。"""

    def __init__(self, path: str = ""):
        self.path = path or _db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    def _open(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_calls(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL, method TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    estimated INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_ai_method ON ai_calls(method, ts);
                CREATE TABLE IF NOT EXISTS monthly(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL, turn INTEGER NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_monthly_turn ON monthly(turn);
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL, turn INTEGER NOT NULL,
                    name TEXT NOT NULL, payload TEXT DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, ts);
                CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
                """
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(k,v) VALUES('schema_version',?)",
                (str(_SCHEMA_VERSION),))
            self._conn.commit()
        except Exception:
            self._conn = None

    # ---- 写入 ----
    def record_ai_call(self, method: str, prompt_tokens: int = 0,
                       completion_tokens: int = 0, estimated: bool = False) -> bool:
        """记录一次 AI 调用计量（AIClient._add_usage 挂钩）。"""
        if self._conn is None:
            return False
        try:
            with _lock:
                self._conn.execute(
                    "INSERT INTO ai_calls(ts,method,prompt_tokens,completion_tokens,estimated) "
                    "VALUES(?,?,?,?,?)",
                    (time.time(), method[:40], int(prompt_tokens or 0),
                     int(completion_tokens or 0), 1 if estimated else 0))
                self._conn.commit()
            return True
        except Exception:
            return False

    def record_monthly(self, turn: int, metrics: dict) -> bool:
        """记录月度快照（键值自由：国库/仓廪/口碑/派系满意度等）。"""
        if self._conn is None:
            return False
        try:
            with _lock:
                self._conn.execute(
                    "INSERT INTO monthly(ts,turn,payload) VALUES(?,?,?)",
                    (time.time(), int(turn or 0),
                     json.dumps(metrics or {}, ensure_ascii=False)))
                self._conn.commit()
            return True
        except Exception:
            return False

    def record_event(self, turn: int, name: str, payload: dict = None) -> bool:
        """记录事件触发（name=事件 ID，payload=选项/后果摘要）。"""
        if self._conn is None:
            return False
        try:
            with _lock:
                self._conn.execute(
                    "INSERT INTO events(ts,turn,name,payload) VALUES(?,?,?,?)",
                    (time.time(), int(turn or 0), str(name or "")[:60],
                     json.dumps(payload or {}, ensure_ascii=False)))
                self._conn.commit()
            return True
        except Exception:
            return False

    # ---- 查询（dev 侧分析用）----
    def summary(self) -> dict:
        """计量汇总：AI 调用总量/按方法分桶/月度条数/事件条数。"""
        if self._conn is None:
            return {}
        try:
            with _lock:
                total = self._conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), "
                    "COALESCE(SUM(completion_tokens),0) FROM ai_calls").fetchone()
                by_method = self._conn.execute(
                    "SELECT method, COUNT(*), COALESCE(SUM(prompt_tokens),0), "
                    "COALESCE(SUM(completion_tokens),0) FROM ai_calls "
                    "GROUP BY method ORDER BY COUNT(*) DESC").fetchall()
                months = self._conn.execute("SELECT COUNT(*) FROM monthly").fetchone()[0]
                events = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            return {
                "ai_calls": total[0], "prompt_tokens": total[1],
                "completion_tokens": total[2],
                "by_method": [{"method": m, "calls": c, "prompt": p, "completion": x}
                              for m, c, p, x in by_method],
                "monthly_records": months, "event_records": events,
            }
        except Exception:
            return {}

    def monthly_series(self) -> list:
        """按回合升序导出月度快照（平衡分析/回放用）。"""
        if self._conn is None:
            return []
        try:
            with _lock:
                rows = self._conn.execute(
                    "SELECT turn, payload FROM monthly ORDER BY turn, id").fetchall()
            return [{"turn": t, **json.loads(p)} for t, p in rows]
        except Exception:
            return []

    def close(self) -> None:
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None


def enabled() -> bool:
    """遥测开关：环境变量 SONGZUO_TELEMETRY=1。"""
    return os.environ.get("SONGZUO_TELEMETRY") == "1"


def get_store() -> Optional[TelemetryStore]:
    """进程级单例。未启用返回 None（调用方直接跳过）。"""
    global _store
    if not enabled():
        return None
    if _store is None:
        _store = TelemetryStore()
    return _store
