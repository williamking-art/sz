import { useGameStore, hudTodos } from "../store/gameStore";
import { statusColor } from "../utils/format";
import inkLandscape from "../assets/hud_ink_landscape.svg?url";
import sealImage from "../../../public/images/seal.png?url";

// 左侧常驻在办栏：宣纸卡片，描金标题「在办」
// 数据源与呈现对齐 game/ui/panels_core.py::_refresh_left_card（longterm_public + longterm_secret）
export default function LeftTodo() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const todos = hudTodos(state);

  return (
    <div className="pointer-events-auto absolute left-4 top-[88px] z-20 w-[min(292px,calc(100vw-2rem))] sm:left-7 sm:top-[94px]">
      <div className="sz-docket-panel overflow-hidden">
        <div className="sz-docket-art relative flex min-h-[67px] items-end border-b border-[#8f6e28]/45 px-4 pb-2.5">
          <img src={inkLandscape} alt="" aria-hidden="true" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#f6ecd6]/85 via-[#f6ecd6]/48 to-[#f6ecd6]/5" />
          <div className="relative flex w-full items-end justify-between">
            <div>
              <span className="block font-kai text-[9px] tracking-[.32em] text-[#8f6e28]">中 书 · 枢 密 · 三 司</span>
              <span className="mt-0.5 block font-kai text-[16px] font-bold tracking-[.22em] text-[#2b1d12]">在 办 庶 务</span>
            </div>
            <img src={sealImage} alt="" aria-hidden="true" className="mb-0.5 h-7 w-7 object-contain opacity-80" />
          </div>
        </div>
        <ul className="sz-docket-list space-y-1 px-2 py-2">
          {/* 空状态（P1-1 / P2-1）：不伪造占位事务，且必须说明"无事务"的含义 + 给出下一步入口，
              不能只丢一句"— 暂无 —"让玩家以为漏看了什么。 */}
          {todos.length === 0 && (
            <li className="px-2 py-1.5">
              <p className="text-[13px] text-dim">— 暂无在办之事 —</p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-dim">
                事务需先立案（拟旨下诏 / 施政）才会出现在此；立案后由相关衙署与派系的支持、
                以及吏治是否通畅决定成败。
              </p>
              <button
                onClick={() => pushOverlay({ kind: "todo", title: "在办事务" })}
                className="mt-1.5 rounded border border-gold px-2 py-0.5 text-[11.5px] text-ink transition hover:bg-gold-light"
              >
                查看在办事务与立案入口
              </button>
            </li>
          )}
          {todos.map((t, i) => (
            <li key={i}>
              <button
                onClick={() => pushOverlay(t.isFocus ? { kind: "focus", title: "国策大计" } : { kind: "todo", title: "在办事务" })}
                className={`group flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition ${
                  t.isFocus ? "bg-red/10 hover:bg-red/15 border border-red/30 my-0.5" : "hover:bg-gold-light"
                }`}
              >
                <span className={`flex-1 truncate text-[13.5px] font-medium leading-snug ${t.isFocus ? "font-bold text-red" : "text-ink"}`}>
                  {t.label}
                </span>
                <span className="h-2.5 w-[65px] shrink-0 overflow-hidden rounded-sm bg-[#dfd1b0]">
                  {t.progress < 0 ? (
                    /* P1-27：无真实进度 → 「在办」脉冲条，不伪造百分比 */
                    <span
                      className="block h-full w-1/3 animate-pulse rounded-sm"
                      style={{ backgroundColor: t.isFocus ? "#a93226" : "#8a7a5a" }}
                    />
                  ) : (
                    <span
                      className="block h-full rounded-sm transition-all"
                      style={{
                        width: `${Math.min(100, Math.round(t.progress * 0.65))}%`,
                        backgroundColor: t.isFocus ? "#a93226" : statusColor(t.progress)
                      }}
                    />
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
