#!/usr/bin/env bash
# 宋祚 MCP（mcp-songzuo）部署 / 更新脚本
# 幂等：重复执行 = 重新构建并滚动重启
set -euo pipefail

cd /opt/mcp-songzuo

if [ ! -f .env ]; then
  echo "[fatal] 缺少 /opt/mcp-songzuo/.env" >&2
  exit 1
fi

echo "==> 构建镜像"
docker compose build

echo "==> 启动容器"
docker compose up -d

echo "==> 等待健康检查通过"
for i in $(seq 1 30); do
  st=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' mcp-songzuo 2>/dev/null || echo missing)
  echo "  [$i/30] health=$st"
  if [ "$st" = "healthy" ]; then break; fi
  if [ "$st" = "missing" ]; then echo "  [fatal] 容器不存在" >&2; exit 1; fi
  sleep 2
done

echo "==> 容器状态"
docker compose ps

echo "==> 本机 /healthz 探测"
curl -s -m 5 http://127.0.0.1:9000/healthz || echo "(healthz 未响应)"
echo
echo "==> 最近日志"
docker logs --tail 20 mcp-songzuo 2>&1 || true
