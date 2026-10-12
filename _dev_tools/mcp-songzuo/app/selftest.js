/**
 * 自测：真起一个进程 + 真发 HTTP，覆盖 MCP 全流程与鉴权边界。
 * 用法：node selftest.js
 */
"use strict";

const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PORT = 19123;
const TOKEN_A = "tok-agentA-secret";
const TOKEN_B = "tok-agentB-secret";
const STATE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "mcp-selftest-"));

let pass = 0;
let fail = 0;
function check(name, cond, extra) {
  if (cond) {
    pass++;
    console.log(`  PASS  ${name}`);
  } else {
    fail++;
    console.log(`  FAIL  ${name}${extra ? " :: " + JSON.stringify(extra) : ""}`);
  }
}

function post(body, token) {
  return new Promise((resolve, reject) => {
    const data = Buffer.from(JSON.stringify(body), "utf8");
    const req = http.request(
      {
        host: "127.0.0.1",
        port: PORT,
        path: "/mcp",
        method: "POST",
        headers: Object.assign(
          { "Content-Type": "application/json", "Content-Length": data.length },
          token ? { Authorization: `Bearer ${token}` } : {}
        ),
      },
      (res) => {
        let out = "";
        res.on("data", (c) => (out += c));
        res.on("end", () => resolve({ status: res.statusCode, body: out }));
      }
    );
    req.on("error", reject);
    req.end(data);
  });
}

const rpc = (method, params, id = 1) => ({ jsonrpc: "2.0", id, method, params });
const parse = (r) => {
  try {
    return JSON.parse(r.body);
  } catch {
    return null;
  }
};

function waitForPort(timeoutMs = 15000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.request(
        { host: "127.0.0.1", port: PORT, path: "/healthz", method: "GET" },
        (res) => {
          res.resume();
          resolve(res.statusCode);
        }
      );
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) reject(new Error("server did not start"));
        else setTimeout(tick, 200);
      });
      req.end();
    };
    tick();
  });
}

(async () => {
  const child = spawn(process.execPath, [path.join(__dirname, "index.js")], {
    env: Object.assign({}, process.env, {
      PORT: String(PORT),
      HOST: "127.0.0.1",
      STATE_DIR,
      STORAGE_DRIVER: "local",
      MCP_TOKENS: `agentA:${TOKEN_A},agentB:${TOKEN_B}`,
      MCP_TOKEN: "",
    }),
    stdio: "ignore", // 避开受限沙箱下的管道限制
  });

  try {
    const healthStatus = await waitForPort();
    console.log(`\n[healthz] HTTP ${healthStatus}\n`);

    console.log("1) 协议与鉴权");
    const noAuth = await post(rpc("initialize", { protocolVersion: "2025-06-18" }), null);
    check("无 token 被拒 401", noAuth.status === 401, noAuth.status);
    const badAuth = await post(rpc("initialize", {}), "wrong-token");
    check("错误 token 被拒 401", badAuth.status === 401, badAuth.status);

    const init = await post(
      rpc("initialize", { protocolVersion: "2025-06-18", clientInfo: { name: "selftest" } }),
      TOKEN_A
    );
    const initBody = parse(init);
    check("initialize 200", init.status === 200, init.status);
    check("serverInfo.name = mcp-songzuo", initBody?.result?.serverInfo?.name === "mcp-songzuo", initBody?.result?.serverInfo);
    check("capabilities.tools 存在", !!initBody?.result?.capabilities?.tools);

    const notif = await post({ jsonrpc: "2.0", method: "notifications/initialized" }, TOKEN_A);
    check("notification 返回 202 空体", notif.status === 202 && notif.body === "", `${notif.status}/${notif.body}`);

    console.log("\n2) tools/list");
    const list = parse(await post(rpc("tools/list", {}), TOKEN_A));
    const names = (list?.result?.tools || []).map((t) => t.name).sort();
    check("8 个工具", names.length === 8, names);
    check("debug_read 已移除", !names.includes("debug_read"), names);
    check(
      "工具名齐全",
      ["context_load", "context_save", "log_append", "log_read", "project_create", "project_list", "state_get", "state_set"].every(
        (n) => names.includes(n)
      ),
      names
    );

    console.log("\n3) 工具调用（含 caller 归因）");
    const pc = parse(await post(rpc("tools/call", { name: "project_create", arguments: { name: "songzuo", description: "宋祚" } }), TOKEN_A));
    check("project_create ok", pc?.result?.content?.[0]?.text?.includes('"ok": true'), pc?.result?.content?.[0]?.text);

    const ss = parse(await post(rpc("tools/call", { name: "state_set", arguments: { project: "songzuo", key: "phase", value: { step: 3 } } }), TOKEN_A));
    const ssText = ss?.result?.content?.[0]?.text || "";
    check("state_set ok", ssText.includes('"ok": true'), ssText);
    check("platform 自动记为 agentA（多 agent 归因）", ssText.includes('"platform": "agentA"'), ssText);

    const sg = parse(await post(rpc("tools/call", { name: "state_get", arguments: { project: "songzuo", key: "phase" } }), TOKEN_B));
    check("agentB 能读到 agentA 写的值（跨 agent 共享）", sg?.result?.content?.[0]?.text?.includes('"step": 3'), sg?.result?.content?.[0]?.text);

    const idx = parse(await post(rpc("tools/call", { name: "state_get", arguments: { project: "songzuo" } }), TOKEN_B));
    check("state_get 无 key 时列索引", idx?.result?.content?.[0]?.text?.includes('"phase"'), idx?.result?.content?.[0]?.text);

    const cs = parse(await post(rpc("tools/call", { name: "context_save", arguments: { project: "songzuo", summary: "自测快照", data: { todo: ["a", "b"] } } }), TOKEN_A));
    check("context_save ok", cs?.result?.content?.[0]?.text?.includes('"ok": true'), cs?.result?.content?.[0]?.text);

    const cl = parse(await post(rpc("tools/call", { name: "context_load", arguments: { project: "songzuo" } }), TOKEN_B));
    check("context_load 取回最新快照", cl?.result?.content?.[0]?.text?.includes("自测快照"), cl?.result?.content?.[0]?.text);

    const la = parse(await post(rpc("tools/call", { name: "log_append", arguments: { project: "songzuo", message: "第一条日志" } }), TOKEN_A));
    check("log_append ok", la?.result?.content?.[0]?.text?.includes('"ok": true'), la?.result?.content?.[0]?.text);
    await post(rpc("tools/call", { name: "log_append", arguments: { project: "songzuo", message: "第二条日志" } }), TOKEN_B);

    const lr = parse(await post(rpc("tools/call", { name: "log_read", arguments: { project: "songzuo", limit: 10 } }), TOKEN_A));
    const lrText = lr?.result?.content?.[0]?.text || "";
    check("log_read 两条都在", lrText.includes("第一条日志") && lrText.includes("第二条日志"), lrText);
    check("日志带 platform 归因", lrText.includes('"platform": "agentB"'), lrText);

    const pl = parse(await post(rpc("tools/call", { name: "project_list", arguments: {} }), TOKEN_A));
    check("project_list 含 songzuo", pl?.result?.content?.[0]?.text?.includes("songzuo"), pl?.result?.content?.[0]?.text);

    console.log("\n4) 边界与容错");
    const unknown = parse(await post(rpc("tools/call", { name: "nope", arguments: {} }), TOKEN_A));
    check("未知工具返回 error", !!unknown?.error, unknown);

    const badMethod = parse(await post(rpc("no/such/method", {}), TOKEN_A));
    check("未知方法 -32601", badMethod?.error?.code === -32601, badMethod);

    const badJson = await new Promise((resolve) => {
      const data = Buffer.from("{not json", "utf8");
      const req = http.request(
        { host: "127.0.0.1", port: PORT, path: "/mcp", method: "POST",
          headers: { "Content-Type": "application/json", "Content-Length": data.length, Authorization: `Bearer ${TOKEN_A}` } },
        (res) => { res.resume(); res.on("end", () => resolve(res.statusCode)); }
      );
      req.end(data);
    });
    check("非法 JSON 返回 400", badJson === 400, badJson);

    const getMcp = await new Promise((resolve) => {
      const req = http.request({ host: "127.0.0.1", port: PORT, path: "/mcp", method: "GET" }, (res) => {
        res.resume();
        res.on("end", () => resolve(res.statusCode));
      });
      req.end();
    });
    check("GET /mcp 返回 405", getMcp === 405, getMcp);

    console.log("\n5) 持久化与损坏保护");
    const stateFile = path.join(STATE_DIR, "states", "songzuo", "phase.json");
    check("状态文件已落盘", fs.existsSync(stateFile), stateFile);
    const onDisk = JSON.parse(fs.readFileSync(stateFile, "utf8"));
    check("落盘内容正确", onDisk.value && onDisk.value.step === 3, onDisk);

    // 把状态文件写成损坏 JSON，读取必须报错而不是当成空
    fs.writeFileSync(stateFile, "{ this is not json", "utf8");
    const corrupt = parse(await post(rpc("tools/call", { name: "state_get", arguments: { project: "songzuo", key: "phase" } }), TOKEN_A));
    check("损坏文件返回 error（不伪装为空）", !!corrupt?.error, corrupt);
    check("错误信息提到 storage", /storage/i.test(corrupt?.error?.message || ""), corrupt?.error?.message);
  } catch (e) {
    fail++;
    console.log(`  FAIL  异常中断: ${e.message}`);
  } finally {
    child.kill("SIGKILL");
    await new Promise((r) => setTimeout(r, 300));
    try {
      fs.rmSync(STATE_DIR, { recursive: true, force: true });
    } catch {}
  }

  console.log(`\n===== 自测结果: ${pass} 通过 / ${fail} 失败 =====`);
  process.exit(fail === 0 ? 0 : 1);
})();
