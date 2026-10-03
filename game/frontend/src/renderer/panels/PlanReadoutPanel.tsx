import { useGameStore } from "../store/gameStore";

/**
 * 计划/工程因果回看（规格 decree-action-chain 任务 6）。
 *
 * 纪律：**只渲染 `/api/readouts` 的 `plan` 字段**（core/plan_readout.py 单点派生），
 * 前端**不复制任何算法**——进度、产能、产出、层级文案全部来自后端。
 *
 * 四层级**分开展示**（不得混写）：旨意受理 / 执行推进 / 工程告成 / 效果生效。
 * 「议毕但无程序侧落点」的事务单列一块，明确标为**待支持**（不得显示为已告成）。
 */

const PHASE_ORDER = ["accepted", "advancing", "completed", "effective"] as const;

const PHASE_HINT: Record<string, string> = {
  accepted: "已受理，尚未动工",
  advancing: "在办（政治推进轨道，非效果开关）",
  completed: "工程已告成",
  effective: "产出已生效",
};

export default function PlanReadoutPanel({ route }: { route?: string }) {
  const readouts = useGameStore((s) => s.readouts);
  const plan = readouts?.plan;

  if (!plan) {
    return (
      <div className="px-3 py-2 text-xs text-amber-200/60">
        计划读数未下发（后端 readouts 可能派生失败）——不以空白冒充“无工程”。
      </div>
    );
  }

  const labels = plan.phase_labels || {};
  // `route` 给定时**四层级与台账一并过滤**（否则按路看时层级里仍混着别路的条目）
  const forRoute = <T extends { route?: string }>(items: T[]): T[] =>
    route ? items.filter((it) => it.route === route) : items;
  const projects = (plan.projects || []).filter((p) => !route || p.route === route);
  const unsupported = plan.unsupported_tasks || [];

  return (
    <div className="space-y-2 text-xs">
      {/* ---- 四层级：分列，互不混写 ---- */}
      <div className="grid grid-cols-2 gap-2">
        {PHASE_ORDER.map((k) => {
          const items = forRoute(plan.phases?.[k] || []);
          return (
            <div key={k} className="rounded border border-amber-700/40 bg-black/20 p-2">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-semibold text-amber-200">
                  {labels[k] || k}
                </span>
                <span className="text-amber-200/50">{items.length}</span>
              </div>
              <div className="text-[10px] text-amber-200/40">{PHASE_HINT[k]}</div>
              <ul className="mt-1 space-y-0.5">
                {items.slice(0, 5).map((it, i) => (
                  <li key={`${k}-${i}`} className="truncate text-amber-100/80">
                    {it.route ? `${it.route}·` : ""}
                    {it.title}
                    {typeof it.progress === "number" && k === "advancing"
                      ? ` ${it.progress}%`
                      : ""}
                  </li>
                ))}
                {items.length === 0 && (
                  <li className="text-amber-200/30">（无）</li>
                )}
              </ul>
            </div>
          );
        })}
      </div>

      {/* ---- 逐地点工程：状态/进度/产能/产出/来源 ---- */}
      {projects.length > 0 && (
        <div className="rounded border border-amber-700/40 bg-black/20 p-2">
          <div className="mb-1 font-semibold text-amber-200">
            工程台账（{projects.length}）
          </div>
          <table className="w-full text-left text-[11px]">
            <thead className="text-amber-200/50">
              <tr>
                <th className="pr-2">地点·名称</th>
                <th className="pr-2">状态</th>
                <th className="pr-2">进度</th>
                <th className="pr-2">产能</th>
                <th>产出</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.pid} className="text-amber-100/80">
                  <td className="pr-2 truncate">
                    {p.route}·{p.name}
                    {p.dynamic && (
                      <span className="ml-1 rounded bg-amber-800/40 px-1 text-[9px]">
                        旨意
                      </span>
                    )}
                  </td>
                  <td className="pr-2">{p.status_label}</td>
                  <td className="pr-2">{p.progress}%</td>
                  <td className="pr-2">
                    {p.status === "operating" || p.status === "degraded"
                      ? `${Math.round((p.capacity || 0) * 100)}%`
                      : "—"}
                  </td>
                  <td className="truncate">
                    {[
                      ...Object.keys(p.output || {}),
                      ...Object.keys(p.runtime || {}).map((x) => `${x}/月`),
                    ].join("、") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---- 待支持：议毕但无程序侧落点（**不是**告成）---- */}
      {unsupported.length > 0 && (
        <div className="rounded border border-orange-600/50 bg-orange-950/30 p-2">
          <div className="mb-1 font-semibold text-orange-300">
            议毕但未绑定程序侧落点 · 待支持（{unsupported.length}）
          </div>
          <div className="mb-1 text-[10px] text-orange-200/60">
            这些事项进度已满，但没有任何数值随之改变——按规格**不计为告成**。
          </div>
          <ul className="space-y-0.5">
            {unsupported.slice(0, 5).map((u, i) => (
              <li key={`u-${i}`} className="truncate text-orange-100/80">
                {u.name}
                {u.reason ? `：${u.reason}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
