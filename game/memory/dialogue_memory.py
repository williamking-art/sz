# -*- coding: utf-8 -*-
"""宋祚 · 对话记忆库（memory/dialogue_memory.py）

官员对话记忆单独存（玩家主要互动，量大高频），SQLite 数据库：
  saves/slot_{slot}_dialogue.db
    ├── dialogues 表：召对对话（append；id/minister/turn/speaker/text/intent/stance/topic）
    │     speaker 区分两侧：`朕` 为陛下口谕，其余为大臣回奏（同一 minister 会话内）
    ├── summaries 表：每 3 回合总结去重（period/minister/content/ref_ids）
    └── meta 表：schema_version（建库写入）/ turn（save 写入）

核心：每 3 回合 summarize_dialogues(turn) 对近 3 回合对话【总结 + 去重】
  ——同 minister 同主题重复表态合并（去重，防记忆漂移/膨胀），压缩成概要（不动旧数据）。
精确调动：query_for_dialogue 先查 summaries 概要 → 需要细节下钻 dialogues（防调用过多不相干）。
玩家可见（只读）：list_sessions（会话列表）/ list_dialogues（完整会话流）/
  list_summaries（按期纪要）—— 供「社交式」召对面板与其嵌入的记忆库侧栏。
结算失败回滚（A2）：rollback_after(turn) 删 `> turn` 的 dialogues / summaries
  ——本库持有 sqlite 连接、不可深拷贝，故无法随 state 快照还原，只能按水位截断；
  只删 `> turn` 是为不误删同回合内失败前的合法写入。
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

    def rollback_after(self, turn: int) -> dict:
        """结算失败回滚：删除 turn 之后写入的召对与总结。

        对称 `MemoryGraph.rollback_after`（审查 A2 补齐）：对话记忆库同为 SQLite、
        同被快照深拷贝跳过，故结算异常时失败回合的召对会留存 —— 而召对带缓存与
        每 3 回合总结去重，残留会污染后续「卿前番之言」注入。只删「> turn」。
        """
        removed = {"dialogues": 0, "summaries": 0}
        if self._conn is None:
            return removed
        for tbl, col in (("dialogues", "turn"), ("summaries", "end_turn")):
            try:
                cur = self._conn.execute(f"DELETE FROM {tbl} WHERE {col} > ?", (int(turn),))
                removed[tbl] = int(cur.rowcount or 0)
            except sqlite3.Error:
                continue
        try:
            self._conn.commit()
        except sqlite3.Error:
            pass
        return removed

    # ---- 每 3 回合总结去重 ----
    def summarize_dialogues(self, turn: int) -> List[dict]:
        """每 3 回合：对未总结的对话总结 + 去重（含历史遗留的过期窗口）。

        - 覆盖窗口修复：原实现只取「当前 period 窗口」[start,end]，`summarized=0` 的
          过期对话永不再被处理 —— AI 不可用 / 读档跳期 / 结算回滚导致某期未跑时，
          该期对话**永久滞留**（无界增长，且 `query_for_dialogue` 的 details 会把这些
          陈旧原文当「近期细节」注入，实测 turn=6 时返回 turn=1~3 的原文）。现回补所有
          `summarized=0 且 turn <= 本期结束` 的对话，按其自身 period 分组处理。
        - 去重：同 period 同 minister 同主题（topic）的重复表态合并（保留最新 stance）
        - 总结：压缩成概要入 summaries 表（不动旧数据；旧对话标记 summarized）
        返回本次生成的 summaries。
        """
        if self._conn is None:
            return []
        period = turn // _DIALOGUE_PERIOD
        end = period * _DIALOGUE_PERIOD
        rows = self._conn.execute(
            "SELECT id,minister,turn,speaker,text,intent,stance,topic FROM dialogues "
            "WHERE summarized=0 AND turn <= ? ORDER BY turn, id",
            (end,)).fetchall()
        if not rows:
            return []
        # 按对话自身 period 分组（回补历史遗留期）；组内再按 (minister, topic) 去重
        by_period: dict = {}
        for rid, minister, dturn, speaker, text, intent, stance, topic in rows:
            by_period.setdefault(int(dturn) // _DIALOGUE_PERIOD, []).append(
                (rid, minister, speaker, text, intent, stance, topic))
        out = []
        for p in sorted(by_period):
            # 区间须与分组口径同源：行按 `dturn // _DIALOGUE_PERIOD` 归入第 p 期，故第 p 期
            # 恰为回合 [p*3, p*3+2]。原式 `p*3-3+1`（第 1 期标 1–3）与该口径错开一期 ——
            # 面板「第1–3回合」下挂的是第 3–5 回合的对话（玩家可见的归属错误）。
            start = p * _DIALOGUE_PERIOD
            pend = p * _DIALOGUE_PERIOD + _DIALOGUE_PERIOD - 1
            # 去重：按 (minister, topic) 分组，保留最新 stance + 合并文本
            grouped: dict = {}
            for rid, minister, speaker, text, intent, stance, topic in by_period[p]:
                key = (minister, topic or intent or "general")
                if key not in grouped:
                    grouped[key] = {"ids": [], "minister": minister, "topic": key[1],
                                    "texts": [], "stance": stance, "intent": intent}
                g = grouped[key]
                g["ids"].append(rid)
                # 两侧对白（speaker=朕）须标注发言者，否则陛下的口谕会被并入大臣之言
                # ——概要随后喂回 AI 作「卿前番之言」，不标注即等于让大臣把上意记成己见。
                g["texts"].append(text[:60] if speaker == minister
                                  else f"{speaker}：{text[:60]}")
                if stance:
                    g["stance"] = stance
            for g in grouped.values():
                content = f"{g['minister']}（{g['topic']}）：{'；'.join(g['texts'][-3:])} 立场={g['stance'] or '未明'}"
                ref_ids = json.dumps(g["ids"], ensure_ascii=False)
                cur = self._conn.execute(
                    "INSERT INTO summaries(period,minister,start_turn,end_turn,content,ref_ids) "
                    "VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT DO NOTHING",
                    (p, g["minister"], start, pend, content[:400], ref_ids))
                if cur.rowcount <= 0:
                    # 审查 P2-46 修复（静默丢数据）：已存在同 (period,minister) 概要（reload/
                    # re-settle 重跑）时，原实现仍无条件把对话标记 summarized=1 —— 这批对话
                    # 既不进 summaries 也不再参与后续总结（永久丢失）。现改为合并追加进概要，
                    # 数据不丢（content 截断上限 600 字防膨胀）。
                    self._conn.execute(
                        "UPDATE summaries SET content=substr(content || ?, 1, 600) "
                        "WHERE period=? AND minister=?",
                        ("；" + content[:200], p, g["minister"]))
                # 标记旧对话已总结（合并路径同样标记，因内容已并入概要）
                self._conn.executemany(
                    "UPDATE dialogues SET summarized=1 WHERE id=?", [(i,) for i in g["ids"]])
                out.append({"period": p, "minister": g["minister"],
                            "content": content, "ref_count": len(g["ids"])})
        self._conn.commit()
        return out

    # ---- 精确调动（后续对话）----
    def fetch_dialogues_by_ids(self, ids, top_k: int = 8) -> List[dict]:
        """按 id 取召对原文（「细节按需下钻」、审计与记忆库面板共用）。

        原实现 summaries.ref_ids 只写不读 —— 已总结对话的原文再也取不回。
        ids 为空 / 未连接 → 空列表；按 turn 倒序、限量返回。
        """
        ids = [int(i) for i in (ids or [])]
        if not ids or self._conn is None:
            return []
        qmarks = ",".join("?" for _ in ids)
        rows = self._conn.execute(
            f"SELECT id,minister,turn,speaker,text,intent,stance,topic FROM dialogues "
            f"WHERE id IN ({qmarks}) ORDER BY turn DESC, id DESC LIMIT ?",
            (*ids, int(top_k))).fetchall()
        return [{"id": r[0], "minister": r[1], "turn": r[2], "speaker": r[3],
                 "text": r[4], "intent": r[5], "stance": r[6], "topic": r[7]}
                for r in rows]

    def summary_refs(self, minister: str = None, period: int = None,
                     top_k: int = 5) -> List[int]:
        """展开概要的 ref_ids → 对话 id 列表（最近 period 优先）。"""
        if self._conn is None:
            return []
        sql = "SELECT ref_ids FROM summaries WHERE 1=1 "
        params: list = []
        if minister:
            sql += "AND minister=? "
            params.append(minister)
        if period is not None:
            sql += "AND period=? "
            params.append(int(period))
        sql += "ORDER BY period DESC LIMIT ?"
        params.append(int(top_k))
        out: List[int] = []
        for (rids,) in self._conn.execute(sql, params).fetchall():
            try:
                out.extend(int(x) for x in json.loads(rids or "[]"))
            except (TypeError, ValueError):
                continue
        return out

    def list_summaries(self, minister: str = None, limit: int = 20) -> List[dict]:
        """列出对话概要以供审计/记忆库面板展示（只读）。"""
        if self._conn is None:
            return []
        sql = ("SELECT period,minister,start_turn,end_turn,content,ref_ids FROM summaries "
               "WHERE 1=1 ")
        params: list = []
        if minister:
            sql += "AND minister=? "
            params.append(minister)
        sql += "ORDER BY period DESC, minister LIMIT ?"
        params.append(int(limit))
        out = []
        for p, m, s, e, content, rids in self._conn.execute(sql, params).fetchall():
            try:
                n = len(json.loads(rids or "[]"))
            except (TypeError, ValueError):
                n = 0
            out.append({"period": p, "minister": m, "start_turn": s, "end_turn": e,
                        "content": content, "ref_count": n})
        return out

    def list_dialogues(self, minister: str = None, limit: int = 60,
                       ascending: bool = True) -> List[dict]:
        """列出召对原文（只读）—— 「社交式」召对面板的会话回放数据源。

        与 `query_for_dialogue` 的分工：那是给 AI 的省 token 注入（概要优先、限量
        下钻、原文截 80 字），本方法是给玩家看的**完整会话流** —— 不过滤
        `summarized`、不截断正文，且含陛下之言（`speaker="朕"`）以呈现两侧对白。

        取「最近 limit 条」再按时间正序返回（会话面板自上而下即时间轴）。
        """
        if self._conn is None:
            return []
        sql = ("SELECT id,minister,turn,speaker,text,intent,stance,topic,summarized "
               "FROM dialogues WHERE 1=1 ")
        params: list = []
        if minister:
            sql += "AND minister=? "
            params.append(minister)
        sql += "ORDER BY turn DESC, id DESC LIMIT ?"
        params.append(int(limit))
        rows = self._conn.execute(sql, params).fetchall()
        out = [{"id": r[0], "minister": r[1], "turn": r[2], "speaker": r[3],
                "text": r[4], "intent": r[5], "stance": r[6], "topic": r[7],
                "summarized": bool(r[8])} for r in rows]
        if ascending:
            out.reverse()
        return out

    def list_sessions(self, limit: int = 200) -> List[dict]:
        """每个大臣一条会话摘要（只读）：末条发言预览 + 条数 + 末次回合。

        供召对面板左侧「会话列表」显示末条预览与回合标；无库/空表 → []。
        """
        if self._conn is None:
            return []
        rows = self._conn.execute(
            "SELECT d.minister, s.n, d.turn, d.text, d.speaker "
            "FROM dialogues d JOIN ("
            "  SELECT minister, COUNT(*) AS n, MAX(id) AS last_id "
            "  FROM dialogues GROUP BY minister) s "
            "  ON s.minister = d.minister AND s.last_id = d.id "
            "ORDER BY d.turn DESC, d.minister LIMIT ?",
            (int(limit),)).fetchall()
        return [{"minister": r[0], "count": int(r[1]), "last_turn": int(r[2]),
                 "last_text": str(r[3] or "")[:60], "last_speaker": str(r[4] or "")}
                for r in rows]

    def query_for_dialogue(self, minister: str, turn: int,
                           top_k: int = 3, drill_down: bool = True) -> dict:
        """召对注入：先查 summaries 概要（近 3 期），细节按需下钻 dialogues。

        drill_down（补完「细节按需下钻」）：未总结的新近原文优先；不足 top_k 时按最近
        概要的 ref_ids 取已总结原文补齐（标 from_summary=True）。原实现只取
        `summarized=0` 的详情，ref_ids 存了却无人读 → 已总结对话原文永远取不回。
        """
        if self._conn is None:
            return {"summary": "", "details": [], "source": "empty"}
        period = turn // _DIALOGUE_PERIOD
        sums = self._conn.execute(
            "SELECT content, ref_ids FROM summaries WHERE minister=? AND period>=? "
            "ORDER BY period DESC LIMIT ?",
            (minister, max(0, period - 2), 2)).fetchall()
        summary = "；".join(s[0] for s in sums)
        details = self._conn.execute(
            "SELECT id,turn,speaker,text,stance FROM dialogues "
            "WHERE minister=? AND summarized=0 ORDER BY turn DESC LIMIT ?",
            (minister, top_k)).fetchall()
        detail_rows = [{"id": d[0], "turn": d[1], "speaker": d[2], "text": d[3][:80],
                        "stance": d[4], "from_summary": False} for d in details]
        if drill_down and len(detail_rows) < top_k:
            have = {d["id"] for d in detail_rows}
            refs: List[int] = []
            for _content, rids in sums:
                try:
                    refs.extend(int(x) for x in json.loads(rids or "[]"))
                except (TypeError, ValueError):
                    continue
            for row in self.fetch_dialogues_by_ids(
                    [i for i in refs if i not in have], top_k=top_k - len(detail_rows)):
                detail_rows.append({"id": row["id"], "turn": row["turn"],
                                    "speaker": row["speaker"], "text": row["text"][:80],
                                    "stance": row["stance"], "from_summary": True})
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
