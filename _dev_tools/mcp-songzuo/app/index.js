/**
 * 宋祚 MCP — 跨设备 state / context / 工作日志
 * Streamable HTTP endpoint, stateless mode（MCP 2025-06-18）
 *
 * 与旧 CloudBase 版的差异：
 *   1. 存储层可插拔（local | oss），不再依赖 @cloudbase/node-sdk
 *   2. 移除 debug_read（CloudBase 临时 URL 排障专用，公网暴露无意义且会泄漏内部路径）
 *   3. 鉴权改为**多 token**（MCP_TOKENS="dsh:xxx,cursor:yyy"），可按 agent 单独吊销
 *   4. 默认**失败关闭**：未配置任何 token 时拒绝启动（旧版是无声放行）
 *   5. 写路径加进程内串行锁 + 写后回读
 */
"use strict";

const http = require("http");
const { createStorage, StorageError } = require("./storage");

const PROTOCOL_VERSION = "2025-06-18";
const PREFIX = process.env.STATE_PREFIX || "";
const PORT = Number(process.env.PORT || 9000);
const HOST = process.env.HOST || "0.0.0.0";

// ------------------------------------------------------------------ auth setup

/** 解析 MCP_TOKENS="dsh:tok1,cursor:tok2"；兼容单个 MCP_TOKEN。 */
function loadTokens(env) {
  const map = new Map(); // token -> caller name
  const multi = String(env.MCP_TOKENS || "").trim();
  if (multi) {
    for (const part of multi.split(",")) {
      const s = part.trim();
      if (!s) continue;
      const i = s.indexOf(":");
      if (i === -1) map.set(s, "unknown");
      else map.set(s.slice(i + 1).trim(), s.slice(0, i).trim() || "unknown");
    }
  }
  const single = String(env.MCP_TOKEN || "").trim();
  if (single) map.set(single, env.MCP_TOKEN_NAME || "default");
  return map;
}

const TOKENS = loadTokens(process.env);
if (TOKENS.size === 0 && process.env.ALLOW_NO_AUTH !== "1") {
  console.error(
    "[fatal] 未配置 MCP_TOKEN / MCP_TOKENS，拒绝以无鉴权方式启动。\n" +
      "        如确需无鉴权（仅限内网调试），设 ALLOW_NO_AUTH=1。"
  );
  process.exit(1);
}

let storage;
try {
  storage = createStorage(process.env);
} catch (e) {
  console.error(`[fatal] 存储层初始化失败: ${e.message}`);
  process.exit(1);
}

// -------------------------------------------------------------------- utilities

function json(res, code, obj, extraHeaders) {
  const body = JSON.stringify(obj);
  res.writeHead(code, Object.assign({ "Content-Type": "application/json" }, extraHeaders || {}));
  res.end(body);
}
const rpcResult = (id, result) => ({ jsonrpc: "2.0", id, result });
const rpcError = (id, code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });

const nowIso = () => new Date().toISOString();
const tsId = () => Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
const safeName = (s) =>
  String(s || "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 64) || "default";

/** 进程内按 key 串行，缩小 read-modify-write 竞态窗口。 */
const locks = new Map();
function withLock(key, fn) {
  const prev = locks.get(key) || Promise.resolve();
  const next = prev.then(fn, fn);
  locks.set(
    key,
    next.catch(() => {}).finally(() => {
      if (locks.get(key) === next) locks.delete(key);
    })
  );
  return next;
}

/** 读改写封装：写后回读校验。 */
async function mutate(key, fn) {
  return withLock(key, async () => {
    const current = await storage.read(key);
    const updated = await fn(current);
    await storage.write(key, updated);
    await storage.verify(key, updated);
    return updated;
  });
}

const k = {
  projects: () => `${PREFIX}projects.json`,
  state: (p, key) => `${PREFIX}states/${p}/${key}.json`,
  stateIndex: (p) => `${PREFIX}states/${p}/__index.json`,
  context: (p, id) => `${PREFIX}contexts/${p}/${id}.json`,
  contextIndex: (p) => `${PREFIX}contexts/${p}/__index.json`,
  log: (p) => `${PREFIX}logs/${p}.json`,
};

// --------------------------------------------------------------- tool handlers

async function projectList() {
  const reg = (await storage.read(k.projects())) || { projects: [] };
  return reg.projects;
}

async function projectCreate({ name, description }) {
  const key = safeName(name);
  await mutate(k.projects(), (reg) => {
    const r = reg || { projects: [] };
    if (!r.projects.find((p) => p.name === key)) {
      r.projects.push({ name: key, description: description || "", createdAt: nowIso() });
    }
    return r;
  });
  return { ok: true, project: key };
}

async function writeState(opts, caller) {
  const p = safeName(opts.project);
  const key = safeName(opts.key);
  const platform = opts.platform || caller || null;
  const doc = { project: p, key, value: opts.value, platform, updatedAt: nowIso() };
  await mutate(k.state(p, key), () => doc);
  await mutate(k.stateIndex(p), (idx) => {
    const i = idx || { keys: [] };
    if (!i.keys.includes(key)) i.keys.push(key);
    return i;
  });
  return { ok: true, project: p, key, platform, updatedAt: doc.updatedAt };
}

async function stateGet({ project, key }) {
  const p = safeName(project);
  if (key) {
    const doc = await storage.read(k.state(p, safeName(key)));
    return doc || { found: false };
  }
  const idx = (await storage.read(k.stateIndex(p))) || { keys: [] };
  return { project: p, keys: idx.keys };
}

async function contextSave({ project, summary, data }, caller) {
  const p = safeName(project);
  const id = tsId();
  const snapshot = {
    id,
    project: p,
    summary,
    data: data || null,
    platform: caller || null,
    savedAt: nowIso(),
  };
  await mutate(k.context(p, id), () => snapshot);
  await mutate(k.contextIndex(p), (idx) => {
    const i = idx || { ids: [] };
    i.ids.push(id);
    if (i.ids.length > 50) i.ids = i.ids.slice(-50);
    return i;
  });
  return { ok: true, snapshotId: id, savedAt: snapshot.savedAt };
}

async function contextLoad({ project, snapshotId }) {
  const p = safeName(project);
  if (snapshotId) {
    const doc = await storage.read(k.context(p, safeName(snapshotId)));
    return doc || { found: false };
  }
  const idx = (await storage.read(k.contextIndex(p))) || { ids: [] };
  if (!idx.ids.length) return { found: false, message: "no snapshots yet" };
  const latest = idx.ids[idx.ids.length - 1];
  return (await storage.read(k.context(p, latest))) || { found: false };
}

async function logAppend({ project, message }, caller) {
  const p = safeName(project);
  await mutate(k.log(p), (log) => {
    const l = log || { entries: [] };
    l.entries.push({ at: nowIso(), platform: caller || null, message });
    if (l.entries.length > 500) l.entries = l.entries.slice(-500);
    return l;
  });
  return { ok: true };
}

async function logRead({ project, limit }) {
  const p = safeName(project);
  const log = (await storage.read(k.log(p))) || { entries: [] };
  const n = Math.max(1, Math.min(200, Number(limit) || 30));
  return { project: p, entries: log.entries.slice(-n) };
}

// --------------------------------------------------------------- tool registry

const TOOLS = [
  {
    name: "state_set",
    description:
      "Set a key-value state for a project (cross-device shared). Any JSON value.",
    inputSchema: {
      type: "object",
      properties: {
        project: { type: "string", description: "Project name" },
        key: { type: "string" },
        value: { description: "Any JSON value" },
        platform: { type: "string", description: "Caller platform tag; defaults to the authenticated caller" },
      },
      required: ["project", "key", "value"],
    },
    run: writeState,
  },
  {
    name: "state_get",
    description: "Get one state value by key, or list all keys of a project.",
    inputSchema: {
      type: "object",
      properties: { project: { type: "string" }, key: { type: "string" } },
      required: ["project"],
    },
    run: stateGet,
  },
  {
    name: "context_save",
    description: "Save a session context snapshot (summary + arbitrary data) for a project.",
    inputSchema: {
      type: "object",
      properties: {
        project: { type: "string" },
        summary: { type: "string", description: "Summary of current work state" },
        data: { description: "Arbitrary JSON payload (todo list, decisions, file list...)" },
      },
      required: ["project", "summary"],
    },
    run: contextSave,
  },
  {
    name: "context_load",
    description: "Load the latest context snapshot of a project (or by snapshotId).",
    inputSchema: {
      type: "object",
      properties: { project: { type: "string" }, snapshotId: { type: "string" } },
      required: ["project"],
    },
    run: contextLoad,
  },
  {
    name: "log_append",
    description: "Append a work-log entry to a project.",
    inputSchema: {
      type: "object",
      properties: { project: { type: "string" }, message: { type: "string" } },
      required: ["project", "message"],
    },
    run: logAppend,
  },
  {
    name: "log_read",
    description: "Read recent work-log entries of a project.",
    inputSchema: {
      type: "object",
      properties: { project: { type: "string" }, limit: { type: "number" } },
      required: ["project"],
    },
    run: logRead,
  },
  {
    name: "project_list",
    description: "List all registered projects.",
    inputSchema: { type: "object", properties: {} },
    run: projectList,
  },
  {
    name: "project_create",
    description: "Register a new project namespace.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" }, description: { type: "string" } },
      required: ["name"],
    },
    run: projectCreate,
  },
];

async function callTool(name, args, caller) {
  const tool = TOOLS.find((t) => t.name === name);
  if (!tool) throw new Error("Unknown tool: " + name);
  const res = await tool.run(args || {}, caller);
  return { content: [{ type: "text", text: JSON.stringify(res, null, 2) }] };
}

// ------------------------------------------------------------- JSON-RPC dispatch

async function handleRpc(msg, caller) {
  const { id, method, params } = msg;
  const isNotification = id === undefined || id === null;
  try {
    if (method === "initialize") {
      return rpcResult(id, {
        protocolVersion: params && params.protocolVersion ? params.protocolVersion : PROTOCOL_VERSION,
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "mcp-songzuo", version: "2.0.0" },
      });
    }
    if (method === "ping") return rpcResult(id, {});
    if (method === "tools/list") {
      return rpcResult(id, { tools: TOOLS.map(({ run, ...rest }) => rest) });
    }
    if (method === "tools/call") {
      if (!params || !params.name) return rpcError(id, -32602, "tools/call requires params.name");
      return rpcResult(id, await callTool(params.name, params.arguments, caller));
    }
    if (isNotification) return null; // notifications/initialized 等
    return rpcError(id, -32601, "Method not found: " + method);
  } catch (e) {
    if (isNotification) return null;
    const msg2 = e instanceof StorageError ? `storage error: ${e.message}` : String((e && e.message) || e);
    return rpcError(id, -32000, msg2);
  }
}

// ------------------------------------------------------------------ HTTP server

function authenticate(req) {
  if (TOKENS.size === 0) return { ok: true, caller: "anonymous" };
  const auth = req.headers["authorization"] || "";
  const m = /^Bearer\s+(.+)$/i.exec(String(auth).trim());
  if (!m) return { ok: false };
  const caller = TOKENS.get(m[1].trim());
  return caller ? { ok: true, caller } : { ok: false };
}

async function readBody(req, limitBytes = 8 * 1024 * 1024) {
  const chunks = [];
  let total = 0;
  for await (const c of req) {
    total += c.length;
    if (total > limitBytes) throw new Error("request body too large");
    chunks.push(c);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function handleRequest(req, res) {
  const url = (req.url || "/").split("?")[0];

  // 健康检查（容器 healthcheck 用，不鉴权、不泄漏内容）
  if (req.method === "GET" && (url === "/healthz" || url === "/health")) {
    try {
      const info = await storage.health();
      return json(res, 200, { ok: true, storage: info, tools: TOOLS.length });
    } catch (e) {
      return json(res, 503, { ok: false, error: e.message });
    }
  }

  if (req.method !== "POST") {
    res.writeHead(405, { Allow: "POST" });
    res.end("Method Not Allowed");
    return;
  }

  const auth = authenticate(req);
  if (!auth.ok) {
    res.writeHead(401, { "Content-Type": "text/plain" });
    res.end("Unauthorized");
    return;
  }

  let body;
  try {
    body = await readBody(req);
  } catch (e) {
    res.writeHead(413, { "Content-Type": "text/plain" });
    res.end(e.message);
    return;
  }

  let msgs;
  try {
    msgs = JSON.parse(body);
    if (!Array.isArray(msgs)) msgs = [msgs];
  } catch (e) {
    res.writeHead(400, { "Content-Type": "text/plain" });
    res.end("Invalid JSON");
    return;
  }

  const responses = [];
  for (const m of msgs) {
    const r = await handleRpc(m, auth.caller);
    if (r) responses.push(r);
  }

  const headers = { "Mcp-Session-Id": "sess-" + tsId() };
  if (!responses.length) {
    res.writeHead(202, headers);
    res.end();
    return;
  }
  const out = responses.length === 1 ? responses[0] : responses;
  json(res, 200, out, headers);
}

const server = http.createServer((req, res) => {
  handleRequest(req, res).catch((e) => {
    console.error("[request error]", e);
    try {
      res.writeHead(500, { "Content-Type": "text/plain" });
      res.end("Internal error");
    } catch (_) {}
  });
});

server.listen(PORT, HOST, () => {
  console.log(
    `[mcp-songzuo] listening on ${HOST}:${PORT} | storage=${storage.name} | ` +
      `tokens=${TOKENS.size} (${[...TOKENS.values()].join(", ") || "none"}) | tools=${TOOLS.length}`
  );
});

for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    console.log(`[mcp-songzuo] ${sig} received, shutting down`);
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  });
}
