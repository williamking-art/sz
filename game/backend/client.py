# -*- coding: utf-8 -*-
"""宋祚 · 前端后端客户端抽象层

前后端分离的核心抽象：前端（tkinter）只通过这个 BackendClient 与游戏逻辑交互，
不直接 import / 调用 core.commands。这样：
  - LocalBackend  ：逻辑在本进程内执行（开发 / 单机离线，等同改造前行为）
  - HttpBackend   ：逻辑在远程 Rust 后端（songzuo_server）执行，前端只收发 JSON 快照
两者对前端暴露完全相同的接口，切换只需改一个环境变量（SONGZUO_BACKEND）。

上线时玩家运行前端，后端部署到服务器；前端设 SONGZUO_BACKEND=http://服务器:8080 即可。
"""

import os
import json
import urllib.request
import urllib.error

from core import commands as cmd
from core.game_state import GameState
from ai.client import AIClient


class BackendClient:
    """后端客户端接口（模板方法）。子类实现 new_game / advance / action / resolve_event。"""

    def new_game(self, difficulty, ai_client):
        raise NotImplementedError

    def advance(self, state, ai_client):
        raise NotImplementedError

    def action(self, state, action, params, ai_client=None):
        raise NotImplementedError

    def resolve_event(self, state, event_title, choice_idx, ai_client=None):
        raise NotImplementedError

    def save(self, state, slot=1):
        raise NotImplementedError

    def load(self, slot=1):
        raise NotImplementedError

    def save_slots(self):
        raise NotImplementedError

    def conclude(self, state, ai_client=None):
        raise NotImplementedError

    @staticmethod
    def create() -> "BackendClient":
        """按环境变量 SONGZUO_BACKEND 选择实现；缺省走本地。"""
        url = os.environ.get("SONGZUO_BACKEND", "").strip()
        if url:
            return HttpBackend(url.rstrip("/"))
        return LocalBackend()


class LocalBackend(BackendClient):
    """本地后端：直接调用 core.commands（与改造前行为一致）。"""

    def new_game(self, difficulty, ai_client):
        return cmd.new_game(difficulty, ai_client)

    def advance(self, state, ai_client):
        events = cmd.advance_month(state)
        log, report = cmd.settle_turn(state, ai_client)
        # 与 HttpBackend 保持统一四元组签名 (events, log, report, new_state)
        return events, log, report, state

    def action(self, state, action, params, ai_client=None):
        # 统一返回 (message, state)；本地模式下 state 即原对象（可能被动作修改）
        # 分派表：action 名 → handler(state, params, ai_client) -> (message, state)
        # 仅在此处做分派表化（Local 多路直调），HttpBackend 走单一端点转发，语义不同不得复用。
        handlers = {
            "issue_decree":
                lambda s, p, ai: (cmd.issue_decree(s, p, direct=p.get("is_direct", False)), s),
            "issue_secret_decree":
                lambda s, p, ai: (cmd.issue_secret_decree(s, p.get("target", ""), p.get("content", "")), s),
            "issue_edict_from_review":
                lambda s, p, ai: (cmd.issue_edict_from_review(s, p.get("draft_id", ""), p.get("decision", "approve")), s),
            "reject_edict_draft":
                lambda s, p, ai: (cmd.reject_edict_draft(s, p.get("draft_id", "")), s),
            "issue_free_decree":
                lambda s, p, ai: (cmd.issue_free_decree(s, p.get("parse_result", {}), p.get("minister", ""),
                                                        is_secret=p.get("is_secret", False)), s),
            "merge_drafts":
                lambda s, p, ai: (cmd.merge_drafts(s, p.get("draft_ids", [])), s),
            "do_personal_action":
                lambda s, p, ai: (cmd.do_personal_action(s, p.get("name", "")), s),
            "audience_dialogue":
                lambda s, p, ai: (cmd.audience_dialogue(s, p.get("minister", ""), p.get("text", ""), ai), s),
            "start_tech_research":
                lambda s, p, ai: self._research_action(s, p),
            "approve_invention":
                lambda s, p, ai: self._invention_action(s, p, "approve"),
            "reject_invention":
                lambda s, p, ai: self._invention_action(s, p, "reject"),
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"未知动作: {action}")
        return handler(state, params, ai_client)

    @staticmethod
    def _research_action(state, params):
        """start_tech_research 分派（int/bool/局部 import 封装，保持与改造前一致）。"""
        from core.asset_context import start_research
        msg = start_research(state, params.get("node_id", ""),
                             int(params.get("silver", 0) or 0),
                             fund=params.get("fund", "treasury"),
                             source=params.get("source", "panel"),
                             signoff=bool(params.get("signoff", False)))
        return msg, state

    @staticmethod
    def _invention_action(state, params, mode):
        """approve/reject_invention 分派（局部 import 封装，避免模块顶层循环 import）。"""
        from core.asset_context import approve_invention, reject_invention
        if mode == "approve":
            msg = approve_invention(state, params.get("index", 0),
                                    fund=params.get("fund", "treasury"),
                                    signoff=bool(params.get("signoff", False)))
        else:
            msg = reject_invention(state, params.get("index", 0))
        return msg, state

    def resolve_event(self, state, event_title, choice_idx, ai_client=None):
        return cmd.resolve_event(state, event_title, choice_idx, ai_client), state

    def save(self, state, slot=1):
        return cmd.save(state, slot)

    def load(self, slot=1):
        return cmd.load(slot)

    def save_slots(self):
        return cmd.save_slots()

    def conclude(self, state, ai_client=None):
        return cmd.conclude(state, ai_client)


class HttpBackend(BackendClient):
    """远程后端（Rust 服务 songzuo_server）：前端只收发 JSON 快照。

    后端持有 GameState，前端本地持有一个 GameState 副本用于渲染。
    每次动作后后端返回完整状态 JSON，前端用 GameState 重建副本。
    """

    def __init__(self, base_url):
        self.base = base_url

    def _post(self, path, payload=None):
        body = json.dumps(payload if payload is not None else {}).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"后端错误 {e.code}: {e.read().decode('utf-8', 'ignore')}")
        except Exception as e:
            raise RuntimeError(f"无法连接后端 {self.base}: {e}")

    @staticmethod
    def _to_state(d):
        """把后端返回的状态字典重建为 GameState 副本（前端渲染用）。"""
        s = GameState(d.get("difficulty", "史实"))
        for k, v in d.items():
            if hasattr(s, k):
                try:
                    setattr(s, k, v)
                except Exception:
                    pass
        return s

    def new_game(self, difficulty, ai_client):
        r = self._post("/api/new_game", {"difficulty": difficulty})
        return self._to_state(r["state"])

    def advance(self, state, ai_client):
        r = self._post("/api/advance")
        # 同步最新 AI 客户端（本地仍持有配置用于判断是否可用）
        events = [e for e in r.get("events", [])]
        log = r.get("log", [])
        report = r.get("report", "")
        # 用返回的状态刷新本地副本
        new_state = self._to_state(r["state"])
        return events, log, report, new_state

    def action(self, state, action, params, ai_client=None):
        r = self._post("/api/action", {"action": action, "params": params})
        return r.get("message", ""), self._to_state(r["state"])

    def resolve_event(self, state, event_title, choice_idx, ai_client=None):
        r = self._post("/api/resolve_event", {"title": event_title, "choice": choice_idx})
        return r.get("message", ""), self._to_state(r["state"])

    def save(self, state, slot=1):
        self._post("/api/save", {"slot": slot})
        return True

    def load(self, slot=1):
        r = self._post("/api/load", {"slot": slot})
        return self._to_state(r["state"])

    def save_slots(self):
        # 后端持有存档列表；Rust 侧暂未实现 /api/save_slots，先回退本地读取
        try:
            return cmd.save_slots()
        except Exception:
            return []

    def conclude(self, state, ai_client=None):
        raise NotImplementedError("HttpBackend 暂不支持 conclude；Rust 后端尚未实现结局评估。")
