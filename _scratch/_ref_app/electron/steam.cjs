EAM_STAT_NAMES = new Set([
  "STAT_RUNS_STARTED",
  "STAT_TURNS_PLAYED",
  "STAT_DECREES_ISSUED",
  "STAT_SAVES_CREATED",
  "STAT_ENDINGS_REACHED",
  "STAT_MAX_TURN_REACHED",
]);

const MAX_STAT_NAMES = new Set(["STAT_MAX_TURN_REACHED"]);

// 发布配置 steam.config.json（appId/authUrl/depot 真值）。两个来源，优先 asar 外：
//   1) <resourcesPath>/steam.config.json —— asar 外，发布前由 tools/steam/inject_steam_config.cjs
//      注入。GitHub Actions 出的包 asar 里没有 config（它是 gitignore 的本地文件，CI checkout
//      拿不到），上传前注入到此处即可，无需重打 asar。
//   2) ./steam.config.json —— 随 asar（本机 dist:mac 且 config 在文件夹里时才有）。
// env 仍可覆盖（开发用）。两者都没有则 appId/authUrl 为空 → 回落玩家手填 key。
let releaseConfig = {};
try {
  const fsMod = require("node:fs");
  const pathMod = require("node:path");
  const external = process.resourcesPath
    ? pathMod.join(process.resourcesPath, "steam.config.json")
    : "";
  if (external && fsMod.existsSync(external)) {
    releaseConfig = JSON.parse(fsMod.readFileSync(external, "utf8")) || {};
  } else {
    releaseConfig = require("./steam.config.json") || {};
  }
} catch {
  releaseConfig = {};
}

const DEFAULT_AUTH_IDENTITY =
  process.env.MING_SIM_STEAM_AUTH_IDENTITY ||
  (typeof releaseConfig.identity === "string" && releaseConfig.identity.trim()) ||
  "ming-salvage-server";
const AUTH_TICKET_TTL_MS = 10 * 60 * 1000;
const DEFAULT_AUTH_URL =
  process.env.MING_SIM_STEAM_AUTH_URL ||
  (typeof releaseConfig.authUrl === "string" && releaseConfig.authUrl.trim()) ||
  "";

// ---------------------------------------------------------------------------
// 应用层对称加密（AES-256-GCM）
// 密钥派生：SHA256(steamId64 + ":" + appSalt)，双方独立计算，无需协商。
// appSalt 从 steam.config.json 读取，发版前由 inject_steam_config.cjs 注入到包里。
// ---------------------------------------------------------------------------

const crypto = require("node:crypto");

const APP_SALT =
  (typeof releaseConfig.appSalt === "string" && releaseConfig.appSalt.trim()) || "";

const deriveKey = (steamId64, salt) => {
  return crypto.createHash("sha256").update(`${steamId64}:${salt}`).digest();
};

const deriveLoginKey = (salt) => {
  return crypto.createHash("sha256").update(`login:${salt}`).digest();
};

const aesEncrypt = (plaintext, key) => {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const data = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return { iv: iv.toString("hex"), tag: tag.toString("hex"), data: data.toString("hex") };
};

const aesDecrypt = (payload, key) => {
  const iv = Buffer.from(payload.iv, "hex");
  const tag = Buffer.from(payload.tag, "hex");
  const data = Buffer.from(payload.data, "hex");
  const decipher = crypto.createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
};

// 加密请求体（若已配置 appSalt 和 steamId64）
const encryptBody = (body, key) => {
  if (!key) return body;
  const plaintext = JSON.stringify(body);
  return { enc: aesEncrypt(plaintext, key) };
};

// 解密响应（若响应含 enc 字段）
const decryptResponse = (data, key) => {
  if (!key || !data || typeof data !== "object" || !data.enc) return data;
  try {
    return JSON.parse(aesDecrypt(data.enc, key));
  } catch (e) {
    warn("decryptResponse failed:", e instanceof Error ? e.message : String(e));
    return data;
  }
};

let client = null;
let initAttempted = false;
let initError = "";
let nextAuthTicketId = 1;
const activeAuthTickets = new Map();

const log = (...args) => console.log("[steam]", ...args);
const warn = (...args) => console.warn("[steam]", ...args);

const parseAppId = () => {
  const raw = process.env.MING_SIM_STEAM_APP_ID || process.env.STEAM_APP_ID || "";
  const envAppId = Number.parseInt(raw, 10);
  if (Number.isFinite(envAppId) && envAppId > 0) return envAppId;
  const configAppId = Number.parseInt(String(releaseConfig.appId ?? ""), 10);
  return Number.isFinite(configAppId) && configAppId > 0 ? configAppId : undefined;
};

const normalizeInt = (value, fallback = 0) => {
  const n = Number.parseInt(String(value), 10);
  if (!Number.isFinite(n)) return fallback;
  return n;
};

const statNameOrThrow = (name) => {
  const statName = String(name || "").trim();
  if (!STEAM_STAT_NAMES.has(statName)) {
    throw new Error(`Unsupported Steam stat: ${statName || "(empty)"}`);
  }
  return statName;
};

// 打包版直接双击启动时弹回 Steam 客户端重启（true=本进程应立即退出）。
// 必须在 init 之前调；appId 未配置或失败时一律放行。
const restartAppIfNecessary = () => {
  const appId = parseAppId();
  if (typeof appId !== "number") return false;
  try {
    const steamworks = require("steamworks.js");
    return Boolean(steamworks.restartAppIfNecessary(appId));
  } catch (error) {
    warn("restartAppIfNecessary failed:", error instanceof Error ? error.message : String(error));
    return false;
  }
};

const getClient = () => {
  if (client || initAttempted) return client;
  initAttempted = true;
  try {
    const steamworks = require("steamworks.js");
    const appId = parseAppId();
    client = typeof appId === "number" ? steamworks.init(appId) : steamworks.init();
    log(`initialized${typeof appId === "number" ? ` appId=${appId}` : ""}`);
  } catch (error) {
    initError = error instanceof Error ? error.message : String(error);
    client = null;
    warn("unavailable:", initError);
  }
  return client;
};

const unavailable = () => ({
  ok: false,
  available: false,
  appId: parseAppId() ?? null,
  error: initError || "Steamworks is not initialized.",
});

const normalizeIdentity = (identity) => {
  const value = String(identity || DEFAULT_AUTH_IDENTITY).trim();
  return value || DEFAULT_AUTH_IDENTITY;
};

const normalizeAuthUrl = (url) => {
  const value = String(url || DEFAULT_AUTH_URL).trim();
  if (!value) throw new Error("Steam auth server URL is not configured.");
  const parsed = new URL(value);
  // demo 过渡期允许公网 http（验票服务与 new-api 同为 IP+端口直连，未上域名/证书）。
  // 上 https 域名后建议恢复强制 https。
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Steam auth server URL must be http(s)://.");
  }
  return parsed.toString();
};

const parseServerResponse = async (response) => {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const statusPayload = (steam) => {
  const steamId = steam.localplayer.getSteamId();
  return {
    appId: steam.utils.getAppId(),
    steamId64: steamId?.steamId64?.toString?.() || "",
    personaName: steam.localplayer.getName(),
  };
};

const getStatus = () => {
  const steam = getClient();
  if (!steam) return unavailable();
  try {
    return {
      ok: true,
      available: true,
      ...statusPayload(steam),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("status failed:", message);
    return { ...unavailable(), error: message };
  }
};

const cancelAuthTicket = (ticketId) => {
  const key = String(ticketId || "");
  const entry = activeAuthTickets.get(key);
  if (!entry) {
    return { ok: false, available: Boolean(client), ticketId: key, error: "Auth ticket not found." };
  }
  activeAuthTickets.delete(key);
  clearTimeout(entry.timer);
  try {
    entry.ticket.cancel();
    return { ok: true, available: Boolean(client), ticketId: key };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("cancelAuthTicket failed:", message);
    return { ok: false, available: Boolean(client), ticketId: key, error: message };
  }
};

const rememberAuthTicket = (ticket) => {
  const ticketId = String(nextAuthTicketId++);
  const timer = setTimeout(() => {
    cancelAuthTicket(ticketId);
  }, AUTH_TICKET_TTL_MS);
  timer.unref?.();
  activeAuthTickets.set(ticketId, { ticket, timer });
  return ticketId;
};

const getAuthTicket = async (identity) => {
  const steam = getClient();
  if (!steam) return unavailable();
  const normalizedIdentity = normalizeIdentity(identity);
  try {
    const ticket = await steam.auth.getAuthTicketForWebApi(normalizedIdentity);
    const ticketBytes = ticket.getBytes();
    const ticketId = rememberAuthTicket(ticket);
    return {
      ok: true,
      available: true,
      ...statusPayload(steam),
      identity: normalizedIdentity,
      ticket: Buffer.from(ticketBytes).toString("hex"),
      ticketId,
      expiresInSeconds: Math.floor(AUTH_TICKET_TTL_MS / 1000),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("getAuthTicket failed:", message);
    return { ok: false, available: true, identity: normalizedIdentity, error: message };
  }
};

const authenticateWithServer = async (options = {}) => {
  let authTicket = null;
  try {
    const url = normalizeAuthUrl(options.url);
    const identity = normalizeIdentity(options.identity);
    authTicket = await getAuthTicket(identity);
    if (!authTicket.ok) return authTicket;

    const plainBody = {
      appid: authTicket.appId,
      identity: authTicket.identity,
      ticket: authTicket.ticket,
      steamId64: authTicket.steamId64,
      personaName: authTicket.personaName,
      ...(options.payload && typeof options.payload === "object" ? options.payload : {}),
    };

    // 登录请求用 login 专用密钥加密（此时 steamid 尚未经服务端验证）
    const loginKey = APP_SALT ? deriveLoginKey(APP_SALT) : null;
    const requestBody = encryptBody(plainBody, loginKey);

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers && typeof options.headers === "object" ? options.headers : {}),
      },
      body: JSON.stringify(requestBody),
    });
    const rawData = await parseServerResponse(response);

    // 响应用用户密钥解密（steamId64 来自本地 Steam SDK，与服务端验证的一致）
    const userKey = APP_SALT && authTicket.steamId64 ? deriveKey(authTicket.steamId64, APP_SALT) : null;
    const data = decryptResponse(rawData, userKey);

    return {
      ok: response.ok,
      available: true,
      appId: authTicket.appId,
      steamId64: authTicket.steamId64,
      personaName: authTicket.personaName,
      identity: authTicket.identity,
      status: response.status,
      data,
      error: response.ok ? undefined : `Steam auth server returned HTTP ${response.status}.`,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("authenticateWithServer failed:", message);
    return { ok: false, available: Boolean(client), error: message };
  } finally {
    if (authTicket?.ticketId) {
      cancelAuthTicket(authTicket.ticketId);
    }
  }
};

const readStatInt = (steam, statName) => {
  const value = steam.stats.getInt(statName);
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
};

const storeStats = (steam) => {
  const stored = steam.stats.store();
  if (!stored) warn("storeStats returned false");
  return stored;
};

const addStatInt = (name, delta) => {
  const steam = getClient();
  if (!steam) return unavailable();
  try {
    const statName = statNameOrThrow(name);
    const amount = normalizeInt(delta, 0);
    const previous = readStatInt(steam, statName);
    const value = previous + amount;
    const setOk = steam.stats.setInt(statName, value);
    const storeOk = storeStats(steam);
    return { ok: Boolean(setOk && storeOk), available: true, name: statName, previous, value };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("addStatInt failed:", message);
    return { ok: false, available: true, error: message };
  }
};

const setStatInt = (name, value) => {
  const steam = getClient();
  if (!steam) return unavailable();
  try {
    const statName = statNameOrThrow(name);
    const requested = normalizeInt(value, 0);
    const previous = readStatInt(steam, statName);
    const next = MAX_STAT_NAMES.has(statName) ? Math.max(previous, requested) : requested;
    const setOk = steam.stats.setInt(statName, next);
    const storeOk = storeStats(steam);
    return { ok: Boolean(setOk && storeOk), available: true, name: statName, previous, value: next };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("setStatInt failed:", message);
    return { ok: false, available: true, error: message };
  }
};

// 创意工坊已订阅条目：本地缓存查询，不发网络请求。main.cjs 起后端 ready 后 POST 一次，
// 之后 30s 轮询、仅 id/state 集合哈希变化才再 POST（steamworks.js 没有 onItemInstalled 回调，
// 只能轮询）。bigint 必须转 string——JSON.stringify 不认 bigint。见
// docs/steam-workshop-cloud-plan.md §1.2。
const listWorkshopItems = () => {
  const steam = getClient();
  if (!steam || !steam.workshop) return [];
  try {
    return steam.workshop.getSubscribedItems().map((id) => {
      let info = null;
      try {
        info = steam.workshop.installInfo(id);
      } catch {
        info = null;
      }
      let state = 0;
      try {
        state = Number(steam.workshop.state(id)) || 0;
      } catch {
        state = 0;
      }
      return {
        id: String(id),
        state,
        folder: info?.folder || "",
        sizeOnDisk: info ? String(info.sizeOnDisk) : "0",
        timestamp: info?.timestamp || 0,
      };
    });
  } catch (error) {
    warn("listWorkshopItems failed:", error instanceof Error ? error.message : String(error));
    return [];
  }
};

const flushStats = () => {
  const steam = getClient();
  if (!steam) return unavailable();
  try {
    return { ok: Boolean(storeStats(steam)), available: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warn("flushStats failed:", message);
    return { ok: false, available: true, error: message };
  }
};

// 微交易充值：注册 Steam 的 MicroTxnAuthorizationResponse 回调。玩家在游戏内授权框点
// 「确认/取消」后触发，把 {appId, orderId, authorized} 交给 onResponse，主进程再转给渲染层去
// 调后端 finalize。返回退订函数；Steam 不可用或回调命名空间缺失则返回 noop（充值入口自动不可用）。
const registerMicroTxnCallback = (onResponse) => {
  const steam = getClient();
  if (!steam || !steam.callback || typeof steam.callback.register !== "function") {
    warn("microtxn callback unavailable (Steam not initialized).");
    return () => {};
  }
  try {
    // SteamCallback.MicroTxnAuthorizationResponse = 9
    const handle = steam.callback.register(9, (value) => {
      try {
        onResponse({
          appId: Number(value?.appId ?? value?.app_id ?? 0),
          orderId: String(value?.orderId ?? value?.order_id ?? ""),
          authorized: Boolean(value?.authorized),
        });
      } catch (e) {
        warn("microtxn onResponse threw:", e instanceof Error ? e.message : String(e));
      }
    });
    return () => {
      try {
        handle?.disconnect?.();
      } catch {
        /* ignore */
      }
    };
  } catch (error) {
    warn("registerMicroTxnCallback failed:", error instanceof Error ? error.message : String(error));
    return () => {};
  }
};

module.exports = {
  restartAppIfNecessary,
  getAppId: () => parseAppId() ?? null,
  getDefaultAuthUrl: () => DEFAULT_AUTH_URL,
  getStatus,
  getAuthTicket,
  cancelAuthTicket,
  authenticateWithServer,
  addStatInt,
  setStatInt,
  flushStats,
  listWorkshopItems,
  registerMicroTxnCallback,
  // 加密工具（供 main.cjs 包装 quota/topup 等 steamserver 请求）
  encryptBody,
  decryptResponse,
  deriveKey,
  getAppSalt: () => APP_SALT,
};
{
  "ap