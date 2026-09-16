import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { getApiClient, type MeterResult, type MeterRow } from "../api/client";

// Token 用量表 —— 迁移自 Tk game/ui/panels_meta.py::_panel_token_meter（L276）
// 数据源 /api/meter（分组聚合由 ai/token_meter.grouped_meter_rows 提供，Tk/Web 单一权威源）。
// 语义：召对·预过滤/缓存命中行不消耗 token；「合计」行命中列 = 召对省调率。
export default function MeterPanel() {
  const [data, setData] = useState<MeterResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setData(await getApiClient().meter());
    } catch (e) {
      console.error("[meter]", e);
      setMsg("计量读取失败：" + (e instanceof Error ? e.message : String(e)));
    }
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().meter();
        if (alive) setData(res);
      } catch (e) {
        console.error("[meter]", e);
        if (alive) setMsg("计量读取失败：" + (e instanceof Error ? e.message : String(e)));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  async function reset() {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await getApiClient().resetMeter();
      setMsg("Token 计量与召对命中统计已清零。");
      await refresh();
    } catch (e) {
      console.error("[meter/reset]", e);
      setMsg("清零失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  const rows: MeterRow[] = data?.rows ?? [];

  return (
    <div className="space-y-4">
      <p className="text-sm leading-relaxed text-dim">
        AI 调用 token 计量（按契约方法分桶；召对命中＝预过滤/缓存拦截，不消耗 token）。
      </p>

      <div className="overflow-hidden rounded-lg border border-gold/40 bg-paper/60">
        {data === null ? (
          <p className="flex items-center justify-center gap-2 py-8 text-sm text-dim">
            <Loader2 size={14} className="animate-spin" /> 计量读取中…
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-red text-[#f3e6c4]">
                <th className="px-3 py-2 text-left font-kai">调用类型</th>
                <th className="px-3 py-2 text-right font-kai">次数</th>
                <th className="px-3 py-2 text-right font-kai">Prompt</th>
                <th className="px-3 py-2 text-right font-kai">Completion</th>
                <th className="px-3 py-2 text-right font-kai">命中</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isTotal = r.type === "合计";
                return (
                  <tr
                    key={r.type}
                    className={
                      isTotal
                        ? "bg-[#f1e7cf] font-bold text-ink"
                        : "border-b border-gold/20 text-ink last:border-0"
                    }
                  >
                    <td className="px-3 py-1.5">{r.type}</td>
                    <td className="px-3 py-1.5 text-right">{Number(r.calls).toLocaleString("en-US")}</td>
                    <td className="px-3 py-1.5 text-right">{Number(r.prompt).toLocaleString("en-US")}</td>
                    <td className="px-3 py-1.5 text-right">{Number(r.completion).toLocaleString("en-US")}</td>
                    <td className="px-3 py-1.5 text-right">
                      {typeof r.hit === "string" ? r.hit : Number(r.hit).toLocaleString("en-US")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs leading-relaxed text-dim">
          说明：Prompt/Completion 按方法分桶累计；「合计」行命中列＝召对省调率。
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void refresh()}
            className="flex items-center gap-1.5 rounded border border-gold/50 bg-paper/70 px-3 py-1 font-kai text-xs text-ink transition hover:bg-gold-light/40"
          >
            <RefreshCw size={12} /> 刷新
          </button>
          <button
            onClick={reset}
            disabled={busy}
            className="flex items-center gap-1.5 rounded border border-red/50 bg-paper/70 px-3 py-1 font-kai text-xs text-red transition hover:bg-red/10 disabled:opacity-60"
          >
            {busy && <Loader2 size={12} className="animate-spin" />} 清零计量
          </button>
        </div>
      </div>

      {msg && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="text-sm text-ink">{msg}</p>
        </div>
      )}
    </div>
  );
}
