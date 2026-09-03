# -*- coding: utf-8 -*-
"""宋祚 · 语义模型下载器（B2 一次性工具）

把 BAAI/bge-small-zh-v1.5 的 ONNX 版下载到
assets/models/bge-small-zh-v1.5/{model.onnx, tokenizer.json}，
供 ai/semantic.py 使用。

用法（需先 pip install huggingface_hub，见 requirements-extras.txt）：
    python -m ai.model_setup

说明：
- ONNX 版取自 Xenova/bge-small-zh-v1.5（transformers.js 导出，含 tokenizer.json）；
- 约 90MB；下载一次即可，随包分发或用户首启下载均可；
- 下载失败不影响游戏：semantic.py 会自动降级为字面检测。
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    d = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(os.path.dirname(d), "assets", "models", "bge-small-zh-v1.5")
    os.makedirs(target, exist_ok=True)
    files = [
        ("Xenova/bge-small-zh-v1.5", "onnx/model.onnx", "model.onnx"),
        ("Xenova/bge-small-zh-v1.5", "tokenizer.json", "tokenizer.json"),
    ]
    try:
        from huggingface_hub import hf_hub_download
    except Exception:
        print("[model_setup] 缺少 huggingface_hub：请先 pip install huggingface_hub")
        print("           （见 requirements-extras.txt；不装则语义层自动降级，游戏不受影响）")
        return 1
    for repo, src, dst in files:
        dest_path = os.path.join(target, dst)
        if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
            print(f"[model_setup] 已存在，跳过: {dst}")
            continue
        print(f"[model_setup] 下载 {repo}:{src} ...")
        try:
            p = hf_hub_download(repo_id=repo, filename=src)
            import shutil
            shutil.copyfile(p, dest_path)
            print(f"[model_setup] 完成: {dest_path}")
        except Exception as e:
            print(f"[model_setup] 下载失败 {src}: {e}")
            return 1
    print("[model_setup] 全部就绪。语义防复读/记忆检索已启用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
