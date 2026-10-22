# -*- coding: utf-8 -*-
"""本地知识库构建/查询工具（知识库本地化）。

> 历史注（2026-10-22）：原文案写的是「替代原 CloudBase PG 方案」——CloudBase 已随云侧迁阿里云**停用**，
> 该说法只作历史背景；现行实现**只读写本地 SQLite**，不连任何云端数据库。

两个独立 SQLite 库（一库一知识库）：
  - 游戏库：game/assets/kb/game_kb.sqlite    —— 游戏设计文档，随游戏分发，游戏内 AI 经 kb_search 工具调用
  - 开发库：_dev_tools/game-docs/kb/dev_kb.sqlite —— 开发工程文档，仅开发用，不随游戏分发

用法：
  python build_kb.py build                      # 重建两个库
  python build_kb.py query "冗兵" [--db game|dev] [--top 3]

查询算法（FTS5 trigram + LIKE 兜底）**唯一权威源是游戏内 `ai/kb_query.py::_search()`**；
本工具的 `search()` 只是转调它（自动把 game/ 加进 sys.path），故开发侧与运行时所见完全一致，
不存在两份副本漂移。
"""
import argparse
import hashlib
import pathlib
import re
import sqlite3
import sys

KB_DIR = pathlib.Path(__file__).resolve().parent          # _dev_tools/game-docs/kb
DOCS_DIR = KB_DIR.parent / "docs"                          # _dev_tools/game-docs/docs
GAME_ROOT = KB_DIR.parents[2]                              # 项目根（sz）
GAME_DB = GAME_ROOT / "game" / "assets" / "kb" / "game_kb.sqlite"
DEV_DB = KB_DIR / "dev_kb.sqlite"

MAX_CHUNK = 1800  # 单块目标上限（字符）

# (标题, 文件名, doc_kind) —— 按归属库分组
GAME_DOCS = [
    ("游戏机制说明", "游戏机制说明.md", "design"),
    ("货币口径规范（M0/M1/M2）", "货币口径规范_M0M1M2.md", "design"),
    ("财力消耗设计", "财力消耗设计.md", "design"),
    ("宋代官制与三冗设计", "宋代官制与三冗设计.md", "design"),
    ("利益集团与经济金融工程科技整改落地说明", "利益集团与经济金融工程科技整改_落地说明_2026-09-19.md", "design"),
    ("外邦省域产业链设计", "外邦省域产业链设计_2026-09-22.md", "design"),
    # 2026-09-27 补：局势系统实施规范（原误置于 reviews/，已归位 docs/）
    ("局势系统实施规范", "局势系统实施规范.md", "design"),
]
DEV_DOCS = [
    # —— 本地开发优先（2026-09-27 扩源）：把"本地才有"的开发资料收进开发库 ——
    ("开发服务器与回归测试说明", "开发服务器与回归测试说明.md", "ops"),
    # 仓库与各目录导览（部分**不入库**，只在本地存在；正因如此更该进开发库）
    ("宋祚 仓库总览", "README.md", "guide"),
    ("game 本体说明", "game/README.md", "guide"),
    ("core 内核导览", "game/core/README.md", "guide"),
    ("content 数据导览", "game/content/README.md", "guide"),
    ("engine 契约应用导览", "game/engine/README.md", "guide"),
    ("ai 契约与叙事导览", "game/ai/README.md", "guide"),
    ("backend 接口导览", "game/backend/README.md", "guide"),
    ("frontend 前端导览", "game/frontend/README.md", "guide"),
    ("assets 资源导览", "game/assets/README.md", "guide"),
    ("memory 记忆层导览", "game/memory/README.md", "guide"),
    ("telemetry 遥测导览", "game/telemetry/README.md", "guide"),
    ("audio 音频导览", "game/audio/README.md", "guide"),
    ("saves 存档导览", "game/saves/README.md", "guide"),
    ("_dev_tools 工具导览", "_dev_tools/README.md", "guide"),
    ("game-docs 文档树导览", "_dev_tools/game-docs/README.md", "guide"),
    ("reviews 归档导览", "_dev_tools/game-docs/reviews/README.md", "guide"),
    # 现行设计与史料索引（本地开发最常查）
    ("POP 体系改良（合并版）", "_dev_tools/game-docs/analysis/POP改良_合并版_2026-09-27.md", "design"),
    ("改进方案（合并版）", "_dev_tools/game-docs/analysis/改进方案_合并版_2026-09-22.md", "design"),
    ("全审台账索引（2026-09-18）", "_dev_tools/game-docs/archive/全审台账索引_2026-09-18.md", "audit"),
    ("会话交接（失败会话复盘）", "_dev_tools/game-docs/archive/2026-10-21-historical/交接_失败会话_2026-09-26.md", "ops"),
]

SCHEMA = """
CREATE TABLE documents(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  source_path TEXT NOT NULL UNIQUE,
  doc_kind TEXT,
  content TEXT NOT NULL,
  content_hash TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE chunks(
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  heading TEXT,
  content TEXT NOT NULL,
  UNIQUE(document_id, chunk_index)
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(content, tokenize='trigram');
"""


# ---------------------------------------------------------------
# 切块（与云端 gen_sql.py 同一套逻辑）
# ---------------------------------------------------------------
def split_by_heading(text, pattern):
    """按标题行切分，返回 [(heading, body)]；标题行本身不计入 body。"""
    chunks = []
    heading = "(开篇)"
    buf = []
    for line in text.split("\n"):
        if re.match(pattern, line):
            body = "\n".join(buf).strip()
            if body:
                chunks.append((heading, body))
            heading = re.sub(r"^#+\s*", "", line).strip()
            buf = []
        else:
            buf.append(line)
    body = "\n".join(buf).strip()
    if body:
        chunks.append((heading, body))
    return chunks


def hard_split(heading, body):
    """超长块按段落硬切。"""
    out = []
    buf = ""
    idx = 0
    for para in body.split("\n\n"):
        cand = (buf + "\n\n" + para) if buf else para
        if buf and len(cand) > MAX_CHUNK:
            out.append((heading if idx == 0 else f"{heading}（续{idx}）", buf.strip()))
            idx += 1
            buf = para
        else:
            buf = cand
    if buf.strip():
        out.append((heading if idx == 0 else f"{heading}（续{idx}）", buf.strip()))
    return out


def chunk_doc(text):
    """先按 # / ## 切，超长的再按 ### 切，仍超长按段落硬切。"""
    result = []
    for heading, body in split_by_heading(text, r"^#{1,2}\s+"):
        if len(body) <= MAX_CHUNK:
            result.append((heading, body))
            continue
        subs = split_by_heading(body, r"^###\s+")
        real_subs = [s for s in subs if s[0] != "(开篇)"]
        if real_subs:
            for h2, b2 in subs:
                hh = heading if h2 == "(开篇)" else f"{heading} / {h2}"
                if len(b2) <= MAX_CHUNK:
                    result.append((hh, b2))
                else:
                    result.extend(hard_split(hh, b2))
        else:
            result.extend(hard_split(heading, body))
    return result


# ---------------------------------------------------------------
# 构建
# ---------------------------------------------------------------
def resolve_src(fname: str):
    """解析源文件：**先 `game-docs/docs/`，找不到再到仓库根**（支持 `game/README.md` 这类路径）。"""
    p = DOCS_DIR / fname
    if p.exists():
        return p
    return GAME_ROOT / fname


def build_db(db_path, docs):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    total = 0
    for title, fname, kind in docs:
        text = resolve_src(fname).read_text(encoding="utf-8")
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()
        cur = conn.execute(
            "INSERT INTO documents(title, source_path, doc_kind, content, content_hash)"
            " VALUES (?,?,?,?,?)",
            (title, fname, kind, text, digest))
        doc_id = cur.lastrowid
        chunks = chunk_doc(text)
        for idx, (heading, body) in enumerate(chunks):
            # 块内容带《文档名》章节前缀，命中结果自带出处
            prefixed = f"《{title}》{heading}\n\n{body}"
            cur = conn.execute(
                "INSERT INTO chunks(document_id, chunk_index, heading, content)"
                " VALUES (?,?,?,?)",
                (doc_id, idx, heading, prefixed))
            conn.execute("INSERT INTO chunks_fts(rowid, content) VALUES (?,?)",
                         (cur.lastrowid, prefixed))
        total += len(chunks)
        print(f"  {fname}: {len(text)} chars -> {len(chunks)} chunks")
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    return total


# ---------------------------------------------------------------
# 查询（与 game/ai/kb_query.py 保持一致：FTS5 → LIKE AND → LIKE OR）
# ---------------------------------------------------------------
def _runtime_search():
    """取游戏内唯一权威检索实现；game/ 不在 sys.path 时自动补上。"""
    g = str(GAME_ROOT / "game")
    if g not in sys.path:
        sys.path.insert(0, g)
    from ai.kb_query import _search
    return _search


_search_impl = None


def search(conn, query, top_k=3):
    """返回 [(heading, content, score)]；score 仅 FTS5 路径有真实 bm25（越小越相关）。

    算法本体在 `game/ai/kb_query.py::_search()`（FTS5 trigram → LIKE AND → LIKE OR），
    此处仅转调，保证开发侧与游戏内行为一致。
    """
    global _search_impl
    if _search_impl is None:
        _search_impl = _runtime_search()
    return _search_impl(conn, query, top_k)


def cmd_build():
    print(f"game kb -> {GAME_DB}")
    n1 = build_db(GAME_DB, GAME_DOCS)
    print(f"dev kb  -> {DEV_DB}")
    n2 = build_db(DEV_DB, DEV_DOCS)
    print(f"done: game {n1} chunks, dev {n2} chunks")


def cmd_query(text, db, top):
    path = GAME_DB if db == "game" else DEV_DB
    if not path.exists():
        sys.exit(f"kb not built: {path}（先运行 python build_kb.py build）")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = search(conn, text, top)
    conn.close()
    for i, (heading, content, score) in enumerate(rows):
        print(f"--- [{i+1}] score={score:.4f} | {heading}")
        print(content[:300].replace("\n", " ") + ("..." if len(content) > 300 else ""))
    if not rows:
        print("(no hit)")


def main():
    # Windows GBK 控制台打印 emoji（文档内含 ✅ 等）不崩溃
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="重建游戏库与开发库")
    q = sub.add_parser("query", help="查询知识库")
    q.add_argument("text")
    q.add_argument("--db", choices=["game", "dev"], default="game")
    q.add_argument("--top", type=int, default=3)
    args = ap.parse_args()
    if args.cmd == "build":
        cmd_build()
    else:
        cmd_query(args.text, args.db, args.top)


if __name__ == "__main__":
    main()
