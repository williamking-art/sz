#!/usr/bin/env bash
# 安装 acme.sh（多通道回退；get.acme.sh / github 直连在本链路时通时断）
set -euo pipefail

SRC=/root/acme-src
rm -rf "$SRC" /root/acme.tar.gz

fetch() {
  local name="$1" url="$2" out="$3"
  echo "  -> 尝试 $name"
  if timeout 90 curl -sL --max-time 80 -o "$out" "$url" && [ -s "$out" ]; then
    echo "     成功 ($(stat -c%s "$out") 字节)"
    return 0
  fi
  echo "     失败"
  return 1
}

echo "==> 下载 acme.sh 源码包"
ok=0
fetch "gh-proxy"  "https://gh-proxy.com/https://github.com/acmesh-official/acme.sh/archive/refs/heads/master.tar.gz" /root/acme.tar.gz && ok=1
if [ $ok -eq 0 ]; then
  fetch "gitee"   "https://gitee.com/neilpang/acme.sh/repository/archive/master.tar.gz" /root/acme.tar.gz && ok=1
fi
if [ $ok -eq 0 ]; then
  fetch "jsdelivr acme.sh 单文件" "https://cdn.jsdelivr.net/gh/acmesh-official/acme.sh@master/acme.sh" /root/acme.tar.gz && ok=2
fi

if [ $ok -eq 0 ]; then
  echo "[fatal] 所有通道均失败" >&2
  exit 1
fi

if [ $ok -eq 1 ]; then
  tar xzf /root/acme.tar.gz -C /root
  mv /root/acme.sh-master "$SRC"
  echo "==> 从源码包安装"
  cd "$SRC"
  ./acme.sh --install --home /root/.acme.sh --accountemail "admin@songzuo.online" 2>&1 | tail -4
else
  echo "==> 单文件模式安装"
  mkdir -p /root/.acme.sh
  cp /root/acme.tar.gz /root/.acme.sh/acme.sh
  chmod +x /root/.acme.sh/acme.sh
  /root/.acme.sh/acme.sh --install --home /root/.acme.sh --accountemail "admin@songzuo.online" 2>&1 | tail -4 || true
fi

echo "==> 版本"
/root/.acme.sh/acme.sh --version

echo "==> 默认 CA 设为 Let's Encrypt"
/root/.acme.sh/acme.sh --set-default-ca --server letsencrypt
