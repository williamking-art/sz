#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 CloudBase PostgreSQL 中的冗余副本表。

背景：典章知识库已从 CloudBase PG 迁移到本地 SQLite（game/assets/kb/game_kb.sqlite），
云端 PG 中可能残留旧知识库表或临时表。本脚本通过 CloudBase HTTP PG 直连端点列出 public
schema 下的表，默认只报告不删除，确认后再清理。

凭据（优先级从高到低）：
1. 环境变量 TCB_PG_API_KEY
2. <repo>/.cloudbase/pg_api_key.txt

用法：
    # 只列出候选冗余表（ dry-run ）
    python _dev_tools/game-dev/scripts/cleanup_cloudbase_pg.py

    # 真正删除（先会再确认一次列表）
    python _dev_tools/game-dev/scripts/cleanup_cloudbase_pg.py --apply

    # 把某个表加入保留白名单
    python _dev_tools/game-dev/scripts/cleanup_cloudbase_pg.py --keep legacy_logs
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.request
from typing import List, Optional


ROOT = pathlib.Path(__file__).resolve().parents[3]  # sz/
PROJECT_JSON = ROOT / ".cloudbase" / "project.json"
API_KEY_FILE = ROOT / ".cloudbase" / "pg_api_key.txt"

# 当前仍需要保留的业务表（经济对账 / CI 遥测）；其余表均视为候选冗余。
DEFAULT_KEEP = {"dev_ci_runs", "dev_econ_monthly"}


def load_env_id() -> str:
    if not PROJECT_JSON.exists():
        sys.exit(f"未找到项目配置：{PROJECT_JSON}")
    data = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
    env_id = data.get("envId") or data.get("environmentId") or data.get("env_id")
    if not env_id:
        sys.exit(f"{PROJECT_JSON} 中未找到 envId")
    return env_id


def load_api_key() -> str:
    key = os.environ.get("TCB_PG_API_KEY", "").strip()
    if key:
        return key
    if API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(
            "缺少 CloudBase PG 管理员 API Key。\n"
            "请设置环境变量 TCB_PG_API_KEY，或写入 .cloudbase/pg_api_key.txt"
        )
    return key


def exec_sql(env_id: str, api_key: str, sql: str, role: str = "cloudbase_postgres") -> dict:
    url = f"https://{env_id}.api.tcloudbasegateway.com/v1/rdb/exec-pgsql"
    payload = json.dumps({"sql": sql, "role": role}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def list_public_tables(env_id: str, api_key: str) -> List[str]:
    sql = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    result = exec_sql(env_id, api_key, sql)
    rows = result.get("data", []) if isinstance(result, dict) else result
    return [row["table_name"] for row in rows]


def drop_tables(env_id: str, api_key: str, tables: List[str]) -> None:
    for table in tables:
        sql = f'DROP TABLE IF EXISTS "{table}" CASCADE'
        print(f"  执行: {sql}")
        exec_sql(env_id, api_key, sql)


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 CloudBase PG 冗余表")
    parser.add_argument("--apply", action="store_true", help="真正删除候选表（默认只报告）")
    parser.add_argument("--keep", action="append", default=[], help="额外保留的表名（可多次）")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    env_id = load_env_id()
    api_key = load_api_key()
    keep = DEFAULT_KEEP | set(args.keep)

    print(f"环境 ID: {env_id}")
    print(f"保留表: {sorted(keep)}")
    print("正在列出 public schema 下所有表...")

    all_tables = list_public_tables(env_id, api_key)
    print(f"  共 {len(all_tables)} 张表: {all_tables}")

    candidates = [t for t in all_tables if t not in keep]
    if not candidates:
        print("未发现候选冗余表，无需清理。")
        return

    print(f"\n候选冗余表（{len(candidates)} 张）: {candidates}")

    if not args.apply:
        print("\n本次为 dry-run，未执行删除。如确认清理，请加 --apply 重跑。")
        return

    print("\n⚠️  即将删除上述候选表，此操作不可恢复！")
    try:
        ans = input("确认删除？请输入 yes 继续: ")
    except EOFError:
        ans = "no"
    if ans.strip().lower() != "yes":
        print("已取消。")
        return

    drop_tables(env_id, api_key, candidates)
    print("\n清理完成。重新列出 public 表...")
    remaining = list_public_tables(env_id, api_key)
    print(f"  剩余 {len(remaining)} 张表: {remaining}")


if __name__ == "__main__":
    main()
