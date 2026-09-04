import { useState, useRef } from "react";
import { Settings, Lock, Unlock, X } from "lucide-react";
import { useGameStore, hudEra, hudPrestige, hudPopular, hudTreasury, hudPrivy, hudToken, getTreasuryDetail, getPrivyDetail, BudgetFlowData } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";

// 顶部状态条：朱红徽章「宋」+ 古意纪年 + 四枚数值胶囊 + 词元计数
export default function TopBar() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [activeCapsule, setActiveCapsule] = useState<"treasury" | "privy" | null>(null);
  const [pinned, setPinned] = useState(false);

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
          typeKey="treasury"
          text={`◈国库 ${humanizeCoin(treasury)}`}
          isOpen={activeCapsule === "treasury"}
          isPinned={pinned && activeCapsule === "treasury"}
          onOpen={() => {
            if (!pinned) setActiveCapsule("treasury");
          }}
          onClose={() => {
            if (!pinned) setActiveCapsule(null);
          }}
          onTogglePin={() => {
            if (activeCapsule === "treasury" && pinned) {
              setPinned(false);
              setActiveCapsule(null);
            } else {
              setActiveCapsule("treasury");
              setPinned(true);
            }
          }}
          data={getTreasuryDetail(state)}
        />
        <HoverDetailCapsule
          typeKey="privy"
          text={`⛃内帑 ${humanizeCoin(privy)}`}
          isOpen={activeCapsule === "privy"}
          isPinned={pinned && activeCapsule === "privy"}
          onOpen={() => {
            if (!pinned) setActiveCapsule("privy");
          }}
          onClose={() => {
            if (!pinned) setActiveCapsule(null);
          }}
          onTogglePin={() => {
            if (activeCapsule === "privy" && pinned) {
              setPinned(false);
              setActiveCapsule(null);
            } else {
              setActiveCapsule("privy");
              setPinned(true);
            }
          }}
          data={getPrivyDetail(state)}
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

/** 古籍账本风格深度收支悬浮卡片：
 *  - 鼠标悬停 300ms 自动常驻锁定，杜绝在移向卡片或滚动时意外闪退
 *  - 鼠标真正离开卡片与胶囊区域后才延时收起
 *  - 支持点击胶囊或锁图标主动锁定/常驻阅读
 */
function HoverDetailCapsule({
  text, isOpen, isPinned, onOpen, onClose, onTogglePin, data
}: {
  typeKey: "treasury" | "privy";
  text: string;
  isOpen: boolean;
  isPinned: boolean;
  onOpen: () => void;
  onClose: () => void;
  onTogglePin: () => void;
  data: BudgetFlowData;
}) {
  const closeTimerRef = useRef<number | null>(null);

  function handleMouseEnter() {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    onOpen();
  }

  function handleMouseLeave() {
    if (isPinned) return;
    // 留出 400ms 的舒适缓冲区，使用户在卡片与按钮之间移动、或查阅时不会闪烁关闭
    closeTimerRef.current = window.setTimeout(() => {
      onClose();
    }, 400);
  }

  return (
    <div
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        onClick={onTogglePin}
        title={isPinned ? "已锁定明细（点击解除）" : "点击锁定明细常驻查看"}
        className={`whitespace-nowrap rounded-[2px] border px-2 py-1 text-[13px] font-bold transition flex items-center gap-1 ${
          isOpen
            ? "border-gold bg-gold-light text-red shadow-sm"
            : "border-border text-ink hover:bg-gold-light"
        }`}
      >
        <span>{text}</span>
        {isPinned && <Lock size={11} className="text-red animate-pulse" />}
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full z-30 pt-1.5"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <div className="w-[340px] rounded-[4px] border border-gold bg-[#f9f5ea] shadow-2xl p-3.5 select-text font-kai animate-card-in text-ink">
            {/* 1. 顶部古典题头与锁定/关闭控制钮 */}
            <div className="flex items-center justify-between border-b border-gold/40 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[16px] font-bold tracking-[0.18em] text-red-dark">
                  {data.title}
                </span>
                <button
                  onClick={onTogglePin}
                  title={isPinned ? "点击解除锁定" : "锁定此卡片常驻查看"}
                  className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] border transition ${
                    isPinned
                      ? "border-red/40 bg-red/10 text-red font-bold"
                      : "border-gold/40 text-dim hover:text-ink hover:bg-gold-light/40"
                  }`}
                >
                  {isPinned ? <Lock size={11} /> : <Unlock size={11} />}
                  {isPinned ? "已锁定" : "锁定"}
                </button>
              </div>

              <button
                onClick={onTogglePin}
                title="关闭"
                className="rounded p-0.5 text-dim hover:bg-gold-light hover:text-ink transition"
              >
                <X size={15} />
              </button>
            </div>

            {/* 2. 入/出/净 三列横向核心汇总盘 */}
            <div className="my-2.5 grid grid-cols-3 divide-x divide-gold/30 rounded border border-gold/40 bg-card py-2 text-center shadow-inner">
              <div className="px-1">
                <div className="text-[11px] text-dim">月入总盘</div>
                <div className="text-[14px] font-bold text-emerald-800 mt-0.5">
                  +{humanizeCoin(data.totalIn)}
                </div>
              </div>
              <div className="px-1">
                <div className="text-[11px] text-dim">月支刚性</div>
                <div className="text-[14px] font-bold text-red-dark mt-0.5">
                  -{humanizeCoin(data.totalOut)}
                </div>
              </div>
              <div className="px-1">
                <div className="text-[11px] text-dim">净结余</div>
                <div className={`text-[14px] font-bold mt-0.5 ${data.net >= 0 ? "text-emerald-800 font-extrabold" : "text-red-dark font-extrabold"}`}>
                  {data.net >= 0 ? `+${humanizeCoin(data.net)}` : `-${humanizeCoin(Math.abs(data.net))}`}
                </div>
              </div>
            </div>

            {data.subNotice && (
              <p className="mb-2 text-[10.5px] leading-relaxed text-dim border-b border-gold/20 pb-1.5">
                ※ {data.subNotice}
              </p>
            )}

            {/* 3. 纵向滚动明细区（可舒适滚动查看） */}
            <div className="max-h-[400px] space-y-3 overflow-y-auto pr-1">
              {/* 固定收入区块（收：绿） */}
              <div>
                <div className="flex items-center justify-between border-b border-gold/30 pb-0.5 mb-1.5">
                  <span className="text-[13px] font-bold text-emerald-800">固定收入明细</span>
                  <span className="text-[11px] font-bold text-emerald-800">+{humanizeCoin(data.totalIn)}</span>
                </div>
                <div className="space-y-1.5">
                  {data.incomes.map((item) => (
                    <div key={item.name} className="rounded border border-gold/25 bg-paper/70 p-2 shadow-sm">
                      <div className="flex items-center justify-between text-[12.5px]">
                        <span className="font-bold text-ink">{item.name}</span>
                        <span className="font-bold text-emerald-800">+{humanizeCoin(item.amount)}</span>
                      </div>
                      {item.formula && (
                        <div className="mt-1 text-[10.5px] text-dim leading-snug">
                          税基：{item.formula}
                        </div>
                      )}
                      {item.desc && (
                        <div className="mt-0.5 text-[10.5px] text-ink-light leading-snug">
                          {item.desc}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* 固定支出区块（支：红） */}
              <div>
                <div className="flex items-center justify-between border-b border-gold/30 pb-0.5 mb-1.5">
                  <span className="text-[13px] font-bold text-red-dark">固定支出明细</span>
                  <span className="text-[11px] font-bold text-red-dark">-{humanizeCoin(data.totalOut)}</span>
                </div>
                <div className="space-y-1.5">
                  {data.expenses.map((item) => (
                    <div key={item.name} className="rounded border border-gold/25 bg-paper/70 p-2 shadow-sm">
                      <div className="flex items-center justify-between text-[12.5px]">
                        <span className="font-bold text-ink">{item.name}</span>
                        <span className="font-bold text-red-dark">-{humanizeCoin(item.amount)}</span>
                      </div>
                      {item.formula && (
                        <div className="mt-1 text-[10.5px] text-dim leading-snug">
                          规制：{item.formula}
                        </div>
                      )}
                      {item.desc && (
                        <div className="mt-0.5 text-[10.5px] text-ink-light leading-snug">
                          {item.desc}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}