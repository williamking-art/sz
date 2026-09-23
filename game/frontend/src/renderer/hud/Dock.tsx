import { Landmark, Users, Newspaper, ScrollText, PenLine, Play, Globe2, Lock, Trees, FileText, Building2, ClipboardList, Stamp, BookOpen, Flame } from "lucide-react";
import { useGameStore } from "../store/gameStore";
import { getApiClient } from "../api/client";

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
  const pendingCount = (() => {
    const raw = (state as Record<string, unknown> | null)?.ai_pending_actions;
    if (!Array.isArray(raw)) return 0;
    return raw.filter((a) => (a as { status?: string })?.status === "pending").length;
  })();

  async function handleAdvance() {
    if (advancing) return;
    setAdvancing(true);
    // 迁移补齐：结算前抓关键指标快照，供浮层展示本月涨跌（原 Tk 有、Web 缺）
    const before = snapshotHud(state);
    try {
      const res = await getApiClient().advance();
      setState(res.state);
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
      (async () => {
        let cancelled = false;
        const _t = window.setInterval(async () => {
          try {
            const r = await getApiClient().pollRich();
            if (cancelled || !r.ready) return;          // 未就绪：下轮再查
            window.clearInterval(_t);
            cancelled = true;
            // 后台结算失败（AI 拒绝式）→ 弹"推演未成"（原因 code），不走富化弹。
            if (r.settle_error) {
              if (useGameStore((s) => s.state)?.turn === stNow?.turn) {
                pushOverlay({
                  kind: "advance",
                  title: "推演未成",
                  props: {
                    error:
                      `回合结算未成：${r.settle_error}（可重试；民间情况文本仍在上方）`
                  }
                });
              }
              return;
            }
            // 富化已收尾但两路皆空 → 无第二轮可弹，静默收尾（民间情况仍在首段弹窗）。
            if (!r.rich_report && !r.rich_civilian) return;
            if (useGameStore((s) => s.state)?.turn === stNow?.turn) {
              pushOverlay({
                kind: "advance",
                title: "回合报告",
                props: {
                  stage: "final",
                  report: r.rich_report,          // 官方月报（结算后的官方总结）
                  rich_civilian: r.rich_civilian, // AI 民间反应富版（与首段同源不同时）
                  events: res.events,
                  log: Array.isArray(r.log) ? r.log : res.log,  // 朝报（后台结算产出，随 round2 到位）
                  before,
                  after: r.state
                      ? snapshotHud(r.state)        // 结算后快照（round2 带），差异正确
                      : snapshotHud(res.state)
                }
              });
            }
          } catch {
            /* 轮询失败静默——民间情况文本已在读 */
          }
        }, 4000);
        window.setTimeout(() => {
          window.clearInterval(_t);
          cancelled = true;
        }, 180_000);   // 装饰层失败也不无限轮询（3 分钟上限）
      })();
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

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end justify-between px-6 pb-5">
      {/* 左：命令钮横排 */}
      <div className="pointer-events-auto flex items-center gap-2.5">
        {COMMANDS.map((c) => (
          <button
            key={c.key}
            onClick={() => pushOverlay({ kind: c.key as never, title: c.label })}
            title={c.label}
            className="group sz-dock-btn relative flex h-14 w-14 flex-col items-center justify-center rounded-full"
          >
            <span className="text-red transition group-hover:scale-110">{c.icon}</span>
            <span className="mt-0.5 text-[11.5px] font-bold text-ink">{c.label}</span>
            {c.key === "pending" && pendingCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red px-1 font-sans text-[10px] font-bold text-paper shadow">
                {pendingCount > 9 ? "9+" : pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 右：回合推演大按钮 */}
      <div className="pointer-events-auto">
        <button
          onClick={handleAdvance}
          disabled={advancing}
          className="sz-btn-primary group relative flex h-16 w-16 items-center justify-center rounded-full disabled:opacity-60"
        >
          {!advancing && <span className="absolute inset-0 rounded-full animate-breathe" />}
          <Play size={26} className="relative transition group-hover:scale-110" />
          <span className="absolute -bottom-6 whitespace-nowrap font-kai text-sm tracking-widest text-ink">
            {advancing ? "推演中…" : "回合推演"}
          </span>
        </button>
      </div>
    </div>
  );
}