# -*- coding: utf-8 -*-
"""打印本地两个知识库的统计信息（文档数/块数/字符数/**与磁盘源的一致性**）。只读。

⚠️ 2026-09-27 修正：原来的 `OK/DRIFT` 比较的是「**库内** content 与**库内** content_hash」——
那是**库自洽性**检查，**恒为 OK**，测不出"源文档已更新而库未重建"（实测踩坑：7 篇里 5 篇已脱节
却全报 OK）。现改为与**磁盘上的源文件**比对：库里的 `content_hash`（建库时算）vs 磁盘当前内容哈希。
`STALE` = **需要重建**（跑 `python build_kb.py build`）。
"""
import hashlib
import pathlib
import sqlite3
import sys

KB_DIR = pathlib.Path(__file__).resolve().parent
DOCS_DIR = KB_DIR.parent / "docs"                     # 与 build_kb.py 的 DOCS_DIR 一致
REPO_ROOT = KB_DIR.parents[2]                         # 仓库根（sz/）
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
    stale = 0
    for title, sp, h in conn.execute(
            "SELECT title, source_path, content_hash FROM documents ORDER BY source_path"):
        disk = DOCS_DIR / sp
        if not disk.exists():
            disk = REPO_ROOT / sp                     # 支持 `game/README.md` 这类仓库根相对路径
        if not disk.exists():
            flag, n = "MISS ", 0
        else:
            now = disk.read_text(encoding="utf-8")
            n = len(now)
            if hashlib.md5(now.encode("utf-8")).hexdigest() == h:
                flag = "OK   "
            else:
                flag = "STALE"
                stale += 1
        print(f"    [{flag}] {sp} (磁盘 {n} chars) {title}")
    if stale:
        print(f"    ⚠️ {stale} 篇已脱节 → 跑 `python build_kb.py build` 重建")
    conn.close()
    return stale


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1:
        sys.exit(1 if stat(pathlib.Path(sys.argv[1])) else 0)
    # 退出码可用作**本地门禁**：非 0 = 有 STALE（改了文档但没重建知识库）
    bad = stat(GAME_DB) + stat(DEV_DB)
    if bad:
        print(f"\n❌ {bad} 篇脱节：跑 `python build_kb.py build` 重建后再提交")
    sys.exit(1 if bad else 0)
