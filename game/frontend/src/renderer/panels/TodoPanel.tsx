import { useState } from "react";
import { useGameStore, pick, type PanelKind } from "../store/gameStore";
import { getApiClient } from "../api/client";
import { asStr, clampPct } from "../utils/format";

// 在办事务（P1-1「长期事务 × 圣旨支持模型」的前端呈现）
//
// 后端单点：`core/longterm_task.py` 已把面板需要的全部读数算好并随快照下发
// （`task.readout`：支持方/阻力方/当前阻碍/下月预判/最近因果变化/圣旨留痕）。
// **前端只渲染、不复制任何算法**（口径单点：算法在 core，端点薄壳）。
//
// 玩家必须能回答五问（审查任务书 P1-1 验收 5）：
//   ① 事务要达成什么 → goal / success_condition
//   ② 需要谁支持     → supporters（含"按哪条声明得出"的理由）
//   ③ 当前阻力/缺口  → opposers + obstruction.blockers
//   ④ 哪道圣旨产生了什么变化 → decree_history + last_change
//   ⑤ 下月可能如何推进 → forecast
type Dict = Record<string, unknown>;

/** 非有限数一律 null（缺失 → 显示"未定义"，**不回退 0/1**）。 */
function asNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function dict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function list(v: unknown): Dict[] {
  return Array.isArray(v) ? (v as Dict[]).filter((x) => x && typeof x === "object") : [];
}
function mult(v: number | null): string {
  return v === null ? "未定义" : `×${v.toFixed(2)}`;
}

/** 三种颁旨方式（成本/通道/支持增量差异的**说明**在此；数值单点在 `core/longterm_task`）。 */
const KINDS: { key: string; label: string; hint: string }[] = [
  { key: "督行", label: "督行诏", hint: "常规督责：皇威 −1，占诏令带宽" },
  { key: "调兵督行", label: "调兵督行", hint: "民政事务调兵强制施行：皇威 −2，本月军队通道参与（加成）" },
  { key: "御笔中旨", label: "御笔中旨", hint: "绕过会签：皇威 −3，走密旨通道，官场支持增量更小" },
];

function Chip({ name, influence, reason, tone }: {
  name: string; influence: number | null; reason: string; tone: "sup" | "opp";
}) {
  return (
    <span
      title={reason}
      className={`inline-flex items-baseline gap-1 rounded border px-1.5 py-0.5 text-[11.5px] ${
        tone === "sup"
          ? "border-[#5c7a4a]/50 bg-[#eef3e6] text-[#3f5730]"
          : "border-red/40 bg-red/10 text-red"
      }`}
    >
      <span className="font-medium">{name}</span>
      <span className="text-dim">{influence === null ? "—" : influence}</span>
    </span>
  );
}

export default function TodoPanel({ props }: { props?: Dict }) {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const pushUiLog = useGameStore((s) => s.pushUiLog);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  // 初始页签可由浮层 props 指定（`pushOverlay({kind:"todo", props:{tab:"secret"}})`；
  // 截图台也用同一入口渲染密令页，保证"截图的是真实组件"而非另写一份 mock 视图）。
  const [tab, setTab] = useState<"public" | "secret">(props?.tab === "secret" ? "secret" : "public");
  const [busy, setBusy] = useState<string>("");
  const [result, setResult] = useState<string>("");

  const issues = pick<Dict[]>(state, tab === "public" ? "longterm_public" : "longterm_secret", []);

  async function issue(taskId: string, kind: string, name: string) {
    if (busy) return;
    setBusy(`${taskId}:${kind}`);
    setResult("");
    try {
      const res = await getApiClient().action("issue_task_decree", { task_id: taskId, kind });
      if (res.state) setState(res.state);
      const msg = res.message || "已下旨（后端未返回说明，请以事务面板变化为准）。";
      setResult(msg);
      pushUiLog(`〔${name}〕${msg}`);
    } catch (e) {
      // 非幂等端点：绝不自动重试（可能已 commit）
      setResult(`颁旨未成：${e instanceof Error ? e.message : String(e)}（未自动重试）`);
    } finally {
      setBusy("");
    }
  }

  const openers: { kind: PanelKind; title: string; label: string }[] = [
    { kind: "decree", title: "拟旨", label: "拟旨下诏" },
    { kind: "ministers", title: "群臣", label: "召对群臣" },
    { kind: "pending", title: "朱批待阅", label: "朱批待阅" },
    { kind: "governance", title: "治务枢纽", label: "治务枢纽" },
  ];

  return (
    <div className="space-y-4">
      {/* 页签 */}
      <div className="flex items-center gap-2">
        {([["public", "公 开 事 务"], ["secret", "密 令"]] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-lg px-4 py-1.5 font-kai text-sm tracking-widest transition ${
              tab === key ? "bg-red text-paper" : "bg-paper/60 text-red hover:bg-gold-light"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-[12px] text-dim">
          在办 {issues.length} 件
        </span>
      </div>

      {result && (
        <p className="rounded border border-gold/50 bg-paper/60 px-3 py-2 text-[12.5px] leading-relaxed text-ink">
          {result}
        </p>
      )}

      {issues.length === 0 ? (
        <div className="rounded-lg border border-gold/40 bg-paper/50 px-4 py-6 text-center">
          <p className="font-kai text-[15px] text-ink">
            — 暂无在办{tab === "public" ? "公开事务" : "密令"} —
          </p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-dim">
            事务**不会**自己按时间办成：需先立案（下诏/施政），再由相关衙署与派系的支持、
            以及吏治是否通畅共同决定成败。当前没有任何事务在推行，故不会出现在办条目。
          </p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {openers.map((o) => (
              <button
                key={o.kind}
                onClick={() => pushOverlay({ kind: o.kind, title: o.title })}
                className="rounded border border-gold px-3 py-1 font-kai text-[12.5px] text-ink transition hover:bg-gold-light"
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {issues.map((t, i) => {
            const rd = dict(t.readout);
            const name = asStr(t.task_name ?? t.title, "事务");
            const id = asStr(t.id);
            const progress = asNum(t.progress) ?? asNum(rd.progress);   // 审查 D2：缺失不回落 0
            const hasProgress = progress !== null;
            const goal = asStr(rd.goal, asStr(t.goal, asStr(t.summary, "（未记载目标）")));
            const success = asStr(rd.success_condition);
            const org = asStr(rd.org_hint, asStr(t.org_hint, "—"));
            const minister = asStr(rd.minister, asStr(t.minister, "—"));
            const kindWord = asStr(rd.kind, "—");
            const stage = asStr(rd.stage, "在办");
            const supporters = list(rd.supporters);
            const opposers = list(rd.opposers);
            const obstruction = dict(rd.obstruction);
            const blockers = Array.isArray(obstruction.blockers)
              ? (obstruction.blockers as unknown[]).map((x) => asStr(x)).filter(Boolean)
              : [];
            const forecast = dict(rd.forecast);
            const history = list(rd.decree_history);
            const lastChange = asStr(rd.last_change, asStr(t.last_change));
            const outcome = asStr(rd.outcome, "在办");
            const defined = obstruction.defined === true;
            const isSecretRow = tab === "secret";

            return (
              <div
                key={id || i}
                className={`rounded-lg border bg-paper/60 p-3 ${isSecretRow ? "border-[#6b4e16]" : "border-gold/40"}`}
              >
                {/* 标题 + 阶段 */}
                <div className="flex flex-wrap items-baseline gap-2">
                  <p className="font-kai text-[15px] font-bold text-ink">{name}</p>
                  <span className="rounded border border-gold/50 px-1.5 py-0.5 text-[11px] text-dim">
                    {kindWord} · {org}
                  </span>
                  <span className="rounded bg-red/10 px-1.5 py-0.5 text-[11px] text-red">{stage}</span>
                  <span className="ml-auto text-[11.5px] text-dim">
                    承办：{minister}　工期：{asNum(t.months) === null ? "未定义" : `${asNum(t.months)} 月`}
                  </span>
                </div>

                {/* 目标 / 成功条件 */}
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink">目标：{goal}</p>
                {success && (
                  <p className="mt-0.5 text-[12px] leading-relaxed text-dim">成败：{success}</p>
                )}

                {/* 进度（审查 D2：缺失 → 不画条、显示"未定义"，不得显示"推进 0.0%"） */}
                <div className="mt-2 h-2.5 overflow-hidden rounded-full border border-gold/50 bg-[#e0d3b3]">
                  {hasProgress && (
                    <div
                      className="h-full rounded-full bg-red transition-all"
                      style={{ width: `${clampPct(progress)}%` }}
                    />
                  )}
                </div>
                <p className="mt-1 text-[12px] text-dim">
                  {hasProgress ? `推进 ${progress.toFixed(1)}%` : "推进 未定义"}
                  {!defined && <span className="ml-1 text-red">（吏治读数未定义 → 本月不推进）</span>}
                </p>

                {/* 支持方 / 阻力方 */}
                <div className="mt-2 space-y-1">
                  <p className="text-[12px] text-ink-light">
                    支持方：
                    {supporters.length === 0
                      ? <span className="text-dim">{asStr(rd.stance_note, "未声明立场（不编造支持者）")}</span>
                      : supporters.slice(0, 4).map((s) => (
                          <Chip key={asStr(s.name)} name={asStr(s.name)} influence={asNum(s.influence)}
                                reason={asStr(s.reason)} tone="sup" />
                        ))}
                  </p>
                  <p className="text-[12px] text-ink-light">
                    阻力方：
                    {opposers.length === 0
                      ? <span className="text-dim">无</span>
                      : opposers.slice(0, 4).map((o) => (
                          <Chip key={asStr(o.name)} name={asStr(o.name)} influence={asNum(o.influence)}
                                reason={asStr(o.reason)} tone="opp" />
                        ))}
                  </p>
                </div>

                {/* 当前阻碍 */}
                <div className="mt-2 rounded border border-border/70 bg-paper/70 px-2 py-1.5">
                  <p className="text-[12px] font-medium text-ink-light">
                    当前阻碍（执行能力 {mult(asNum(obstruction.clerks_mult))}
                    {asNum(obstruction.civil_mult) !== null && ` · 民心/识字率 ${mult(asNum(obstruction.civil_mult))}`}
                    {asNum(obstruction.army_mult) !== null && ` · 军队 ${mult(asNum(obstruction.army_mult))}`}
                    {obstruction.military_applies === false && " · 军队未参与"}）
                  </p>
                  {blockers.length > 0 && (
                    <ul className="mt-1 list-inside list-disc space-y-0.5 text-[11.5px] leading-relaxed text-dim">
                      {blockers.slice(0, 4).map((b, bi) => <li key={bi}>{b}</li>)}
                    </ul>
                  )}
                </div>

                {/* 下月预判 + 最近因果变化 */}
                <p className="mt-2 text-[12.5px] leading-relaxed text-ink">
                  下月预判：{asStr(forecast.text, "无读数")}
                </p>
                {lastChange && (
                  <p className="mt-1 text-[12px] leading-relaxed text-ink-light">最近变化：{lastChange}</p>
                )}

                {/* 圣旨留痕 */}
                {history.length > 0 && (
                  <div className="mt-2">
                    <p className="text-[12px] font-medium text-ink-light">圣旨留痕（最近 {Math.min(3, history.length)} 道）</p>
                    <ul className="mt-0.5 space-y-0.5">
                      {history.slice(-3).reverse().map((h, hi) => (
                        <li key={hi} className={`text-[11.5px] leading-relaxed ${h.executed === true ? "text-[#3f5730]" : "text-red"}`}>
                          第 {asNum(h.turn) ?? "?"} 回合「{asStr(h.title)}」（{asStr(h.kind)}，督责{asStr(h.target)}）：
                          {asStr(h.note)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 操作：颁旨影响支持与阻力（≠ 保证成功） */}
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-border/60 pt-2">
                  {outcome !== "在办" && (
                    <span className="text-[11.5px] text-dim">已结案：{outcome}</span>
                  )}
                  {KINDS.map((k) => {
                    // 密令不支持"调兵督行"（后端 `issue_task_decree` 会明确拒绝：会暴露事机）；
                    // 前端必须**禁用并说明**，不能等玩家点了才被驳回。
                    const blockedSecret = isSecretRow && k.key === "调兵督行";
                    const disabled = !!busy || outcome !== "在办" || blockedSecret;
                    const tip = blockedSecret
                      ? "密令不可调兵督行（会暴露事机），请改用「督行诏」或「御笔中旨」"
                      : `${k.hint}；施行与否由会签与吏治决定，本诏不保其必成`;
                    return (
                      <button
                        key={k.key}
                        title={tip}
                        disabled={disabled}
                        onClick={() => issue(id, k.key, name)}
                        className="rounded border border-red/50 bg-red/5 px-2.5 py-1 text-[12px] text-red transition hover:bg-red/15 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {busy === `${id}:${k.key}` ? "颁旨中…" : k.label}
                      </button>
                    );
                  })}
                  <span className="text-[11px] text-dim">颁旨只改支持/阻力，成事仍看吏治与执行</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
