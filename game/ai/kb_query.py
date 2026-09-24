# -*- coding: utf-8 -*-
"""游戏内知识库查询（本地 SQLite FTS5，随游戏分发，只读）。

- 库文件：assets/kb/game_kb.sqlite（由 _dev_tools/game-docs/kb/build_kb.py 构建）
- 供 AI 工具 kb_search 调用（见 ai/client_utils.py 的 _TOOL_SCHEMAS / _tool_dispatch）。
- 查询算法（FTS5 trigram + LIKE 兜底）**唯一权威源即本文件 `_search()`**：
  _dev_tools/game-docs/kb/build_kb.py 的开发侧查询直接复用它，不再各存一份副本。
- 降级哲学（同 ai/semantic.py）：库缺失 / FTS5 不可用 / 任何异常 → 返回降级文本，
  绝不抛进 AI 管线。
"""
import os
import sqlite3

from content.data import get_resource

_DB_PATH = None          # 惰性解析（_MEIPASS 在运行初期可能就位，延迟到首次调用）
_conn = None             # 懒加载只读连接（单例复用）
_available = None        # 能力探测缓存：True/False

#: 单次返回给 AI 的总字符上限（防 token 膨胀，与 query_state 的省 token 哲学一致）
MAX_RESULT_CHARS = 1500

#: 查询串长度上限（AI 可能回传整段话；超长只慢不炸，仍截断以省时）
MAX_QUERY_CHARS = 100


def _detect_available():
    """探测本地知识库是否可用：库文件存在 + SQLite 支持 FTS5 trigram。"""
    global _DB_PATH
    try:
        path = get_resource("kb/game_kb.sqlite")
        if not os.path.isfile(path):
            return False
        _DB_PATH = path
        # trigram tokenizer 需要 SQLite >= 3.34；旧环境静默降级
        probe = sqlite3.connect(":memory:")
        try:
            probe.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
        finally:
            probe.close()
        return True
    except Exception:
        # sqlite3.Error ⊂ Exception：合并分支（探测期任何失败都只是「不可用」）
        return False


def kb_stats(state) -> dict:
    """典章库用量统计（按存档累计，非全局）：`calls` 调用次数 / `hits` 命中次数。

    存在意义：知识库若从不被 AI 调用，就是白做的——而在此之前**没有任何埋点**能证明
    它被调用过（`telemetry.record_ai_call` 标注 intentionally_unwired）。本计数器由
    `client_utils._tool_dispatch` 在 kb_search 分支累加，经 `/api/meter` 与召对命中率
    同表可见，使「典章库是否真在发挥作用」变为可观测。

    命中率 = hits / calls；持续为 0 说明工具没被触发（应查 prompt 引导/工具面），
    命中率过低说明检索算法需要调优。
    """
    st = getattr(state, "_kb_stats", None)
    if not isinstance(st, dict):
        st = {}
        state._kb_stats = st
    st.setdefault("calls", 0)
    st.setdefault("hits", 0)
    return st


def kb_available():
    """知识库可用性（结果缓存，进程内只探测一次）。"""
    global _available
    if _available is None:
        _available = _detect_available()
    return _available


def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    return _conn


def _search(conn, query, top_k):
    """[(heading, content, score)]；与 build_kb.py search() 同一算法。

    FTS5 trigram（>=3 字符可靠）→ LIKE AND → LIKE OR 三级兜底。
    """
    terms = [t for t in query.split() if t.strip()]
    if not terms:
        return []
    match_q = " ".join('"' + t.replace('"', '""') + '"' for t in terms)
    try:
        rows = conn.execute(
            "SELECT c.heading, c.content, bm25(chunks_fts) AS score"
            " FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid"
            " WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
            (match_q, top_k)).fetchall()
    except sqlite3.Error:
        rows = []
    if rows:
        return rows
    where_and = " AND ".join("content LIKE ?" for _ in terms)
    pats = [f"%{t}%" for t in terms]
    rows = conn.execute(
        f"SELECT heading, content, 0.0 FROM chunks WHERE {where_and}"
        " ORDER BY length(content) LIMIT ?",
        (*pats, top_k)).fetchall()
    if rows:
        return rows
    where_or = " OR ".join("content LIKE ?" for _ in terms)
    hits = " + ".join("(content LIKE ?)" for _ in terms)
    return conn.execute(
        f"SELECT heading, content, 0.0 FROM chunks WHERE {where_or}"
        f" ORDER BY ({hits}) DESC, length(content) LIMIT ?",
        (*pats, *pats, top_k)).fetchall()


def kb_search(query, top_k=3):
    """检索游戏设计知识库，返回给 AI 的拼接文本（带出处，总量截断）。

    永不抛异常；不可用时返回空串（调用方据此给降级话术）。
    """
    try:
        if not kb_available():
            return ""
        rows = _search(_get_conn(), str(query)[:MAX_QUERY_CHARS], top_k)
        if not rows:
            return ""
        parts = []
        used = 0
        for i, (heading, content, _score) in enumerate(rows):
            seg = f"【典章·{i + 1}】{content.strip()}"
            if used + len(seg) > MAX_RESULT_CHARS:
                seg = seg[: max(0, MAX_RESULT_CHARS - used)]
            if not seg:
                break
            parts.append(seg)
            used += len(seg)
        return "\n\n".join(parts)
    except Exception:
        return ""
