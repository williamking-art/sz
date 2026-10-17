import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";

// 统一读数索引面板（P5 第一片 · M84）
//
// 数据来源：后端 `/api/readouts::hub`（= `core/domains/economy/readout_hub.collect`，
// **12 项**只读读数聚合：货币/库存/流量/州府一致性/工坊资金/家计/治所市场/缺工/
// P1 试点链条缺口/P1 主瓶颈/岗位容量…）。
//
// 🔴 纪律（根 AGENTS.md §3-2/§3-3 + 前端 AGENTS.md 禁区）：
//   · 本面板**只呈现，不重算**——所有数字与 `source` 一律直读后端（口径单点）；
//   · **缺失值显式呈现「未定义」**：后端契约是 `display === "undefined"`，
//     面板**不得回落 0**；有 `reason` 时一并展示（让玩家知道"为什么读不到"）；
//   · `drill_down` 只在用户点开时展示（读数**能下钻到来源**）。

type Row = {
  label: string;
  value: unknown;
  display: string;
  unit: string;
  source: string;
  drill_down?: unknown;
  reason?: string | null;
};
type Hub = {
  readouts?: Record<string, Row>;
  ok_count?: number;
  undefined_count?: number;
  note?: string;
};

/** 有值 ⇒ 原样展示（后端已给字符串）；不可读 ⇒ **「未定义」占位**（绝不显示 0）。
 *
 * 抽成**可测纯函数**：后端契约是 `display === "undefined"`，此处是**唯一**的展示映射点
 * （前端不重算、不造默认值）。 */
export function hubRowText(row: Pick<Row, "display">): string {
  return row.display === "undefined" ? "未定义" : row.display;
}

function DisplayText({ row }: { row: Row }) {
  if (row.display === "undefined") {
    return <span className="text-dim" title={row.reason ?? "后端未给出原因"}>未定义</span>;
  }
  return <span>{row.display}</span>;
}

export default function ReadoutHubPanel() {
  const [hub, setHub] = useState<Hub | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  // 🔴 M246（Jev 甲 0.737「明确失败提示 + 重试」）：`tick` 只用于**重新触发取数**。
  //   ⚠️ 前半（明确失败提示）本面板 **M84 已实现**；本次补的是**重试**。
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (!alive) return;
        setHub((res as unknown as { hub?: Hub }).hub ?? null);
      } catch (e) {
        console.error("[readouts:hub]", e);
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, [tick]);

  if (err) {
    return (
      <div className="space-y-2 py-6 text-center">
        <p className="text-[13px] text-dim">
          读数不可用（端点 <code>/api/readouts</code> 未响应或失败）：{err}
        </p>
        <button
          type="button"
          className="rounded border border-white/15 px-3 py-1 text-[13px] hover:bg-white/10"
          onClick={() => {
            // 重试：先清失败态（回到「正在读取」），再触发一次取数
            setErr(null);
            setHub(null);
            setTick((t) => t + 1);
          }}
        >
          重试
        </button>
        <p className="text-[11px] text-dim">
          说明：本面板**只读**后端读数（口径单点，前端**不重算、不用 store 兜底造数**）；
          缺失一律显示「未定义」。
        </p>
      </div>
    );
  }
  if (!hub) {
    return (
      <p className="flex items-center justify-center gap-2 py-6 text-[13px] text-dim">
        <Loader2 className="h-4 w-4 animate-spin" /> 正在读取统一读数索引…
      </p>
    );
  }
  const rows = Object.entries(hub.readouts ?? {});

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">统一读数索引（{rows.length} 项）</h3>
        <span className="text-[12px] text-dim">
          有值 {hub.ok_count ?? 0} · 未定义 {hub.undefined_count ?? 0}
        </span>
      </div>
      {hub.note ? <p className="text-[12px] text-dim">{hub.note}</p> : null}
      {hub.readouts?.court_vs_system_contrast ? (
        <div className="rounded border border-amber-500/30 bg-amber-950/20 p-2.5 text-[12px] text-amber-200/90">
          <div className="font-semibold text-amber-300">
            🏛️ 朝廷层度支 vs 🌐 系统层物理账目严格分离（硬约束口径）
          </div>
          <div className="mt-1 text-[11px] leading-relaxed text-amber-200/70">
            朝廷层（国库/内帑/太仓）仅为朝廷直接掌握头寸；民间 POP 财富与治所府库为百姓与地方存留，非朝廷可用款。
            当前读数：{hub.readouts.court_vs_system_contrast.display}
          </div>
        </div>
      ) : null}
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-dim">
            <th className="py-1">读数</th>
            <th className="py-1">值</th>
            <th className="py-1">单位</th>
            <th className="py-1">来源（可下钻）</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, row]) => (
            <tr
              key={key}
              className="cursor-pointer border-t border-white/5 hover:bg-white/5"
              onClick={() => setOpenKey(openKey === key ? null : key)}
              title="点开查看下钻明细"
            >
              <td className="py-1 pr-2">{row.label}</td>
              <td className="py-1 pr-2 font-mono">
                <DisplayText row={row} />
              </td>
              <td className="py-1 pr-2 text-dim">{row.unit}</td>
              <td className="py-1 text-dim">
                {key}
                {row.reason ? <div className="text-[11px]">原因：{row.reason}</div> : null}
                {openKey === key ? (
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/30 p-2 text-[11px]">
                    {JSON.stringify(row.drill_down ?? { source: row.source }, null, 2)}
                  </pre>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-dim">
        只读索引：数字与来源一律直读后端（口径单点，前端不重算）；**缺失一律显示「未定义」，不回落 0**。
      </p>
    </div>
  );
}
