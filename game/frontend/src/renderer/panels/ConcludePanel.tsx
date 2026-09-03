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
  const [data, setData] = useState<{ ev: Dict; ai: unknown } | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          {/* 规则评估 */}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
            <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">朝 野 评 议</p>
            <div className="mt-2 space-y-1 text-sm text-ink">
              {Object.entries(data.ev).map(([k, v]) => (
                <p key={k}>
                  · {k}：{typeof v === "object" ? JSON.stringify(v) : String(v)}
                </p>
              ))}
              {Object.keys(data.ev).length === 0 && (
                <p className="text-dim">（规则评估暂无数据）</p>
              )}
            </div>
          </div>

          {/* AI 史评 */}
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
            <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">太 史 令 曰</p>
            {data.ai ? (
              <p className="mt-2 whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">
                {typeof data.ai === "string"
                  ? data.ai
                  : asStr(asDict(data.ai).text ?? asDict(data.ai).content ?? asDict(data.ai).eval, "") ||
                    JSON.stringify(data.ai)}
              </p>
            ) : (
              <p className="mt-2 text-sm text-dim">
                （AI 未接入，史评从阙。接入 AI 后可得一代之史笔。）
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
