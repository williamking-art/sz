import * as React from "react";
import { Landmark, Users, Newspaper, ScrollText, PenLine, Play, Globe2, Lock, Trees, FileText, Building2, ClipboardList, Stamp, BookOpen, Flame } from "lucide-react";
import { useGameStore } from "../store/gameStore";
import { getApiClient, subscribeRichPoll } from "../api/client";
import { audioEngine } from "../audio/engine";

// 底部命令 dock：朝堂/群臣/朝报/个人行止/拟旨 + 回合推演
const COMMANDS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "court", label: "朝堂", icon: <Landmark size={20} /> },
  { key: "ministers", label: "群臣", icon: <Users size={20} /> },
  { key: "gazette", label: "朝报", icon: <Newspaper size={20} /> },
  { key: "personal", label: "行止", icon: <ScrollText size={20} /> },
  { key: "diplomacy", label: "邦交", icon: <Globe2 size={20} /> },
  { key: "decree", label: "拟旨", icon: <PenLine size={20} /> },
  { key: "secretdecree", label: "密旨", icon: <Lock size={20} /> },
  { key: "pending", label: "批红", icon: <Stamp size={20} /> },
  { key: "land", label: "田亩", icon: <Trees size={20} /> },
  { key: "dailylog", label: "日志", icon: <FileText size={20} /> },
  { key: "memory", label: "记忆", icon: <BookOpen size={20} /> },
  { key: "situation", label: "局势", icon: <Flame size={20} /> },
  { key: "centralorg", label: "机枢", icon: <Building2 size={20} /> },
  { key: "governance", label: "治务", icon: <ClipboardList size={20} /> }
];

/** 关键 HUD 指标快照（供结算浮层做「本月损益 ▲▼」对比；迁移自 Tk `_settle_show` 的 snap）。 */
function snapshotHud(s: unknown): Record<string, number> {
  const g = (k: string, d = 0) => {
    const v = s && typeof s === "object" ? (s as Record<string, unknown>)[k] : undefined;
    return typeof v === "number" && Number.isFinite(v) ? v : d;
  };
  return {
    treasury: g("treasury"),
    imperial_treasury: g("imperial_treasury"),
    population_satisfaction: g("population_satisfaction"),
    prestige: g("prestige")
  };
}

export default function Dock() {
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const pushUiLog = useGameStore((s) => s.pushUiLog);
  const advancing = useGameStore((s) => s.advancing);
  const setAdvancing = useGameStore((s) => s.setAdvancing);
  const setState = useGameStore((s) => s.setState);
  const state = useGameStore((s) => s.state);
  // P0-6：禁止在 setInterval 回调里调用 Hook。用 ref 镜像当前 turn，轮询里只读 ref。
  const turnRef = React.useRef<number | undefined>(undefined);
  turnRef.current = (state as Record<string, unknown> | null)?.turn as number | undefined;
  // P1-25：轮询 interval 挂到 ref，组件卸载时清理（否则关 Dock 后仍 pollRich/pushOverlay）
  const pollTimerRef = React.useRef<number | null>(null);
  React.useEffect(() => () => {
    if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
  }, []);
  async function handleAdvance() {
    if (advancing) return;
    audioEngine.playClick();
    setAdvancing(true);
    // 迁移补齐：结算前抓关键指标快照，供浮层展示本月涨跌（原 Tk 有、Web 缺）
    const before = snapshotHud(state);
    try {
      const res = await getApiClient().advance();
      setState(res.state);
      audioEngine.playSfx("sfx_gong", { volumeBias: 0.6 });
      // 迁移补齐：即时回执（原 Tk `_log_lines`）——朝报面板「近日机务回执」可查
      {
        const st = res.state as Record<string, unknown> | undefined;
        pushUiLog(
          `〔推演〕${String(st?.era_name ?? "")}${String(st?.year ?? "")}年${String(st?.month ?? "")}月 回合结算完成`
        );
      }
      // 两段式（2026-09-21「民间情况先行」+ 前后两次弹窗分工）：
      //  ① 首段 overlay＝**民间情况**（程序真值民间反应，立即可读；数值结算已完成）；
      //  ② round2 富化就位（rich_ready=true）后再弹**回合报告**（官方月报富版/奏章）。
      // 两次用同一 kind="advance"、不同 title/props.stage 区分；第二弹仅当回合未推进
      // （用户仍在读民间情况）。若玩家已推进下一回合，富文本由侧栏面板自然可见，不再弹。
      const stNow = res.state as Record<string, unknown> | undefined;
      pushOverlay({
        kind: "advance",
        title: "民间情况",
        props: {
          stage: "civilian",
          events: res.events,
          log: res.log,
          report: res.report,
          rich_pending: (stNow as Record<string, unknown> | undefined)?.rich_ready === false,
          before,
          after: snapshotHud(res.state)
        }
      });
      // round2 富化轮询（两侧：AI 民间反应版 + 官方月报；就位后弹「回合报告」）
      // S-1（2026-09-21 重审）：① settle_error 优先判；② 富文本未就位**不清 interval**
      // 继续等（原实现 `if (r.ready) { clearInterval }` 单次触发，命中后台回滚的
      // 「ready + 无错误 + 上月富文本」窗口会弹**上月**报告并吞掉「推演未成」）；
      // ③ ready 且两路皆空（三路 AI 全失败且本地兜底也未产出的极端态）→ 静默收尾。
      // P2-37：订阅共享轮询器，不再自起 setInterval 与 AdvancePanel 抢跑。
      {
        const stNow = res.state as Record<string, unknown> | undefined;
        const unsubscribe = subscribeRichPoll((r) => {
          if (!r.ready) return;
          unsubscribe();
          if (r.settle_error) {
            if (turnRef.current === stNow?.turn) {
              pushOverlay({
                kind: "advance",
                title: "推演未成",
                props: {
                  error: `回合结算未成：${r.settle_error}（可重试；民间情况文本仍在上方）`
                }
              });
            }
            return;
          }
          if (!r.rich_report && !r.rich_civilian) return;
          if (turnRef.current === stNow?.turn) {
            pushOverlay({
              kind: "advance",
              title: "回合报告",
              props: {
                stage: "final",
                report: r.rich_report,
                scenes: r.rich_report_scenes ?? [],
                rich_civilian: r.rich_civilian,
                events: res.events,
                log: Array.isArray(r.log) ? r.log : res.log,
                before,
                after: r.state ? snapshotHud(r.state) : snapshotHud(res.state)
              }
            });
          }
        });
        // 3 分钟上限：后端一直不 ready 也停表
        window.setTimeout(() => unsubscribe(), 180_000);
      }
    } catch (e) {
      console.error("[advance]", e);
      // 推演为全游戏级强制 AI（core/commands.py::settle_turn 拒绝式），
      // 后端未配 AI 时抛 500，此处转为可读提示而非静默失败。
      const raw = e instanceof Error ? e.message : String(e);
      const hint = /HTTP 500|Internal Server Error/i.test(raw)
        ? "推演需接入 AI：请配置 AI 设置（OpenAI 兼容 API）后重试。"
        : raw;
      pushUiLog("[推演] 未成：" + hint);
      pushOverlay({ kind: "advance", title: "推演未成", props: { error: hint } });
    } finally {
      setAdvancing(false);
    }
  }

  const primary = COMMANDS.filter((command) =>
    ["court", "ministers", "gazette", "decree"].includes(command.key)
  );

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end justify-between gap-3 px-5 pb-4 sm:px-7 sm:pb-5">
      {/* 高频政务置于案几式长栏；其余入口收进右侧职司图籍，避免十四枚圆钮压住天下舆图。 */}
      <div className="pointer-events-auto flex min-w-0 items-center gap-1.5 overflow-x-auto rounded-sm border border-[#8f6e28]/60 bg-[#f6ecd6]/90 p-2 shadow-[0_10px_34px_rgba(28,18,12,.22)] backdrop-blur-md sm:gap-2 sm:px-3">
        <div className="mr-1 hidden h-10 w-10 shrink-0 items-center justify-center border border-[#caa24a]/60 bg-[#8a2b22] text-[#f6ecd6] shadow-sm sm:flex">
          <Landmark size={20} strokeWidth={1.5} />
        </div>
        <div className="mr-1 hidden shrink-0 border-r border-[#8f6e28]/35 pr-3 sm:block">
          <p className="font-kai text-[10px] tracking-[.28em] text-[#8f6e28]">御 前 机 务</p>
          <p className="font-kai text-[13px] font-bold tracking-[.12em] text-[#2b1d12]">常行四事</p>
        </div>
        {primary.map((c) => (
          <button
            key={c.key}
            onClick={() => {
              audioEngine.playClick();
              pushOverlay({ kind: c.key as never, title: c.label });
            }}
            title={c.label}
            className={`group sz-command-tile relative flex h-12 min-w-[62px] shrink-0 flex-col items-center justify-center px-2 sm:h-[54px] sm:min-w-[74px] ${c.key === "decree" ? "is-primary" : ""}`}
          >
            <span className="text-[#8a2b22] transition group-hover:-translate-y-0.5">{c.icon}</span>
            <span className="mt-0.5 font-kai text-[11px] font-bold tracking-[.1em] text-[#2b1d12] sm:text-[12px]">{c.label}</span>
          </button>
        ))}
      </div>

      {/* 回合推演独立成玺印式主操作，视觉上与日常面板入口分开。 */}
      <div className="pointer-events-auto">
        <button
          onClick={handleAdvance}
          disabled={advancing}
          className="sz-advance-seal group relative flex h-[58px] min-w-[68px] shrink-0 items-center justify-center gap-2 px-3 disabled:cursor-wait disabled:opacity-65 sm:h-[66px] sm:min-w-[154px] sm:px-4"
        >
          {!advancing && <span className="sz-advance-glint absolute inset-1" aria-hidden="true" />}
          <Play size={21} className="relative" fill="currentColor" />
          <span className="relative hidden text-left sm:block">
            <span className="block font-kai text-[15px] font-bold tracking-[.2em]">{advancing ? "推演中" : "推演天下"}</span>
            <span className="mt-0.5 block text-[9px] tracking-[.2em] opacity-75">{advancing ? "諸司奏報彙集" : "頒旨後 · 推進一月"}</span>
          </span>
          <span className="relative font-kai text-[11px] font-bold sm:hidden">{advancing ? "稍候" : "推演"}</span>
        </button>
      </div>
    </div>
  );
}
