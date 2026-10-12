#!/usr/bin/env bash
# 用 acme.sh + 阿里云 DNS-01 为 mcp.songzuo.online 签发 Let's Encrypt 证书。
# DNS-01 的好处：不需要对外开放 80 端口，也不需要 ICP 备案就能完成域名验证。
set -euo pipefail

ACME=/root/.acme.sh/acme.sh
DOMAIN=mcp.songzuo.online

if [ ! -f "$ACME" ]; then
  echo "[fatal] acme.sh 未安装，请先运行 /root/install_acme.sh" >&2
  exit 1
fi

# dns_ali 插件读的是**导出的**环境变量 Ali_Key / Ali_Secret。
# 仅 source 只设 shell 变量，插件读不到（实测报 "You don't specify aliyun api key and secret yet."）。
set -a
# shellcheck disable=SC1091
source /opt/mcp-songzuo/.dns-aliyun.env
set +a

if [ -z "${Ali_Key:-}" ] || [ -z "${Ali_Secret:-}" ]; then
  echo "[fatal] .dns-aliyun.env 未提供 Ali_Key / Ali_Secret" >&2
  exit 1
fi

echo "==> 凭据已导出 (Ali_Key=${Ali_Key:0:6}...)"
"$ACME" --set-default-ca --server letsencrypt

echo "==> 签发证书（DNS-01 / dns_ali / EC-256）"
"$ACME" --issue --dns dns_ali -d "$DOMAIN" --keylength ec-256

echo "==> 安装证书到 /opt/mcp-songzuo/certs"
mkdir -p /opt/mcp-songzuo/certs
"$ACME" --install-cert -d "$DOMAIN" --ecc \
  --key-file       /opt/mcp-songzuo/certs/mcp.key \
  --fullchain-file /opt/mcp-songzuo/certs/mcp.crt \
  --reloadcmd      "docker exec mcp-songzuo-nginx nginx -s reload 2>/dev/null || true"

chmod 600 /opt/mcp-songzuo/certs/mcp.key
chmod 644 /opt/mcp-songzuo/certs/mcp.crt

echo "==> 证书信息"
ls -la /opt/mcp-songzuo/certs
openssl x509 -in /opt/mcp-songzuo/certs/mcp.crt -noout -subject -issuer -dates

echo "==> acme.sh 续期定时任务"
crontab -l 2>/dev/null | grep acme.sh || echo "(未找到 cron 条目)"
