# foundation/state — GameState 与状态字段注册

> 🔴 **当前为空骨架（0 个实现文件）**。阶段 0 建的目录，尚未迁入任何模块。
> 写「当前事实」而非计划：这里**现在什么都没有**，不要以为 GameState 在这里。

## 现状

```
__init__.py   仅 docstring
```

GameState 本体仍在 `core/game_state.py`。

## 🔴 若将来迁入，须注意

- `game_state.py` 是 §五 登记的**反向边现场**之一（对 `ensure_hidden_in_pops`、
  `core.officialdom` 的引用），且实测它 10 个异常处理体里曾有 **6 个纯 `pass`、0 个记日志**。
  迁移时**异常必须 `logging.warning(..., exc_info=True)` 留痕**，
  且要有「结果非空/守恒成立」的**哨兵断言**（不只留痕）。
- `game_state.py` 取**私有名**（如 `ensure_hidden_in_pops` 之外的模块私有符号）⇒
  迁入后桩面必须仍含私有符号，否则 `ImportError`。
