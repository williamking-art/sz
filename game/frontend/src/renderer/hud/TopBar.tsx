import { useState } from "react";
import { Settings, ChevronDown, ChevronUp } from "lucide-react";
import { useGameStore, hudEra, hudPrestige, hudPopular, hudTreasury, hudPrivy, hudToken, getTreasuryDetail, getPrivyDetail, BudgetFlowData } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";

// 顶部状态条：朱红徽章「宋」+ 古意纪年 + 四枚数值胶囊 + 词元计数
export default function TopBar() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [open, setOpen] = useState<"treasury" | "privy" | null>(null);

  const era = hudEra(state);
  const prestige = hudPrestige(state);
  const popular = hudPopular(state);
  const treasury = hudTreasury(state);
  const privy = hudPrivy(state);
  const token = hudToken(state);

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between px-4 pt-3">
      {/* 左：纯正大宋皇室徽标 + 纪元（庄严只读展示，不做按钮） */}
      <div className="pointer-events-auto flex items-center gap-3 rounded-[3px] border border-gold bg-card px-2.5 py-1.5 shadow-paper">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red ring-2 ring-gold shadow-sm">
          <span className="font-kai text-[20px] font-bold leading-none text-[#f3e6c4]">宋</span>
        </div>
        <span className="whitespace-nowrap font-kai text-[15px] font-bold tracking-wide text-ink">
          {era || "建中靖国元年正月"}
        </span>
      </div>

      {/* 右：数值胶囊 + 词元 */}
      <div className="pointer-events-auto flex items-center gap-2 rounded-[3px] border border-gold bg-card px-2.5 py-2 shadow-paper">
        <span className="whitespace-nowrap rounded-[2px] border border-border px-2 py-1 text-[13px] font-bold text-ink">
          ◆威望 {Math.round(prestige)}
        </span>
        <span className="whitespace-nowrap rounded-[2px] border border-border px-2 py-1 text-[13px] font-bold text-ink">
          ♥民心 {Math.round(popular)}
        </span>
        <HoverDetailCapsule
          text={`◈国库 ${humanizeCoin(treasury)}`}
          open={open === "treasury"}
          onToggle={() => setOpen(open === "treasury" ? null : "treasury")}
          onClose={() => setOpen(null)}
          data={getTreasuryDetail(state)}
          isTreasury
        />
        <HoverDetailCapsule
          text={`⛃内帑 ${humanizeCoin(privy)}`}
          open={open === "privy"}
          onToggle={() => setOpen(open === "privy" ? null : "privy")}
          onClose={() => setOpen(null)}
          data={getPrivyDetail(state)}
          isTreasury={false}
        />
        {token !== null && (
          <span className="whitespace-nowrap px-1 text-[12px] font-bold text-dim">
            词元 ▸ {token.toLocaleString("en-US")}
          </span>
        )}

        {/* 右上角新设专属齿轮设置入口（主菜单 / 存档 / AI配置） */}
        <button
          onClick={() => pushOverlay({ kind: "settings", title: "机务设置" })}
          title="系统机务设置 / 返回主菜单"
          className="group flex h-7 w-7 items-center justify-center rounded-[2px] border border-border bg-paper/60 text-ink-light transition hover:border-gold hover:bg-gold-light hover:text-red"
        >
          <Settings size={15} className="transition group-hover:rotate-45" />
        </button>
      </div>
    </div>
  );
}

/** 古籍账本风格深度收支悬浮卡片（对齐参考图古典设计：入/出/净三列 + 明细折叠公式） */
function HoverDetailCapsule({
  text, open, onToggle, onClose, data, isTreasury
}: {
  text: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  data: BudgetFlowData;
  isTreasury: boolean;
}) {
  return (
    <div className="relative" onMouseLeave={onClose}>
      <button
        onMouseEnter={onToggle}
        onFocus={onToggle}
        className={`whitespace-nowrap rounded-[2px] border px-2 py-1 text-[13px] font-bold transition ${
          open ? "border-gold bg-gold-light text-red" : "border-border text-ink hover:bg-gold-light"
        }`}
      >
        {text}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-1.5 w-[330px] rounded-[4px] border border-gold bg-[#f9f5ea] shadow-2xl p-3 select-text font-kai animate-card-in">
          {/* 1. 顶部古典题头 */}
          <div className="flex items-center justify-between border-b border-gold/40 pb-2">
            <span className="text-[15px] font-bold tracking-[0.2em] text-red-dark">
              {data.title}
            </span>
            <span className="text-[11px] text-dim">月度会计推演</span>
          </div>

          {/* 2. 入/出/净 三列横向核心汇总盘 */}
          <div className="my-2.5 grid grid-cols-3 divide-x divide-gold/30 rounded border border-gold/40 bg-card py-1.5 text-center shadow-inner">
            <div className="px-1">
              <div className="text-[11px] text-dim">入</div>
              <div className="text-[13px] font-bold text-amber-900">
                {humanizeCoin(data.totalIn)}
              </div>
            </div>
            <div className="px-1">
              <div className="text-[11px] text-dim">出</div>
              <div className="text-[13px] font-bold text-emerald-800">
                {humanizeCoin(data.totalOut)}
              </div>
            </div>
            <div className="px-1">
              <div className="text-[11px] text-dim">净</div>
              <div className={`text-[13px] font-bold ${data.net >= 0 ? "text-red font-extrabold" : "text-emerald-800"}`}>
                {data.net >= 0 ? `+${humanizeCoin(data.net)}` : `-${humanizeCoin(Math.abs(data.net))}`}
              </div>
            </div>
          </div>

          {data.subNotice && (
            <p className="mb-2 text-[10px] leading-tight text-dim border-b border-gold/20 pb-1.5">
              ※ {data.subNotice}
            </p>
          )}

          {/* 3. 纵向滚动明细区 */}
          <div className="max-h-[380px] space-y-3 overflow-y-auto pr-1">
            {/* 固定收入区块 */}
            <div>
              <div className="flex items-center justify-between border-b border-gold/30 pb-0.5 mb-1.5">
                <span className="text-[13px] font-bold text-amber-900">固定收入</span>
                <span className="text-[11px] font-bold text-amber-900">+{humanizeCoin(data.totalIn)}</span>
              </div>
              <div className="space-y-1.5">
                {data.incomes.map((item) => (
                  <div key={item.name} className="rounded border border-gold/20 bg-paper/60 p-1.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="font-bold text-ink">{item.name}</span>
                      <span className="font-bold text-amber-900">+{humanizeCoin(item.amount)}</span>
                    </div>
                    {item.formula && (
                      <div className="mt-0.5 text-[10px] text-dim leading-snug">
                        税基：{item.formula}
                      </div>
                    )}
                    {item.desc && (
                      <div className="mt-0.5 text-[10px] text-ink-light leading-snug">
                        {item.desc}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 固定支出区块 */}
            <div>
              <div className="flex items-center justify-between border-b border-gold/30 pb-0.5 mb-1.5">
                <span className="text-[13px] font-bold text-emerald-800">固定支出</span>
                <span className="text-[11px] font-bold text-emerald-800">-{humanizeCoin(data.totalOut)}</span>
              </div>
              <div className="space-y-1.5">
                {data.expenses.map((item) => (
                  <div key={item.name} className="rounded border border-gold/20 bg-paper/60 p-1.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="font-bold text-ink">{item.name}</span>
                      <span className="font-bold text-emerald-800">-{humanizeCoin(item.amount)}</span>
                    </div>
                    {item.formula && (
                      <div className="mt-0.5 text-[10px] text-dim leading-snug">
                        规制：{item.formula}
                      </div>
                    )}
                    {item.desc && (
                      <div className="mt-0.5 text-[10px] text-ink-light leading-snug">
                        {item.desc}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}