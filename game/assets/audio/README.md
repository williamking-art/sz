# assets/audio · 音频资源

> 层归属：**游戏本体**（美术/音频资源层）。

## 现状
- 目录内目前只有 `.gitkeep`（**占位**）：音频具体内容由运行期槽位登记驱动；
- 槽位登记与播放逻辑在 `game/audio/manifest.py`（槽位定义）与 `game/audio/tts.py`（朗读，**播放未接线**）。

## 关联
- 打包：`SongZuo.spec` 的 datas 白名单**未包含**本目录（当前无实际音频文件）；
  将来加入音频文件时，需同时更新 spec 白名单与 `game/audio/manifest.py`。
---
最后更新：2026-09-27（补目录文档）
