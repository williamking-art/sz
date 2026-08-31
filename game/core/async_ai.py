# -*- coding: utf-8 -*-
"""宋祚 · AI 异步调用层（T6 异步化核心，改造计划 H 节落地）

线程纪律（Tkinter 与 GameState 均非线程安全）：
- 后台 worker 只做「AI 网络调用 + 契约纯函数校验」——即 ai/client.py 各契约方法
  内部的网络请求、validate / 安全过滤 / 复读检测（这些都不写 GameState）；
- 一切「写 GameState / 更新 UI」必须回到主线程，经 ui.after(100ms) 轮询 future，
  在 on_success / on_error 回调内执行（主线程落地 + 呈现）。

ThreadPoolExecutor 固定 ≤2 worker（守护线程，Python 3.9+ 不阻塞解释器退出）：
- worker 数上限 = 2，绝不随调用量增长（防并发 AI 请求打爆限流）；
- 同一 AIClient 实例的内部缓存（_cache / _prev_texts / token_usage / 能力探测位）
  非线程安全 → 按 client 实例加互斥锁（弱引用键控），串行化对同一实例的并发调用；
- 进程退出时线程池线程不阻塞解释器（ThreadPoolExecutor 线程为 daemon）。

结算拆分（settle_turn 的异步版，见 run_settlement_ai）：
  ① 后台 AI 推演族（economy 强制 + 按需唤醒领域契约）→ 只返回 {attr: result} 不写 state；
  ② 主线程 on_success 落地（写 state 槽位 → run_monthly_settlement 本地 12 步结算）；
  ③ 月报叙事由调用方经 run_ai_call 后补（不阻塞结算完成）。
"""
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

__all__ = ["run_ai_call", "run_settlement_ai", "shutdown"]

#: 后台线程池上限（固定 ≤2，防止并发 AI 请求过多）
_MAX_WORKERS = 2
#: 主线程轮询间隔（毫秒）
_POLL_MS = 100

_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS,
                               thread_name_prefix="songzuo-ai")

#: 同一 AIClient 实例的互斥锁（WeakKeyDictionary，client 被回收后自动释放）
_client_locks = weakref.WeakKeyDictionary()
_client_locks_guard = threading.Lock()


def _client_lock(client):
    """取得某 client 实例的互斥锁（串行化同一实例的并发调用）。"""
    with _client_locks_guard:
        lock = _client_locks.get(client)
        if lock is None:
            lock = _client_locks[client] = threading.Lock()
        return lock


def shutdown(wait: bool = False) -> None:
    """关闭全局线程池（测试/进程收尾用；正常 GUI 退出无需调用）。"""
    _EXECUTOR.shutdown(wait=wait)


# ============================================================
# 单次 AI 契约调用（后台网络 + 校验 → 主线程回调）
# ============================================================
def run_ai_call(client, method_name, *args, on_success=None, on_error=None,
                ui=None, **kwargs):
    """后台执行一次 AI 契约调用，完成后回到主线程回调。

    参数：
      client        AIClient 实例（须有 method_name 方法）
      method_name   AI 契约方法名（如 polish_decree / council_review /
                    monthly_report / parse_decree / dialogue）
      *args, **kwargs  透传给方法的参数。**入参快照（state_summary / posture /
                    history 等）必须在主线程先取好**，后台只做网络 + 纯函数校验。
      on_success    主线程回调 fn(result)：result 为方法返回值（dict / str / None）
      on_error      主线程回调 fn(exc)：exc 为异常（AIRuntimeError 或其它）
      ui            提供 .after(ms, fn) 的主线程宿主（self.root / self）；
                    None 时只提交并返回 future，不启动轮询。

    返回：concurrent.futures.Future（UI 路径由 after 轮询驱动，无需调用方等待）。
    """
    method = getattr(client, method_name, None)
    if method is None:
        _fail(ui, on_error, TypeError(f"AI 客户端无方法：{method_name}"))
        return None
    lock = _client_lock(client)
    future = _EXECUTOR.submit(_call_guarded, method, args, kwargs, lock)
    if ui is None:
        return future
    _schedule_poll(future, ui, on_success, on_error)
    return future


def _call_guarded(method, args, kwargs, lock):
    """worker 体：锁内执行「AI 网络调用 + 契约纯函数校验」（不写 GameState）。"""
    with lock:
        return method(*args, **kwargs)


def _schedule_poll(future, ui, on_success, on_error):
    """after(100ms) 轮询 future；完成后在主线程触发回调。"""
    def _poll():
        if not future.done():
            try:
                ui.after(_POLL_MS, _poll)
            except Exception:
                pass  # 宿主已销毁：放弃轮询
            return
        try:
            result = future.result()
        except Exception as e:  # noqa: BLE001
            _fail(ui, on_error, e)
            return
        _call_cb(ui, on_success, result)
    try:
        ui.after(_POLL_MS, _poll)
    except Exception:
        pass


def _call_cb(ui, cb, value):
    """主线程回调（on_success / on_error 同源）：回调自身异常不吞死 mainloop。"""
    if cb is None:
        return
    try:
        cb(value)
    except Exception as e:  # noqa: BLE001
        _show_error(ui, "AI 回调异常", e)


def _fail(ui, on_error, exc):
    """失败路径：优先 on_error 回调；缺省弹错（AIRuntimeError 语义对齐）。"""
    if on_error is not None:
        _call_cb(ui, on_error, exc)
        return
    _show_error(ui, "AI 叙事中断", exc)


def _show_error(ui, title, exc):
    """缺省错误弹窗：宿主是面板实例走 self.messagebox，否则走 ui.dialog 自制弹窗。"""
    try:
        msg = str(exc)
        if hasattr(ui, "messagebox"):
            ui.messagebox.showerror(title, msg)
        else:
            from ui.dialog import show_error as _dlg_error
            parent = getattr(ui, "root", None) or ui
            _dlg_error(parent, title, msg)
    except Exception:
        pass


# ============================================================
# 结算拆分：后台 AI 推演族（①）→ 主线程落地 + 12 步结算（②）
# ============================================================
def _cumulative_diff(state) -> str:
    """落地改进 6：其他 Agent 上轮结果摘要（认知层档位词，注入并行各 agent 的 posture）。"""
    try:
        parts = []
        eco = getattr(state, "_economy_ai", None)
        if isinstance(eco, dict):
            parts.append(f"景气{eco.get('景气', '中')}")
        dip = getattr(state, "_diplomacy_ai", None)
        if isinstance(dip, dict):
            parts.append(f"外交{str(dip.get('attitude', ''))}")
        mil = getattr(state, "_military_ai", None)
        if isinstance(mil, dict):
            parts.append(f"军{str(mil.get('power', ''))}")
        rel = getattr(state, "_relief_ai", None)
        if isinstance(rel, dict):
            parts.append(f"灾{rel.get('disaster_level', 0)}")
        return "\n【上轮各司推演】" + "、".join(parts) if parts else ""
    except Exception:
        return ""


def run_settlement_ai(client, posture, state, woken, ui, on_success, on_error):
    """后台执行结算前 AI 推演族，完成后回到主线程回调（不写 state）。

    参数：
      client        AIClient 实例
      posture       结算输入快照（主线程先取 state.posture）
      state         GameState 只读引用（persona / 记忆注入用；后台只读不写）
      woken         route_agents 返回的唤醒 Agent id 列表；
                    None 表示路由失败 → 退化为 P1 三契约（diplomacy/military/relief）
      ui            提供 .after(ms, fn) 的主线程宿主
      on_success    主线程回调 fn(results)：results 为 {state_attr: result} 字典，
                    调用方在此落地（写槽位 → run_monthly_settlement → 叙事后补）
      on_error      主线程回调 fn(exc)：economy 推演失败抛 AIRuntimeError
                    （拒绝式：结算不进行，与 settle_turn 全游戏级强制 AI 一致）

    返回：concurrent.futures.Future。
    """
    def _worker():
        from concurrent.futures import as_completed
        results = {}
        jobs = {}
        lock = _client_lock(client)

        # 落地改进 6（并行上下文共享）：注入其他 Agent 上轮结果摘要（cumulative_diff，
        # 认知层档位词，保上下文连贯；并行无需顺序依赖）
        _diff_hint = _cumulative_diff(state)

        # economy 强制推演（拒绝式，**与其余 Agent 并行**）：失败/非法 → 整单拒绝，不伪造
        def _run_eco():
            eco = client.economy_decide(posture + _diff_hint)
            if not isinstance(eco, dict) or eco.get("_error"):
                from core.errors import AIRuntimeError
                from content.data import AI_ERROR_CODES
                raise AIRuntimeError(
                    AI_ERROR_CODES.get("AI_CONTRACT_FAILED", "AI 输出不满足契约"))
            return eco

        fut_eco = _EXECUTOR.submit(_call_guarded, _run_eco, (), {}, lock)
        jobs[fut_eco] = "_economy_ai"

        # 其余唤醒 Agent → 线程池并行（同一 client 实例锁内串行化，安全优先）
        if woken is None:
            # 路由失败退化：P1 三契约保底注入（与 settle_turn 同步路径一致）
            tasks = (("_diplomacy_ai", "diplomacy_decide"),
                     ("_military_ai", "military_decide"),
                     ("_relief_ai", "relief_decide"))
        else:
            try:
                from core.agent_router import AGENT_DEFS
            except Exception:
                AGENT_DEFS = {}
            tasks = []
            for aid in woken:
                adef = AGENT_DEFS.get(aid) or {}
                method = adef.get("method")
                attr = adef.get("settle_attr")
                if not method or not attr or attr == "_economy_ai":
                    continue  # narrative 无槽位 / economy 已强制注入
                tasks.append((attr, method))

        def _run_agent(attr, method):
            r = getattr(client, method)(posture + _diff_hint, state=state)
            if isinstance(r, dict) and not r.get("_error"):
                return (attr, r)
            return ("_contract_failed", {"agent": attr, "method": method,
                                         "error": "contract_failed"})

        for attr, method in tasks:
            fut = _EXECUTOR.submit(_call_guarded, _run_agent, (attr, method), {}, lock)
            jobs[fut] = attr

        # 统一收集：economy 失败 → 拒绝式 raise；非 economy 失败 → 收集失败信号
        # （T8 推演分级：不静默、不伪造；主线程 on_success 落地 _ai_failures）
        failures = []
        for fut in as_completed(jobs):
            attr = jobs[fut]
            try:
                val = fut.result()
            except Exception as e:
                if attr == "_economy_ai":
                    raise   # economy 拒绝式：结算不进行
                failures.append({"agent": attr, "error": f"{type(e).__name__}: {e}"})
                continue
            if attr == "_economy_ai":
                results["_economy_ai"] = val
            elif isinstance(val, tuple) and val and val[0] == "_contract_failed":
                failures.append(val[1])
            elif val is not None:
                _a, _r = val      # _run_agent 返回 (attr, result)
                results[_a] = _r
        if failures:
            results["_ai_failures"] = failures
        return results

    future = _EXECUTOR.submit(_worker)
    _schedule_poll(future, ui, on_success, on_error)
    return future


def _settle_guarded(client, worker):
    """结算推演族同样按 client 串行化（防与其它 AI 调用并发改同一 client 内部缓存）。"""
    with _client_lock(client):
        return worker()
