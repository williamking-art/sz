import { useEffect, useState } from "react";
import { Scroll, Loader2, Play, FolderOpen, BookOpen, Settings, Crown } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

const DIFFICULTIES: { key: string; label: string; desc: string; tag: string }[] = [
  { key: "史实", label: "史实推演", tag: "标准", desc: "依徽宗建中靖国元年旧制，外患隐现，南北党争未定，人事如常。" },
  { key: "轻松", label: "治平致治", tag: "易", desc: "四方灾异减半，流民易附，财赋丰润，宜初习治国大政。" },
  { key: "艰难", label: "社稷倾危", tag: "难", desc: "内忧外患交攻，金人崛起神速，仓廪吃紧，非通达军政难撑大局。" }
];

export default function StartPanel() {
  const [view, setView] = useState<"menu" | "newgame">("menu");
  const [diff, setDiff] = useState("史实");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [hasSave, setHasSave] = useState(false);

  const setState = useGameStore((s) => s.setState);
  const popOverlay = useGameStore((s) => s.popOverlay);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const backendReady = useGameStore((s) => s.backendReady);

  useEffect(() => {
    async function checkSave() {
      try {
        const res = await getApiClient().health();
        if (res.has_state) setHasSave(true);
      } catch {
        // 忽略
      }
    }
    if (backendReady) checkSave();
  }, [backendReady]);

  async function startNewGame() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await getApiClient().newGame(diff);
      setState(res.state);
      popOverlay();
    } catch (e) {
      console.error("[new_game]", e);
      setErr("开局失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  async function loadExistingGame() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await getApiClient().load(1);
      setState(res.state);
      popOverlay();
    } catch (e) {
      console.error("[load_game]", e);
      setErr("载入存档失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-center space-y-6 py-2">
      {/* 顶部：大宋皇家徽标与书法标题 */}
      <div className="flex flex-col items-center text-center">
        <div className="relative mb-2 flex h-20 w-20 items-center justify-center rounded-full bg-red shadow-card ring-4 ring-gold">
          <span className="font-kai text-4xl font-bold tracking-widest text-[#f8ecd0]">宋</span>
          <div className="absolute -bottom-1 -right-1 rounded-full bg-gold px-1.5 py-0.5 text-[10px] font-bold text-ink">
            官制
          </div>
        </div>
        <h1 className="font-kai text-3xl font-bold tracking-[0.3em] text-ink drop-shadow-sm">
          宋 祚
        </h1>
        <p className="mt-1 font-kai text-sm tracking-widest text-red-dark">
          北宋徽宗朝 · 治国推演模拟器
        </p>
        <p className="mt-2 max-w-md font-kai text-xs leading-relaxed text-dim/90 border-y border-gold/30 py-1.5">
          建中靖国元年正月，帝赵佶即天子位。改元求治，调和新旧；然辽金迭代，外患渐迫，千秋社稷系于一念。
        </p>
      </div>

      {view === "menu" ? (
        /* 主功能入口菜单 */
        <div className="w-full max-w-sm space-y-2.5">
          {/* 1. 承统继业 · 新朝开局 */}
          <button
            onClick={() => setView("newgame")}
            className="group flex w-full items-center justify-between rounded-lg border-2 border-gold/60 bg-gradient-to-r from-paper to-card px-5 py-3 shadow-paper transition hover:border-red hover:bg-gold-light/40"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-red/10 text-red transition group-hover:bg-red group-hover:text-paper">
                <Crown size={18} />
              </div>
              <div className="text-left">
                <div className="font-kai text-base font-bold tracking-wider text-ink">承统开局</div>
                <div className="font-kai text-[11px] text-dim">定纪元难易，登极受贺</div>
              </div>
            </div>
            <span className="font-kai text-xs text-red">践祚 ▸</span>
          </button>

          {/* 2. 重理朝政 · 继续旧局 */}
          <button
            onClick={loadExistingGame}
            disabled={busy || !hasSave}
            className={`group flex w-full items-center justify-between rounded-lg border px-5 py-3 shadow-paper transition ${
              hasSave
                ? "border-gold/40 bg-card hover:border-gold hover:bg-gold-light/30"
                : "cursor-not-allowed border-border/40 bg-paper/40 opacity-50"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-paper text-ink-light transition group-hover:text-red">
                <FolderOpen size={18} />
              </div>
              <div className="text-left">
                <div className="font-kai text-base font-medium tracking-wider text-ink">继续旧局</div>
                <div className="font-kai text-[11px] text-dim">
                  {hasSave ? "自前朝密档接续理政" : "暂无归档，请先开局"}
                </div>
              </div>
            </div>
            {hasSave && <span className="font-kai text-xs text-ink-light">接续 ▸</span>}
          </button>

          {/* 3. 大宋典籍库 */}
          <button
            onClick={() => pushOverlay({ kind: "codex", title: "大宋典制 · 图鉴" })}
            className="flex w-full items-center justify-between rounded-lg border border-gold/40 bg-card/80 px-5 py-2.5 shadow-sm transition hover:border-gold hover:bg-gold-light/20"
          >
            <div className="flex items-center gap-3">
              <BookOpen size={16} className="text-goldDark" />
              <span className="font-kai text-sm tracking-wider text-ink">大宋典制（图鉴百览）</span>
            </div>
            <span className="font-kai text-xs text-dim">187 辞条</span>
          </button>

          {/* 4. 机务设置 */}
          <button
            onClick={() => pushOverlay({ kind: "settings", title: "机务设置" })}
            className="flex w-full items-center justify-between rounded-lg border border-gold/30 bg-card/60 px-5 py-2.5 shadow-sm transition hover:border-gold hover:bg-gold-light/20"
          >
            <div className="flex items-center gap-3">
              <Settings size={16} className="text-dim" />
              <span className="font-kai text-sm tracking-wider text-ink">机务设置（AI 接口与参数）</span>
            </div>
            <span className="font-kai text-xs text-dim">配置</span>
          </button>
        </div>
      ) : (
        /* 新朝开局：难易度择定 */
        <div className="w-full max-w-sm space-y-3.5">
          <div className="flex items-center justify-between border-b border-gold/30 pb-1.5">
            <span className="font-kai text-sm font-bold text-red-dark">【择定朝堂时局】</span>
            <button
              onClick={() => setView("menu")}
              className="font-kai text-xs text-dim hover:text-ink"
            >
              ◂ 返回主单
            </button>
          </div>

          <div className="space-y-2">
            {DIFFICULTIES.map((d) => (
              <button
                key={d.key}
                onClick={() => setDiff(d.key)}
                className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition ${
                  diff === d.key
                    ? "border-red bg-red/10 shadow-paper ring-1 ring-red/40"
                    : "border-border bg-paper/70 hover:border-gold hover:bg-gold-light/20"
                }`}
              >
                <div
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                    diff === d.key ? "border-red bg-red text-paper" : "border-dim"
                  }`}
                >
                  {diff === d.key && <div className="h-1.5 w-1.5 rounded-full bg-paper" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-kai text-sm font-bold tracking-wider text-ink">
                      {d.label}
                    </span>
                    <span className="rounded bg-card px-1 py-0.2 font-kai text-[10px] text-red-dark">
                      {d.tag}
                    </span>
                  </div>
                  <p className="mt-0.5 font-kai text-xs leading-relaxed text-dim">{d.desc}</p>
                </div>
              </button>
            ))}
          </div>

          {err && (
            <div className="rounded border border-red/40 bg-red/10 p-2.5 font-kai text-xs text-red">
              {err}
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setView("menu")}
              className="rounded px-3 py-1.5 font-kai text-xs text-dim hover:text-ink"
            >
              取消
            </button>
            <button
              onClick={startNewGame}
              disabled={busy}
              className="flex items-center gap-2 rounded-lg bg-red px-8 py-2 font-kai text-sm tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              {busy ? "定朔继位中…" : "即 天 子 位"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
