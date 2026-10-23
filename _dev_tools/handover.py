# -*- coding: utf-8 -*-
"""宋祚 · 本地交接层（2026-10-09 起取代 CloudBase 交接 MCP）

> **云侧迁移标注（2026-10-22）**：被取代的 CloudBase 已随「云侧全面转阿里云」**停用并归档**；
> 云侧现行方案是阿里云 ECS 上的自托管 MCP（见 `game-docs/docs/开发服务器与回归测试说明.md` §8.1）。
> 本模块的定位不变：**交接状态唯一权威仍是本机文件层**，MCP 只作跨设备只读快照。

**为什么换**：交接 MCP 的 `/mcp` 路由在网关侧返回 410（同域其它路径是结构化 404，
带/不带 token 结果一致 ⇒ 不是凭据问题，是函数/触发器 Gone），云端读写通道不可用。
用户裁定：**本项目放弃 MCP，改用本机交接**；载体 = 仓库内 `_dev_tools/handover/`（入库），
云端存量一次性导出并归档入库（原始 JSON 原样保留在 `archive/cloud_2026-10-09/`）。

**目录形态（一条一文件，天然免"读-改-写整份 JSON"的并发覆盖）**：

    _dev_tools/handover/
    ├── INDEX.md              # 由 `summary` 生成，勿手改
    ├── agents.json           # agent 注册表 + 文件归属（共享，改前先读）
    ├── phase/<Agent>.json    # 各 agent **独占**
    ├── tasks/<ID>.json       # 任务板：一条一文件，认领只碰自己那条
    ├── decisions/<ID>.json   # 待裁/已裁：一条一文件（verdict 只由裁定人写）
    ├── worklog/<ts>-<agent>.md   # 追加 = 新建文件，永不重写历史
    ├── context/<snapshotId>.json # 快照
    └── archive/cloud_2026-10-09/   # 云端原始存量（只读留档）

退出码沿用旧 R4 纪律：**0 才代表已落地**（写后回读逐字校验），3=校验不一致，2=用法错。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       # …/sz
HERE = os.path.join(REPO, "_dev_tools", "handover")
MIRROR = os.path.join(REPO, "tmp", "mcp_sync")
ARCHIVE = os.path.join(HERE, "archive", "cloud_2026-10-09")
SUBDIRS = ("phase", "tasks", "decisions", "worklog", "context")


# ── 基础 IO：全部显式 utf-8；写后回读逐字比对 ─────────────────────
def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _case_clash(path):
    """返回与目标**仅大小写不同**的已存在同名文件（Windows/macOS 文件系统不区分大小写）。

    实测踩过：`phase/Qoder.json` 与 `phase/qoder.json`（云端两个键，一个是已退役墓碑）
    在大小写不敏感卷上会互相覆盖 —— 现行状态被历史墓碑吃掉，且不会报任何错。
    """
    d = os.path.dirname(path) or "."
    base = os.path.basename(path)
    if not os.path.isdir(d):
        return None
    for f in os.listdir(d):
        if f != base and f.lower() == base.lower():
            return os.path.join(d, f)
    return None


def write_json(path, obj) -> bool:
    clash = _case_clash(path)
    if clash:
        print("WRITE_FAIL 大小写撞名：%s ←→ %s（本机文件系统不区分大小写）"
              % (os.path.relpath(path, REPO).replace(os.sep, "/"),
                 os.path.relpath(clash, REPO).replace(os.sep, "/")))
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)                      # 原子替换：并发读者不会读到半个文件
    try:
        with open(path, encoding="utf-8") as fh:
            back = fh.read()
    except OSError:
        return False
    if back != text:
        return False
    json.loads(back)                           # 回读还必须是合法 JSON
    return True


def write_text(path, text) -> bool:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read() == text


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slug_ts(iso: str) -> str:
    return re.sub(r"[-:]", "", iso.replace("Z", "")).replace("T", "T") + "Z"


# ── import-cloud：一次性把云端存量搬进来（幂等） ──────────────────
def cmd_import_cloud(_args) -> int:
    for name in ("state.json", "worklog.json", "context.json"):
        if not os.path.isfile(os.path.join(MIRROR, name)):
            print("IMPORT_FAIL 缺镜像文件 %s（先确认 tmp/mcp_sync/ 还在）" % name)
            return 2
    os.makedirs(ARCHIVE, exist_ok=True)
    for d in SUBDIRS:
        os.makedirs(os.path.join(HERE, d), exist_ok=True)

    # ① 原始 JSON 原样留档（逐字节复制，不改写）
    copied = 0
    for name in ("state.json", "worklog.json", "context.json", "SUMMARY.md"):
        src = os.path.join(MIRROR, name)
        if not os.path.isfile(src):
            continue
        with open(src, "rb") as fh:
            blob = fh.read()
        dst = os.path.join(ARCHIVE, name)
        if not (os.path.isfile(dst) and open(dst, "rb").read() == blob):
            with open(dst, "wb") as fh:
                fh.write(blob)
        copied += 1
    print("归档原始文件 %d 份 → %s" % (copied, os.path.relpath(ARCHIVE, REPO).replace(os.sep, "/")))

    st = read_json(os.path.join(MIRROR, "state.json"))["state"]

    # ② agents.json
    if "agents" in st:
        ok = write_json(os.path.join(HERE, "agents.json"), st["agents"])
        print("agents.json 落地=%s" % ok)
        if not ok:
            return 3

    # ③ phase_<X> → phase/X.json（共享键 `phase` 单独留档，不作现行状态）
    for k, v in st.items():
        if k == "phase":
            write_json(os.path.join(HERE, "phase", "_legacy_shared_phase.json"),
                       {"_note": "云端共享键 phase 的历史值（多 agent 互相覆盖，已废弃）", "value": v})
        elif k.startswith("phase_"):
            agent = k[len("phase_"):]
            # 已退役的键（云端大小写重复那种）另存为 `_retired.` 前缀：
            # 既留档，又不与现行 phase 文件抢同一个大小写不敏感的名字。
            retired = isinstance(v, dict) and v.get("retired")
            fname = ("_retired." if retired else "") + agent + ".json"
            if not write_json(os.path.join(HERE, "phase", fname), v):
                return 3
            print("phase/%s 落地%s" % (fname, "（墓碑）" if retired else ""))

    # ④ tasks.board → tasks/<ID>.json
    board = (st.get("tasks") or {}).get("board") or {}
    meta = {k: v for k, v in (st.get("tasks") or {}).items() if k != "board"}
    write_json(os.path.join(HERE, "tasks", "_meta.json"), meta or {"schema": 2})
    for tid, entry in board.items():
        obj = dict(entry)
        obj["id"] = tid
        obj["_source"] = "cloud:tasks.board"
        if not write_json(os.path.join(HERE, "tasks", tid + ".json"), obj):
            return 3
    print("tasks/ 落地 %d 条" % len(board))

    # ⑤ decisions.items → decisions/<ID>.json
    dec = st.get("decisions") or {}
    items = dec.get("items") or {}
    write_json(os.path.join(HERE, "decisions", "_meta.json"),
               {"schema": dec.get("schema"), "note": dec.get("note"),
                "_source": "cloud:decisions"})
    for did, entry in items.items():
        obj = dict(entry) if isinstance(entry, dict) else {"value": entry}
        obj["id"] = did
        obj["_source"] = "cloud:decisions.items"
        if not write_json(os.path.join(HERE, "decisions", did + ".json"), obj):
            return 3
    print("decisions/ 落地 %d 条" % len(items))

    # ⑥ worklog → 一条一个 md（追加式，永不重写）
    entries = read_json(os.path.join(MIRROR, "worklog.json")).get("entries") or []
    n = 0
    for e in entries:
        if not isinstance(e, dict) or "message" not in e:
            continue
        msg = e["message"]
        m = re.match(r"^\s*\d{4}-\d\d-\d\d\s+([A-Za-z0-9_\-]+)", msg)
        agent = m.group(1) if m else "unknown"
        fname = "%s-%s.md" % (slug_ts(e.get("at", now_utc())), agent)
        p = os.path.join(HERE, "worklog", fname)
        if os.path.exists(p):
            continue
        body = "---\nat: %s\nagent: %s\nsource: cloud:worklog\n---\n\n%s\n" % (
            e.get("at", ""), agent, msg)
        if not write_text(p, body):
            return 3
        n += 1
    print("worklog/ 落地 %d 条（跳过已存在）" % n)

    # ⑦ context 快照
    ctx = read_json(os.path.join(MIRROR, "context.json"))
    snaps = ctx.get("snapshots") or ctx.get("list") or []
    if isinstance(ctx, dict) and not snaps and ctx.get("data") is not None:
        snaps = [ctx]
    for s in snaps:
        sid = s.get("id") or s.get("snapshotId") or slug_ts(s.get("savedAt", now_utc()))
        if sid and not os.path.exists(os.path.join(HERE, "context", sid + ".json")):
            write_json(os.path.join(HERE, "context", sid + ".json"), s)
    print("context/ 落地 %d 份" % len(snaps))
    print("IMPORT verdict=ok —— 接着跑 `python _dev_tools/handover.py summary`")
    return 0


# ── log / phase / claim / decide ─────────────────────────────────
def cmd_log(args) -> int:
    msg = args.message
    if not msg:
        print("用法：handover.py log \"<消息>\"")
        return 2
    m = re.match(r"^\s*\d{4}-\d\d-\d\d\s+([A-Za-z0-9_\-]+)", msg)
    agent = m.group(1) if m else (args.agent or "unknown")
    iso = now_utc()
    p = os.path.join(HERE, "worklog", "%s-%s.md" % (slug_ts(iso), agent))
    if os.path.exists(p):                     # 同一秒同名（两 agent 同时写）→ 加后缀，不覆盖
        p = p[:-3] + "-%d.md" % (int(time.time() * 1000) % 100000)
    body = "---\nat: %s\nagent: %s\nsource: local\n---\n\n%s\n" % (iso, agent, msg)
    if not write_text(p, body):
        print("LOG verdict=failed（回读不一致）")
        return 3
    print("LOG verdict=landed file=%s" % os.path.relpath(p, REPO).replace(os.sep, "/"))
    return 0


def _pid_alive(pid) -> bool:
    """尽力判断进程是否仍存活（失败偏向"存活"）。C1（Jev B 0.676）。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except OSError as e:
        if getattr(e, "errno", None) == 3 or getattr(e, "winerror", None) == 87:
            return False
        return True
    except Exception:  # noqa: BLE001
        return True
    return True


#: 侧车新鲜窗口：超过则视为可接管（防崩溃后永久锁死）
OWNER_TTL_SECONDS = 6 * 3600


def _owner_path(agent: str) -> str:
    return os.path.join(HERE, "phase", ".owner", agent + ".json")


def _check_phase_owner(agent: str) -> tuple:
    """(allow, reason)：同机另一会话仍在写该 agent 的 phase 时 allow=False。"""
    path = _owner_path(agent)
    if not os.path.isfile(path):
        return True, ""
    obj = read_json(path)
    if not isinstance(obj, dict):
        return True, ""
    pid = obj.get("pid")
    started = obj.get("startedAt") or ""
    try:
        import calendar
        import time as _t
        ts = calendar.timegm(_t.strptime(started, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:  # noqa: BLE001
        ts = 0
    age = int(__import__("time").time()) - ts
    if pid == os.getpid():
        return True, ""
    if age > OWNER_TTL_SECONDS:
        return True, "owner 侧车已过期（%ss），可接管" % age
    if not _pid_alive(pid):
        return True, "owner 进程 %s 已不存在，可接管" % pid
    return False, ("phase/%s.json 正被同机进程 %s 占用（起始 %s）；"
                   "并发同名会话请换名（如 DSH-lead2），确需接管加 --force"
                   % (agent, pid, started or "?"))


def _mark_phase_owner(agent: str) -> None:
    path = _owner_path(agent)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, {"agent": agent, "pid": os.getpid(), "startedAt": now_utc()})


def cmd_phase(args) -> int:
    src = args.file
    if not src or not os.path.isfile(src):
        print("用法：handover.py phase <Agent> --file <json>（文件须是 object）")
        return 2
    obj = read_json(src)
    if not isinstance(obj, dict):
        print("phase 值必须是 object")
        return 2
    allow, reason = _check_phase_owner(args.agent)
    if not allow and not getattr(args, "force", False):
        print("PHASE verdict=blocked（%s）" % reason)
        return 3
    if reason:
        print("PHASE note=%s" % reason)
    obj.setdefault("agent", args.agent)
    obj["updatedAt"] = obj.get("updatedAt") or now_utc()
    p = os.path.join(HERE, "phase", args.agent + ".json")
    if not write_json(p, obj):
        print("PHASE verdict=failed")
        return 3
    _mark_phase_owner(args.agent)
    print("PHASE verdict=landed key=phase/%s" % args.agent)
    return 0


def cmd_claim(args) -> int:
    if not args.agent:
        print("claim 需要 --agent <名字>（或设 SONGZUO_AGENT）")
        return 2
    p = os.path.join(HERE, "tasks", args.task_id + ".json")
    if not os.path.isfile(p):
        print("板上没有 %s（新建请写 tasks/<ID>.json 再 claim）" % args.task_id)
        return 2
    obj = read_json(p)
    holder = obj.get("claimedBy")
    if args.action == "claim":
        if holder and holder != args.agent:
            print("CLAIM verdict=blocked（%s 已被 %s 认领）" % (args.task_id, holder))
            return 3
        obj["claimedBy"] = args.agent
        obj["status"] = args.status or "in_progress"
        obj["claimedAt"] = now_utc()
    else:
        obj["status"] = args.status or "done"
        if args.commit:
            obj["commit"] = args.commit
    if not write_json(p, obj):
        print("CLAIM verdict=failed")
        return 3
    print("CLAIM verdict=landed task=%s status=%s claimedBy=%s"
          % (args.task_id, obj.get("status"), obj.get("claimedBy") or "-"))
    return 0


def cmd_decide(args) -> int:
    p = os.path.join(HERE, "decisions", args.decision_id + ".json")
    if not os.path.isfile(p):
        print("没有该决策项：%s" % p)
        return 2
    obj = read_json(p)
    obj["status"] = args.status
    if args.verdict:
        if args.ruler:
            obj["verdict"] = args.verdict
            obj["verdictBy"] = args.ruler
            obj["verdictAt"] = now_utc()
        else:
            print("decide 需要 --ruler <裁定人> 才能写 verdict（我不替你下裁定）")
            return 2
    if not write_json(p, obj):
        print("DECIDE verdict=failed")
        return 3
    print("DECIDE verdict=landed %s status=%s" % (args.decision_id, obj["status"]))
    return 0


# ── summary / board / check ─────────────────────────────────────
def _load_dir(sub, suffix=".json"):
    """列子目录里的条目文件（`_` 前缀是元数据，跳过）。

    ⚠️ 这里必须用**字面后缀**而不是正则串：写 `endswith(r"\\.json$")` 会让每个文件都匹配失败，
    于是 board/check/summary 全都"扫到 0 条"却报问题=0 —— 恒真的自检比没有自检更糟（实测踩过）。
    """
    d = os.path.join(HERE, sub)
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.startswith("_") or not f.endswith(suffix):
            continue
        try:
            out.append((f, read_json(os.path.join(d, f))))
        except Exception as e:
            out.append((f, {"_read_error": type(e).__name__ + ": " + str(e)[:80]}))
    return out


def cmd_board(_args) -> int:
    for f, v in _load_dir("tasks"):
        if f.startswith("_"):
            continue
        print("%-34s %-16s claimedBy=%-8s %s" % (f[:-5], v.get("status"), v.get("claimedBy") or "-",
                                                 str(v.get("title"))[:60]))
    return 0


def cmd_check(_args) -> int:
    bad = []
    for f, v in _load_dir("tasks"):
        if f.endswith(".json") and not f.startswith("_"):
            if v.get("id") != f[:-5]:
                bad.append("tasks/%s 的 id 字段与文件名不一致" % f)
            if v.get("status") in ("in_progress",) and not v.get("claimedBy"):
                bad.append("tasks/%s in_progress 但无 claimedBy" % f)
    for f, v in _load_dir("decisions"):
        if not f.startswith("_") and v.get("id") != f[:-5]:
            bad.append("decisions/%s 的 id 字段与文件名不一致" % f)
    n_log = len([f for f in os.listdir(os.path.join(HERE, "worklog")) if f.endswith(".md")])
    n_tasks = len([1 for f, _ in _load_dir("tasks") if not f.startswith("_")])
    n_dec = len([1 for f, _ in _load_dir("decisions") if not f.startswith("_")])
    # 🔴 下限断言：扫到 0 条不是"没问题"，而是"扫描本身失效"（本工具刚踩过这个假绿）。
    if n_tasks == 0 or n_dec == 0 or n_log == 0:
        bad.append("计数出现 0（tasks=%d decisions=%d worklog=%d）——判据扫描失效，不是干净"
                   % (n_tasks, n_dec, n_log))
    print("check: tasks=%d decisions=%d worklog=%d 问题=%d" % (n_tasks, n_dec, n_log, len(bad)))
    for b in bad:
        print("  !", b)
    return 0 if not bad else 3


def cmd_summary(_args) -> int:
    tasks = [(f, v) for f, v in _load_dir("tasks") if not f.startswith("_")]
    decs = [(f, v) for f, v in _load_dir("decisions") if not f.startswith("_")]
    logs = sorted([f for f in os.listdir(os.path.join(HERE, "worklog")) if f.endswith(".md")])
    phases = [(f, v) for f, v in _load_dir("phase") if not f.startswith("_")]

    open_tasks = [(f, v) for f, v in tasks if v.get("status") not in ("done", "completed", "wont-fix")]
    open_dec = [(f, v) for f, v in decs if str(v.get("status", "")).lower() in
                ("open", "待裁定", "needs-impact-report", "design-done", "recommended-no")]
    lines = ["# 交接索引 · 宋祚（本机交接层）", "",
             "> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；",
             "> 生成时间：%s · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)" % now_utc(),
             "", "## 各 agent 当前阶段", ""]
    for f, v in phases:
        lines.append("- **%s**（updatedAt=%s）：%s" % (
            f[:-5], v.get("updatedAt", "-"), str(v.get("phase"))[:160]))
    lines += ["", "## 任务板（未完成）", ""]
    for f, v in open_tasks:
        lines.append("- `%s` %s ｜status=**%s**｜claimedBy=%s" % (
            f[:-5], str(v.get("title"))[:70], v.get("status"), v.get("claimedBy") or "（未认领）"))
    if not open_tasks:
        lines.append("- （无）")
    lines += ["", "## 待裁 / 未闭环决策", ""]
    for f, v in open_dec:
        lines.append("- `%s` [%s] %s" % (f[:-5], v.get("status"), str(v.get("title"))[:70]))
    if not open_dec:
        lines.append("- （无）")
    lines += ["", "## 最近 8 条工作日志", ""]
    for f in logs[-8:]:
        head = f[:-3]
        lines.append("- `%s` → [`worklog/%s`](worklog/%s)" % (head, f, f))
    lines += ["", "## 计数", "",
              "- tasks %d（未完成 %d）· decisions %d（未闭环 %d）· worklog %d · phase 文件 %d"
              % (len(tasks), len(open_tasks), len(decs), len(open_dec), len(logs), len(phases)),
              "- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）", ""]
    p = os.path.join(HERE, "INDEX.md")
    text = "\n".join(lines)
    if not write_text(p, text):
        print("SUMMARY verdict=failed")
        return 3
    print("SUMMARY verdict=landed INDEX.md（tasks %d / decisions %d / worklog %d）"
          % (len(tasks), len(decs), len(logs)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="宋祚本机交接层")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import-cloud", help="一次性把 tmp/mcp_sync 的云端存量搬进来（幂等）")
    p = sub.add_parser("log", help="追加一条工作日志（新文件，不重写历史）")
    p.add_argument("message", nargs="?")
    p.add_argument("--agent")
    p = sub.add_parser("phase", help="写自己独占的 phase 文件")
    p.add_argument("agent")
    p.add_argument("--file", required=True)
    p.add_argument("--force", action="store_true",
                   help="强制接管同机被占用的同名 phase（默认拒绝，见 C1）")
    p = sub.add_parser("claim", help="认领任务")
    p.add_argument("action", choices=["claim", "finish"])
    p.add_argument("task_id")
    p.add_argument("--agent")
    p.add_argument("--status")
    p.add_argument("--commit")
    p = sub.add_parser("decide", help="更新决策项状态（写 verdict 需 --ruler）")
    p.add_argument("decision_id")
    p.add_argument("--status", required=True)
    p.add_argument("--verdict")
    p.add_argument("--ruler")
    sub.add_parser("board", help="列任务板")
    sub.add_parser("check", help="完整性自检（id 与文件名一致等）")
    sub.add_parser("summary", help="重建 INDEX.md")
    args = ap.parse_args(argv)
    if getattr(args, "cmd", None) in ("claim", "phase", "log") and getattr(args, "agent", None) is None:
        args.agent = os.environ.get("SONGZUO_AGENT", "")
        if args.cmd == "phase" and not args.agent:
            print("phase 需要 agent 名（或设 SONGZUO_AGENT）")
            return 2
    return {"import-cloud": cmd_import_cloud, "log": cmd_log, "phase": cmd_phase,
            "claim": cmd_claim, "decide": cmd_decide, "board": cmd_board,
            "check": cmd_check, "summary": cmd_summary}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
