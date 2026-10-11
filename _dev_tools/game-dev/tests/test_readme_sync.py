# -*- coding: utf-8 -*-
"""README 同步纪律（开发纪律的可执行化）。

背景：AGENTS.md §6.1 要求「改了模块行为/文件增删就要同步该目录 README」。
这条规矩靠自觉执行，实测**反复漏**（新增模块不进索引、README 里留着过期用例数与失效状态）。
本用例把两条纪律变成**会在全量里红的断言**，让漏改在提交前暴露。

两条断言：

1. **索引完整性**：COVERED 列出的目录里，每个受跟踪的代码/文档文件都必须在该目录 README 里
   出现过（全名或去扩展名的 stem 皆可）。新增文件忘了写进索引 ⇒ 这里炸。
2. **取数口径**：README 里出现「N passed / N tests / N 用例」时，**必须带日期**（YYYY-MM-DD）
   或显式标注为历史快照。裸的用例数会变成第二个真相源。

为什么按目录白名单而不是全仓扫描：archive/ 与资产目录**有意不逐条列**（见其 README），
tests/ 明确声明不维护静态清单；把它们一起纳入只会逼出无意义的豁免噪音。
"""
import os
import re
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "game"))
REPO = os.path.normpath(os.path.join(_GAME_ROOT, ".."))

#: 受纪律覆盖的目录（相对仓库根）。选择标准：该目录 README 本身就是索引。
COVERED = [
    "game/ai",
    "game/application",
    "game/audio",
    "game/backend",
    "game/content",
    "game/content/data_factions",
    "game/content/ministers",
    "game/core/domains/administration",
    "game/core/domains/administration/read_models",
    "game/core/domains/construction",
    "game/core/domains/culture",
    "game/core/domains/diplomacy",
    "game/core/domains/economy",
    "game/core/domains/economy/read_models",
    "game/core/domains/military",
    "game/core/domains/politics",
    "game/core/domains/population",
    "game/core/domains/production",
    "game/core/foundation/common",
    "game/core/foundation/ledger",
    "game/core/foundation/persistence",
    "game/core/workflows",
    "game/engine",
    "game/frontend/src/renderer/api",
    "game/frontend/src/renderer/audio",
    "game/frontend/src/renderer/components",
    "game/frontend/src/renderer/data",
    "game/frontend/src/renderer/hud",
    "game/frontend/src/renderer/map",
    "game/frontend/src/renderer/panels",
    "game/frontend/src/renderer/store",
    "game/frontend/src/renderer/utils",
    "game/memory",
    "game/telemetry",
    "_dev_tools/handover",
    # --- game-docs：这些目录的 README 自己就是索引，必须跟着文件增删同步 ---
    "_dev_tools/game-docs/analysis",
    "_dev_tools/game-docs/docs",
    "_dev_tools/game-docs/reviews",
    "_dev_tools/game-docs/specs/construction",
    "_dev_tools/game-docs/specs/cross-cutting",
    "_dev_tools/game-docs/specs/diplomacy",
    "_dev_tools/game-docs/specs/economy",
    "_dev_tools/game-docs/specs/economy/unified-civilian-market",
    "_dev_tools/game-docs/specs/population",
    "_dev_tools/game-docs/specs/production",
    "_dev_tools/game-docs/specs/transport",
]

#: 不要求进索引的扩展名（资源 / 配置 / 锁 / 样式等，不是"模块"）。
NON_CODE_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg",
    ".mp3", ".wav", ".ogg", ".flac", ".ttf", ".otf", ".woff", ".woff2",
    ".json", ".lock", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".css", ".scss", ".map",
}

#: 逐目录的显式豁免（**必须写理由**，禁止图省事大范围豁免）。
EXEMPT = {
    # 面板目录里两个非面板模块：会话守卫及其自检，不属于面板索引表语义
    "game/frontend/src/renderer/panels": {"sessionGuard.ts", "sessionGuard.selftest.ts"},
}


def _tracked_files():
    """仓库内受跟踪文件（相对路径，/ 分隔）。

    🔴 **必须带 `-c core.quotepath=false`**：git 默认把非 ASCII 路径转义成 `\345\270\202` 这种
    八进制形式，于是**中文文件名与 README 正文永远比对不上** ⇒ 检查会静默假报通过。
    本用例最初就踩了这个坑（`reviews/`、`docs/`、`specs/economy/` 全被漏检）。
    """
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        pytest.skip("git 不可用，跳过 README 同步检查")
    paths = [l for l in out.stdout.splitlines() if l.strip()]
    # 自检：出现八进制转义说明 quotepath 没生效，此时**必须报错**而不是放行
    assert not any("\\3" in p and p.count("\\") >= 2 for p in paths), (
        "git 路径仍被 quotepath 转义（非 ASCII 文件名会漏检）；检查 core.quotepath 设置"
    )
    return paths


@pytest.mark.parametrize("d", COVERED)
def test_directory_readme_indexes_all_code_files(d):
    """目录内每个代码/文档文件都要在 README 里出现（全名或 stem）。"""
    readme = os.path.join(REPO, d.replace("/", os.sep), "README.md")
    assert os.path.isfile(readme), d + "/README.md 不存在（受纪律覆盖的目录必须有 README）"
    with open(readme, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    prefix = d + "/"
    siblings = [p[len(prefix):] for p in _tracked_files()
                if p.startswith(prefix) and "/" not in p[len(prefix):]]
    exempt = EXEMPT.get(d, set())

    missing = []
    for name in sorted(siblings):
        if name == "README.md" or name.startswith("__") or name.startswith("."):
            continue
        if os.path.splitext(name)[1].lower() in NON_CODE_EXTS:
            continue
        if name in exempt:
            continue
        stem = os.path.splitext(name)[0]
        if name in text or stem in text:
            continue
        missing.append(name)

    assert not missing, (
        d + " 有 %d 个文件没写进 README 索引：%s" % (len(missing), missing)
        + "。请补进该目录 README（或按 NON_CODE_EXTS/EXEMPT 规则说明为何不必列）"
    )


#: 裸用例数检测：数字 + passed/tests/用例
_COUNT_RX = re.compile(r"[0-9]{3,5}\s*(?:passed|tests\b|用例)")
_DATE_RX = re.compile(r"20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]")
#: 明确标成历史/禁止语境的，不算裸数
_HISTORY_MARKERS = ("历史", "快照", "当时", "旧值", "过期", "不得", "不要", "禁止", "不复跑")


def test_readmes_do_not_state_undated_test_counts():
    """README 里的用例数必须带日期或标为历史快照，否则会变成第二个真相源。"""
    offenders = []
    for p in _tracked_files():
        if not p.endswith("README.md"):
            continue
        if p.startswith("_dev_tools/game-docs/archive/") or "/archive/" in p:
            continue  # 归档按原样存真，不追改
        path = os.path.join(REPO, p.replace("/", os.sep))
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if not _COUNT_RX.search(ln):
                continue
            if _DATE_RX.search(ln):
                continue
            if any(k in ln for k in _HISTORY_MARKERS):
                continue
            offenders.append(p + ":" + str(i) + ": " + ln.strip()[:90])

    assert not offenders, (
        "README 出现未标日期的用例数（应带 YYYY-MM-DD，或指向 --junitxml 口径）：\n"
        + "\n".join(offenders)
    )


#: Markdown 相对链接
_LINK_RX = re.compile(r"\]\(([^)]+)\)")


def test_readmes_have_no_broken_relative_links():
    """README 的相对链接必须能解析（防「文件改名 / 挪目录后链接烂掉」）。

    实测价值：本轮据此抓出 **7 处坏链**——`specs/` 分子目录后，多个 README 仍指向
    `specs/<规格>/tasks.md` 平铺旧路径（`game-docs/README.md`、`game-docs/docs/README.md`、
    `game/README.md`、`game/core/README.md` 各若干）。
    """
    broken = []
    for p in _tracked_files():
        if not p.endswith("README.md"):
            continue
        if p.startswith("_dev_tools/game-docs/archive/") or "/archive/" in p:
            continue  # 归档按原样存真，不追改
        path = os.path.join(REPO, p.replace("/", os.sep))
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        base = os.path.dirname(path)
        for m in _LINK_RX.finditer(text):
            url = m.group(1).strip().split("#")[0]
            if not url or url.startswith(("http://", "https://", "mailto:")):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, url))):
                broken.append(p + " -> " + url)

    assert not broken, (
        "README 有 %d 处坏链（改名/挪目录后未同步）：\n" % len(broken)
        + "\n".join(broken[:20])
    )

