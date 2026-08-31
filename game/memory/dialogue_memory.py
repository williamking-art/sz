# -*- coding: utf-8 -*-
"""宋祚 · 对话记忆库（memory/dialogue_memory.py）

官员对话记忆单独存（玩家主要互动，量大高频），SQLite 数据库：
  saves/slot_{slot}_dialogue.db
    ├── dialogues 表：召对对话（append；id/minister/turn/speaker/text/intent/stance/topic）
    ├── summaries 表：每 3 回合总结去重（period/minister/content/ref_ids）
    └── meta 表：schema_version/turn/slot

核心：每 3 回合 summarize_dialogues(turn) 对近 3 回合对话【总结 + 去重】
  ——同 minister 同主题重复表态合并（去重，防记忆漂移/膨胀），压缩成概要（不动旧数据）。
精确调动：query_for_dialogue 先查 summaries 概要 → 需要细节下钻 dialogues（防调用过多不相干）。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import List, Optional

_SCHEMA_VERSION = 1
_DIALOGUE_PERIOD = 3  # 每 3 回合总结去重


def _dialogue_path(slot: int) -> str:
    from content.data import SAVE_DIR
    return os.path.join(SAVE_DIR, f"slot_{slot}_dialogue.db")


class DialogueMemory:
    def __init__(self, slot: Optional[int] = None):
        self.slot = slot
        self.turn = 0
        self._conn: Optional[sqlite3.Connection] = None
        if slot is not None:
            self._open(slot)

    def _open(self, slot: int) -> None:
        self.slot = slot
        path = _dialogue_path(slot)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dialogues(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                minister TEXT NOT NULL, turn INTEGER NOT NULL,
                speaker TEXT NOT NULL, text TEXT NOT NULL,
                intent TEXT DEFAULT '', stance TEXT DEFAULT '', topic TEXT DEFAULT '',
                summarized INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_dial_minister ON dialogues(minister, turn);
            CREATE INDEX IF NOT EXISTS idx_dial_turn ON dialogues(turn);
            CREATE TABLE IF NOT EXISTS summaries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period INTEGER NOT NULL, minister TEXT NOT NULL,
                start_turn INTEGER NOT NULL, end_turn INTEGER NOT NULL,
                content TEXT NOT NULL, ref_ids TEXT DEFAULT '[]'
            );
            -- 审查 P2-1 修复：补 UNIQUE 约束，让 ON CONFLICT DO NOTHING 真正去重
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sum_period ON summaries(period, minister);
            CREATE TABLE IF NOT EXISTS meta(
                k TEXT PRIMARY KEY, v TEXT
            );
            """
        )
        self._conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('schema_version',?)",
                           (str(_SCHEMA_VERSION),))
        self._conn.commit()

    # ---- 写入 ----
    def add_dialogue(self, minister: str, turn: int, speaker: str, text: str,
                     intent: str = "", stance: str = "", topic: str = "") -> int:
        """追加一条召对对话。"""
        if self._conn is None:
            self._open(self.slot or 0)
        cur = self._conn.execute(
            "INSERT INTO dialogues(minister,turn,speaker,text,intent,stance,topic) "
            "VALUES(?,?,?,?,?,?,?)",
            (minister, turn, speaker, text[:500], intent[:50], stance[:20], topic[:50]))
        self._conn.commit()
        return cur.lastrowid

    # ---- 每 3 回合总结去重 ----
    def summarize_dialogues(self, turn: int) -> List[dict]:
        """每 3 回合：对近 3 回合对话总结 + 去重。

        - 去重：同 minister 同主题（topic）的重复表态合并（保留最新 stance）
        - 总结：压缩成概要入 summaries 表（不动旧数据；旧对话标记 summarized）
        返回本次生成的 summaries。
        """
        if self._conn is None:
            return []
        period = turn // _DIALOGUE_PERIOD
        start = max(0, (period - 1) * _DIALOGUE_PERIOD + 1) if period > 0 else 1
        end = period * _DIALOGUE_PERIOD
        rows = self._conn.execute(
            "SELECT id,minister,text,intent,stance,topic FROM dialogues "
            "WHERE turn BETWEEN ? AND ? AND summarized=0 ORDER BY turn",
            (start, end)).fetchall()
        if not rows:
            return []
        # 去重：按 (minister, topic) 分组，保留最新 stance + 合并文本
        grouped: dict = {}
        for rid, minister, text, intent, stance, topic in rows:
            key = (minister, topic or intent or "general")
            if key not in grouped:
                grouped[key] = {"ids": [], "minister": minister, "topic": key[1],
                                "texts": [], "stance": stance, "intent": intent}
            g = grouped[key]
            g["ids"].append(rid)
            g["texts"].append(text[:60])
            if stance:
                g["stance"] = stance
        out = []
        for g in grouped.values():
            content = f"{g['minister']}（{g['topic']}）：{'；'.join(g['texts'][-3:])} 立场={g['stance'] or '未明'}"
            ref_ids = json.dumps(g["ids"], ensure_ascii=False)
            cur = self._conn.execute(
                "INSERT INTO summaries(period,minister,start_turn,end_turn,content,ref_ids) "
                "VALUES(?,?,?,?,?,?) "
                "ON CONFLICT DO NOTHING",
                (period, g["minister"], start, end, content[:400], ref_ids))
            # 标记旧对话已总结
            self._conn.executemany(
                "UPDATE dialogues SET summarized=1 WHERE id=?", [(i,) for i in g["ids"]])
            out.append({"period": period, "minister": g["minister"],
                        "content": content, "ref_count": len(g["ids"])})
        self._conn.commit()
        return out

    # ---- 精确调动（后续对话）----
    def query_for_dialogue(self, minister: str, turn: int,
                           top_k: int = 3) -> dict:
        """召对注入：先查 summaries 概要（近 3 回合），细节按需下钻 dialogues。"""
        if self._conn is None:
            return {"summary": "", "details": [], "source": "empty"}
        period = turn // _DIALOGUE_PERIOD
        sums = self._conn.execute(
            "SELECT content FROM summaries WHERE minister=? AND period>=? "
            "ORDER BY period DESC LIMIT ?",
            (minister, max(0, period - 2), 2)).fetchall()
        summary = "；".join(s[0] for s in sums)
        details = self._conn.execute(
            "SELECT turn,speaker,text,stance FROM dialogues "
            "WHERE minister=? AND summarized=0 ORDER BY turn DESC LIMIT ?",
            (minister, top_k)).fetchall()
        detail_rows = [{"turn": d[0], "speaker": d[1], "text": d[2][:80],
                        "stance": d[3]} for d in details]
        return {"summary": summary[:400], "details": detail_rows,
                "source": "db"}

    # ---- 存档 ----
    def save(self, slot: int) -> bool:
        if self._conn is None:
            return False
        self._conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('turn',?)",
                           (str(self.turn),))
        self._conn.commit()
        return True

    def load(self, slot: int) -> bool:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        try:
            self._open(slot)
            row = self._conn.execute("SELECT v FROM meta WHERE k='turn'").fetchone()
            self.turn = int(row[0]) if row else 0
            return True
        except Exception:
            # 损坏 → 重建空库（不阻断）
            try:
                if self._conn:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._open(slot)
            self.turn = 0
            return False

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


# 模块级便捷函数（挂 state）
def get_dialogue_memory(state) -> DialogueMemory:
    dm = getattr(state, "_dialogue_memory", None)
    if dm is None:
        slot = getattr(state, "memory_slot", 0) or 0
        dm = DialogueMemory(slot)
        state._dialogue_memory = dm
    return dm
