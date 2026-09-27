# _dev_tools/ ——《宋祚》开发工具与文档

> 本目录是项目内**非运行时**内容：测试套件、文档、资产管线、专家团目录。
> 注意 `.gitignore` 的策略是"**只放行明确列出的子目录**"（历史上有大量一次性脚本与
> skill 大目录，故默认 `_dev_tools/*` 不入库）——新增要入库的东西，记得同时改 `.gitignore`。

| 子目录/文件 | 内容 | 入库？ |
|---|---|---|
| **`game-dev/tests/`** | **测试套件**（`game/pytest.ini` 的 `testpaths` 指向此处） | ✅ 入库 |
| `game-dev/requirements-dev.txt` | 测试依赖清单 | ✅ |
| `game-dev/skill/`、`analytics/`、`replay/`、`scripts/`、`build_exe.py`、`SongZuo.spec` | 开发辅助（部分已过时/体量大） | ❌ 默认不入库 |
| **`game-docs/`** | **文档树**（`docs/` 权威机制、`analysis/` 分析、`kb/` 知识库、`reviews/` 归档）——见其 [README](game-docs/README.md) | ✅ 入库 |
| `game-assets-src/` | **立绘/资产管线源脚本与源图**（2026-09-26 从 `game/content/` 迁出：避免随 PyInstaller 打包进分发版） | ✅ 入库 |
| `songzuo-game-studio/` | 专家团目录（工作目录，体积大） | ✅ 部分入库 |
| `agnes_gen.py` | Agnes 图像/文本生成脚本 | ✅ |
| `dev-env.ps1`、`cloudbase-check.ps1` | 开发环境脚本；**工具链自检脚本**（把历次踩坑变成一条 PASS/FAIL 命令，`-Fix` 可自动修） | ✅ |
| `_scratch/` | 临时区 | ❌ |

## 常用

```powershell
# 工具链自检（PASS/FAIL，可 -Fix）
pwsh -File D:\codebuddy\sz\_dev_tools\cloudbase-check.ps1

# 知识库重建（产物 kb/dev_kb.sqlite 不入库）
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\game-docs\kb\build_kb.py
```

## 纪律

1. **测试入口唯一**：`game-dev/tests/`（别在别处新建测试目录）；
2. **临时脚本放 `_scratch/`**（已 gitignore），不要留在 `_dev_tools/` 顶层；
3. **工具链踩坑要固化**：新踩的坑请加进 `cloudbase-check.ps1` 或对应文档，而不是只在会话里修一次。
