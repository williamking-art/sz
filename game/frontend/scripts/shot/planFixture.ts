// 截图台 plan fixture（**仅 dev 用**）——由**真实后端口径单点**产出，非手写：
//   `core.plan_readout.build_plan_readout(state)`（`backend/server.py:817` 的同源调用；
//   state = commands.new_game()，seed=20261013，先跑 6 个月结算）。
//   ⚠️ 重新生成见本目录 README；**不要手改数字**（口径单点）。生成日期：2026-10-14（M272）

export const PLAN = {
  "phases": {
    "accepted": [],
    "advancing": [],
    "completed": [],
    "effective": []
  },
  "phase_labels": {
    "accepted": "旨意受理",
    "advancing": "执行推进",
    "completed": "工程告成",
    "effective": "效果生效"
  },
  "projects": [],
  "unsupported_tasks": [],
  "unresolved": [],
  "counts": {
    "unsupported_total": 0,
    "runtime_yield": 0.0,
    "accepted": 0,
    "advancing": 0,
    "completed": 0,
    "effective": 0,
    "projects": 0,
    "dynamic_blueprints": 0
  }
};
