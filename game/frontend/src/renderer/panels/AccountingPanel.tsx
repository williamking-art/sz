import { useEffect, useState } from "react";
import { Loader2, Users2 } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";

// 会计录 —— 对齐 game/ui/panels_economy.py::_panel_accounting（L1214）
// 名义岁入 vs 实际到库、月用度、库藏/货币/物价读数；派生读数走 /api/readouts::finance。
// 三冗不可见不可直裁——用度只呈总盘，对治须走变法长期政务。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

// 征率 0~1 小数 → 中文/百分比展示（Tk _format_rate）
function formatRate(rate: number): string {
  const r = Math.round(rate * 100) / 100;
  const ones: Record<string, string> = {
    "0.05": "半成", "0.1": "一成", "0.15": "一成五", "0.2": "二成", "0.25": "二成五",
    "0.3": "三成", "0.35": "三成五", "0.4": "四成"
  };
  const name = ones[String(r)] ?? `${(r * 100).toFixed(0)}%`;
  return `${name}（${(r * 100).toFixed(0)}%）`;
}

export default function AccountingPanel() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [fin, setFin] = useState<Dict | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (alive) setFin(asDict(res.finance));
      } catch (e) {
        console.error("[readouts]", e);
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无会计可览。</p>;
  }

  const commerceRate = pick<number>(state, "commerce_tax_rate", 0.1);
  const treasury = pick<number>(state, "treasury", 0);
  const imperialTreasury = pick<number>(state, "imperial_treasury", 0);
  const moneySupply = pick<number>(state, "money_supply", 0);
  const priceLevel = pick<number>(state, "price_level", 1);
  const payraiseBudget = pick<number>(state, "payraise_budget", 0);
  const wasteReform = asDict(pick(state, "waste_reform", {}));

  if (!fin) {
    return (
      <div className="space-y-4">
        <p className="px-1 text-sm leading-relaxed text-dim">
          会计录：岁入盈亏，一目了然。然朝廷用度止呈总盘，冗费深藏其中，非省浮费、裁冗员之变法不足以治之。
        </p>
        <div className="flex items-center justify-center gap-2 rounded-lg border border-gold/40 bg-paper/60 p-6 text-sm text-dim">
          {error ? (
            <span className="text-red">财政读数读取失败：{error}</span>
          ) : (
            <>
              <Loader2 size={16} className="animate-spin" /> 户部会计读数核算中…
            </>
          )}
        </div>
      </div>
    );
  }

  const nominalAnnual = asNum(fin.nominal_annual);
  const monthlyIn = asNum(fin.monthly_in);
  const diff = nominalAnnual / 12 - monthlyIn;
  const totalOut = asNum(fin.total_out);
  const net = asNum(fin.net);

  const inParts = [
    `工商 ${humanizeCoin(asNum(fin.commerce))}`,
    `役钱 ${humanizeCoin(asNum(fin.poll))}`,
    asNum(fin.maritime) > 0 ? `市舶 ${humanizeCoin(asNum(fin.maritime))}` : "",
    `二税折色 ${humanizeCoin(asNum(fin.tax_color))}`,
    `盐课 ${humanizeCoin(asNum(fin.salt_coin))}`
  ].filter(Boolean);

  const outParts = [
    `常支 ${humanizeCoin(asNum(fin.expenditure))}`,
    asNum(fin.army_cash) > 0 ? `军费 ${humanizeCoin(asNum(fin.army_cash))}` : "",
    asNum(fin.official_cash) > 0 ? `官俸 ${humanizeCoin(asNum(fin.official_cash))}` : "",
    asNum(fin.sui_gong) > 0 ? `岁币 ${humanizeCoin(asNum(fin.sui_gong))}` : ""
  ].filter(Boolean);

  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        会计录：岁入盈亏，一目了然。然朝廷用度止呈总盘，冗费深藏其中，非省浮费、裁冗员之变法不足以治之。
      </p>

      {/* 工商征率 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="工 商 征 率" />
        <p className="mt-1.5 text-sm font-bold text-ink">当前征率：{formatRate(commerceRate)}</p>
        <p className="mt-1 text-xs leading-relaxed text-dim">
          口径：0.05~0.40 为综合税负（商税+榷货+坊场钱），非单一商税。调征率请经拟旨（如「征三成」「0.13」）。
        </p>
      </div>

      {/* 岁入盈虚 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="岁 入 盈 虚" />
        <p className="mt-1.5 text-sm font-bold text-ink">
          名义岁入：{humanizeCoin(nominalAnnual)}/年（账面，贴史实）
        </p>
        <p className="mt-1 text-sm text-ink">
          实际月入：{humanizeCoin(monthlyIn)}/月　（{inParts.join(" + ")}）
        </p>
        <p className="mt-1 text-xs leading-relaxed text-dim">
          差额 {humanizeCoin(diff)}/月即「隐漏与拖欠」——账面名义与实到之距，正田赋隐漏、胥吏侵蚀之漏出。
        </p>
      </div>

      {/* 月用度 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="月 用 度" />
        <p className="mt-1.5 text-sm text-ink">
          月用度：{humanizeCoin(totalOut)}/月　（{outParts.join(" + ")}）
        </p>
        {payraiseBudget > 0 && (
          <p className="mt-1 text-xs text-dim">
            厚禄养廉：加俸预算尚余 {humanizeCoin(payraiseBudget)}，逐月摊还驱动诸路俸给充足。
          </p>
        )}
        {wasteReform.active === true && (
          <p className="mt-1 text-xs text-dim">
            变法{wasteReform.kind === "reduce_office" ? "裁汰冗员" : "省浮费"}推进中：
            月省 {humanizeCoin(asNum(wasteReform.savings))}，用度渐降。
          </p>
        )}
        <p className="mt-1 text-xs leading-relaxed text-dim">
          用度止呈总盘——冗官冗费深藏其中，账目无从分辨。欲治三冗，唯经拟旨下「省浮费/裁汰冗员」长期变法。
        </p>
        <p className={`mt-1.5 text-sm font-bold ${net >= 0 ? "text-emerald-800" : "text-red"}`}>
          净额：{net >= 0 ? `月结余 +${humanizeCoin(net)}` : `月亏空 -${humanizeCoin(Math.abs(net))}`}
        </p>
      </div>

      {/* 库藏泉货 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="库 藏 泉 货" />
        <p className="mt-1.5 text-sm text-ink">
          国库：{humanizeCoin(treasury)}　内帑：{humanizeCoin(imperialTreasury)}
          {asNum(fin.wine_coin) > 0 ? `（含酒课月 ${humanizeCoin(asNum(fin.wine_coin))}）` : ""}
        </p>
        <p className="mt-1 text-sm text-dim">
          货币供给：{humanizeCoin(moneySupply)}　物价：{priceLevel.toFixed(2)}（钱/物之比）　
          钱荒：{String(fin.shortage_desc ?? "—")}
        </p>
      </div>

      {/* 底部快捷操作 */}
      <div className="pt-2 border-t border-gold/30 flex items-center justify-between">
        <button
          onClick={() => pushOverlay({ kind: "pop", title: "天下民生 · 六民生齿与财帛" })}
          className="flex items-center gap-1.5 rounded border border-gold/60 bg-paper px-3 py-1.5 font-kai text-xs text-ink transition hover:bg-gold-light"
        >
          <Users2 size={14} className="text-goldDark" /> 查阅六民生齿与民间财帛 (POP)
        </button>
        <button
          onClick={() => pushOverlay({ kind: "decree", title: "拟旨 · 度支" })}
          className="rounded bg-red px-4 py-1.5 font-kai text-xs font-bold text-paper transition hover:bg-red-dark"
        >
          拟旨度支
        </button>
      </div>
    </div>
  );
}
