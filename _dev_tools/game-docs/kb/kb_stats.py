# -*- coding: utf-8 -*-
"""打印本地两个知识库的统计信息（文档数/块数/字符数/哈希）。只读。"""
import hashlib
import pathlib
import sqlite3
import sys

KB_DIR = pathlib.Path(__file__).resolve().parent
GAME_DB = KB_DIR.parents[2] / "game" / "assets" / "kb" / "game_kb.sqlite"
DEV_DB = KB_DIR / "dev_kb.sqlite"


def stat(path):
    print(f"--- {path}")
    if not path.exists():
        print("    MISSING")
        return
    print(f"    size={path.stat().st_size / 1024:.0f} KiB")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    docs, chunks, chars = conn.execute(
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks),"
        " (SELECT COALESCE(sum(length(content)),0) FROM chunks)").fetchone()
    print(f"    documents={docs} chunks={chunks} chunk_chars={chars}")
    for title, sp, h in conn.execute(
            "SELECT title, source_path, content_hash FROM documents ORDER BY source_path"):
        text = conn.execute("SELECT content FROM documents WHERE source_path=?", (sp,)).fetchone()[0]
        flag = "OK " if hashlib.md5(text.encode("utf-8")).hexdigest() == h else "DRIFT"
        print(f"    [{flag}] {sp} ({len(text)} chars) {title}")
    conn.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1:
        stat(pathlib.Path(sys.argv[1]))
    else:
        stat(GAME_DB)
        stat(DEV_DB)
