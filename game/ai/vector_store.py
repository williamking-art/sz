# -*- coding: utf-8 -*-
"""宋祚 · 向量近邻检索库（B2：sqlite-vec 可选，纯 Python 兜底）

用途：大臣记忆/设定 RAG 的向量存储与检索。
- sqlite-vec 可用 → vec0 虚拟表（ANN）；
- 不可用 → 普通表 + 暴力余弦（几千条以内延迟可接受，桌面游戏规模足够）；
- 嵌入向量以 float32 BLOB 存储；元数据 JSON 随行。

与 memory/dialogue_memory.py 的关系：对话库存原文（SQLite FTS 语义），
本库存向量（语义近邻）——两者互补，不互替。
"""
from __future__ import annotations

import json
import sqlite3
import struct
import threading
from typing import Optional

__all__ = ["VectorStore"]


def _to_blob(vec) -> bytes:
    return struct.pack(f"{len(vec)}f", *[float(x) for x in vec])


def _from_blob(blob: bytes) -> list:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


class VectorStore:
    """向量库。sqlite-vec 优先，缺失自动回落暴力检索；失败静默。"""

    def __init__(self, path: str, dim: int = 512):
        self.path = path
        self.dim = int(dim)
        self._conn: Optional[sqlite3.Connection] = None
        self._use_vec_ext = False
        self._lock = threading.Lock()
        self._open()

    def _open(self) -> None:
        try:
            os_makedirs = __import__("os").makedirs
            parent = __import__("os").path.dirname(self.path)
            if parent:
                os_makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            # 尝试加载 sqlite-vec 扩展
            try:
                import sqlite_vec
                self._conn.enable_load_extension(True)
                sqlite_vec.load(self._conn)
                self._conn.enable_load_extension(False)
                self._conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_items USING vec0("
                    f"id TEXT PRIMARY KEY, embedding float[{self.dim}])")
                self._use_vec_ext = True
            except Exception:
                self._use_vec_ext = False
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS items("
                "id TEXT PRIMARY KEY, text TEXT NOT NULL, meta TEXT DEFAULT '{}', "
                "embedding BLOB NOT NULL, ts REAL DEFAULT 0)")
            self._conn.commit()
        except Exception:
            self._conn = None

    @property
    def mode(self) -> str:
        return "sqlite-vec" if self._use_vec_ext else "brute-force"

    def add(self, item_id: str, text: str, embedding, meta: dict = None) -> bool:
        """写入/覆盖一条向量。"""
        if self._conn is None or not embedding:
            return False
        try:
            import time
            blob = _to_blob(embedding)
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO items(id,text,meta,embedding,ts) VALUES(?,?,?,?,?)",
                    (str(item_id), str(text or ""), json.dumps(meta or {}, ensure_ascii=False),
                     blob, time.time()))
                if self._use_vec_ext:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO vec_items(id, embedding) VALUES(?, ?)",
                        (str(item_id), blob))
                self._conn.commit()
            return True
        except Exception:
            return False

    def search(self, query_embedding, top_k: int = 5) -> list:
        """近邻检索。返回 [{"id","text","meta","score"}]，score=余弦相似度（越大越近）。"""
        if self._conn is None or not query_embedding:
            return []
        try:
            if self._use_vec_ext:
                # sqlite-vec 返回距离（越小越近），换算为余弦相似度口径
                blob = _to_blob(query_embedding)
                with self._lock:
                    rows = self._conn.execute(
                        "SELECT i.id, i.text, i.meta, v.distance "
                        "FROM vec_items v JOIN items i ON i.id = v.id "
                        "WHERE v.embedding MATCH ? AND k = ? "
                        "ORDER BY v.distance LIMIT ?",
                        (blob, max(int(top_k), 1), max(int(top_k), 1))).fetchall()
                return [{"id": r[0], "text": r[1], "meta": json.loads(r[2] or "{}"),
                         "score": 1.0 - float(r[3])} for r in rows]
            # 暴力余弦（numpy 优先）
            with self._lock:
                rows = self._conn.execute(
                    "SELECT id, text, meta, embedding FROM items").fetchall()
            q = query_embedding
            try:
                import numpy as np
                qv = np.asarray(q, dtype=float)
                qn = float((qv * qv).sum() ** 0.5) or 1.0
                scored = []
                for rid, text, meta, blob in rows:
                    v = np.frombuffer(blob, dtype=np.float32).astype(float)
                    n = float((v * v).sum() ** 0.5) or 1.0
                    scored.append((float((qv * v).sum() / (qn * n)), rid, text, meta))
            except Exception:
                def _cos(blob):
                    v = _from_blob(blob)
                    na = sum(x * x for x in q) ** 0.5 or 1.0
                    nb = sum(x * x for x in v) ** 0.5 or 1.0
                    return sum(x * y for x, y in zip(q, v)) / (na * nb)
                scored = [(_cos(blob), rid, text, meta)
                          for rid, text, meta, blob in rows]
            scored.sort(key=lambda x: -x[0])
            return [{"id": rid, "text": text, "meta": json.loads(meta or "{}"),
                     "score": s} for s, rid, text, meta in scored[:max(int(top_k), 1)]]
        except Exception:
            return []

    def count(self) -> int:
        try:
            with self._lock:
                return int(self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])
        except Exception:
            return 0

    def close(self) -> None:
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
