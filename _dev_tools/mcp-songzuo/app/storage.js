/**
 * 存储层：可插拔驱动（local | oss）。
 *
 * 设计纪律（继承自《宋祚》交接层的历史教训）：
 *   「失败绝不伪装成云端为空」——read() 只在对象**确实不存在**时返回 null；
 *   鉴权失败 / 网络错误 / 5xx 等一律 throw，绝不当成「空」，
 *   否则一次读取故障会把整个状态库静默清空（sync_mcp_state.py 的真实事故）。
 *
 *   「写后回读」——write() 落盘后回读比对，不一致即 throw。
 */
"use strict";

const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");

/** 对象不存在（可安全视为空）与真实故障的区分。 */
class NotFound extends Error {}
class StorageError extends Error {}

// ---------------------------------------------------------------- local driver

function createLocalDriver({ dir }) {
  const root = path.resolve(dir);
  fs.mkdirSync(root, { recursive: true });

  // key -> 文件路径，并阻断路径穿越
  function resolve(key) {
    const rel = String(key).replace(/\\/g, "/").replace(/^\/+/, "");
    const full = path.resolve(root, rel);
    if (full !== root && !full.startsWith(root + path.sep)) {
      throw new StorageError(`key escapes storage root: ${key}`);
    }
    return full;
  }

  return {
    name: "local",
    async read(key) {
      const full = resolve(key);
      let raw;
      try {
        raw = await fsp.readFile(full, "utf8");
      } catch (e) {
        if (e.code === "ENOENT") return null; // 确实不存在
        throw new StorageError(`read failed for ${key}: ${e.code || e.message}`);
      }
      try {
        return JSON.parse(raw);
      } catch (e) {
        // 文件存在但内容损坏：绝不当作空，否则会覆盖掉可人工抢救的数据
        throw new StorageError(`corrupt JSON at ${key}: ${e.message}`);
      }
    },
    async write(key, data) {
      const full = resolve(key);
      await fsp.mkdir(path.dirname(full), { recursive: true });
      const tmp = `${full}.tmp-${process.pid}-${Date.now()}`;
      const body = JSON.stringify(data, null, 2);
      await fsp.writeFile(tmp, body, "utf8");
      await fsp.rename(tmp, full); // POSIX 原子替换
      return { key, bytes: Buffer.byteLength(body) };
    },
    async verify(key, data) {
      const back = await this.read(key);
      if (JSON.stringify(back) !== JSON.stringify(data)) {
        throw new StorageError(`write-after-read mismatch at ${key}`);
      }
    },
    async health() {
      const probe = `.healthcheck`;
      await this.write(probe, { at: new Date().toISOString() });
      const back = await this.read(probe);
      if (!back || !back.at) throw new StorageError("health probe readback failed");
      return { driver: "local", root, ok: true };
    },
  };
}

// ------------------------------------------------------------------ oss driver

function createOssDriver({ bucket, region, prefix, accessKeyId, accessKeySecret, endpoint }) {
  let OSS;
  try {
    OSS = require("ali-oss");
  } catch (e) {
    throw new StorageError(
      "STORAGE_DRIVER=oss 需要 ali-oss 依赖：在 app 目录执行 npm install ali-oss"
    );
  }
  const client = new OSS({
    region,
    bucket,
    accessKeyId,
    accessKeySecret,
    ...(endpoint ? { endpoint } : {}),
    secure: true,
  });

  const full = (key) => `${prefix}${String(key).replace(/^\/+/, "")}`;

  function isNotFound(e) {
    const code = String((e && (e.code || e.name)) || "");
    const status = (e && e.status) || 0;
    return code === "NoSuchKey" || code === "NoSuchBucket" || status === 404;
  }

  return {
    name: "oss",
    async read(key) {
      const k = full(key);
      try {
        const r = await client.get(k);
        const text = Buffer.isBuffer(r.content) ? r.content.toString("utf8") : String(r.content);
        return JSON.parse(text);
      } catch (e) {
        if (isNotFound(e)) return null; // 确实不存在
        throw new StorageError(`oss read failed for ${k}: ${(e && e.code) || e.message}`);
      }
    },
    async write(key, data) {
      const k = full(key);
      const body = JSON.stringify(data, null, 2);
      await client.put(k, Buffer.from(body, "utf8"));
      return { key: k, bytes: Buffer.byteLength(body) };
    },
    async verify(key, data) {
      const back = await this.read(key);
      if (JSON.stringify(back) !== JSON.stringify(data)) {
        throw new StorageError(`write-after-read mismatch at ${full(key)}`);
      }
    },
    async health() {
      const probe = ".healthcheck";
      await this.write(probe, { at: new Date().toISOString() });
      const back = await this.read(probe);
      if (!back || !back.at) throw new StorageError("oss health probe readback failed");
      return { driver: "oss", bucket, prefix, ok: true };
    },
  };
}

// ---------------------------------------------------------------------- factory

function createStorage(env = process.env) {
  const driver = String(env.STORAGE_DRIVER || "local").toLowerCase();
  if (driver === "oss") {
    const missing = ["OSS_BUCKET", "OSS_REGION", "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
      .filter((k) => !env[k]);
    if (missing.length) {
      throw new StorageError(`STORAGE_DRIVER=oss 缺少环境变量: ${missing.join(", ")}`);
    }
    return createOssDriver({
      bucket: env.OSS_BUCKET,
      region: env.OSS_REGION,
      prefix: env.OSS_PREFIX || "mcp-state/",
      accessKeyId: env.ALIBABA_CLOUD_ACCESS_KEY_ID,
      accessKeySecret: env.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
      endpoint: env.OSS_ENDPOINT || undefined,
    });
  }
  if (driver === "local") {
    return createLocalDriver({ dir: env.STATE_DIR || "/data/mcp-state" });
  }
  throw new StorageError(`unknown STORAGE_DRIVER: ${driver}`);
}

module.exports = { createStorage, StorageError, NotFound };
