import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient, type ReadoutsResult } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";
import constants from "../data/constants.json";

// 仓廪漕运 —— 对齐 game/ui/panels_economy.py::_panel_granary（L1304）
// 太仓虚实/泉货通滞/诸路储粮；月入月出派生读数走 /api/readouts::granary。
// 仓廪施政（折变/和籴/赈济/漕运/扩建）请经「拟旨」，此处只读。
type Dict = Record<string, unknown>;

const PREFECTURE_LIST = constants.prefecture_list as string[];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function grainPrice(v: number): string {
  return v > 0 ? `${v.toFixed(3)}贯/石` : "—";
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

export default function GranaryPanel() {
  const state = useGameStore((s) => s.state);
  const [ro, setRo] = useState<ReadoutsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (alive) setRo(res);
      } catch (e) {
        console.error("[readouts]", e);
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无仓廪可览。</p>;
  }

  const granary = pick<number>(state, "granary", 0);
  const granaryCap = Math.max(pick<number>(state, "granary_cap", 1), 1);
  const grainPriceState = pick<number>(state, "grain_price", 0);
  const canalBlock = pick<number>(state, "canal_block", 0);
  const coin = asDict(pick(state, "coin", {}));
  const priceLevel = pick<number>(state, "price_level", 1);
  const paySystem = asDict(pick(state, "pay_system", {}));
  const singleWhip = pick(state, "single_whip", false) === true;
  const prefectures = asDict(pick(state, "prefectures", {}));

  const fin = asDict(ro?.finance);
  const gr = ro?.granary;
  const util = typeof gr?.capacity_used === "number" ? gr.capacity_used : granary / granaryCap;
  const trend = typeof fin.price_trend === "string" ? fin.price_trend : "（初设）";
  const shortageDesc = typeof fin.shortage_desc === "string" ? fin.shortage_desc : "";

  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        仓廪虚实，系乎国运。田赋本色征粟入诸路，漕运输太仓，折变换钱养朝廷。
      </p>

      {/* 太仓虚实 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="太 仓 虚 实" />
        <div className="mt-2 flex items-center gap-3">
          <div className="h-3.5 flex-1 overflow-hidden rounded-full border border-gold/60 bg-[#efe2c4]">
            <div
              className="h-full rounded-full bg-[#8a671e] transition-all"
              style={{ width: `${Math.min(100, util * 100)}%` }}
            />
          </div>
          <span className="shrink-0 text-xs text-dim">
            太仓存粮 {wan(granary, "石")} / {wan(granaryCap, "石")}
          </span>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-dim">
          {ro ? (
            <>
              太仓月入（田赋本色）：{wan(asNum(gr?.monthly), "石")}　
              月出（军粮{Math.round(asNum(gr?.army))}+官禄{Math.round(asNum(gr?.official))}+
              吏禄{Math.round(asNum(gr?.clerk))}+雀鼠耗+贪腐损耗）
            </>
          ) : error ? (
            <>派生读数读取失败：{error}</>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 size={12} className="animate-spin" /> 派生读数读取中…
            </span>
          )}
        </p>
        <p className="mt-1.5 text-sm text-dim">
          米价趋势：{trend}　|　米价约 {grainPrice(grainPriceState)}　|　
          漕运：{canalBlock >= 40 ? "阻塞" : "通畅"}（{canalBlock}）
        </p>
      </div>

      {/* 泉货通滞 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="泉 货 通 滞" />
        <p className="mt-2 text-sm text-ink">
          钱荒：{shortageDesc || "—"}　|　物价水平：{priceLevel.toFixed(2)}（钱/物之比）　|　
          俸禄：{String(paySystem.mode ?? "本色折色")}　|　
          {singleWhip ? "一条鞭（折银）" : "本色征粮"}
        </p>
      </div>

      {/* 诸路储粮 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="诸 路 储 粮" />
        <div className="mt-1.5">
          {PREFECTURE_LIST.slice(0, 6).map((name) => {
            const p = asDict(prefectures[name]);
            const gp = typeof p.grain_price === "number" ? p.grain_price : grainPriceState;
            return (
              <p key={name} className="py-1 text-sm text-ink">
                · {name}　储粮 {wan(asNum(p.storage), "石")}　粮产 {wan(asNum(p.grain), "石")}　
                米价 {grainPrice(gp)}
              </p>
            );
          })}
        </div>
      </div>

      {/* 仓廪之政 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="仓 廪 之 政" />
        <p className="mt-1.5 text-sm leading-relaxed text-dim">
          仓廪调度（折变、和籴、赈济、漕运、扩建仓储）与颁一条鞭/方田均税等大政，
          请经「拟旨」系统施行，由中枢推演落地。
        </p>
      </div>
    </div>
  );
}
