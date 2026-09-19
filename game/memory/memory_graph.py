# -*- coding: utf-8 -*-
"""宋祚 · 记忆知识库（Phase 3a 升级 T7：SQLite 数据库化，一轮游戏 = 一个 SQLite 数据库）。

**图谱存「史」、GameState 存「态」**：跨回合连贯、大臣记得历史。

- Entity 类型：minister / event / decision / task / org / institution / external_power
  + 压缩产物 summary / period_summary（存 summaries 表）。
- Relation 类型：supports / opposes / involves / produces / progresses / promises /
  stance / governs（带 timestamp/weight/half_life→λ 衰减）。
- 存储：`saves/slot_{slot}.db`（一轮一库），五张表：
    state      —— schema_version / turn / archived / 迁移标记（key-value）
    entities   —— eid 主键 + (type,name) 索引（INSERT OR REPLACE 幂等去重）
    relations  —— (src,dst,rtype) 唯一索引（INSERT OR REPLACE），archived 标记列
    summaries  —— compress / summarize_period 的 SQL 聚合产物（period 索引）
    change_log —— 每次写盘/压缩/总结/归档留痕（事务内追加）
  - 原子写入：单事务（`with conn:`，异常自动 ROLLBACK，不产生半写状态）。
  - 写入去重：INSERT OR REPLACE（主键冲突即覆盖，无重复行）。
  - 兼容性调适：entities 主键用 eid（业务生成的语义唯一键，如 decision_5_赈济京畿），
    (type,name) 作普通索引加速领域查询——若按派单字面 (type+name) 唯一索引，同名的
    跨回合决策/事件会被覆盖（如每月重复颁布的同类诏令），违背"历史连贯可查"的用户
    理由；eid 主键保留全部历史实体，重复写同一 eid 仍由 REPLACE 去重（交付说明已披露）。
- 运行时：内存镜像（self.entities/self.relations）为读写主路径，保证既有调用方
  （ai/ core/ content/ministers/persona.py 直接访问 .entities/.relations）语义零变化；
  SQLite 为持久化与精确调动后端。save() 把镜像快照进 db；load() 读回镜像。
- 压缩/总结：
    compress(turn)         —— 每 6 回合：SQL 聚合近 6 回合关系 → summary 实体
                              （etype=summary，period=turn//6），旧数据不动（只读聚合）。
    summarize_period(turn) —— 每 12 回合：聚合本轮决策/事件 → period_summary 实体。
  - 两者均幂等（同 period 重复调用 REPLACE 覆盖），固定 turn 序列结果确定。
- 精确调动：
    query_sql()            —— SQL 查询：领域(type/name)/时间窗/rtype/top_k/权重×衰减排序+索引。
    query_summaries()      —— SQL 查 summaries 表（层级检索第一层：概要）。
    retrieve_hierarchical()—— 先 summaries 概要 → 细节按需（query 下钻）。
- 存档兼容：旧 JSON 记忆文件（slot_{slot}_memory.json）自动迁移或重建（损坏不阻断游戏）；
  主存档 JSON（GameState）+ 记忆 .db 同槽位分离，save_load.py 只调 save()/load() 零改动。
- 迁移说明：旧 `slot_{slot}_memory.json` 与 `slot_{slot}_memory_archive.json` 为 Phase 3a
  遗留格式；T7 起以 `slot_{slot}.db` 为权威，旧 JSON 迁移后保留不删除（安全回退）。
- 原则：真值（economy_history/corruption）不注入图谱/AI；AI 失败不伪造。
"""
import os
import json
import re
import sqlite3
import time
from datetime import datetime

import logging

from content.data import SAVE_DIR, MEMORY_RELATION_DECAY, MEMORY_ARCHIVE_WEIGHT

log = logging.getLogger("memory_graph")

# 实体类型（业务 7 类 + 压缩产物 2 类）
ENTITY_TYPES = ("minister", "event", "decision", "task", "org", "institution", "external_power")
SUMMARY_TYPES = ("summary", "period_summary")
# 关系类型（8 类）
RELATION_TYPES = ("supports", "opposes", "involves", "produces", "progresses",
                  "promises", "stance", "governs")

_SCHEMA_VERSION = 2          # T7：SQLite 后端（v1 为 Phase 3a JSON 格式）
_JSON_SCHEMA_VERSION = 1     # 旧 JSON 格式版本（迁移判定用）
_COMPRESS_INTERVAL = 6       # 每 6 回合压缩一次
_PERIOD_INTERVAL = 12        # 每 12 回合周期总结一次
_ARCHIVE_INTERVAL = 12       # 每 12 回合归档低权重旧史（容量治理；只打标记、不物理删除）


def _memory_path(slot: int, archive: bool = False) -> str:
    """旧 Phase 3a JSON 记忆文件路径（迁移源，保留兼容）。"""
    base = f"slot_{slot}_memory{'_archive' if archive else ''}.json"
    return os.path.join(SAVE_DIR, base)


def _db_path(slot: int) -> str:
    """T7 SQLite 记忆库路径（一轮一库，与主存档 slot_{slot}.json 平级分离）。"""
    return os.path.join(SAVE_DIR, f"slot_{slot}.db")


def _quarantine_file(path: str) -> str:
    """把损坏文件改名为 `<path>.corrupt`；同名已存在则加纳秒后缀，绝不覆盖既有现场。

    返回备份路径；文件不存在 / 改名失败返回 ""。
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


def _quarantine_db(slot: int) -> str:
    """隔离损坏的记忆库主库及 -wal/-shm 边车，返回主库备份路径（或 ""）。"""
    db = _db_path(slot)
    backup = _quarantine_file(db)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(db + suffix):
            _quarantine_file(db + suffix)
    return backup


def _backup_corrupt_copy(path: str) -> str:
    """为损坏的迁移源（旧 JSON）**另存** `<path>.corrupt` 备份。

    与 db 的隔离不同：旧 JSON 是人工诊断现场，项目既有回归（test_memory_graph::
    test_corrupt_rebuild）明确要求**保留原文件**，故此处只复制不移动；返回备份路径。
    """
    if not path or not os.path.exists(path):
        return ""
    backup = path + ".corrupt"
    if os.path.exists(backup):
        backup = f"{path}.corrupt.{time.time_ns()}"
    try:
        with open(path, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
        return backup
    except OSError as e:
        log.error("备份损坏 JSON 失败（%s）：%s", path, e)
        return ""


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
    eid          TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    attrs        TEXT NOT NULL DEFAULT '{}',
    created_turn INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_entities_type_name ON entities(type, name);
CREATE TABLE IF NOT EXISTS relations (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    rtype    TEXT NOT NULL,
    turn     INTEGER NOT NULL DEFAULT 0,
    weight   REAL NOT NULL DEFAULT 1.0,
    note     TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    UNIQUE(src, dst, rtype)
);
CREATE INDEX IF NOT EXISTS idx_relations_turn  ON relations(turn);
CREATE INDEX IF NOT EXISTS idx_relations_rtype ON relations(rtype);
CREATE INDEX IF NOT EXISTS idx_relations_src   ON relations(src);
CREATE INDEX IF NOT EXISTS idx_relations_dst   ON relations(dst);
CREATE TABLE IF NOT EXISTS summaries (
    eid         TEXT PRIMARY KEY,
    stype       TEXT NOT NULL,             -- summary | period_summary
    period      INTEGER NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    attrs       TEXT NOT NULL DEFAULT '{}',
    created_turn INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_summaries_period ON summaries(period);
CREATE TABLE IF NOT EXISTS change_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    slot   INTEGER NOT NULL DEFAULT 0,
    turn   INTEGER NOT NULL DEFAULT 0,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    ts     TEXT NOT NULL DEFAULT ''
);
"""


class MemoryGraph:
    """记忆知识库：Entity + Relation，SQLite 持久化 + 内存镜像 + 压缩/总结/精确调动。

    接口兼容 Phase 3a：add_entity/add_relation/upsert_relation/query/keyword_search/
    summarize/record_decision/record_event/to_dict/from_dict/save/load/archive 签名不变；
    新增：compress/summarize_period/query_sql/query_summaries/retrieve_hierarchical/migrate_json、
    rollback_after（结算失败按水位截断关系/实体/总结/变更日志，A2；内存镜像 + SQLite 双侧）。
    """

    def __init__(self, schema_version: int = _SCHEMA_VERSION):
        self.schema_version = schema_version
        self.turn = 0
        self.entities = {}        # eid -> {"eid","type","name","attrs":{},"created_turn"}
        self.relations = []       # [{src,dst,rtype,turn,weight,note[,archived]}]
        self.archived = 0         # 归档关系计数
        self._slot = None         # 最近 save/load 的槽位（None=未落盘，SQL 查询一律回退内存，绝不碰真实槽位）
        self._migrated = False    # 本次 load 是否发生过旧 JSON 迁移
        #: 损坏诊断（None=正常；非空=已隔离损坏库/损坏迁移源）
        self.load_error = None
        #: 最近一次 _load_from_db 失败分类（"corrupt" | "unavailable"）
        self.load_failure = None

    # ---------------- 基础写入（内存镜像，语义与 Phase 3a 一致） ----------------
    def add_entity(self, eid: str, etype: str, name: str = "", attrs=None, turn: int = 0) -> str:
        eid = str(eid)
        if eid in self.entities:
            return eid
        if etype not in ENTITY_TYPES + SUMMARY_TYPES:
            etype = "institution"
        self.entities[eid] = {
            "eid": eid, "type": etype, "name": name or eid,
            "attrs": dict(attrs or {}), "created_turn": turn,
        }
        return eid

    def add_relation(self, src: str, dst: str, rtype: str, weight: float = 1.0,
                     turn: int = 0, note: str = "", boost: bool = False) -> None:
        """写入关系（图谱存史：不物理删除，重复同向关系叠加权重，重大事件 boost 强化）。"""
        if rtype not in RELATION_TYPES:
            return
        w = max(0.1, float(weight))
        if boost:
            w *= 1.5
        for r in self.relations:
            if r["src"] == src and r["dst"] == dst and r["rtype"] == rtype:
                r["weight"] = min(10.0, r.get("weight", 1.0) + w)
                r["turn"] = turn
                if note:
                    r["note"] = note
                # 审查 P2-10 修复：合并时清 archived 标志，让归档关系重新活跃可见
                r["archived"] = False
                return
        self.relations.append({
            "src": src, "dst": dst, "rtype": rtype,
            "turn": turn, "weight": w, "note": note or "",
        })

    def rollback_after(self, turn: int) -> dict:
        """结算失败回滚：截断 turn 之后写入的记忆（关系/实体/总结/变更日志）。

        审查 A2 补齐：`_snapshot_state` 深拷贝会跳过含 SQLite 连接的对象，故结算
        异常回滚只还原 state 字段，**记忆库仍留着失败回合已写入的关系** —— 重试时
        同一事实被再次 upsert，关系权重叠加（min(10.0, …) 且不可逆），盘面语义偏移。

        只删「> turn」，不删「== turn」：同回合内失败前的合法写入可能是既有事实，
        宁可少删不可误删。SQL 侧列名随 schema 版本而异，单表失败即跳过、不中断。
        返回各表删除条数。
        """
        turn = int(turn)
        removed = {"relations": 0, "entities": 0, "summaries": 0, "change_log": 0}
        for r in list(self.relations):
            if int(r.get("turn", 0) or 0) > turn:
                self.relations.remove(r)
                removed["relations"] += 1
        for eid in [k for k, v in list(self.entities.items())
                    if int(v.get("created_turn", 0) or 0) > turn]:
            self.entities.pop(eid, None)
            removed["entities"] += 1
        if self._slot is not None:
            try:
                conn = self._connect(self._slot)
            except Exception:  # noqa: BLE001
                return removed
            try:
                for tbl, col in (("relations", "turn"), ("entities", "created_turn"),
                                 ("summaries", "created_turn"), ("change_log", "turn")):
                    try:
                        cur = conn.execute(f"DELETE FROM {tbl} WHERE {col} > ?", (turn,))
                        removed[tbl] += int(cur.rowcount or 0)
                    except sqlite3.Error:
                        continue      # 该表无此列（schema 版本差异）→ 跳过，不中断
                conn.commit()
            except sqlite3.Error:
                pass
            finally:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
        return removed

    def upsert_relation(self, src, dst, rtype, weight=1.0, turn=0, note="", boost=False):
        """同向关系覆盖权重（用于 stance/promises 的更新语义）。"""
        self.add_relation(src, dst, rtype, weight=weight, turn=turn, note=note, boost=boost)

    # ---------------- 衰减 ----------------
    def _lambda(self, rtype: str) -> float:
        return MEMORY_RELATION_DECAY.get(rtype, 0.02)

    def _eff_weight(self, r, cur_turn: int) -> float:
        """w_eff = w_base × exp(-λ × Δturn)。"""
        d = max(0, cur_turn - r.get("turn", cur_turn))
        lam = self._lambda(r["rtype"])
        return r.get("weight", 1.0) * (2.718281828 ** (-lam * d))

    # ---------------- 检索（内存镜像，语义不变） ----------------
    def query(self, subject: str, rtypes=None, time_window: int = 0, top_k: int = 12):
        """seed 实体 BFS 1-2 跳 + 关系类型过滤 + 时间窗过滤 + 权重×时间衰减排序。

        返回 [(src_eid, dst_eid, rtype, w_eff, note), ...]（与 Phase 3a 一致）。
        """
        seed = subject if subject in self.entities else self._find_entity_by_name(subject)
        if seed is None:
            return []
        rtypes = set(rtypes) if rtypes else set(RELATION_TYPES)
        cur_turn = self.turn
        out = []
        seen = set()           # 关系键去重 (src,dst,rtype)
        seen_eids = {seed}     # 审查 P2-11 修复：节点级去重用独立集合（原拿 eid 字符串去 in 关系键元组，恒真）
        frontier = {seed}
        for hop in (1, 2):
            nxt = set()
            for eid in frontier:
                for r in self.relations:
                    if r.get("archived"):
                        continue
                    if int(r.get("turn", 0) or 0) > cur_turn:
                        # 审查 B-1/J-10 同源修复：内存检索须与 query_sql 的 `r.turn <= cur_turn`
                        # 同口径——读旧档后记忆库里仍留「未来回合」关系，原实现不过滤会把
                        # 未发生之事当既成事实注入（AI「记得未来」）。
                        continue
                    if r["src"] == eid and r["dst"] not in seen_eids:
                        hit = r["dst"]
                    elif r["dst"] == eid and r["src"] not in seen_eids:
                        hit = r["src"]
                    else:
                        continue
                    if r["rtype"] not in rtypes:
                        continue
                    if time_window and cur_turn - r["turn"] > time_window:
                        continue
                    key = (r["src"], r["dst"], r["rtype"])
                    if key in seen:
                        continue
                    seen.add(key)
                    seen_eids.add(hit)
                    w = self._eff_weight(r, cur_turn)
                    out.append((r["src"], r["dst"], r["rtype"], w, r.get("note", "")))
                    nxt.add(hit)
            frontier = nxt
        out.sort(key=lambda x: -x[3])
        return out[:top_k]

    def _find_entity_by_name(self, name: str):
        for eid, e in self.entities.items():
            if e["name"] == name or name in eid:
                return eid
        return None

    @staticmethod
    def _query_tokens(text: str) -> set:
        """查询分词：中文 2-gram + 西文/数字词（关键词检索共用）。

        缺陷修复（中文检索失效）：原实现用「连续中文/字母数字 ≥2 字」的贪婪正则取词，
        对中文是**整段一个 token**——如「赈济京畿灾民如何施行」只切出该 11 字串本身，
        `token in blob` 需整段子串精确命中，于是玩家自然语言检索恒 0 命中，
        `ai/client.py` 拟旨注入的「既往同类诏令」长期空转（静默失效）。
        改为中文 2-gram + 西文词：任一片段命中即计分，命中片段多者优先。
        """
        if not text:
            return set()
        toks = set()
        for run in re.findall(r"[\u4e00-\u9fa5]+", text):
            if len(run) == 1:
                toks.add(run)
            else:
                toks.update(run[i:i + 2] for i in range(len(run) - 1))
        for word in re.findall(r"[A-Za-z0-9]+", text):
            if len(word) >= 2:
                toks.add(word.lower())
        return toks

    def keyword_search(self, text: str, top_k: int = 12):
        """按文本关键词（实体名/关系 note）检索相关关系（内存实现）。

        命中打分 = 命中的查询 token 数（中文 2-gram / 西文词），先按命中数、再按
        w_eff 排序；且不检索「未来回合」关系（与 query_sql 的 `r.turn <= cur_turn`
        同口径，见 query() 注释）。
        """
        toks = self._query_tokens(text)
        if not toks:
            return []
        hits = []
        cur_turn = self.turn
        for r in self.relations:
            if r.get("archived"):
                continue
            if int(r.get("turn", 0) or 0) > cur_turn:
                continue
            s = self.entities.get(r["src"], {}).get("name", r["src"])
            d = self.entities.get(r["dst"], {}).get("name", r["dst"])
            blob = f"{s}{d}{r.get('note','')}".lower()
            score = sum(1 for t in toks if t in blob)
            if not score:
                continue
            w = self._eff_weight(r, cur_turn)
            hits.append((s, d, r["rtype"], w, r.get("note", ""), score))
        hits.sort(key=lambda x: (-x[5], -x[3]))
        return [(h[0], h[1], h[2], h[3], h[4]) for h in hits[:top_k]]

    # ---------------- 摘要 ----------------
    def summarize(self, rows, max_chars: int = 160) -> str:
        """把检索结果压成紧凑中文「相关历史」（AI 注入用，脱敏——只含实体名/档位词/事件）。"""
        if not rows:
            return ""
        parts = []
        for s, d, rt, w, note in rows:
            verb = {
                "supports": "支持", "opposes": "反对", "involves": "涉", "produces": "促成",
                "progresses": "推进", "promises": "许诺", "stance": "态度", "governs": "主政",
            }.get(rt, rt)
            sn = self.entities.get(s, {}).get("name", s)
            dn = self.entities.get(d, {}).get("name", d)
            seg = f"{sn}{verb}{dn}"
            if note:
                seg += f"（{note}）"
            if len("；".join(parts) + seg) > max_chars:
                break
            parts.append(seg)
        return "；".join(parts)

    # ============================================================
    # T7 新增：SQL 精确调动（领域/时间窗/rtype/top_k/权重×衰减排序 + 索引）
    # ============================================================
    def _decay_case_sql(self, alias: str = "r") -> str:
        """生成按 rtype 取 λ 的 CASE 表达式（与内存 _lambda 同源）。"""
        cases = " ".join(f"WHEN '{k}' THEN {v}" for k, v in MEMORY_RELATION_DECAY.items())
        default = MEMORY_RELATION_DECAY.get("involves", 0.03)
        return f"CASE {alias}.rtype {cases} ELSE {default} END"

    def query_sql(self, subject: str = "", rtypes=None, time_window: int = 0,
                  top_k: int = 12, min_weight: float = 0.0, slot: int = None):
        """SQL 精确调动：领域/时间窗/rtype/top_k/权重排序（走索引）。

        - subject：实体 eid 或名称（命中 eid 或 name）→ 仅返回与其相连的关系；
          空串 = 全库范围（用于压缩聚合/全局检索）。
        - time_window：>0 时只取 (cur_turn - time_window, cur_turn] 回合的关系。
        - rtypes：None/空 = 全部类型；否则只取指定类型。
        - min_weight：过滤 w_eff 下限。
        - slot：目标数据库槽位；默认 self._slot（未落盘时回退内存等价实现）。
        返回与 query() 相同的 5 元组列表 [(src, dst, rtype, w_eff, note)]。
        """
        rtypes = set(rtypes) if rtypes else set(RELATION_TYPES)
        cur_turn = self.turn
        slot = slot if slot is not None else self._slot
        # 未落盘，或该槽位 db 文件尚不存在（新开局 / 刚换档 / 首次调用）→ 内存等价实现。
        # 原实现只在 slot is None 时回退，db 缺失一律 return [] —— 记忆明明在内存镜像里
        # 却「查无此事」（记忆库面板与压缩聚合会显示为空）。
        if slot is None or not os.path.exists(_db_path(slot)):
            # 未落盘（纯内存测试/运行早期）→ 内存等价实现，保证接口一致
            out = []
            for r in self.relations:
                if r.get("archived") or r["rtype"] not in rtypes:
                    continue
                if r["turn"] > cur_turn:
                    continue                      # 历史查询不含"未来"回合
                if time_window and cur_turn - r["turn"] > time_window:
                    continue
                if subject and not (
                    r["src"] == subject or r["dst"] == subject
                    or self.entities.get(r["src"], {}).get("name") == subject
                    or self.entities.get(r["dst"], {}).get("name") == subject
                ):
                    continue
                w = self._eff_weight(r, cur_turn)
                if min_weight and w < min_weight:
                    continue
                out.append((r["src"], r["dst"], r["rtype"], w, r.get("note", "")))
            out.sort(key=lambda x: -x[3])
            return out[:top_k]
        db = _db_path(slot)
        if not os.path.exists(db):
            return []
        lam_expr = self._decay_case_sql("r")
        inner = (f"SELECT r.src, r.dst, r.rtype, "
                 f"r.weight * exp(-{lam_expr} * (? - r.turn)) AS w_eff, r.note "
                 f"FROM relations r WHERE r.archived = 0 AND r.turn <= ? AND r.turn >= ? ")
        params = [cur_turn, cur_turn, cur_turn - time_window if time_window else -1 << 30]
        if subject:
            inner += ("AND (r.src = ? OR r.dst = ? OR r.src IN "
                      "(SELECT eid FROM entities WHERE name = ? OR eid = ?) OR r.dst IN "
                      "(SELECT eid FROM entities WHERE name = ? OR eid = ?)) ")
            params += [subject, subject, subject, subject, subject, subject]
        if rtypes != set(RELATION_TYPES):
            placeholders = ",".join("?" for _ in rtypes)
            inner += f"AND r.rtype IN ({placeholders}) "
            params += sorted(rtypes)
        if min_weight:
            # 子查询包裹：先算 w_eff 别名，再按阈值过滤（HAVING 引用别名在无 GROUP BY 时不可靠）
            sql = f"SELECT * FROM ({inner}) WHERE w_eff >= ? ORDER BY w_eff DESC LIMIT ?"
            params += [min_weight, top_k]
        else:
            sql = inner + "ORDER BY w_eff DESC LIMIT ?"
            params.append(top_k)
        try:
            conn = self._connect(slot)
            try:
                cur = conn.execute(sql, params)
                return [tuple(row) for row in cur.fetchall()]
            finally:
                conn.close()
        except sqlite3.Error as e:
            # D 修复（静默降级）：SQL 用到 exp()，若运行环境 SQLite 未编译
            # SQLITE_ENABLE_MATH_FUNCTIONS 则会抛错；原实现直接 return [] →
            # 记忆检索/压缩/总结全部静默归零且无任何线索。此处记 warning 便于诊断。
            log.warning("memory.query_sql 失败（降级为空）：%s", e)
            return []

    def query_summaries(self, period: int = None, stype: str = None,
                        top_k: int = 12, slot: int = None):
        """SQL 查 summaries 表（层级检索第一层：概要）。

        返回 [{eid, stype, period, name, attrs(dict), created_turn}, ...]；
        period 给定 → 精确命中；stype 过滤 summary/period_summary。
        """
        slot = slot if slot is not None else self._slot
        # 与 query_sql 同规：未落盘或槽位 db 缺失 → 从内存镜像过滤 summary 类实体
        if slot is None or not os.path.exists(_db_path(slot)):
            # 未落盘：从内存 entities 过滤 summary 类实体
            rows = []
            for e in self.entities.values():
                if e["type"] not in SUMMARY_TYPES:
                    continue
                if stype and e["type"] != stype:
                    continue
                p = (e.get("attrs") or {}).get("period")
                if period is not None and p != period:
                    continue
                rows.append({"eid": e["eid"], "stype": e["type"], "period": p,
                             "name": e["name"], "attrs": e.get("attrs") or {},
                             "created_turn": e.get("created_turn", 0)})
            rows.sort(key=lambda x: -(x["period"] or 0))
            return rows[:top_k]
        db = _db_path(slot)
        if not os.path.exists(db):
            return []
        sql = "SELECT eid, stype, period, name, attrs, created_turn FROM summaries WHERE 1=1 "
        params = []
        if period is not None:
            sql += "AND period = ? "
            params.append(period)
        if stype:
            sql += "AND stype = ? "
            params.append(stype)
        sql += "ORDER BY period DESC LIMIT ?"
        params.append(top_k)
        try:
            conn = self._connect(slot if slot is not None else self._slot)
            try:
                rows = []
                for row in conn.execute(sql, params):
                    try:
                        attrs = json.loads(row[4]) if row[4] else {}
                    except (TypeError, ValueError):
                        attrs = {}
                    rows.append({"eid": row[0], "stype": row[1], "period": row[2],
                                 "name": row[3], "attrs": attrs, "created_turn": row[5]})
                return rows
            finally:
                conn.close()
        except sqlite3.Error:
            return []

    def query_change_log(self, limit: int = 50, action: str = None,
                         slot: int = None) -> list:
        """读 change_log 表（审计/回放用）。

        该表自 T7 起每次写盘/压缩/总结/归档都追加留痕，却**没有任何读取入口**（只写不读，
        审计能力空置）。此处补上只读查询：
        - action 可选过滤（save_snapshot / compress / summarize_period / archive）；
        - 按 id 倒序（最新在前）；库不存在/未落盘/读失败 → 空列表（不抛，记 warning）。
        返回 [{id, turn, action, detail, ts}]。
        """
        slot = slot if slot is not None else self._slot
        if slot is None or not os.path.exists(_db_path(slot)):
            return []
        sql = "SELECT id, turn, action, detail, ts FROM change_log "
        params = []
        if action:
            sql += "WHERE action = ? "
            params.append(action)
        sql += "ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        try:
            conn = self._connect(slot)
            try:
                return [{"id": r[0], "turn": r[1], "action": r[2],
                         "detail": r[3], "ts": r[4]}
                        for r in conn.execute(sql, params)]
            finally:
                conn.close()
        except sqlite3.Error as e:
            log.warning("memory.query_change_log 读取失败（降级为空）：%s", e)
            return []

    def retrieve_hierarchical(self, subject: str = "", period: int = None,
                              top_k: int = 12, slot: int = None) -> dict:
        """层级检索：先 summaries 概要 → 细节按需（query 下钻）。

        返回 {"level": 1|2, "summary": str, "rows": [...], "source": "summary"|"detail"}。
        - level=1：命中指定 period 的概要（summary/period_summary），只给概要，不展开细节；
        - level=2：无概要/未指定 period → query(subject) 细节行 + summarize 压缩注入文本。
        """
        if period is not None:
            su = self.query_summaries(period=period, slot=slot)
            if su:
                s = su[0]
                parts = [f"{s['name']}"]
                a = s.get("attrs") or {}
                for k in ("decision_count", "event_count", "relation_count"):
                    if k in a:
                        parts.append(f"{k}={a[k]}")
                top = a.get("top_relations")
                if isinstance(top, list) and top:
                    parts.append("要略：" + "；".join(str(x) for x in top[:5]))
                return {"level": 1, "summary": "，".join(parts), "rows": [],
                        "source": "summary"}
        rows = self.query(subject, top_k=top_k) if subject else self.query_sql(
            rtypes=None, time_window=0, top_k=top_k, slot=slot)
        return {"level": 2, "summary": self.summarize(rows), "rows": rows,
                "source": "detail"}

    # ============================================================
    # T7 新增：压缩（每 6 回合）与周期总结（每 12 回合）——SQL 聚合，旧数据不动
    # ============================================================
    def _aggregate_relations(self, time_window: int, top_k: int, slot: int = None) -> list:
        """SQL 聚合近 time_window 回合的关系（按 w_eff 排序取 top_k），未落盘时回退内存。"""
        rows = self.query_sql(rtypes=None, time_window=time_window,
                              top_k=top_k, slot=slot)
        out = []
        for src, dst, rt, w, note in rows:
            sn = self.entities.get(src, {}).get("name", src)
            dn = self.entities.get(dst, {}).get("name", dst)
            seg = f"{sn}→{dn}({rt})"
            if note:
                seg += f"〔{note}〕"
            out.append(seg)
        return out

    def compress(self, turn: int, slot: int = None) -> str:
        """每 6 回合压缩：SQL 聚合近 6 回合关系 → summary 实体（etype=summary）。

        - period = turn // 6；eid = summary_{period}；幂等（重复调用 REPLACE 覆盖）。
        - 旧数据不动：只 SELECT 聚合写入 summaries 表，不修改原 entities/relations。
        - 返回 summary eid；聚合失败返回空串。
        """
        period = max(0, turn // _COMPRESS_INTERVAL)
        start = max(0, turn - _COMPRESS_INTERVAL)
        eid = f"summary_{period}"
        # 审查 P2-49 修复（相邻概要重叠）：query_sql 的 time_window 是**左闭**区间
        # [turn-window, turn]，用 window=interval 会让边界回合（如 turn=6）同时落入
        # 第 1/2 期概要。改为 window=interval-1 → [turn-interval+1, turn]，即左开右闭
        # (turn-interval, turn]，与 start_turn（左开边界）元数据口径一致、相邻期不重叠。
        top = self._aggregate_relations(max(1, _COMPRESS_INTERVAL - 1), 8, slot)
        attrs = {
            "period": period, "start_turn": start, "end_turn": turn,
            "relation_count": len(top), "top_relations": top,
        }
        name = f"第{period}期概要"
        # 内存镜像同步（保证 .entities 完整可查）
        self.entities[eid] = {"eid": eid, "type": "summary", "name": name,
                              "attrs": attrs, "created_turn": turn}
        slot = slot if slot is not None else self._slot
        if slot is None:
            return eid          # 未落盘：仅内存镜像（save() 时会一并写入 summaries 表）
        db = _db_path(slot)
        if not os.path.exists(db):
            return eid
        try:
            conn = self._connect(slot)
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO summaries(eid, stype, period, name, attrs, created_turn) "
                        "VALUES(?,?,?,?,?,?)",
                        (eid, "summary", period, name, json.dumps(attrs, ensure_ascii=False), turn))
                    conn.execute(
                        "INSERT INTO change_log(slot, turn, action, detail, ts) VALUES(?,?,?,?,?)",
                        (slot, turn, "compress", f"period={period} relations={len(top)}", _now_str()))
                return eid
            finally:
                conn.close()
        except sqlite3.Error:
            return ""

    def summarize_period(self, turn: int, slot: int = None) -> str:
        """每 12 回合周期总结：聚合本轮决策/事件 + 关键关系 → period_summary 实体。

        - period = turn // 12；eid = period_summary_{period}；幂等 REPLACE。
        - 旧数据不动：只聚合写入 summaries 表。
        - 返回 period_summary eid；失败返回空串。
        """
        period = max(0, turn // _PERIOD_INTERVAL)
        start = max(0, turn - _PERIOD_INTERVAL)
        eid = f"period_summary_{period}"
        decisions = [e for e in self.entities.values()
                     if e["type"] == "decision" and start < e.get("created_turn", 0) <= turn]
        events = [e for e in self.entities.values()
                  if e["type"] == "event" and start < e.get("created_turn", 0) <= turn]
        ministers = sorted({e["name"] for e in self.entities.values()
                            if e["type"] == "minister"
                            and start < e.get("created_turn", 0) <= turn})
        # 审查 P2-49：同 compress——窗口取 interval-1，使关系聚合区间与上方实体过滤
        # 的 (start, turn] 左开右闭区间一致，相邻周期不共享边界回合。
        top = self._aggregate_relations(max(1, _PERIOD_INTERVAL - 1), 8, slot)
        attrs = {
            "period": period, "start_turn": start, "end_turn": turn,
            "decision_count": len(decisions), "event_count": len(events),
            "minister_count": len(ministers),
            "top_relations": top,
        }
        name = f"第{period}轮史略"
        self.entities[eid] = {"eid": eid, "type": "period_summary", "name": name,
                              "attrs": attrs, "created_turn": turn}
        slot = slot if slot is not None else self._slot
        if slot is None:
            return eid
        db = _db_path(slot)
        if not os.path.exists(db):
            return eid
        try:
            conn = self._connect(slot)
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO summaries(eid, stype, period, name, attrs, created_turn) "
                        "VALUES(?,?,?,?,?,?)",
                        (eid, "period_summary", period, name,
                         json.dumps(attrs, ensure_ascii=False), turn))
                    conn.execute(
                        "INSERT INTO change_log(slot, turn, action, detail, ts) VALUES(?,?,?,?,?)",
                        (slot, turn, "summarize_period",
                         f"period={period} decisions={len(decisions)} events={len(events)}",
                         _now_str()))
                return eid
            finally:
                conn.close()
        except sqlite3.Error:
            return ""

    # ============================================================
    # SQLite 存储层（事务原子写 / 唯一索引去重 / INSERT OR REPLACE）
    # ============================================================
    @staticmethod
    def _connect(slot: int) -> sqlite3.Connection:
        """打开（必要时创建）槽位记忆库：按需建表 + WAL + busy 超时。

        审查 P2-47 修复：原实现每次连接都 executescript(_SCHEMA_SQL)（DDL 会触发写事务/
        隐式提交），只读查询也因此反复建表，并发下更易 database is locked；且未启用 WAL
        （dialogue_memory 已启用，二者不一致）。
        现改为「探测 entities 表是否存在」按需建表（一次 sqlite_master 查询，开销极低）；
        不使用进程内缓存——库文件可能被外部删除/替换（测试、多存档目录切换），
        按路径缓存会漏建表。
        """
        os.makedirs(SAVE_DIR, exist_ok=True)
        conn = sqlite3.connect(_db_path(slot), timeout=5)
        # P2-13：建连/建表中途失败必须关掉句柄再抛 —— 否则损坏库被占用，
        # Windows 无法 os.replace 隔离（WinError 32），quarantine 静默失败。
        try:
            conn.execute("PRAGMA busy_timeout = 3000")
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass
            _has = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='entities'").fetchone()
            if not _has:
                conn.executescript(_SCHEMA_SQL)
                conn.commit()
            return conn
        except sqlite3.Error:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            raise

    def save(self, slot: int) -> bool:
        """回合末原子写盘：单事务快照内存镜像 → SQLite（INSERT OR REPLACE 幂等去重）。

        state/entities/relations/summaries/change_log 五表同事务；任一失败 ROLLBACK，
        不产生半写状态。summary/period_summary 实体仅写 summaries 表（业务实体写 entities 表）。
        """
        slot = int(slot)
        self._slot = slot
        try:
            conn = self._connect(slot)
        except sqlite3.Error:
            return False
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO state(key, value) VALUES(?,?)",
                             ("schema_version", str(self.schema_version)))
                conn.execute("INSERT OR REPLACE INTO state(key, value) VALUES(?,?)",
                             ("turn", str(self.turn)))
                conn.execute("INSERT OR REPLACE INTO state(key, value) VALUES(?,?)",
                             ("archived", str(self.archived)))
                # 审查 P2-48 修复（快照语义）：先清主表再全量重写。原实现只 INSERT OR REPLACE
                # 不删除，内存里已删除的实体/关系会在 DB 永久残留（与「快照」语义不符）。
                conn.execute("DELETE FROM entities")
                conn.execute("DELETE FROM relations")
                # D 修复（快照语义不完整）：summaries 原只 INSERT OR REPLACE，不从内存
                # 移除的旧 summary 行会永久残留；而 rollback_after 却会按 created_turn
                # 删 summaries（两处语义不一致）。此处与主表同规，先清后全量重写。
                conn.execute("DELETE FROM summaries")
                for e in self.entities.values():
                    if not isinstance(e, dict):
                        continue
                    if e.get("type") in SUMMARY_TYPES:
                        continue      # summary 实体走 summaries 表
                    if not str(e.get("eid", "")).strip():
                        # 审查 P2-48：空 eid 会在主键 '' 上互相 REPLACE（丢数据），跳过
                        log.warning("memory.save: 跳过无 eid 实体：%r", e.get("name", ""))
                        continue
                    try:
                        attrs_json = json.dumps(e.get("attrs") or {}, ensure_ascii=False)
                    except (TypeError, ValueError):
                        attrs_json = "{}"
                    conn.execute(
                        "INSERT OR REPLACE INTO entities(eid, type, name, attrs, created_turn) "
                        "VALUES(?,?,?,?,?)",
                        (str(e.get("eid", "")), str(e.get("type", "institution")),
                         str(e.get("name", "")), attrs_json, int(e.get("created_turn", 0) or 0)))
                for r in self.relations:
                    if not isinstance(r, dict):
                        continue
                    conn.execute(
                        "INSERT OR REPLACE INTO relations(src, dst, rtype, turn, weight, note, archived) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (str(r.get("src", "")), str(r.get("dst", "")), str(r.get("rtype", "")),
                         int(r.get("turn", 0) or 0), float(r.get("weight", 1.0)),
                         str(r.get("note", "") or ""), int(1 if r.get("archived") else 0)))
                for e in self.entities.values():
                    if isinstance(e, dict) and e.get("type") in SUMMARY_TYPES:
                        try:
                            attrs_json = json.dumps(e.get("attrs") or {}, ensure_ascii=False)
                        except (TypeError, ValueError):
                            attrs_json = "{}"
                        conn.execute(
                            "INSERT OR REPLACE INTO summaries(eid, stype, period, name, attrs, created_turn) "
                            "VALUES(?,?,?,?,?,?)",
                            (str(e.get("eid", "")), str(e.get("type", "summary")),
                             int((e.get("attrs") or {}).get("period", 0)),
                             str(e.get("name", "")), attrs_json,
                             int(e.get("created_turn", 0) or 0)))
                conn.execute(
                    "INSERT INTO change_log(slot, turn, action, detail, ts) VALUES(?,?,?,?,?)",
                    (slot, self.turn, "save_snapshot",
                     f"entities={sum(1 for e in self.entities.values() if isinstance(e, dict))} "
                     f"relations={len(self.relations)}", _now_str()))
            return True
        except (sqlite3.Error, ValueError, TypeError):
            return False          # 事务上下文已自动 ROLLBACK
        finally:
            conn.close()

    def _load_from_db(self, slot: int) -> bool:
        """从 SQLite 读回内存镜像（含 summaries 实体并入 .entities）。"""
        try:
            conn = self._connect(slot)
        except sqlite3.OperationalError as e:
            self.load_failure = ("unavailable", e)  # 例如 database is locked（非损坏）
            return False
        except sqlite3.DatabaseError as e:
            self.load_failure = ("corrupt", e)      # file is not a database / 物理损坏
            return False
        except (sqlite3.Error, OSError) as e:
            self.load_failure = ("unavailable", e)  # 权限 / 其它不可用
            return False
        try:
            self.schema_version = int(self._state_get(conn, "schema_version") or _SCHEMA_VERSION)
            self.turn = int(self._state_get(conn, "turn") or 0)
            self.archived = int(self._state_get(conn, "archived") or 0)
            ents = {}
            for row in conn.execute("SELECT eid, type, name, attrs, created_turn FROM entities"):
                try:
                    attrs = json.loads(row[3]) if row[3] else {}
                except (TypeError, ValueError):
                    attrs = {}
                ents[row[0]] = {"eid": row[0], "type": row[1], "name": row[2],
                                "attrs": attrs, "created_turn": row[4]}
            for row in conn.execute("SELECT eid, stype, period, name, attrs, created_turn FROM summaries"):
                try:
                    attrs = json.loads(row[4]) if row[4] else {}
                except (TypeError, ValueError):
                    attrs = {}
                attrs = dict(attrs)
                attrs.setdefault("period", row[2])
                ents[row[0]] = {"eid": row[0], "type": row[1], "name": row[3],
                                "attrs": attrs, "created_turn": row[5]}
            rels = []
            for row in conn.execute("SELECT src, dst, rtype, turn, weight, note, archived FROM relations"):
                rels.append({"src": row[0], "dst": row[1], "rtype": row[2],
                             "turn": row[3], "weight": row[4], "note": row[5],
                             "archived": bool(row[6])})
            self.entities = ents
            self.relations = rels
            return True
        except sqlite3.OperationalError as e:
            self.load_failure = ("unavailable", e)
            self.entities = {}
            self.relations = []
            return False
        except (sqlite3.DatabaseError, TypeError, ValueError) as e:
            self.load_failure = ("corrupt", e)
            self.entities = {}
            self.relations = []
            return False
        except sqlite3.Error as e:
            self.load_failure = ("unavailable", e)
            self.entities = {}
            self.relations = []
            return False
        finally:
            conn.close()

    @staticmethod
    def _state_get(conn: sqlite3.Connection, key: str) -> str:
        row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else ""

    def load(self, slot: int) -> bool:
        """按槽位加载记忆库（SQLite 权威）；无 db 时尝试旧 JSON 迁移，否则建空图。

        审查 P2-13 修复：损坏库 / 损坏迁移源**不再静默变空**——
          - 迁移源损坏：保留原 JSON 现场并另存 `<path>.corrupt`，记录 `self.load_error`；
          - 库损坏 / 结构异常：隔离为 `<db>.corrupt`（含 -wal/-shm），记录 `self.load_error`；
          - 仅「无库且无迁移源」的**新局**才返回正常空图（`load_error` 保持 None）。
        返回 False 均可在 `self.load_error` 取到可诊断原因；返回 True 才是正常加载。
        """
        slot = int(slot)
        self._slot = slot
        self._migrated = False
        self.load_error = None
        self.load_failure = None
        db = _db_path(slot)
        if not os.path.exists(db):
            if os.path.exists(_memory_path(slot)):
                # 旧 Phase 3a JSON 迁移（migrate_json 内部区分「损坏」与「写库失败」）
                if not self.migrate_json(slot):
                    self.entities = {}
                    self.relations = []
                    return False
            else:
                # 全新开局：无库无迁移源 → 正常空图（非损坏，load_error 保持 None）
                self.entities = {}
                self.relations = []
                return False
        ok = self._load_from_db(slot)
        if not ok:
            kind, err = getattr(self, "load_failure", None) or ("corrupt", None)
            self.entities = {}
            self.relations = []
            if kind == "corrupt":
                backup = _quarantine_db(slot)
                self.load_error = (f"记忆库损坏 / 无法解析，已隔离为 "
                                   f"{backup or (_db_path(slot) + '.corrupt')}（slot={slot}）：{err}")
            else:
                # 仅暂时不可用（如 database is locked）：保留原文件，绝不冒充损坏
                self.load_error = (f"记忆库暂时不可用（未隔离，非损坏判定；slot={slot}）：{err}")
            log.error(self.load_error)
        return ok

    def migrate_json(self, slot: int) -> bool:
        """旧 JSON 记忆文件 → SQLite 迁移（迁移后旧 JSON 保留，不删除；可安全回退）。

        P2-13：损坏 JSON / 顶层非对象 / 结构非法 → 另存 `.corrupt` 备份 + 记录
        `self.load_error` + 返回 False，**不再**让上层把「迁移失败」当「空图」静默吞掉。
        """
        jpath = _memory_path(slot)
        if not os.path.exists(jpath):
            return False
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            backup = _backup_corrupt_copy(jpath)
            self.load_error = (f"旧记忆 JSON 损坏，无法迁移（slot={slot}）：{e}；"
                               f"备份={backup or (jpath + '.corrupt')}")
            log.error(self.load_error)
            return False
        if not isinstance(data, dict):
            backup = _backup_corrupt_copy(jpath)
            self.load_error = (f"旧记忆 JSON 顶层非对象（slot={slot}）："
                               f"{type(data).__name__}；备份={backup or (jpath + '.corrupt')}")
            log.error(self.load_error)
            return False
        try:
            self.from_dict(data)      # 旧 schema（v1）兼容加载
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            backup = _backup_corrupt_copy(jpath)
            self.load_error = (f"旧记忆 JSON 结构非法（slot={slot}）：{e}；"
                               f"备份={backup or (jpath + '.corrupt')}")
            log.error(self.load_error)
            return False
        self._migrated = True
        # 迁移后写 SQLite；archive JSON（若有）并入 archived 标记
        ok = self.save(slot)
        if not ok:
            self.load_error = f"旧记忆 JSON 合法，但迁移写库失败（slot={slot}）"
            log.error(self.load_error)
            return False
        if ok:
            try:
                apath = _memory_path(slot, archive=True)
                if os.path.exists(apath):
                    with open(apath, "r", encoding="utf-8") as f:
                        arch = json.load(f) or []
                    for r in arch:
                        if isinstance(r, dict):
                            r = dict(r)
                            r["archived"] = True
                            self.relations.append(r)
                    self.archived += len(arch)
                    self.save(slot)   # 归档关系补写
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        return ok

    def archive(self, slot: int, weight_below: float = MEMORY_ARCHIVE_WEIGHT) -> int:
        """归档低权重旧史（w_eff < 阈值）：SQLite relations.archived 标记，不物理删除。

        与 Phase 3a 差异：不再写 memory_archive.json，改 db 内 archived 列（仍可查证历史）。
        - 幂等：已归档的行不再计数（重复调用返回 0）。
        - 生产接线：`finish_turn` 每 `_ARCHIVE_INTERVAL` 回合调用一次（原实现零调用方，
          关系/实体只增不减 —— 每回合全量重写 save() 的 IO 随历史线性放大）。
        - 只写本轮**新归档**的行（原实现每轮 UPDATE 全部 archived 行，代价随历史累加）。
        """
        moved = 0
        cur_turn = self.turn
        newly = []
        for r in self.relations:
            if not r.get("archived") and self._eff_weight(r, cur_turn) < weight_below:
                r["archived"] = True
                newly.append(r)
                moved += 1
        if not moved:
            return 0
        self.archived += moved
        slot = int(slot)
        if not os.path.exists(_db_path(slot)):
            return moved          # 未落盘：仅内存标记（save() 时写入 db archived 列）
        try:
            conn = self._connect(slot)
            try:
                with conn:
                    for r in newly:
                        conn.execute(
                            "UPDATE relations SET archived = 1 "
                            "WHERE src = ? AND dst = ? AND rtype = ?",
                            (r["src"], r["dst"], r["rtype"]))
                    conn.execute(
                        "INSERT INTO change_log(slot, turn, action, detail, ts) VALUES(?,?,?,?,?)",
                        (slot, cur_turn, "archive", f"moved={moved}", _now_str()))
                return moved
            finally:
                conn.close()
        except sqlite3.Error:
            return 0

    # ---------------- 内存态导出/导入（迁移与兼容用） ----------------
    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "turn": self.turn,
                "entities": self.entities, "relations": self.relations,
                "archived": self.archived}

    def from_dict(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError("memory graph 数据损坏")
        self.schema_version = int(data.get("schema_version", _JSON_SCHEMA_VERSION))
        self.turn = int(data.get("turn", 0))
        ents = data.get("entities") or {}
        self.entities = {k: v for k, v in ents.items()
                         if isinstance(v, dict) and k}
        rels = data.get("relations") or []
        self.relations = [r for r in rels if isinstance(r, dict)]
        self.archived = int(data.get("archived", 0))

    # ---------------- 便捷写入（业务点调用，经 _safety_filter 后再写入） ----------------
    def record_decision(self, title: str, effects, minister="", turn: int = 0,
                        supports=(), opposes=(), note=""):
        """决策落地：decision 实体 + produces 效果 + 大臣 supports/opposes。"""
        did = f"decision_{turn}_{title}"[:64]
        self.add_entity(did, "decision", title, {"effects": effects}, turn=turn)
        if minister:
            mid = self.add_entity(f"minister_{minister}", "minister", minister, turn=turn)
            self.add_relation(mid, did, "involves", weight=1.0, turn=turn, note="决策相关")
        for m in supports or ():
            mid = self.add_entity(f"minister_{m}", "minister", m, turn=turn)
            self.add_relation(mid, did, "supports", weight=1.2, turn=turn, note="赞同")
        for m in opposes or ():
            mid = self.add_entity(f"minister_{m}", "minister", m, turn=turn)
            self.add_relation(mid, did, "opposes", weight=1.2, turn=turn, note="反对")
        return did

    def record_event(self, eid, title, involved=(), turn: int = 0):
        """事件：event 实体 + involves 关联。"""
        self.add_entity(eid, "event", title, turn=turn)
        for name in involved or ():
            mid = self.add_entity(f"minister_{name}", "minister", name, turn=turn)
            self.add_relation(eid, mid, "involves", weight=1.0, turn=turn, note="涉事")


# 全局便捷函数（供业务点延迟导入调用）
# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：记忆读取便利入口：被 query/query_sql 取代，可评估删除
def get_memory(slot: int) -> MemoryGraph:
    g = MemoryGraph()
    g.load(slot)
    return g


# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：记忆写入便利入口：被 save 取代，可评估删除
def save_memory(slot: int, graph: MemoryGraph) -> bool:
    return graph.save(slot)


# 时间戳辅助（change_log 用）
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
