# `game-dev/` · Python 开发辅助

本目录含测试工具、回归用例、平衡分析、回放占位和运维脚本，不随游戏运行。

## 子目录

| 路径 | 用途 |
|---|---|
| [`tests/`](tests/README.md) | Python 测试入口；测试目录状态与命令见其 README。 |
| [`analytics/`](analytics/README.md) | 平衡指标分析脚本。 |
| [`replay/`](replay/README.md) | 回放工具目录；是否已有可用实现以目录内容为准。 |
| [`scripts/`](scripts/README.md) | 数据库维护和知识库观察等辅助脚本。 |
| `skill/` | 本地开发辅助资料，内容/体积不作为游戏发行依赖。 |

## 同级工具

`requirements-dev.txt` 是开发依赖清单；`verify_ai_connect.py` 和 `verify_refactor.py` 是工作区校验脚本。`build_exe.py`、`_split_*.py`、`SongZuo.spec` 等历史辅助文件位于 `_dev_tools/` 根或其他位置，不是本目录的当前唯一打包入口；后端冻结规格以 [`game/SongZuo.spec`](../../game/SongZuo.spec) 为准。

## 回归命令

从仓库根运行，使用工作区 Python 环境时：

```powershell
$py = "..\.audit-venv\Scripts\python.exe"
$env:PYTHONPATH = ""
$env:CODEBUDDY_SAFE_DELETE_ENABLED = "0"
& $py -m pytest _dev_tools/game-dev/tests -p no:cacheprovider
```

具体环境前置、pytest 配置和长时用例说明见 [`tests/README.md`](tests/README.md) 及 [`../game-docs/docs/开发服务器与回归测试说明.md`](../game-docs/docs/开发服务器与回归测试说明.md)。不要把某次运行的通过数量写成永久基线。
