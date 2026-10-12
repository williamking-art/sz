#!/usr/bin/env bash
# ECS 侧验证：容器内自测 + 真实服务端到端
set -uo pipefail

echo "===== A) 容器内自测 ====="
docker run --rm -v /opt/mcp-songzuo/app/selftest.js:/app/selftest.js:ro \
  mcp-songzuo:2.0.0 node selftest.js
SELFTEST=$?

echo
echo "===== B) 真实服务端到端 (127.0.0.1:9000) ====="
TOK=$(grep '^MCP_TOKENS=' /opt/mcp-songzuo/.env | sed 's/^MCP_TOKENS=//' | tr ',' '\n' | grep '^dsh:' | cut -d: -f2)
BASE=http://127.0.0.1:9000/mcp
post() { curl -s -m 10 -X POST "$BASE" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "$1"; }

echo "-- 无 token（应 401）"
curl -s -o /dev/null -w '   HTTP %{http_code}\n' -m 10 -X POST "$BASE" \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'

echo "-- initialize"
post '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"verify"}}}'
echo

echo "-- tools/list 工具数"
CNT=$(post '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | grep -o '"name":"[a-z_]*"' | wc -l)
echo "   工具数 = $CNT"

echo "-- state_set"
post '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"state_set","arguments":{"project":"songzuo","key":"deploy_verify","value":{"by":"verify.sh","at":"'"$(date -Iseconds)"'"}}}}'
echo

echo "-- state_get 回读"
post '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"state_get","arguments":{"project":"songzuo","key":"deploy_verify"}}}'
echo

echo "-- 容器内落盘"
docker exec mcp-songzuo ls -la /data/mcp-state/states/songzuo/ 2>&1

echo
echo "===== 自测退出码: $SELFTEST ====="
exit $SELFTEST
