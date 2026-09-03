# -*- coding: utf-8 -*-
"""
《宋祚》Agnes AI 官方图像生成客户端（对接最新 agnes-image-2.5-flash 规范）

用于美术 TA（惠宋韵）批量生成北宋大臣立绘、历史事件插画、宋式 UI 纹样。
产物安全落盘至 _scratch/generated-images/，符合专家团工程规范（试验稿绝不直接进 assets/）。

官方文档: https://www.agnes-ai.com/zh-Hans/docs/agnes-image-25-flash#请求示例
Base URL: https://apihub.agnes-ai.com
Endpoint: POST /v1/images/generations
Model: agnes-image-2.5-flash

用法:
    # 1. 命令行快速文生图
    python _dev_tools/agnes_gen.py --prompt "北宋重臣蔡京朝服画像，宋代院体工笔，工笔绢本设色" --ratio 3:4 --size 2K

    # 2. 生成历史事件插图
    python _dev_tools/agnes_gen.py --prompt "北宋宣和年间方腊起义，江南水乡战火，宋代山水画风格，水墨青绿" --ratio 16:9 --size 2K -o fangla.png
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

# 根目录与安全落盘目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_IMG_DIR = os.path.join(BASE_DIR, "_scratch", "generated-images")

API_URL = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_MODEL = "agnes-image-2.5-flash"


def get_api_key() -> str:
    """获取 API Key，优先级：环境变量 AGNES_API_KEY > game/ai_config.json > 命令行。"""
    key = os.environ.get("AGNES_API_KEY")
    if key:
        return key.strip()

    # 尝试读取 game/ai_config.json
    cfg_path = os.path.join(BASE_DIR, "game", "ai_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                key = cfg.get("agnes_api_key") or cfg.get("image_api_key")
                if key:
                    return str(key).strip()
        except Exception:
            pass

    return ""


def generate_image(
    prompt: str,
    api_key: str | None = None,
    size: str = "2K",
    ratio: str = "1:1",
    model: str = DEFAULT_MODEL,
    output_filename: str | None = None,
    proxy: str | None = "http://127.0.0.1:7890",
) -> str | None:
    """调用 agnes-image-2.5-flash 生成图片并下载保存至 _scratch/generated-images/。

    参数:
        prompt: 提示词描述
        api_key: Agnes API 密钥
        size: "1K" | "2K" | "3K" | "4K"
        ratio: "1:1" | "3:4" | "4:3" | "16:9" | "9:16" | "2:3" | "3:2" | "21:9"
        model: 固定为 agnes-image-2.5-flash
        output_filename: 保存文件名（缺省按时间戳命名）
        proxy: HTTP 代理地址（默认使用本地 7890 端口加速）

    返回:
        本地保存的图片绝对路径，失败返回 None。
    """
    key = api_key or get_api_key()
    if not key:
        print("[错误] 未配置 AGNES_API_KEY！请在环境变量中设置或传入 --key 参数。")
        print("      示例: set AGNES_API_KEY=your_key 或 python _dev_tools/agnes_gen.py --key your_key ...")
        return None

    os.makedirs(SCRATCH_IMG_DIR, exist_ok=True)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Songzuo-Game-Studio/1.0 (Agnes-Image-Client)",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "ratio": ratio,
        "extra_body": {
            "response_format": "url",
        },
    }

    req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API_URL, data=req_data, headers=headers, method="POST")

    # 配置代理
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        opener = urllib.request.build_opener()

    print(f"[Agnes AI] 正在发起生图请求: 模型={model}, 尺寸={size}, 比例={ratio}")
    print(f"[Agnes AI] 提示词: {prompt[:60]}...")

    start_t = time.time()
    try:
        with opener.open(req, timeout=90) as resp:
            resp_bytes = resp.read()
            resp_json = json.loads(resp_bytes.decode("utf-8"))
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8", errors="ignore")
        print(f"[Agnes AI] API 请求失败 HTTP {err.code}: {err_msg}")
        return None
    except Exception as exc:
        print(f"[Agnes AI] 网络请求异常: {exc}")
        return None

    elapsed = time.time() - start_t
    print(f"[Agnes AI] 模型生成成功，耗时 {elapsed:.1f}s")

    # 提取生成的图片 URL
    data_list = resp_json.get("data", [])
    if not data_list or not data_list[0].get("url"):
        print(f"[Agnes AI] 响应中未包含图片 URL: {resp_json}")
        return None

    img_url = data_list[0]["url"]
    print(f"[Agnes AI] 图片已就绪，正在下载: {img_url[:60]}...")

    if not output_filename:
        ts = int(time.time())
        output_filename = f"agnes_{ts}_{ratio.replace(':', 'x')}.png"

    dest_path = os.path.join(SCRATCH_IMG_DIR, output_filename)

    try:
        img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(img_req, timeout=60) as img_resp:
            with open(dest_path, "wb") as f_out:
                f_out.write(img_resp.read())
        print(f"[Agnes AI] 下载并安全保存至: {dest_path}")
        return dest_path
    except Exception as dl_err:
        print(f"[Agnes AI] 下载图片失败: {dl_err}")
        print(f"           请手动从 URL 获取: {img_url}")
        return img_url


def main():
    parser = argparse.ArgumentParser(description="宋祚 Agnes AI 生图工具 (agnes-image-2.5-flash)")
    parser.add_argument("--prompt", "-p", required=True, help="图片生成提示词")
    parser.add_argument("--ratio", "-r", default="1:1", choices=["1:1", "3:4", "4:3", "16:9", "9:16", "2:3", "3:2", "21:9"], help="宽高比")
    parser.add_argument("--size", "-s", default="2K", choices=["1K", "2K", "3K", "4K"], help="清晰度档位")
    parser.add_argument("--key", "-k", help="Agnes API Key (缺省从环境变量 AGNES_API_KEY 获取)")
    parser.add_argument("--output", "-o", help="输出文件名 (保存至 _scratch/generated-images/)")
    parser.add_argument("--no-proxy", action="store_true", help="禁用本地 7890 代理")

    args = parser.parse_args()
    proxy = None if args.no_proxy else "http://127.0.0.1:7890"

    saved = generate_image(
        prompt=args.prompt,
        api_key=args.key,
        size=args.size,
        ratio=args.ratio,
        output_filename=args.output,
        proxy=proxy,
    )
    if saved:
        print(f"\n[完成] 产物已安全落盘: {saved}")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
