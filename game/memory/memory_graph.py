# -*- coding: utf-8 -*-
"""宋祚 · 记忆知识库（Phase 3a，言枢密方案已审）。

**图谱存「史」、GameState 存「态」**：跨回合连贯、大臣记得历史。

- Entity 7 类：minister / event / decision / task / org / institution / external_power
- Relation 8 类：supports / opposes / involves / produces / progresses / promises /
  stance / governs（带 timestamp/weight/half_life→λ 衰减）
- 存储：`saves/slot_{slot}_memory.json`（回合末原子写盘）+ `_memory_archive.json` 归档；
  schema_version + 迁移；损坏时从存档重放重建（不阻断游戏）。
- 衰减：w_eff = w_base × exp(-λ × Δturn)，λ 按关系类型（content.data.MEMORY_RELATION_DECAY
  单一权威源）；重大事件强化；不物理删除。
- 检索：query（seed 实体 BFS 1-2 跳 + 过滤 + 权重×时间排序）、keyword_search、summarize。
- AI 注入：召对/拟旨/推演/月报 query → summarize 注入 state_summary（脱敏）。
- 原则：真值（economy_history/corruption）不注入图谱/AI；minister_memory 升级为图谱投影
  （读时从图谱生成，短期双写兼容）。

注意：`saves/slot_{slot}_memory.json` 与主存档 `saves/slot_{slot}.json` 平级，
不破坏既有单文件存档结构（方案语义「按槽位分离」以平级文件实现）。
"""
import os
import json
import re
from datetime import datetime

from content.data import SAVE_DIR, MEMORY_RELATION_DECAY, MEMORY_ARCHIVE_WEIGHT

# 实体类型（7 类）
ENTITY_TYPES = ("minister", "event", "decision", "task", "org", "institution", "external_power")
# 关系类型（8 类）
RELATION_TYPES = ("supports", "opposes", "involves", "produces", "progresses",
                  "promises", "stance", "governs")

_SCHEMA_VERSION = 1


def _memory_path(slot: int, archive: bool = False) -> str:
    base = f"slot_{slot}_memory{'_archive' if archive else ''}.json"
    return os.path.join(SAVE_DIR, base)


class MemoryGraph:
    """记忆知识库：Entity + Relation，带衰减/检索/摘要/存档/归档。"""

    def __init__(self, schema_version: int = _SCHEMA_VERSION):
        self.schema_version = schema_version
        self.turn = 0
        self.entities = {}        # eid -> {"eid","type","name","attrs":{},"created_turn"}
        self.relations = []       # [{src,dst,rtype,turn,weight,note}]
        self.archived = 0         # 归档关系计数

    # ---------------- 基础写入 ----------------
    def add_entity(self, eid: str, etype: str, name: str = "", attrs=None, turn: int = 0) -> str:
        eid = str(eid)
        if eid in self.entities:
            return eid
        if etype not in ENTITY_TYPES:
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
                return
        self.relations.append({
            "src": src, "dst": dst, "rtype": rtype,
            "turn": turn, "weight": w, "note": note or "",
        })

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

    # ---------------- 检索 ----------------
    def query(self, subject: str, rtypes=None, time_window: int = 0, top_k: int = 12):
        """seed 实体 BFS 1-2 跳 + 关系类型过滤 + 时间窗过滤 + 权重×时间衰减排序。

        返回 [(src_name, dst_name, rtype, w_eff, note), ...]。
        """
        seed = subject if subject in self.entities else self._find_entity_by_name(subject)
        if seed is None:
            return []
        rtypes = set(rtypes) if rtypes else set(RELATION_TYPES)
        out = []
        seen = set()
        frontier = {seed}
        for hop in (1, 2):
            nxt = set()
            for eid in frontier:
                for r in self.relations:
                    if r["src"] == eid and r["dst"] not in seen:
                        hit = r["dst"]
                    elif r["dst"] == eid and r["src"] not in seen:
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
                    w = self._eff_weight(r, self.turn)
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

    def keyword_search(self, text: str, top_k: int = 12):
        """按文本关键词（实体名/关系 note）检索相关关系。"""
        if not text:
            return []
        hits = []
        for r in self.relations:
            s = self.entities.get(r["src"], {}).get("name", r["src"])
            d = self.entities.get(r["dst"], {}).get("name", r["dst"])
            blob = f"{s}{d}{r.get('note','')}"
            if any(k in blob for k in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text)):
                w = self._eff_weight(r, self.turn)
                hits.append((s, d, r["rtype"], w, r.get("note", "")))
        hits.sort(key=lambda x: -x[3])
        return hits[:top_k]

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

    # ---------------- 存储 ----------------
    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "turn": self.turn,
                "entities": self.entities, "relations": self.relations,
                "archived": self.archived}

    def from_dict(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError("memory graph 数据损坏")
        self.schema_version = int(data.get("schema_version", 1))
        self.turn = int(data.get("turn", 0))
        ents = data.get("entities") or {}
        self.entities = {k: v for k, v in ents.items()
                         if isinstance(v, dict) and k}
        rels = data.get("relations") or []
        self.relations = [r for r in rels if isinstance(r, dict)]
        self.archived = int(data.get("archived", 0))

    def save(self, slot: int) -> bool:
        """回合末原子写盘（先写 tmp 再替换）。"""
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            path = _memory_path(slot)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def load(self, slot: int) -> bool:
        """加载记忆图；损坏时重建（不阻断游戏）。"""
        try:
            with open(_memory_path(slot), "r", encoding="utf-8") as f:
                self.from_dict(json.load(f))
            return True
        except (OSError, ValueError, json.JSONDecodeError):
            # 损坏/缺失 → 重建空图（主存档重放重建由上层决定）
            self.entities = {}
            self.relations = []
            return False

    def archive(self, slot: int, weight_below: float = 0.25) -> int:
        """归档低权重旧史（w_eff < 阈值）到 archive 文件；不物理删除。"""
        moved = 0
        arch = []
        keep = []
        for r in self.relations:
            if self._eff_weight(r, self.turn) < weight_below:
                arch.append(r)
                moved += 1
            else:
                keep.append(r)
        if not arch:
            return 0
        self.relations = keep
        self.archived += moved
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            apath = _memory_path(slot, archive=True)
            old = []
            if os.path.exists(apath):
                try:
                    with open(apath, "r", encoding="utf-8") as f:
                        old = json.load(f) or []
                except (OSError, json.JSONDecodeError):
                    old = []
            with open(apath, "w", encoding="utf-8") as f:
                json.dump(old + arch, f, ensure_ascii=False, indent=1)
        except OSError:
            pass
        return moved

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
def get_memory(slot: int) -> MemoryGraph:
    g = MemoryGraph()
    g.load(slot)
    return g


def save_memory(slot: int, graph: MemoryGraph) -> bool:
    return graph.save(slot)


# 时间戳辅助（schema 兼容字段）
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
