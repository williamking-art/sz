#!/usr/bin/env bash
# ECS 侧：从 GitHub 私库拉取 mcp-songzuo 源码并部署（git 挂钩的部署入口）
#
# 仓库：git@github.com:williamking-art/sz.git
# 认证：只读 deploy key —— 私钥 /root/.ssh/id_ed25519_git_ecs（权限 600），
#       对应公钥已加到该仓库的 Deploy keys（只读，不能写回）。
# 路径：_dev_tools/mcp-songzuo/ —— 用 sparse-checkout **只取该子目录**，
#       不拉整个游戏仓库（sz 含游戏资产，全量克隆代价大）。
#
# 流程：git fetch + sparse-checkout → rsync 到部署目录 → deploy.sh
# 注意：rsync 的 --delete 默认**不会删除被 --exclude 排除的文件**，
#       所以部署目录里的 .env / .dns-aliyun.env 不会被误删。
set -euo pipefail

SRC=${MCP_SRC:-/opt/mcp-songzuo-src}
DST=${MCP_DST:-/opt/mcp-songzuo}
REPO=${MCP_REPO:-git@github.com:williamking-art/sz.git}
BRANCH=${MCP_BRANCH:-main}
SUBDIR=${MCP_SUBDIR:-_dev_tools/mcp-songzuo}
KEY=${MCP_GIT_KEY:-/root/.ssh/id_ed25519_git_ecs}

if [ ! -f "$KEY" ]; then
  echo "[fatal] 缺少 git 私钥 $KEY" >&2
  exit 1
fi
export GIT_SSH_COMMAND="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

if [ ! -d "$SRC/.git" ]; then
  echo "==> 首次稀疏克隆 $REPO（只取 $SUBDIR，分支 $BRANCH）"
  git clone --depth 1 --filter=blob:none --sparse -b "$BRANCH" "$REPO" "$SRC"
  git -C "$SRC" sparse-checkout set "$SUBDIR"
else
  echo "==> 拉取最新 ($BRANCH)"
  # ⚠️ `git clone --depth N` 隐含 --single-branch，克隆里可能**没有** origin/<branch>
  #    远程跟踪引用（2026-10-12 实测：改分支名后 `reset --hard origin/main` 报
  #    "ambiguous argument"）。故用显式 refspec 拉进 refs/remotes/origin/<branch>。
  git -C "$SRC" fetch --depth 1 origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
  git -C "$SRC" checkout -B "$BRANCH" "origin/$BRANCH"
  git -C "$SRC" sparse-checkout set "$SUBDIR"
fi

if [ ! -f "$SRC/$SUBDIR/app/index.js" ]; then
  echo "[fatal] 远端 $SUBDIR 下没有 app/index.js，检查 sparse-checkout 或路径" >&2
  exit 1
fi

echo "==> 同步到部署目录 $DST（密钥文件受 --exclude 保护，不会被删）"
mkdir -p "$DST"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.dns-aliyun.env' \
  --exclude 'tokens.txt' \
  --exclude 'certs/' \
  --exclude 'node_modules/' \
  "$SRC/$SUBDIR/" "$DST/"

echo "==> 部署"
bash "$DST/deploy.sh"

echo "==> 完成（远端 $(git -C "$SRC" log -1 --format='%h %s')）"
