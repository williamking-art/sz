import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";

// 终局评估 —— 对齐 game/ui/panels_menu.py::_panel_game_over（L223）
// client.conclude() 取规则评估 eval + AI 史评 ai_eval。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

export default function ConcludePanel() {
  const state = useGameStore((s) => s.state);
  const clearOverlays = useGameStore((s) => s.clearOverlays);
  const setInGame = useGameStore((s) => s.setInGame);
  const [data, setData] = useState<{ ev: Dict; ai: unknown } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 迁移补齐（原 Tk panels_menu `_panel_game_over`）：结局出口——回主菜单
  function backToMenu() {
    clearOverlays();
    setInGame(false);
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().conclude();
        if (alive) setData({ ev: asDict(res.eval), ai: res.ai_eval });
      } catch (e) {
        console.error("[conclude]", e);
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无终局可评。</p>;
  }

  const year = pick<number>(state, "year", 0);
  const eraName = pick<string>(state, "era_name", "");
  const emperorName = pick<string>(state, "emperor_name", "赵佶");

  return (
    <div className="space-y-4">
      <p className="text-center font-kai text-xl font-bold tracking-[0.3em] text-red">
        史 官 定 论
      </p>
      <p className="text-center text-sm text-dim">
        {eraName}{year}年 · 皇帝{emperorName}一朝终局
      </p>

      {error && (
        <div className="rounded-lg border border-red/40 bg-paper/60 p-3">
          <p className="text-sm text-red">终局评估失败：{error}</p>
        </div>
      )}

      {!data && !error && (
        <p className="flex items-center justify-center gap-2 py-10 text-sm text-dim">
          <Loader2 size={16} className="animate-spin" /> 史官秉笔直书中…
        </p>
      )}

      {data && (
        <>
          {/* 规则评估：七维评分 + 加权总分 + 结局（迁移补齐：原 Tk 逐项渲染，
              此前 Web 把 eval 原样 dump，total/outcome/description 未分段呈现） */}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
            <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">朝 野 评 议</p>
            <div className="mt-2 space-y-1 text-sm text-ink">
              {Object.entries(asDict(data.ev.scores)).map(([k, v]) => (
                <p key={k} className="flex items-center justify-between gap-3">
                  <span>· {k}</span>
                  <span className="font-bold">{Math.round(asNum(v, 0))}</span>
                </p>
              ))}
              {Object.keys(asDict(data.ev.scores)).length === 0 && (
                <p className="text-dim">（规则评估暂无数据）</p>
              )}
            </div>
            {asStr(data.ev.outcome) && (
              <div className="mt-3 border-t border-gold/30 pt-3">
                <p className="text-sm text-ink">
                  <span className="font-bold">加权总分</span>：{asNum(data.ev.total, 0)}
                  <span className="ml-3 font-kai font-bold text-red">
                    {asStr(data.ev.outcome)}
                  </span>
                </p>
                {asStr(data.ev.description) && (
                  <p className="mt-1 font-kai text-[14px] leading-relaxed text-dim">
                    {asStr(data.ev.description)}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* AI 史评 */}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
            <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">太 史 令 曰</p>
            {asStr(data.ai) ? (
              // 后端 ai_eval 恒为字符串（core/commands.py::conclude 取 commentary），直接呈现
              <p className="mt-2 whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">
                {asStr(data.ai)}
              </p>
            ) : (
              <p className="mt-2 text-sm text-dim">
                （AI 未接入，史评从阙。接入 AI 后可得一代之史笔。）
              </p>
            )}
          </div>

          {/* 结局出口（迁移补齐：原 Tk「回主菜单」钮此前缺失） */}
          <div className="flex justify-center pt-1">
            <button
              onClick={backToMenu}
              className="rounded-lg bg-red px-8 py-2.5 font-kai text-base tracking-[0.3em] text-paper transition hover:bg-red-dark"
            >
              回 主 菜 单
            </button>
          </div>
        </>
      )}
    </div>
  );
}
