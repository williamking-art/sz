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

退出码（R4 起，**0 才代表已落地**）：
    0  landed / match / 拉取写盘成功
    2  unconfirmed：服务端称已写但 60s 内回读未见（疑 CDN 陈旧窗）——**不要重发**，稍后 summary 复查
    3  lost / failed / mismatch
    4  MCP_FAIL：传输或协议层失败（含函数 20s 超时的 HTTP 433 + ret_code 200401）

`push-state` 的 JSON 形如
`{"phase": "...", "updatedAt": "...", "agent": "...", "verification": {...},
  "openDecisions": [...], "blocked": [...]}`
（整体作为 `key=phase` 的值存下——与 AGENTS.md §6 的约定一致）
`push-context` 的 JSON 形如 `{"summary": "...", "data": {...}}`

凭据：URL 见下方 DEFAULT_URL（非机密）；token **只从环境变量** `CLOUDBASE_MCP_TOKEN`
读取，绝不写进仓库。缺 token 时给出明确报错而不是静默失败。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime

DEFAULT_URL = "https://william-1-d5grtya3z0b5e143d-1440445995.ap-singapore.app.tcloudbase.com/mcp"
DEFAULT_PROJECT = "songzuo"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/sz
OUT_DIR = os.path.join(REPO, "tmp", "mcp_sync")
WORKLOG_LIMIT = 20

# 回读节奏：CDN 陈旧窗实测可达分钟级，所以"读不到"绝不能直接判成"没写进去"。
LOG_READ_TRIES = 12
LOG_READ_GAP = 5.0


class McpError(RuntimeError):
    """服务端明确给出的失败（JSON-RPC error / isError）。"""


class McpTransportError(McpError):
    """HTTP 或解析层失败：**业务结果未知**，既不能当成功，也不能当"云端为空"。

    2026-10-07 实测教训：函数 20s 超时时平台回 HTTP 433 + `{"ret_code":200401,...}`
    （不是 JSON-RPC 信封），旧客户端把它解析成 None/`{}`，`or "ok"` 于是把失败报成成功，
    并让 pull 误判"云端工作日志为空"。真丢的 2 条日志就是这样被掩盖的。
    """


def _describe_body(r: str) -> str:
    """把平台层错误体翻成人话；SCF 超时的 ret_msg 是 base64。"""
    s = (r or "").strip()[:300]
    try:
        j = json.loads(s)
    except Exception:
        return s
    if isinstance(j, dict) and j.get("ret_code"):
        msg = j.get("ret_msg") or ""
        try:
            msg = base64.b64decode(msg).decode("utf-8", "replace")
        except Exception:
            pass
        return "ret_code=%s ret_msg=%s duration=%sms" % (
            j["ret_code"], msg, j.get("duration_in_ms"))
    return s


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
        try:
            r = requests.post(url, headers=headers,
                              data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                              timeout=(10, 50))
        except requests.RequestException as e:
            raise McpTransportError("请求未送达：%s" % e)
        if r.headers.get("mcp-session-id"):
            state["sid"] = r.headers["mcp-session-id"]

        if rid is None:                      # 通知：无响应体是合法的
            if r.status_code in (200, 202, 204):
                return None
            raise McpTransportError("通知 %s 返回 HTTP %s：%s" % (method, r.status_code, _describe_body(r.text)))

        if r.status_code != 200 or not (r.text or "").strip():
            raise McpTransportError("HTTP %s，无有效响应：%s" % (r.status_code, _describe_body(r.text)))

        if "text/event-stream" in r.headers.get("content-type", ""):
            m = None
            for line in r.text.splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(ev, dict) and (ev.get("result") is not None or ev.get("error") is not None):
                    if m is None or ev.get("id") == rid:
                        m = ev          # 优先取本请求 id；否则留住第一个有效事件
            if m is None:
                raise McpTransportError("SSE 无有效 JSON-RPC 事件：%s" % _describe_body(r.text))
            return m

        try:
            m = r.json()
        except ValueError:
            raise McpTransportError("响应非 JSON：%s" % _describe_body(r.text))
        if not isinstance(m, dict) or (m.get("result") is None and m.get("error") is None):
            raise McpTransportError("响应不是 JSON-RPC 信封：%s" % _describe_body(r.text))
        return m

    def call(name, args):
        m = rpc("tools/call", {"name": name, "arguments": args}, 3)
        if m.get("error") is not None:
            e = m["error"]
            raise McpError("%s：JSON-RPC error %s %s" % (name, e.get("code"), e.get("message")))
        res = m.get("result") or {}
        if res.get("isError"):
            raise McpError("%s 调用失败：%s" % (name, res.get("content")))
        parts = res.get("content") or []
        txt = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        if not txt.strip():
            raise McpTransportError("%s 返回空 content，结果未知" % name)
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


def _latest_entries(call, project: str, limit: int = 60) -> list:
    """回读；单次回读本身可能撞超时/陈旧副本，吞掉当"本轮没看到"，由上层轮询决定。"""
    try:
        r = call("log_read", {"project": project, "limit": limit}) or {}
        return r.get("entries") or []
    except McpError:
        return []


def _await_message(call, project: str, message: str, tries: int = LOG_READ_TRIES,
                   gap: float = LOG_READ_GAP):
    """轮询到目标消息可见为止。返回 (landed, 该消息出现的次数)。"""
    seen_count = 0
    for _ in range(tries):
        time.sleep(gap)
        c = sum(1 for e in _latest_entries(call, project) if e.get("message") == message)
        seen_count = max(seen_count, c)
        if c:
            return True, seen_count
    return False, seen_count


def append_log(call, project: str, message: str) -> dict:
    """R4：追加 + 强制回读。两个不许：不许把"无响应"报成成功，不许在状态未知时盲目重发。

    verdict：
      landed        回读已见 —— 唯一可当成功的形态（exit 0）
      unconfirmed   服务端称 verified:true 但我方 60s 内回读未见（疑陈旧窗）→ **不重发**，exit 2
      failed        写入本身明确失败（exit 3）
      lost          写完回读未见且服务端未确认（exit 3）—— 重发前先人工复查
    """
    resp = None
    err = None
    attempts = 0

    def once():
        nonlocal resp, err, attempts
        attempts += 1
        resp, err = None, None
        try:
            resp = call("log_append", {"project": project, "message": message})
        except McpTransportError as e:
            # 结果未知（如平台 433 超时）：写入可能已落地，必须靠回读判定，不能当失败
            err = e
        except McpError as e:
            err = e

    once()
    landed, dups = _await_message(call, project, message)
    if not landed and isinstance(err, McpTransportError):
        once()                       # 状态未知才补发一次；重复条目比丢条目良性
        landed, dups = _await_message(call, project, message)

    confirmed = isinstance(resp, dict) and resp.get("verified") is True
    if landed:
        verdict, code = "landed", 0
    elif confirmed:
        verdict, code = "unconfirmed", 2
    elif err is not None:
        verdict, code = "failed", 3
    else:
        verdict, code = "lost", 3
    return {"verdict": verdict, "confirmed": confirmed, "dups": dups,
            "attempts": attempts, "error": str(err) if err else None, "exit_code": code}


def set_state(call, project: str, key: str, value, platform: str) -> dict:
    """state_set 后回读比对（整键写同样是 RMW，写成功不等于写对了）。"""
    call("state_set", {"project": project, "key": key, "value": value, "platform": platform})
    stored = None
    verdict = "mismatch"
    for i in range(4):
        if i:
            time.sleep(5)
        try:
            got = call("state_get", {"project": project, "key": key}) or {}
        except McpError:
            continue
        stored = got.get("value", got)
        if stored == value:
            verdict = "match"
            break
    return {"verdict": verdict, "stored": stored,
            "exit_code": 0 if verdict == "match" else 3}


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

    # --- 防毁兜底（2026-10-03 加，2026-10-07 R4 改口径）-------------------------------
    # 旧版失败形态：上游超时/433 时 call() 返回 None，`or {}` 把失败伪装成「云端为空」，
    # 而紧接着的 _write 无条件写盘 —— 结果就是**把本地镜像清空**（实测事故：worklog.json
    # 32.8KB→2B、SUMMARY.md 37.9KB→6KB）。R4 起传输/解析层失败一律抛 McpTransportError，
    # 所以这两道守卫现在只在「确认云端为空」时触发；仍保留，因为云端为空同样不该毁镜像。
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
    return {"project": project, "keys": keys, "state": state, "context": context, "worklog": worklog}


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
    try:
        return _dispatch(cmd, project, argv)
    except McpError as e:
        # 失败必须显眼：非 0 退出 + 明说这是"结果未知/失败"，不再打印 ok
        print("MCP_FAIL %s" % e, file=sys.stderr)
        return 4


def _dispatch(cmd: str, project: str, argv) -> int:
    if cmd == "log":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py log \"消息\"")
        call = _client()
        r = append_log(call, project, argv[2])
        print("LOG_APPEND verdict=%s confirmed=%s dups=%d attempts=%s%s" % (
            r["verdict"], r["confirmed"], r["dups"], r["attempts"],
            (" err=" + r["error"]) if r["error"] else ""))
        if r["verdict"] in ("unconfirmed", "lost"):
            print("  别重发（整文件 RMW + CDN 陈旧窗会造重复/覆盖）；"
                  "稍后用 sync_mcp_state.py summary 复查", file=sys.stderr)
        return r["exit_code"]
    if cmd == "push-state":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py push-state 文件.json")
        with open(argv[2], encoding="utf-8") as f:
            value = json.load(f)
        call = _client()
        r = set_state(call, project, "phase", value, "dsh")
        print("PUSH_STATE verdict=%s" % r["verdict"])
        if r["verdict"] != "match":
            print("  回读值与提交值不一致（疑并发覆盖或陈旧副本）。"
                  "不要盲目重写——先 summary 复查，确认不是别人的键被顶掉", file=sys.stderr)
            print("  stored=%s" % str(r["stored"])[:300], file=sys.stderr)
        return r["exit_code"]
    if cmd == "push-context":
        if len(argv) < 3:
            sys.exit("用法：sync_mcp_state.py push-context 文件.json（需含 summary，可选 data）")
        with open(argv[2], encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict) or not payload.get("summary"):
            sys.exit("该 JSON 必须含非空 summary 字段")
        call = _client()
        print(call("context_save", {"project": project, "summary": payload["summary"],
                                    "data": payload.get("data") or {}}))
        got = call("context_load", {"project": project}) or {}
        same = got.get("summary") == payload["summary"]
        print("PUSH_CONTEXT verdict=%s id=%s" % ("match" if same else "mismatch", got.get("id", "-")))
        return 0 if same else 3
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
