# 《宋祚》(Songzuo) 项目仓库

> 宋代经营模拟游戏。**Python 内核**（`game/`）＋ **Electron/React 前端**（`game/frontend/`）
> ＋ **Rust 并行后端**（`songzuo_server/`）。本 README 是**仓库级**说明；
> 游戏本体的分层规范与模块清单见 [`game/README.md`](game/README.md)。

---

## 一、目录结构

| 目录 | 内容 |
|---|---|
| `game/` | **游戏本体**：`core/`（结算内核，月度 12+ 步）、`content/`（数值/文案/大臣/地理等数据）、`engine/`（AI 契约应用层）、`ai/`（叙事客户端）、`backend/`（本地 server/client 抽象）、`frontend/`（Electron+React 界面）、`pytest.ini` |
| `songzuo_server/` | **Rust 后端**（`src/`：月度结算的并行实现与平价校验），`cargo test --offline` |
| `_dev_tools/` | 开发与文档：`game-dev/tests/`（**测试套件**）、`game-docs/`（文档）、`game-assets-src/`（立绘等资产管线）、`songzuo-game-studio/`（专家团目录） |
| `_scratch/` | 临时区（**不入库**，`.gitignore` 忽略） |
| `start.bat` | 启动脚本（含便携 Node 回退下载） |

文档树（`_dev_tools/game-docs/`）见该目录下的 [README](_dev_tools/game-docs/README.md)：
- `docs/` —— **权威机制文档**（`游戏机制说明.md` 等）；
- `analysis/` —— 分析与设计报告（按主题/日期）；
- `kb/` —— 开发知识库产物；
- `reviews/` —— **归档**：历次全审/复审/规范/交接文档（2026-09-27 从工作区根移入）。

## 二、怎么跑

```powershell
# ① Python 测试：workdir 必须是 sz\game（在仓库根跑会误收集 _scratch/*.py）
cd D:\codebuddy\sz\game
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' -m pytest -p no:cacheprovider -q

# ② Rust 后端测试（cargo 不在 PATH）
cd D:\codebuddy\sz\songzuo_server
& "$env:USERPROFILE\.cargo\bin\cargo.exe" test --offline

# ③ 启动游戏（Electron 前端 + 本地后端）
D:\codebuddy\sz\start.bat
```

## 三、开发纪律（历史教训固化，务必遵守）

1. **POP 挂载律**（用户定稿的硬约束，见 `docs/游戏机制说明.md` §五）：
   ① 凡"人"必须落在六类 POP（`农/士绅/工匠/商人/官僚/兵`）的 `size` 上，不得另立人口账本；
   ② 凡"钱/粮"必须落在某 POP 或国库/内帑，POP 之外只允许 `core/money.py` 作**只读对账**；
   ③ 阶层变动走既有通道且 ΣPOP 守恒；④ 禁平行存量账本；⑤ 每条改动配守恒断言 + 回归测试。
   推论：宗室挂 `士绅.clan`、隐户挂 `农.hidden`（加法子池）、家产挂 `士绅.estate`。
2. **六类清单单一权威源** = `content/data.py::GRAIN_CONSUME_PER_CAPITA`（守卫测试 `test_pop_class_single_source.py`）。
3. **测试基线**：每次改动跑全量 pytest ＋ 相关守恒断言；Rust 侧跑 `cargo test`。
4. **提交信息**：中文，写"背景/改动/验证"三段；用 `git commit -F <file>`（避免 PowerShell 直传中文乱码）。
5. **临时产物**入 `_scratch/`（已 gitignore）；**密钥绝不入库**（`ai_config.json`、`*.agnes_key` 等已 ignore）。

## 四、本仓库近期重点（2026-09-27）

- **POP 体系改良**（对照 P 社 Victoria 3）：多职位岗位槽 → 人口标定（户均 5 口）→ 农的职位/丁口子池
  → 税负分层（役钱按应役丁）→ 隐户生产通道 → 子池月度兜底 → 跨 POP 流动带财富。
  设计与交接见 `_dev_tools/game-docs/analysis/POP改良设计_对照V3_2026-09-27.md`、
  `POP改良纲领_2026-09-27.md`、`交接_POP改良_B05B1_2026-09-27.md`。
- 待办（内容/平衡批）：宋侧岗位容量标定 + S3–S5 建筑链路、Rust 官俸平价的自建局触发、
  P4 的 goods 守恒审计、回归门禁（vitest + CI）。

## 五、体积与历史（2026-09-27 瘦身）

**当前体积**：`game/` 约 1.1 GB —— 其中 `frontend/node_modules` **749 MB 是本机依赖**（0 跟踪文件、
`.gitignore` 已忽略、不入库），"项目本体（源码+入库资产）"不到 400 MB；`.git/` 约 **378 MB**
（同日从 628 MB 压下来）。

**做过什么**：

1. 删可再生产物：`frontend/out`(93MB)、立绘合成缓存 `_composed`(57MB)、`assets/_backup_original`(29MB)、
   全部 `__pycache__`、`.pytest_cache`/`.ruff_cache`、`*.bak`、`.coverage` ＝ **约 190 MB**；
   `git gc` 再压 54 MB。
2. **重写历史**（`git filter-repo --invert-paths`）：
   - 删除 `_scratch/` 的**全部历史**与 `assets/demo-acp.mp4`（约 88 MiB）；
   - 把 **257 个大二进制资产**（≥256KB 的 PNG/geojson/topojson/字体等，当前合计 **402 MB**）
     **重置为单版本** —— 历史里每个资产只留当前一份（此前每次改动都新增一份完整 blob，
     是 483 MiB 历史的主因）；
   - 清理指向旧历史的分支与 remote-tracking refs（`main`、`remotes/*`）→ `git gc --prune=now`。
3. 结果：`.git` 628 MB → **378 MB**（当前历史里"当前版二进制"约 270 MiB + 源码/文档历史约 100 MiB）。

**⚠️ 后果**：**所有 commit hash 已改变** —— 2026-09-27 之前文档/报告里引用的 hash（如 `3d46eee6bb`、
`77e5bd35c4`）**均已失效**，检索历史请依据**提交信息**而非 hash。

**备份（确认无误后可删）**：

| 路径 | 体积 | 用途 |
|---|---|---|
| `D:\codebuddy\_scratch\sz-history-20260927-101448.bundle` | 563.9 MB | 重写前的**完整历史**（`git clone <bundle> <dir>` 可整体恢复） |
| `D:\codebuddy\_scratch\asset-snapshot\` | 401.8 MB | 257 个大资产快照（恢复工作区文件用，内容已提交，可删） |

**防复发**：二进制资产（立绘/地图/字体）每改一次就新增一份 blob，是仓库膨胀的根源。后续应改为
**Git LFS**（`.gitattributes` 指定 `*.png *.jpg *.geojson *.topojson *.ttf *.mp4`），
或把大资产**移出 git**（只留工作区 + `.gitignore`，随发行包分发）——后者可把 `.git` 压到 100 MB 级。
