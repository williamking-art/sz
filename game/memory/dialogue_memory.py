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

并发与损坏安全（审查 P2-12 / P2-13 修复）：
  - P2-12：连接以 `check_same_thread=False` 建立（FastAPI 同步端点跑在线程池，句柄可能
    跨线程使用），但**所有**类方法经实例 `threading.RLock` 串行化，写操作有明确事务边界
    （`with conn:` 提交/回滚），并加 `busy_timeout` 抗跨进程并发；锁外不再触碰连接。
  - P2-13：损坏库**不再**「关闭 → 重建空库 → 返回 False」式静默变空。改为隔离原文件
    （`<path>.corrupt`，连同 -wal/-shm 边车），记录 `self.load_error`，返回 False；
    一旦进入损坏态，`add_dialogue` 等写操作拒绝惰性重建新库（返回 -1），
    杜绝「数据没了还看不出来」。
"""
from __future__ import annotations

import functools
import json
import logging
import os
import sqlite3
import threading
import time
from typing import List, Optional

log = logging.getLogger("dialogue_memory")

_SCHEMA_VERSION = 1
_DIALOGUE_PERIOD = 3  # 每 3 回合总结去重

#: 现有对话库必须齐全的表（缺失 → 视为损坏/他库，隔离而非当空库用）
_REQUIRED_TABLES = ("dialogues", "summaries", "meta")


def _dialogue_path(slot: int) -> str:
    from content.data import SAVE_DIR
    return os.path.join(SAVE_DIR, f"slot_{slot}_dialogue.db")


def _quarantine_file(path: str) -> str:
    """把损坏文件改名为 `<path>.corrupt`；备份已存在则加纳秒后缀，绝不覆盖既有现场。

    返回备份路径；文件不存在 / 改名失败返回 ""（调用方据此记录诊断信息，不当成功）。
    """
    if not path or not os.path.exists(path):
        return ""
    backup = path + ".corrupt"
    if os.path.exists(backup):
        backup = f"{path}.corrupt.{time.time_ns()}"
    try:
        os.replace(path, backup)
        return backup
    except OSError as e:
        log.error("隔离损坏文件失败（%s）：%s", path, e)
        return ""


def _quarantine_paths(path: str) -> str:
    """隔离主库及其 -wal/-shm 边车，返回主库备份路径（或 ""）。"""
    backup = _quarantine_file(path)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(path + suffix):
            _quarantine_file(path + suffix)
    return backup


def _synchronized(method):
    """P2-12：所有 DB 访问经实例 RLock 串行化（RLock 允许同类方法内部互调）。"""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class DialogueMemory:
    def __init__(self, slot: Optional[int] = None):
        self.slot = slot
        self.turn = 0
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        #: 损坏诊断（None=正常；非空=已隔离损坏库，禁止再伪装成空库）
        self.load_error = None
        if slot is not None:
            self._open(slot)

    # ---- 连接 / schema（P2-12 线程安全，P2-13 损坏隔离） ----
    @staticmethod
    def _connect(path: str) -> sqlite3.Connection:
        """建连：跨线程可用 + busy 超时（并发写由类方法锁串行化）。"""
        conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
        # P2-13：建连中途失败必须关句柄，否则损坏库被占用导致隔离 rename 失败。
        try:
            conn.execute("PRAGMA busy_timeout = 3000")
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass
            return conn
        except sqlite3.Error:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            raise

    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
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
        conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('schema_version',?)",
                     (str(_SCHEMA_VERSION),))
        conn.commit()

    @staticmethod
    def _verify_existing(conn: sqlite3.Connection) -> None:
        """校验既有库：物理完整性 + 必备表齐全。不合格即抛 sqlite3.DatabaseError。"""
        rows = conn.execute("PRAGMA integrity_check").fetchall()
        if not rows or str(rows[0][0]).strip().lower() != "ok":
            raise sqlite3.DatabaseError("integrity_check 未通过（文件非 SQLite 或已损坏）")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in _REQUIRED_TABLES if t not in tables]
        if missing:
            raise sqlite3.DatabaseError(f"缺少对话库表：{missing}（疑似他库/半写）")

    def _open(self, slot: int) -> bool:
        """打开槽位库：存在则校验、缺失（或 0 字节）则建库。

        损坏 → 隔离为 `.corrupt`、置 `load_error`、`_conn=None`，返回 False；
        **绝不**在损坏文件上重建空库冒充正常。
        """
        path = _dialogue_path(slot)
        self.slot = slot
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existed = os.path.exists(path) and os.path.getsize(path) > 0
        conn = None
        try:
            conn = self._connect(path)
            if existed:
                self._verify_existing(conn)
                conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('schema_version',?)",
                             (str(_SCHEMA_VERSION),))
                conn.commit()
            else:
                self._init_schema(conn)
            with self._lock:
                old = self._conn
                self._conn = conn
                self.load_error = None
            if old is not None and old is not conn:
                try:
                    old.close()
                except Exception:  # noqa: BLE001
                    pass
            return True
        except sqlite3.OperationalError as e:
            # 例如 database is locked：仅暂时不可用，保留原文件（不得冒充损坏）
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
            with self._lock:
                self._conn = None
            self.load_error = f"对话记忆库暂时不可用（未隔离，slot={slot}）：{e}"
            log.error(self.load_error)
            return False
        except (sqlite3.DatabaseError, OSError) as e:
            # file is not a database / 物理损坏 / 结构不符 → 隔离（保留备份）
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
            with self._lock:
                self._conn = None
            backup = _quarantine_paths(path)
            self.load_error = (f"对话记忆库损坏（slot={slot}）：{e}；"
                               f"已隔离为 {backup or (path + '.corrupt')}")
            log.error(self.load_error)
            return False
        except sqlite3.Error as e:
            # 兜底（其它 sqlite3 错误）：按暂时不可用处理，保留原文件
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
            with self._lock:
                self._conn = None
            self.load_error = f"对话记忆库暂时不可用（未隔离，slot={slot}）：{e}"
            log.error(self.load_error)
            return False

    def _ensure_conn(self, slot: Optional[int] = None) -> bool:
        """惰性建连；一旦检出损坏（load_error 非空），拒绝重建新库冒充空库。"""
        if self._conn is not None:
            return True
        if self.load_error:
            return False
        target = slot if slot is not None else (self.slot if self.slot is not None else 0)
        return self._open(target)

    def _close_locked(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ---- 写入 ----
    @_synchronized
    def add_dialogue(self, minister: str, turn: int, speaker: str, text: str,
                     intent: str = "", stance: str = "", topic: str = "") -> int:
        """追加一条召对对话；成功返回新行 id，库损坏/写入失败返回 -1（不抛、不建空库）。"""
        if not self._ensure_conn():
            return -1
        try:
            with self._conn:  # 显式事务边界：成功提交、异常回滚
                cur = self._conn.execute(
                    "INSERT INTO dialogues(minister,turn,speaker,text,intent,stance,topic) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (minister, turn, speaker, text[:500], intent[:50], stance[:20], topic[:50]))
            return int(cur.lastrowid or 0)
        except sqlite3.Error as e:
            log.warning("add_dialogue 写入失败（不阻断召对）：%s", e)
            return -1

    @_synchronized
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
    @_synchronized
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
    @_synchronized
    def fetch_dialogues_by_ids(self, ids, top_k: int = 8) -> List[dict]:
        """按 id 取召对原文（「细节按需下钻」、审计与记忆库面板共用）。

        原实现 summaries.ref_ids 只写不读 —— 已总结对话的原文再也取不回。
        ids 为空 / 未连接 → 空列表；按 turn 倒序、限量返回。
        """
        if self._conn is None:
            return []
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return []
        qmarks = ",".join("?" for _ in ids)
        rows = self._conn.execute(
            f"SELECT id,minister,turn,speaker,text,intent,stance,topic FROM dialogues "
            f"WHERE id IN ({qmarks}) ORDER BY turn DESC, id DESC LIMIT ?",
            (*ids, int(top_k))).fetchall()
        return [{"id": r[0], "minister": r[1], "turn": r[2], "speaker": r[3],
                 "text": r[4], "intent": r[5], "stance": r[6], "topic": r[7]}
                for r in rows]

    @_synchronized
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

    @_synchronized
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

    @_synchronized
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

    @_synchronized
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

    @_synchronized
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
    @_synchronized
    def save(self, slot: int) -> bool:
        if self._conn is None:
            return False
        try:
            with self._conn:
                self._conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('turn',?)",
                                   (str(self.turn),))
            return True
        except sqlite3.Error as e:
            log.warning("对话记忆库写盘失败（slot=%s）：%s", slot, e)
            return False

    @_synchronized
    def load(self, slot: int) -> bool:
        """按槽位加载对话库。

        P2-13：损坏 → 隔离 `.corrupt`、置 `load_error`、返回 False；**绝不**重建空库
        冒充正常空库。库不存在属正常新局，会建空库并返回 True。
        """
        self.slot = int(slot)
        self._close_locked()
        self.turn = 0
        self.load_error = None
        if not self._open(self.slot):
            self.turn = 0
            return False
        try:
            row = self._conn.execute("SELECT v FROM meta WHERE k='turn'").fetchone()
            raw = row[0] if row else None
            self.turn = 0 if raw in (None, "") else int(raw)
            return True
        except sqlite3.OperationalError as e:
            # 例如 database is locked：暂时不可用，保留原文件
            self._close_locked()
            self.load_error = f"对话记忆库暂时不可用（未隔离，slot={self.slot}）：{e}"
            log.error(self.load_error)
            self.turn = 0
            return False
        except (sqlite3.DatabaseError, TypeError, ValueError) as e:
            # meta.turn 被写坏 / 表结构异常 → 同按损坏处理（隔离，不静默变空）
            self._close_locked()
            path = _dialogue_path(self.slot)
            backup = _quarantine_paths(path)
            self.load_error = (f"对话记忆库元数据损坏（slot={self.slot}）：{e}；"
                               f"已隔离为 {backup or (path + '.corrupt')}")
            log.error(self.load_error)
            self.turn = 0
            return False
        except sqlite3.Error as e:
            # 兜底（其它 sqlite3 错误）：暂时不可用，保留原文件
            self._close_locked()
            self.load_error = f"对话记忆库暂时不可用（未隔离，slot={self.slot}）：{e}"
            log.error(self.load_error)
            self.turn = 0
            return False

    @_synchronized
    def close(self) -> None:
        self._close_locked()


# 模块级便捷函数（挂 state）
def get_dialogue_memory(state) -> DialogueMemory:
    dm = getattr(state, "_dialogue_memory", None)
    if dm is None:
        slot = getattr(state, "memory_slot", 0) or 0
        dm = DialogueMemory(slot)
        state._dialogue_memory = dm
    return dm