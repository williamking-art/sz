import { useState, useEffect } from "react";
import { Crown, FolderOpen, BookOpen, Settings, LogOut, Loader2, Play, Sparkles } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

const DIFFICULTIES = [
  { key: "史实", label: "史实推演", tag: "正史", desc: "依建中靖国元年旧制，新旧党争炽烈，北方辽金迭代在即，人事循常。" },
  { key: "轻松", label: "治平之治", tag: "安泰", desc: "四方风调雨顺，岁入充盈，流民易抚，朝堂阻力减半，宜初习治道。" },
  { key: "艰难", label: "天下倒悬", tag: "极危", desc: "仓廪见底，边患交迫，金军南侵更速，非洞悉军政财赋巨擘难力挽狂澜。" }
];

export default function MainMenu() {
  const [view, setView] = useState<"menu" | "newgame">("menu");
  const [diff, setDiff] = useState("史实");
  const [busy, setBusy] = useState(false);
  const [hasSave, setHasSave] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const setState = useGameStore((s) => s.setState);
  const setInGame = useGameStore((s) => s.setInGame);
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

  async function handleNewGame() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await getApiClient().newGame(diff);
      setState(res.state);
      setInGame(true); // 优雅揭晓进入舆图天下
    } catch (e) {
      console.error("[new_game]", e);
      setErr("开局失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadGame() {
    if (busy || !hasSave) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await getApiClient().load(1);
      setState(res.state);
      setInGame(true);
    } catch (e) {
      console.error("[load_game]", e);
      setErr("读取存档失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  function handleQuit() {
    if (window.confirm("圣意已决，就此辞朝退出游戏？")) {
      window.close();
    }
  }

  return (
    <div className="relative h-full w-full overflow-hidden select-none">
      {/* 1. 全景大作壁纸背景（带极缓呼吸电影感） */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
        style={{ backgroundImage: "url('./images/menu_bg_1.png')" }}
      />

      {/* 2. 电影感全屏暗角与宣纸暗色渐变遮罩（左侧深黑渐变衬底，确保菜单字迹极度清晰） */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/55 to-black/30" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-black/40" />

      {/* 3. 左侧大作排版区（完全对齐商业级大战略主界面构图） */}
      <div className="relative z-10 flex h-full flex-col justify-between px-16 py-12">
        {/* 左上：Logo 标题组（无杂乱印章，纯净名家书法题字） */}
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <img
              src="./images/title_calligraphy.png"
              alt="宋祚"
              className="h-28 object-contain drop-shadow-[0_8px_24px_rgba(0,0,0,0.95)] select-none"
            />
            <div className="flex flex-col justify-center gap-1.5 pb-1">
              <span className="self-start rounded border border-gold/70 bg-black/60 px-2.5 py-0.5 font-kai text-xs tracking-widest text-gold shadow-sm">
                建中靖国
              </span>
              <p className="font-sans text-[11px] font-bold tracking-[0.45em] text-gold/90 uppercase drop-shadow-sm">
                THE SONG DYNASTY · MANDATE OF HEAVEN
              </p>
            </div>
          </div>
          <p className="max-w-md font-kai text-sm tracking-widest text-[#d8cfbe]/85 pl-1 border-l-2 border-gold/40 py-0.5">
            “建中靖国元年正月，帝即天子位。辽金迭代，外患渐迫；社稷安危，系于一念。”
          </p>
        </div>

        {/* 左中下：垂直大长条菜单按钮组（参考图核心交互！） */}
        <div className="w-[340px]">
          {view === "menu" ? (
            <div className="space-y-2.5">
              {/* 承统开局 */}
              <MenuButton
                icon={<Crown size={20} className="text-gold" />}
                title="承 统 践 祚"
                subtitle="开启大宋新朝篇章"
                primary
                onClick={() => setView("newgame")}
              />

              {/* 继续旧局 */}
              <MenuButton
                icon={<FolderOpen size={20} className={hasSave ? "text-gold" : "text-white/40"} />}
                title="接 续 朝 政"
                subtitle={hasSave ? "自前朝密档接续理政" : "暂无朝廷归档"}
                disabled={!hasSave || busy}
                onClick={handleLoadGame}
              />

              {/* 大宋典制（图鉴） */}
              <MenuButton
                icon={<BookOpen size={20} className="text-gold/80" />}
                title="大 宋 典 制"
                subtitle="一百八十七辞条国风图鉴"
                onClick={() => pushOverlay({ kind: "codex", title: "大宋典制 · 图鉴" })}
              />

              {/* 机务设置 */}
              <MenuButton
                icon={<Settings size={20} className="text-white/70" />}
                title="治 平 机 务"
                subtitle="AI模型接口 · 视听规制"
                onClick={() => pushOverlay({ kind: "settings", title: "AI 枢密机务配置", props: { initialView: "ai" } })}
              />

              {/* 辞朝退出 */}
              <MenuButton
                icon={<LogOut size={20} className="text-white/50" />}
                title="辞 朝 归 隐"
                subtitle="退出游戏"
                onClick={handleQuit}
              />
            </div>
          ) : (
            /* 展开模式：时局难易度择定 */
            <div className="rounded-lg border-2 border-gold/60 bg-black/75 p-5 shadow-2xl backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-gold/40 pb-2">
                <span className="font-kai text-base font-bold tracking-widest text-gold">
                  【 择 定 登 极 时 局 】
                </span>
                <button
                  onClick={() => setView("menu")}
                  className="font-kai text-xs text-white/60 hover:text-white"
                >
                  ◂ 返回
                </button>
              </div>

              <div className="space-y-2">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d.key}
                    onClick={() => setDiff(d.key)}
                    className={`flex w-full items-start gap-3 rounded-md border p-2.5 text-left transition ${
                      diff === d.key
                        ? "border-red bg-red/20 shadow-sm ring-1 ring-gold/50"
                        : "border-white/10 bg-white/5 hover:border-gold/40 hover:bg-white/10"
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                        diff === d.key ? "border-gold bg-red" : "border-white/30"
                      }`}
                    >
                      {diff === d.key && <div className="h-1.5 w-1.5 rounded-full bg-gold" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-kai text-sm font-bold tracking-wider text-white">
                          {d.label}
                        </span>
                        <span className="rounded bg-black/50 px-1 py-0.2 font-kai text-[10px] text-gold">
                          {d.tag}
                        </span>
                      </div>
                      <p className="mt-0.5 font-kai text-[11px] leading-relaxed text-white/70">
                        {d.desc}
                      </p>
                    </div>
                  </button>
                ))}
              </div>

              {err && (
                <div className="rounded border border-red/40 bg-red/20 p-2 font-kai text-xs text-red-200">
                  {err}
                </div>
              )}

              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={() => setView("menu")}
                  className="rounded px-3 py-1 font-kai text-xs text-white/60 hover:text-white"
                >
                  取消
                </button>
                <button
                  onClick={handleNewGame}
                  disabled={busy}
                  className="flex items-center gap-2 rounded bg-gradient-to-r from-red to-red-dark px-6 py-2 font-kai text-sm font-bold tracking-widest text-[#f8ecd0] shadow-card ring-1 ring-gold transition hover:scale-105 disabled:opacity-50"
                >
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  {busy ? "定朔践祚中…" : "即 天 子 位"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 底部状态栏 */}
        <div className="flex items-center justify-between border-t border-white/10 pt-3 text-[11px] font-kai text-white/40">
          <div className="flex items-center gap-3">
            <span>宋祚 v0.2.0-Alpha · 宣和前夕</span>
            <span>·</span>
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${backendReady ? "bg-emerald-500 animate-pulse" : "bg-red"}`} />
              {backendReady ? "AI 枢密推演引擎已就绪" : "后端连接中…"}
            </span>
          </div>
          <div>宋祚游戏制造组 · 乾清通宝</div>
        </div>
      </div>
    </div>
  );
}

/** 商业级大作主菜单金属长条按钮 */
function MenuButton({
  icon,
  title,
  subtitle,
  primary,
  disabled,
  onClick
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  primary?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`group relative flex w-full items-center justify-between overflow-hidden rounded-md border px-4 py-2.5 text-left transition-all duration-200 ${
        disabled
          ? "cursor-not-allowed border-white/5 bg-black/40 opacity-40"
          : primary
          ? "border-gold/80 bg-gradient-to-r from-red/80 via-black/70 to-black/60 shadow-lg hover:border-gold hover:scale-[1.02] hover:shadow-gold/20"
          : "border-white/15 bg-black/60 shadow-md hover:border-gold/60 hover:bg-black/80 hover:scale-[1.01]"
      }`}
    >
      {/* 悬浮微光扫过效果 */}
      <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover:translate-x-full" />

      <div className="flex items-center gap-3.5 relative z-10">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-black/40 border border-white/10 transition group-hover:border-gold/50">
          {icon}
        </div>
        <div>
          <div className="font-kai text-base font-bold tracking-[0.18em] text-[#f8ecd0] transition group-hover:text-gold">
            {title}
          </div>
          <div className="font-kai text-[11px] text-white/50 tracking-wider">
            {subtitle}
          </div>
        </div>
      </div>

      <span className="font-kai text-xs text-white/30 transition group-hover:text-gold relative z-10">
        ▸
      </span>
    </button>
  );
}
