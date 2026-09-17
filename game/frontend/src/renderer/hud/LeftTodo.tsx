import { useGameStore, hudTodos } from "../store/gameStore";
import { statusColor } from "../utils/format";

// 左侧常驻在办栏：宣纸卡片，描金标题「在办」
// 数据源与呈现对齐 game/ui/panels_core.py::_refresh_left_card（longterm_public + longterm_secret）
export default function LeftTodo() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const todos = hudTodos(state);

  return (
    <div className="pointer-events-auto absolute left-3 top-[92px] z-20 w-[240px]">
      <div className="rounded-[3px] border border-gold bg-card shadow-paper">
        <div className="border-b border-border px-3.5 py-2">
          <span className="font-kai text-[16px] font-bold tracking-[0.25em] text-ink">在 办 庶 务</span>
        </div>
        <ul className="px-2 py-1.5 space-y-1">
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
                  <span
                    className="block h-full rounded-sm transition-all"
                    style={{
                      width: `${Math.min(100, Math.round(t.progress * 0.65))}%`,
                      backgroundColor: t.isFocus ? "#a93226" : statusColor(t.progress)
                    }}
                  />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}