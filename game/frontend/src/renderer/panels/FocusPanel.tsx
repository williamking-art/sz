import { useState } from "react";
import { Loader2, CheckCircle2, Lock, Sparkles, Scroll, Shield, Landmark, FlaskConical, Eye, Coins } from "lucide-react";
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

  // 统计已解锁进度
  const totalNodesCount = Object.keys(branchNodes).length;
  const unlockedCount = Object.values(unlockedNodes).filter((n: any) => n.unlocked).length;

  async function handleUnlock(nodeKey: string, nodeName: string) {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().action("unlock_focus", {
        branch: activeBranch,
        node_key: nodeKey,
      });
      if (res.state) setState(res.state);
      setMsg({ type: "success", text: `大策【${nodeName}】已颁行天下！${res.message || ""}` });
    } catch (e) {
      setMsg({ type: "error", text: "施行失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[520px] flex-col gap-3.5">
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
        <span className="font-kai text-dim">五维互制 · 择一专精</span>
      </div>

      {/* 反馈信息 */}
      {msg && (
        <div
          className={`rounded border p-2.5 font-kai text-xs ${
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
          // 前置检查：如果不是第一个节点，前一个节点必须已解锁 (兼容 prereq 为 string 或 string[] 或 null)
          const rawPrereq = node.prereq;
          const prereqKeys: string[] = Array.isArray(rawPrereq)
            ? rawPrereq
            : typeof rawPrereq === "string"
            ? [rawPrereq]
            : [];
          const prereqSatisfied = prereqKeys.every((pk: string) => unlockedNodes[pk]?.unlocked);
          const canAct = !isUnlocked && prereqSatisfied;

          return (
            <div
              key={nodeKey}
              className={`relative flex flex-col justify-between rounded-lg border p-4 shadow-paper transition ${
                isUnlocked
                  ? "border-gold/80 bg-gradient-to-r from-paper to-gold-light/20 shadow-sm"
                  : canAct
                  ? "border-red/50 bg-card hover:border-gold hover:shadow-card"
                  : "border-border/50 bg-paper/40 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-kai text-base font-bold text-ink">
                      第{idx + 1}策 · {node.name}
                    </span>
                    <span className="rounded bg-card border border-border px-1.5 py-0.2 font-kai text-[10px] text-dim">
                      权级 {node.power_level}
                    </span>
                    {isUnlocked && (
                      <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.2 font-kai text-[10px] font-bold text-emerald-800">
                        <CheckCircle2 size={11} /> 已经推行生效
                      </span>
                    )}
                  </div>
                  <p className="mt-1 font-kai text-xs leading-relaxed text-ink-light">
                    {node.desc}
                  </p>
                </div>

                <div className="shrink-0 pl-3">
                  {isUnlocked ? (
                    <div className="rounded-full bg-gold/20 p-2 text-goldDark">
                      <Sparkles size={18} />
                    </div>
                  ) : canAct ? (
                    <button
                      onClick={() => handleUnlock(nodeKey, node.name)}
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-lg bg-red px-5 py-2 font-kai text-xs font-bold tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
                    >
                      {busy ? <Loader2 size={13} className="animate-spin" /> : <Scroll size={13} />}
                      宣旨施行
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 font-kai text-xs text-dim">
                      <Lock size={13} /> 需先施行前置国策
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
