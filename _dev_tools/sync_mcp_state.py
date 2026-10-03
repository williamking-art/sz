# -*- coding: utf-8 -*-
"""把 CloudBase 交接状态（state / context / worklog）拉到本地镜像，供**没有 MCP 的 agent/离线场景**读取。

为什么需要它：交接状态在云端 MCP（`cloudbase-state-mcp`）里，但并非每个 agent
都能配 MCP。本脚本把 `project=<name>` 的
`state` / 最近 `context` 快照 / `worklog` 落成普通文件，
任何 agent 用 read 工具即可接手 —— 与 edifier 项目既有的
`<workspace>/tmp/mcp_sync/{state,context,worklog}.json` 做法一致。

用法（在 sz/ 任意位置）：
    $py _dev_tools/sync_mcp_state.py                      # 拉取并写镜像（默认）
    $py _dev_tools/sync_mcp_state.py summary              # 只打印摘要
    $py _dev_tools/sync_mcp_state.py log "消息"            # 往云端 worklog 追加一条
    $py _dev_tools/sync_mcp_state.py push-state  文件.json  # 回写 state[key=phase]
    $py _dev_tools/sync_mcp_state.py push-context 文件.json # 回写 context 快照

`push-state` 的 JSON 形如
`{"phase": "...", "updatedAt": "...", "agent": "...", "verification": {...},
  "openDecisions": [...], "blocked": [...]}`
（整体作为 `key=phase` 的值存下——与 AGENTS.md §6 的约定一致）
`push-context` 的 JSON 形如 `{"summary": "...", "data": {...}}`

凭据：URL 见下方 DEFAULT_URL（非机密）；token **只从环境变量** `CLOUDBASE_MCP_TOKEN`
读取，绝不写进仓库。缺 token 时给出明确报错而不是静默失败。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

DEFAULT_URL = "https://william-1-d5grtya3z0b5e143d-1440445995.ap-singapore.app.tcloudbase.com/mcp"
DEFAULT_PROJECT = "songzuo"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/sz
OUT_DIR = os.path.join(REPO, "tmp", "mcp_sync")
WORKLOG_LIMIT = 20


def _client():
    try:
        import requests
    except ImportError:                      # pragma: no cover - 环境缺依赖时的明确提示
        sys.exit("缺依赖 requests：请用 D:\\codebuddy\\.audit-venv\\Scripts\\python.exe 运行本脚本")
    url = os.environ.get("CLOUDBASE_MCP_URL", DEFAULT_URL)
    token = os.environ.get("CLOUDBASE_MCP_TOKEN", "").strip()
    if not token:
        sys.exit("未找到环境变量 CLOUDBASE_MCP_TOKEN（token 不入库，必须由环境提供）\n"
                 "设置示例： [Environment]::SetEnvironmentVariable('CLOUDBASE_MCP_TOKEN','<token>','User')")

    state = {"sid": None}

    def rpc(method, params, rid=None):
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        if rid is not None:
            body["id"] = rid
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "Authorization": "Bearer " + token}
        if state["sid"]:
            headers["Mcp-Session-Id"] = state["sid"]
        r = requests.post(url, headers=headers,
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=45)
        if r.headers.get("mcp-session-id"):
            state["sid"] = r.headers["mcp-session-id"]
        if r.status_code == 202 or not r.text.strip():
            return None
        if "text/event-stream" in r.headers.get("content-type", ""):
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    try:
                        return json.loads(line[5:].strip())
                    except ValueError:
                        pass
            return None
        return r.json()

    def call(name, args):
        m = rpc("tools/call", {"name": name, "arguments": args}, 3)
        if m is None:
            return None
        res = m.get("result") or {}
        if res.get("isError"):
            raise RuntimeError(f"{name} 调用失败：{res}")
        parts = res.get("content") or []
        txt = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        try:
            return json.loads(txt)
        except ValueError:
            return txt

    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "songzuo-sync", "version": "1.0"}}, 1)
    rpc("notifications/initialized", {})
    return call


def _write(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _existing_entries(path: str) -> int:
    """已有镜像里的日志条数；用于「不要用空覆盖非空」的判断。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return len((json.load(f) or {}).get("entries") or [])
    except Exception:
        return 0


def pull(project: str) -> dict:
    call = _client()
    projects = call("project_list", {}) or []
    if project not in [p.get("name") for p in projects]:
        print(f"[warn] 云端没有 project={project}；现有：{[p.get('name') for p in projects]}")
    keys = (call("state_get", {"project": project}) or {}).get("keys", [])
    state = {}
    for k in keys:
        got = call("state_get", {"project": project, "key": k}) or {}
        state[k] = got.get("value", got)
    context = call("context_load", {"project": project}) or {}
    worklog = call("log_read", {"project": project, "limit": WORKLOG_LIMIT}) or {}

    # --- 防毁兜底（2026-10-03 加）----------------------------------------------------
    # 上游超时会话失效时 call() 返回 None，上面的 `or {}` 会把失败伪装成「云端为空」，
    # 而紧接着的 _write 是无条件写盘 —— 结果就是**把本地镜像清空**。
    # 镜像是没有 MCP 的 agent 唯一入口（见 AGENTS.md §1），清空等于让交接断链，故此处宁可不写。
    # 实测事故：云端连续 20s 超时后 worklog.json 被写成 {}（32.8KB→2B）、
    # SUMMARY.md 从 37.9KB 掉到 6KB。
    if not keys and not state and not context and not worklog.get("entries"):
        raise RuntimeError(
            "云端返回全空（疑似超时或 MCP 会话失效），已放弃写盘以免清空本地镜像。"
            "请检查网络与 CLOUDBASE_MCP_TOKEN 后重跑；"
            "若确认云端确实为空，请先手工删除 tmp/mcp_sync 再拉。")
    wl_path = os.path.join(OUT_DIR, "worklog.json")
    if not worklog.get("entries") and _existing_entries(wl_path) > 0:
        raise RuntimeError(
            f"云端工作日志为空，但本地镜像已有 {_existing_entries(wl_path)} 条；"
            "已放弃写盘以免清空。请检查网络与令牌后重跑。")

    _write(os.path.join(OUT_DIR, "state.json"), {"project": project, "fetchedAt": _now(),
                                                 "keys": keys, "state": state})
    _write(os.path.join(OUT_DIR, "context.json"), context)
    _write(os.path.join(OUT_DIR, "worklog.json"), worklog)
    _write_summary(project, state, context, worklog)
    return {"project": project, "keys": keys, "context": context, "worklog": worklog}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_summary(project, state, context, worklog) -> None:
    phase = state.get("phase")
    lines = [f"# 交接镜像 · {project}", "",
             f"> 自动生成，请勿手改；更新：`python _dev_tools/sync_mcp_state.py`",
             f"> 拉取时间：{_now()}", ""]
    if isinstance(phase, dict):
        lines += [f"## 当前阶段", "", f"- {phase.get('phase', '')}", ""]
        ver = phase.get("verification") or {}
        if ver:
            lines += ["## 最近验证", ""] + [f"- {k}: {v}" for k, v in ver.items()] + [""]
        todo = phase.get("openDecisions") or []
        if todo:
            lines += ["## 待裁决 / 待办", ""] + [f"- {t}" for t in todo] + [""]
        blk = phase.get("blocked") or []
        if blk:
            lines += ["## 阻塞", ""] + [f"- {b}" for b in blk] + [""]
    elif phase:
        lines += ["## 当前阶段", "", f"- {phase}", ""]
    if context:
        lines += ["## 最近上下文快照", "",
                  f"- id: `{context.get('id', '')}`  保存于 {context.get('savedAt', '')}",
                  f"- 摘要：{context.get('summary', '')}", ""]
        data = context.get("data") or {}
        if data:
            lines += ["```json", json.dumps(data, ensure_ascii=False, indent=2)[:4000], "```", ""]
    entries = (worklog or {}).get("entries") or []
    if entries:
        lines += ["## 工作日志（最近 %d 条）" % len(entries), ""]
        lines += [f"- `{e.get('at', '')}` {e.get('message', '')}" for e in entries] + [""]
    with open(os.path.join(OUT_DIR, "SUMMARY.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "pull"
    project = os.environ.get("CLOUDBASE_MCP_PROJECT", DEFAULT_PROJECT)
    if cmd == "log":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py log \"消息\"")
        call = _client()
        print(call("log_append", {"project": project, "message": argv[2]}) or "ok")
        return 0
    if cmd == "push-state":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py push-state 文件.json")
        with open(argv[2], encoding="utf-8") as f:
            value = json.load(f)
        call = _client()
        print(call("state_set", {"project": project, "key": "phase",
                                 "value": value, "platform": "dsh"}) or "ok")
        return 0
    if cmd == "push-context":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py push-context 文件.json（需含 summary，可选 data）")
        with open(argv[2], encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict) or not payload.get("summary"):
            sys.exit("该 JSON 必须含非空 summary 字段")
        call = _client()
        print(call("context_save", {"project": project, "summary": payload["summary"],
                                    "data": payload.get("data") or {}}) or "ok")
        return 0
    if cmd == "summary":
        r = pull(project)
        phase = r["state"].get("phase")
        if isinstance(phase, dict):
            for k, v in phase.items():
                print(f"{k}: {v}")
        else:
            print("phase:", phase)
        return 0
    r = pull(project)
    print(f"ok project={r['project']} keys={r['keys']} -> {OUT_DIR}")
    print("  context snapshot:", (r["context"] or {}).get("id", "-"))
    print("  worklog entries:", len(((r["worklog"] or {}).get("entries") or [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
