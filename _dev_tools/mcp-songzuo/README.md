# mcp-songzuo — 宋祚跨设备/跨 agent 状态 MCP

自托管的 MCP 服务（Streamable HTTP, stateless），提供跨设备共享的
state / context 快照 / 工作日志。由原 CloudBase 云函数版迁移而来
（原版因网关侧 `/mcp` 410 停用，源码留档于 `../_scratch/mcp_state_pkg/index.js`）。

- **端点（当前）**：`http://120.25.223.23:18080/mcp` —— 直连 ECS 公网 IP
- **端点（域名 TLS，暂不可用）**：`https://mcp.songzuo.online:8443/mcp`
- **部署主机**：阿里云 ECS `120.25.223.23`（cn-shenzhen）· `/opt/mcp-songzuo`
- **运维台账（含逐 agent token）**：`D:\codebuddy\_credentials\mcp_songzuo.md`

## 为什么直连 IP 而不用域名

`songzuo.online` **未办 ICP 备案**，阿里云按 **SNI 精确拦截**该域名：实测
IP 作 SNI / 伪造域名作 SNI 均返回 200，只有真域名被 reset；同域走 80 端口
直接返回阿里云《Non-compliance ICP Filing》拦截页。这与该域名根域 `@` 的 A
记录被人 DISABLE 是同一个原因。备案通过后可切回 TLS 域名入口（配置已保留）。

## 目录结构

```
mcp-songzuo/
├── app/
│   ├── index.js        # MCP 服务：JSON-RPC 分发 + 8 个工具 + 多 token 鉴权
│   ├── storage.js      # 可插拔存储层（local | oss）
│   ├── selftest.js     # 自测：28 项，真起进程 + 真发 HTTP
│   ├── package.json
│   └── Dockerfile
├── nginx/nginx.conf    # 18080 明文(直连 IP) + 8443 TLS(域名,备用) 反代到 mcp:9000
├── docker-compose.yml  # mcp + nginx 两容器
├── deploy.sh           # 幂等部署：build + up + 等健康检查
├── deploy_from_git.sh  # ECS 侧：从 GitHub 稀疏检出本目录并部署
├── verify.sh           # ECS 侧验证：容器内自测 + 真实服务端到端
├── issue_cert.sh       # acme.sh DNS-01 签证书
└── install_acme.sh     # acme.sh 安装（多镜像源回退）
```

> `.env` / `.dns-aliyun.env` / `tokens.txt` / `certs/` **不在本仓库内**，
> 只存在于 ECS `/opt/mcp-songzuo/`（见 `.gitignore`）。部署时由 `deploy_from_git.sh`
> 的 rsync `--exclude` 保护，不会被删除。

## 与旧 CloudBase 版的差异

1. 存储层可插拔（`local` | `oss`），不再依赖 `@cloudbase/node-sdk`
2. 移除 `debug_read`（CloudBase 排障专用，公网暴露会泄漏内部路径）
3. 鉴权改为**多 token**（`MCP_TOKENS="dsh:xxx,cursor:yyy"`），可按 agent 单独吊销
4. 默认**失败关闭**：未配置 token 时拒绝启动（旧版无声放行）
5. 写路径加进程内串行锁 + 写后回读

## 部署 / 更新（git 挂钩）

源码以**本目录为唯一真源**（随 `sz` 仓库分发到 GitHub），ECS 从 git 拉取：

```bash
# 1) 本机改动 → 提交 → push 到 GitHub（origin: williamking-art/sz）
# 2) ECS 上执行：
ssh -i C:\Users\william\.ssh\sz_cvm_ed25519 root@120.25.223.23
bash /opt/mcp-songzuo/deploy_from_git.sh
```

`deploy_from_git.sh` 用 **sparse-checkout 只取 `_dev_tools/mcp-songzuo/`**，
不拉整个游戏仓库；认证走只读 deploy key（`/root/.ssh/id_ed25519_git_ecs`）。

不带 git 的应急路径：直接改 ECS 上 `/opt/mcp-songzuo/` 再 `bash deploy.sh`（会与 git 版本漂移，仅限救火）。

## 本地开发 / 自测

```powershell
cd app
node selftest.js        # 28 项自测
```

## 注意

- 明文 HTTP 下 token 可被链路嗅探，真正的安全边界是 256-bit 逐 agent token（可单独吊销）。
  备案通过后应改回 TLS 域名入口并关闭 18080。
- 证书用 DNS-01 校验，不需要开放 80 端口、也不需要备案即可签发（但备案未过时域名会被拦）。
- **Docker 单文件 bind mount 的 inode 陷阱**：改 `nginx/nginx.conf` 后必须
  `docker compose up -d --force-recreate nginx` —— 仅 `nginx -s reload` 读到的仍是旧 inode。
- 同机还有 `songzuo-site`(80/8080)、`llm-relay-nginx`(443/9443)、`llm-relay-newapi`(3000)，
  选端口前先 `ss -tln` 确认（8080、443 均已被占用）。
