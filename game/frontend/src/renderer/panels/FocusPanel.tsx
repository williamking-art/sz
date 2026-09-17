import { useState } from "react";
import { Loader2, CheckCircle2, Lock, Sparkles, Scroll, Shield, Landmark, FlaskConical, Eye, Coins, Clock, Ban, BookOpen } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import focusTreeData from "../data/focus_tree.json";

type BranchKey = "govern" | "military" | "science" | "internal" | "tax";

const BRANCHES: { key: BranchKey; label: string; icon: React.ReactNode; desc: string }[] = [
  { key: "govern", label: "政务大策", icon: <Landmark size={16} />, desc: "立宪治道，厘正官制，收揽皇权" },
  { key: "military", label: "军政戎备", icon: <Shield size={16} />, desc: "整饬军旅，充实边防，经略北伐" },
  { key: "science", label: "百工格物", icon: <FlaskConical size={16} />, desc: "水运仪象，火器军工，营造算法" },
  { key: "internal", label: "内卫察访", icon: <Eye size={16} />, desc: "设皇城司，弹劾贪墨，清明朝局" },
  { key: "tax", label: "度支税法", icon: <Coins size={16} />, desc: "清丈经界，盐铁官榷，平抑物价" },
];

export default function FocusPanel() {
  const [activeBranch, setActiveBranch] = useState<BranchKey>("govern");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);

  if (!state) {
    return <div className="py-12 text-center font-kai text-sm text-dim">尚未开局，国策虚位以待。</div>;
  }

  // 运行态国策树数据
  const stateTree = (pick<Record<string, unknown>>(state, "focus_tree", {}) || {}) as Record<string, any>;
  const branchData = (focusTreeData as Record<string, any>)[activeBranch] || {};
  const branchNodes = branchData.nodes || {};
  const currentBranchState = stateTree[activeBranch] || {};
  const unlockedNodes = currentBranchState.nodes || {};

  // 当前中枢正在施行的国策
  const activeFocus = (pick<Record<string, unknown>>(state, "active_focus", {}) || {}) as Record<string, any>;
  const hasActiveFocus = activeFocus && activeFocus.status === "in_progress";

  // 统计已解锁进度
  const totalNodesCount = Object.keys(branchNodes).length;
  const unlockedCount = Object.values(unlockedNodes).filter((n: any) => n.unlocked).length;

  async function handleStartFocus(nodeKey: string, nodeName: string) {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().action("start_focus", {
        branch: activeBranch,
        node_key: nodeKey,
      });
      if (res.state) setState(res.state);
      setMsg({ type: "success", text: res.message || `已宣旨施行【${nodeName}】，中枢正式立案！` });
    } catch (e) {
      setMsg({ type: "error", text: "立案施行失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelFocus() {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().action("cancel_focus", {});
      if (res.state) setState(res.state);
      setMsg({ type: "success", text: res.message || "已中止当前在办大策。" });
    } catch (e) {
      setMsg({ type: "error", text: "中止失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[540px] flex-col gap-3">
      {/* 顶部：五维分支 Tab */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex flex-wrap gap-1.5">
          {BRANCHES.map((b) => (
            <button
              key={b.key}
              onClick={() => {
                setActiveBranch(b.key);
                setMsg(null);
              }}
              className={`flex items-center gap-1.5 rounded px-3 py-1.5 font-kai text-sm transition ${
                activeBranch === b.key
                  ? "bg-red text-paper shadow-sm"
                  : "bg-paper/70 text-ink hover:bg-gold-light/40"
              }`}
            >
              {b.icon} {b.label}
            </button>
          ))}
        </div>
        <div className="font-kai text-xs text-goldDark">
          已施行：{unlockedCount} / {totalNodesCount} 策
        </div>
      </div>

      {/* 分支说明横幅 */}
      <div className="flex items-center justify-between rounded-lg border border-gold/40 bg-card/60 px-4 py-2 text-xs">
        <span className="font-kai text-ink/90">{branchData.desc || ""}</span>
        <span className="font-kai text-dim">耗时推演 · 沉淀AI长期记忆</span>
      </div>

      {/* 全局当前在办大策进度通栏（若有） */}
      {hasActiveFocus && (
        <div className="flex items-center justify-between rounded-lg border border-red/40 bg-red/5 px-4 py-2.5 shadow-sm">
          <div className="flex flex-1 items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red text-paper">
              <Clock size={16} className="animate-pulse" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-kai text-xs font-bold text-red">中枢专精在办大策：</span>
                <span className="font-kai text-sm font-bold text-ink">{activeFocus.name}</span>
                <span className="rounded bg-paper px-1.5 py-0.2 font-kai text-[10px] text-dim border border-border">
                  月耗度支 {activeFocus.cost_per_month} 贯
                </span>
                <span className="font-kai text-xs font-semibold text-goldDark">
                  推进进度：{activeFocus.progress || 0}% ({activeFocus.elapsed_turns || 0}/{activeFocus.total_turns || 3}月)
                </span>
              </div>
              {/* 进度条 */}
              <div className="mt-1.5 h-1.5 w-full max-w-[420px] overflow-hidden rounded-full bg-[#e0d3b3]">
                <div
                  className="h-full rounded-full bg-red transition-all duration-500"
                  style={{ width: `${Math.max(5, Math.min(100, activeFocus.progress || 0))}%` }}
                />
              </div>
            </div>
          </div>
          <button
            onClick={handleCancelFocus}
            disabled={busy}
            title="中止并撤回当前大策施行"
            className="flex items-center gap-1 rounded border border-red/30 bg-card px-2.5 py-1 font-kai text-xs text-red hover:bg-red hover:text-paper transition disabled:opacity-50"
          >
            <Ban size={12} /> 中止废止
          </button>
        </div>
      )}

      {/* 反馈信息 */}
      {msg && (
        <div
          className={`rounded border p-2 font-kai text-xs ${
            msg.type === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800"
              : "border-red/40 bg-red/10 text-red-dark"
          }`}
        >
          {msg.text}
        </div>
      )}

      {/* 核心节点列表 / 树状卡片 */}
      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {Object.entries(branchNodes).map(([nodeKey, node]: [string, any], idx) => {
          const isUnlocked = !!unlockedNodes[nodeKey]?.unlocked;
          const isCurrentActive = hasActiveFocus && activeFocus.node_key === nodeKey;
          
          // 前置检查：如果不是第一个节点，前一个节点必须已解锁 (兼容 prereq 为 string 或 string[] 或 null)
          const rawPrereq = node.prereq;
          const prereqKeys: string[] = Array.isArray(rawPrereq)
            ? rawPrereq
            : typeof rawPrereq === "string"
            ? [rawPrereq]
            : [];
          const prereqSatisfied = prereqKeys.every((pk: string) => unlockedNodes[pk]?.unlocked);
          const canAct = !isUnlocked && !isCurrentActive && prereqSatisfied;

          return (
            <div
              key={nodeKey}
              className={`relative flex flex-col justify-between rounded-lg border p-3.5 shadow-paper transition ${
                isUnlocked
                  ? "border-gold/80 bg-gradient-to-r from-paper to-gold-light/20 shadow-sm"
                  : isCurrentActive
                  ? "border-red bg-red/5 ring-1 ring-red/30 shadow-card"
                  : canAct
                  ? "border-gold/50 bg-card hover:border-gold hover:shadow-card"
                  : "border-border/50 bg-paper/40 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-kai text-base font-bold text-ink">
                      第{idx + 1}策 · {node.name}
                    </span>
                    <span className="rounded bg-card border border-border px-1.5 py-0.2 font-kai text-[10px] text-dim">
                      权级 {node.power_level}
                    </span>
                    <span className="rounded bg-paper border border-border px-1.5 py-0.2 font-kai text-[10px] text-dim">
                      历时 {node.duration || 3} 月
                    </span>
                    <span className="rounded bg-paper border border-border px-1.5 py-0.2 font-kai text-[10px] text-dim">
                      月支 {node.cost_per_month || 10000} 贯
                    </span>

                    {isUnlocked && (
                      <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.2 font-kai text-[10px] font-bold text-emerald-800">
                        <CheckCircle2 size={11} /> 已经大策功成 · AI长期记忆已沉淀
                      </span>
                    )}

                    {isCurrentActive && (
                      <span className="flex items-center gap-1 rounded bg-red/20 px-2 py-0.2 font-kai text-[10px] font-bold text-red">
                        <Clock size={11} className="animate-spin" /> 中枢专精推行中 ({activeFocus.progress}%)
                      </span>
                    )}
                  </div>

                  <p className="mt-1 font-kai text-xs leading-relaxed text-ink-light">
                    {node.desc}
                  </p>

                  {/* 历史沉淀与 AI 推演影响简注 */}
                  {node.narrative_memory && (
                    <div className="mt-2 flex items-start gap-1.5 rounded bg-paper/60 p-1.5 border border-gold/30 text-[11px] font-kai text-ink/80">
                      <BookOpen size={13} className="shrink-0 mt-0.5 text-goldDark" />
                      <span><strong>史评与AI记忆定式：</strong>{node.narrative_memory}</span>
                    </div>
                  )}
                </div>

                <div className="shrink-0 pl-2">
                  {isUnlocked ? (
                    <div className="rounded-full bg-gold/20 p-2 text-goldDark" title="已获帝国朱红御玺印鉴">
                      <Sparkles size={18} />
                    </div>
                  ) : isCurrentActive ? (
                    <button
                      onClick={handleCancelFocus}
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-lg border border-red/40 bg-paper px-4 py-2 font-kai text-xs font-bold text-red shadow-sm hover:bg-red hover:text-paper transition"
                    >
                      <Ban size={13} />
                      中止施行
                    </button>
                  ) : canAct ? (
                    <button
                      onClick={() => handleStartFocus(nodeKey, node.name)}
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-lg bg-red px-4 py-2 font-kai text-xs font-bold tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
                    >
                      {busy ? <Loader2 size={13} className="animate-spin" /> : <Scroll size={13} />}
                      下旨立案
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 font-kai text-xs text-dim">
                      <Lock size={13} /> 需先功成前置大策
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
